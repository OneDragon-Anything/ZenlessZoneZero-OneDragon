#import <CoreAudio/CoreAudio.h>
#import <CoreMedia/CoreMedia.h>
#import <Foundation/Foundation.h>
#import <ScreenCaptureKit/ScreenCaptureKit.h>

#include <algorithm>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <deque>
#include <mutex>
#include <string>
#include <vector>

namespace {

std::mutex g_mutex;
std::condition_variable g_cv;
std::deque<float> g_samples;
bool g_running = false;
std::string g_last_error;
size_t g_max_buffer_samples = 32000 * 2;

void set_error(const std::string& err) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_last_error = err;
}

void push_samples(const float* data, size_t count) {
    if (count == 0) {
        return;
    }
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_running) {
        return;
    }
    g_samples.insert(g_samples.end(), data, data + count);
    if (g_samples.size() > g_max_buffer_samples) {
        g_samples.erase(
            g_samples.begin(),
            g_samples.begin() + static_cast<std::ptrdiff_t>(g_samples.size() - g_max_buffer_samples)
        );
    }
    g_cv.notify_all();
}

}  // namespace

@interface OneDragonSCKAudioDelegate : NSObject <SCStreamOutput, SCStreamDelegate>
@end

@implementation OneDragonSCKAudioDelegate

- (void)stream:(SCStream *)stream
    didOutputSampleBuffer:(CMSampleBufferRef)sampleBuffer
                   ofType:(SCStreamOutputType)type {
    (void)stream;
    if (type != SCStreamOutputTypeAudio) {
        return;
    }
    if (!CMSampleBufferDataIsReady(sampleBuffer)) {
        return;
    }

    CMFormatDescriptionRef formatDesc = CMSampleBufferGetFormatDescription(sampleBuffer);
    const AudioStreamBasicDescription *asbd =
        CMAudioFormatDescriptionGetStreamBasicDescription(formatDesc);
    if (!asbd || asbd->mFormatID != kAudioFormatLinearPCM) {
        return;
    }

    CMItemCount numSamples = CMSampleBufferGetNumSamples(sampleBuffer);
    if (numSamples <= 0) {
        return;
    }

    size_t listSize = 0;
    OSStatus status = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
        sampleBuffer, &listSize, nullptr, 0, nullptr, nullptr, 0, nullptr
    );
    if (status != noErr || listSize == 0) {
        return;
    }

    std::vector<uint8_t> listStorage(listSize);
    auto *bufferList = reinterpret_cast<AudioBufferList *>(listStorage.data());
    CMBlockBufferRef blockBuffer = nullptr;
    status = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
        sampleBuffer,
        nullptr,
        bufferList,
        listSize,
        nullptr,
        nullptr,
        kCMSampleBufferFlag_AudioBufferList_Assure16ByteAlignment,
        &blockBuffer
    );
    if (status != noErr || !blockBuffer) {
        return;
    }

    std::vector<float> mono(static_cast<size_t>(numSamples), 0.0f);
    bool isFloat = (asbd->mFormatFlags & kAudioFormatFlagIsFloat) != 0;
    bool isNonInterleaved = (asbd->mFormatFlags & kAudioFormatFlagIsNonInterleaved) != 0;

    if (isFloat && bufferList->mNumberBuffers >= 1 && bufferList->mBuffers[0].mData != nullptr) {
        if (isNonInterleaved && bufferList->mNumberBuffers > 1) {
            UInt32 numBufs = bufferList->mNumberBuffers;
            for (UInt32 b = 0; b < numBufs; ++b) {
                const auto *samples = static_cast<const float *>(bufferList->mBuffers[b].mData);
                if (!samples) {
                    continue;
                }
                size_t count = std::min<size_t>(
                    static_cast<size_t>(numSamples),
                    bufferList->mBuffers[b].mDataByteSize / sizeof(float)
                );
                for (size_t i = 0; i < count; ++i) {
                    mono[i] += samples[i] / static_cast<float>(numBufs);
                }
            }
        } else {
            UInt32 channels = std::max<UInt32>(1, bufferList->mBuffers[0].mNumberChannels);
            const auto *samples = static_cast<const float *>(bufferList->mBuffers[0].mData);
            size_t totalFrames = std::min<size_t>(
                static_cast<size_t>(numSamples),
                bufferList->mBuffers[0].mDataByteSize / (sizeof(float) * channels)
            );
            for (size_t i = 0; i < totalFrames; ++i) {
                float sum = 0.0f;
                for (UInt32 c = 0; c < channels; ++c) {
                    sum += samples[i * channels + c];
                }
                mono[i] = sum / static_cast<float>(channels);
            }
        }
        push_samples(mono.data(), mono.size());
    }

    CFRelease(blockBuffer);
}

- (void)stream:(SCStream *)stream didStopWithError:(NSError *)error {
    (void)stream;
    if (error) {
        set_error([[error localizedDescription] UTF8String] ?: "SCStream stopped with error");
    }
    std::lock_guard<std::mutex> lock(g_mutex);
    g_running = false;
    g_cv.notify_all();
}

@end

namespace {

SCStream *g_stream = nil;
OneDragonSCKAudioDelegate *g_delegate = nil;
dispatch_queue_t g_audio_queue = nil;

}  // namespace

extern "C" {

int od_sck_audio_start(int sample_rate) {
    @autoreleasepool {
        {
            std::lock_guard<std::mutex> lock(g_mutex);
            if (g_running && g_stream != nil) {
                return 0;
            }
            g_samples.clear();
            g_last_error.clear();
            g_max_buffer_samples = static_cast<size_t>(std::max(sample_rate, 8000) * 2);
        }

        dispatch_semaphore_t sem = dispatch_semaphore_create(0);
        __block SCShareableContent *shareableContent = nil;
        __block NSError *contentError = nil;

        [SCShareableContent
            getShareableContentExcludingDesktopWindows:NO
                                   onScreenWindowsOnly:YES
                                     completionHandler:^(SCShareableContent *content, NSError *error) {
                                         shareableContent = content;
                                         contentError = error;
                                         dispatch_semaphore_signal(sem);
                                     }];

        if (dispatch_semaphore_wait(sem, dispatch_time(DISPATCH_TIME_NOW, 5 * NSEC_PER_SEC)) != 0) {
            set_error("获取 ScreenCaptureKit 共享内容超时");
            return -1;
        }
        if (contentError || !shareableContent || shareableContent.displays.count == 0) {
            std::string msg = contentError
                ? ([[contentError localizedDescription] UTF8String] ?: "未知错误")
                : "未找到可用显示器";
            set_error("无法获取 ScreenCaptureKit 显示器: " + msg);
            return -2;
        }

        SCDisplay *display = shareableContent.displays.firstObject;
        SCContentFilter *filter = [[SCContentFilter alloc] initWithDisplay:display
                                                          excludingWindows:@[]];

        SCStreamConfiguration *config = [[SCStreamConfiguration alloc] init];
        config.capturesAudio = YES;
        config.sampleRate = sample_rate > 0 ? sample_rate : 32000;
        config.channelCount = 2;
        config.excludesCurrentProcessAudio = YES;
        config.width = 2;
        config.height = 2;
        config.minimumFrameInterval = CMTimeMake(1, 1);

        g_delegate = [[OneDragonSCKAudioDelegate alloc] init];
        g_stream = [[SCStream alloc] initWithFilter:filter
                                      configuration:config
                                           delegate:g_delegate];
        g_audio_queue = dispatch_queue_create("one_dragon.sck.audio", DISPATCH_QUEUE_SERIAL);

        NSError *addOutputError = nil;
        if (![g_stream addStreamOutput:g_delegate
                                  type:SCStreamOutputTypeAudio
                    sampleHandlerQueue:g_audio_queue
                                 error:&addOutputError]) {
            std::string msg = addOutputError
                ? ([[addOutputError localizedDescription] UTF8String] ?: "未知错误")
                : "addStreamOutput 失败";
            set_error("添加 ScreenCaptureKit 音频输出失败: " + msg);
            g_stream = nil;
            g_delegate = nil;
            g_audio_queue = nil;
            return -3;
        }

        dispatch_semaphore_t startSem = dispatch_semaphore_create(0);
        __block NSError *startError = nil;
        [g_stream startCaptureWithCompletionHandler:^(NSError *error) {
            startError = error;
            dispatch_semaphore_signal(startSem);
        }];

        if (dispatch_semaphore_wait(startSem, dispatch_time(DISPATCH_TIME_NOW, 5 * NSEC_PER_SEC)) != 0) {
            set_error("启动 ScreenCaptureKit 音频捕获超时");
            g_stream = nil;
            g_delegate = nil;
            g_audio_queue = nil;
            return -4;
        }
        if (startError) {
            std::string msg = [[startError localizedDescription] UTF8String] ?: "未知错误";
            set_error("启动 ScreenCaptureKit 音频捕获失败: " + msg);
            g_stream = nil;
            g_delegate = nil;
            g_audio_queue = nil;
            return -5;
        }

        {
            std::lock_guard<std::mutex> lock(g_mutex);
            g_running = true;
        }
        return 0;
    }
}

int od_sck_audio_read(float* out_buffer, int num_frames, int timeout_ms) {
    if (!out_buffer || num_frames <= 0) {
        return -1;
    }
    std::unique_lock<std::mutex> lock(g_mutex);
    bool ready = g_cv.wait_for(
        lock,
        std::chrono::milliseconds(std::max(1, timeout_ms)),
        [num_frames]() {
            return !g_running || g_samples.size() >= static_cast<size_t>(num_frames);
        }
    );
    if (!g_running) {
        return -2;
    }
    if (!ready || g_samples.size() < static_cast<size_t>(num_frames)) {
        return 0;
    }
    for (int i = 0; i < num_frames; ++i) {
        out_buffer[i] = g_samples.front();
        g_samples.pop_front();
    }
    return num_frames;
}

void od_sck_audio_stop() {
    @autoreleasepool {
        SCStream *streamToStop = nil;
        {
            std::lock_guard<std::mutex> lock(g_mutex);
            g_running = false;
            g_samples.clear();
            streamToStop = g_stream;
            g_stream = nil;
            g_delegate = nil;
            g_audio_queue = nil;
        }
        g_cv.notify_all();

        if (streamToStop != nil) {
            dispatch_semaphore_t stopSem = dispatch_semaphore_create(0);
            [streamToStop stopCaptureWithCompletionHandler:^(NSError *error) {
                (void)error;
                dispatch_semaphore_signal(stopSem);
            }];
            dispatch_semaphore_wait(stopSem, dispatch_time(DISPATCH_TIME_NOW, 2 * NSEC_PER_SEC));
        }
    }
}

const char* od_sck_audio_last_error() {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_last_error.c_str();
}

}  // extern "C"
