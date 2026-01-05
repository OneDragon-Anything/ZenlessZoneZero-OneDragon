import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget

from one_dragon_qt.utils.image_utils import scale_pixmap_for_high_dpi


class Banner(QWidget):
    """展示带有圆角的固定大小横幅小部件，支持图片和视频"""

    def __init__(self, media_path: str, parent=None):
        QWidget.__init__(self, parent)
        self.media_path = media_path
        self.is_video = False
        self.banner_image = None
        self.scaled_image = None

        # 视频播放器组件
        self.media_player = None
        self.graphics_view = None
        self.scene = None
        self.video_item = None
        self._was_playing = False

        self.set_media(media_path)

    def set_media(self, media_path: str) -> None:
        """初始化媒体（图片或视频）"""
        self.media_path = media_path
        if not os.path.isfile(media_path):
            self.is_video = False
            self.banner_image = self._create_fallback_image()
            self._update_scaled_image()
            return

        # 检查是否为视频文件（通过扩展名或文件头判断）
        self.is_video = self._is_video_file(media_path)

        if self.is_video:
            self._init_video(media_path)
        else:
            self._cleanup_video()
            self.banner_image = self._load_image(media_path)
            self._update_scaled_image()

    def _is_video_file(self, file_path: str) -> bool:
        """判断文件是否为视频格式"""
        # 先检查扩展名
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.webm', '.mp4', '.avi', '.mov', '.mkv']:
            return True

        # 无扩展名时，通过文件头（magic bytes）判断
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)
        except OSError:
            return False

        if not header:
            return False

        # WebM: 1A 45 DF A3
        if header[:4] == b'\x1a\x45\xdf\xa3':
            return True

        # MP4/MOV: 开头4字节后是 ftyp
        if len(header) >= 8 and header[4:8] == b'ftyp':
            return True

        # AVI: RIFF....AVI
        if header[:4] == b'RIFF' and header[8:12] == b'AVI ':
            return True

        return False

    def _init_video(self, video_path: str) -> None:
        """初始化视频播放，使用硬件加速"""
        try:
            self._cleanup_video()

            # 创建媒体播放器（Qt 会自动尝试使用硬件加速）
            self.media_player = QMediaPlayer(self)

            # 创建图形视图和视频项
            self.graphics_view = QGraphicsView(self)
            self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.graphics_view.setFrameShape(QGraphicsView.Shape.NoFrame)
            self.graphics_view.setStyleSheet("background: transparent;")

            # 渲染质量优化设置
            self.graphics_view.setRenderHints(
                QPainter.RenderHint.Antialiasing |
                QPainter.RenderHint.SmoothPixmapTransform |
                QPainter.RenderHint.TextAntialiasing
            )
            self.graphics_view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
            self.graphics_view.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
            self.graphics_view.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)

            # 设置初始几何位置
            self.graphics_view.setGeometry(self.rect())

            # 将视图降到底层作为背景
            self.graphics_view.lower()

            self.scene = QGraphicsScene(self)
            self.graphics_view.setScene(self.scene)

            self.video_item = QGraphicsVideoItem()
            self.scene.addItem(self.video_item)

            # 设置视频输出
            self.media_player.setVideoOutput(self.video_item)

            # 设置视频源
            self.media_player.setSource(QUrl.fromLocalFile(video_path))

            # 设置循环播放
            infinite_loops = getattr(QMediaPlayer, "Infinite", None)
            if infinite_loops is None and hasattr(QMediaPlayer, "Loops"):
                infinite_loops = getattr(QMediaPlayer.Loops, "Infinite", -1)
            if infinite_loops is None:
                infinite_loops = -1
            self.media_player.setLoops(int(infinite_loops))

            # 监听视频尺寸变化，用于自动调整和提取第一帧
            self.video_item.nativeSizeChanged.connect(self._on_video_size_changed)

            # 显示视图
            self.graphics_view.show()

            # 开始播放
            self.media_player.play()

        except Exception:
            # 回退到图片模式
            self.is_video = False
            self._cleanup_video()
            self.banner_image = self._create_fallback_image()
            self._update_scaled_image()

    def _on_video_size_changed(self, size) -> None:
        """视频尺寸改变（加载完成），调整视图并提取第一帧"""
        # 调整视频视图大小以适配新尺寸
        self._resize_video_view()

        # 提取第一帧用于主题色
        if not self.video_item or not self.media_player:
            return

        video_sink = self.media_player.videoSink()
        if video_sink:
            frame = video_sink.videoFrame()
            if frame.isValid():
                self.banner_image = frame.toImage()

    def _cleanup_video(self) -> None:
        """清理视频播放器资源"""
        if self.media_player:
            self.media_player.stop()
            self.media_player.deleteLater()
            self.media_player = None
            self._was_playing = False

        if self.graphics_view:
            self.graphics_view.deleteLater()
            self.graphics_view = None

        if self.scene:
            self.scene.deleteLater()
            self.scene = None

        self.video_item = None

    def pause_media(self) -> None:
        """暂停视频播放"""
        if self.is_video and self.media_player:
            self._was_playing = self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            if self._was_playing:
                self.media_player.pause()
        else:
            self._was_playing = False

    def resume_media(self) -> None:
        """恢复媒体播放"""
        if self.is_video and self.media_player and self._was_playing:
            self.media_player.play()
            self._was_playing = False

    def release_media(self) -> None:
        """释放当前媒体资源，便于外部更新文件"""
        if not self.is_video:
            return

        self._cleanup_video()
        self.is_video = False
        self.banner_image = self._create_fallback_image()
        self.scaled_image = None
        self._update_scaled_image()
        self.update()

    def _resize_video_view(self) -> None:
        """调整视频视图大小"""
        if not self.graphics_view or not self.video_item:
            return

        # 设置视图大小和位置（始终填充整个 widget）
        self.graphics_view.setGeometry(self.rect())

        # 获取视频原始尺寸
        video_size = self.video_item.nativeSize()
        if video_size.isEmpty():
            # 视频尺寸未加载时，先设置一个默认大小
            return

        # 计算缩放比例以填充整个区域（保持宽高比）
        # 防止除零错误（控件初次布局或隐藏时）
        if self.width() == 0 or self.height() == 0:
            return

        widget_ratio = self.width() / self.height()
        video_ratio = video_size.width() / video_size.height()

        if widget_ratio > video_ratio:
            # 视频较窄，以宽度为准
            scale = self.width() / video_size.width()
        else:
            # 视频较宽，以高度为准
            scale = self.height() / video_size.height()

        # 设置视频项大小
        self.video_item.setSize(video_size * scale)

        # 更新场景矩形以适配视频项
        scene = self.graphics_view.scene()
        if scene:
            scene.setSceneRect(self.video_item.boundingRect())

        # 确保视图居中显示
        self.graphics_view.centerOn(self.video_item)

    def _load_image(self, image_path: str) -> QImage:
        """加载图片，或创建渐变备用图片"""
        if os.path.isfile(image_path):
            return QImage(image_path)
        return self._create_fallback_image()

    def _create_fallback_image(self) -> QImage:
        """创建渐变备用图片"""
        fallback_image = QImage(2560, 1280, QImage.Format.Format_RGB32)
        fallback_image.fill(Qt.GlobalColor.gray)
        return fallback_image

    def _update_scaled_image(self) -> None:
        """更新缩放后的图片"""
        if self.is_video or not self.banner_image:
            return

        if self.banner_image.isNull():
            return

        original_pixmap = QPixmap.fromImage(self.banner_image)
        self.scaled_image = scale_pixmap_for_high_dpi(
            original_pixmap,
            self.size(),
            self.devicePixelRatio(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding
        )
        self.update()

    def paintEvent(self, event):
        """重载 paintEvent 以绘制缩放后的图片"""
        if self.is_video:
            # 视频模式下无需额外绘制
            return

        if self.scaled_image:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            # 创建圆角路径
            path = QPainterPath()
            path.addRoundedRect(self.rect(), 4, 4)
            painter.setClipPath(path)

            # 计算绘制位置，使图片居中
            pixel_ratio = self.scaled_image.devicePixelRatio()
            logical_width = self.scaled_image.width() // pixel_ratio
            logical_height = self.scaled_image.height() // pixel_ratio
            x = (self.width() - logical_width) // 2
            y = (self.height() - logical_height) // 2

            # 绘制缩放后的图片
            painter.drawPixmap(x, y, self.scaled_image)

    def resizeEvent(self, event):
        """重载 resizeEvent 以更新缩放后的图片或视频"""
        if self.is_video:
            self._resize_video_view()
            # 确保视频视图始终在底层
            if self.graphics_view:
                self.graphics_view.lower()
        else:
            self._update_scaled_image()
        QWidget.resizeEvent(self, event)

    def set_percentage_size(self, width_percentage, height_percentage):
        """设置 Banner 的大小为窗口大小的百分比"""
        parent = self.parentWidget()
        if parent:
            new_width = int(parent.width() * width_percentage)
            new_height = int(parent.height() * height_percentage)
            self.setFixedSize(new_width, new_height)
            if self.is_video:
                self._resize_video_view()
            else:
                self._update_scaled_image()
