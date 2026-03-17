# coding: utf-8
import sys
import os

# 打印当前工作目录和Python路径
print(f"当前工作目录: {os.getcwd()}")
print(f"当前文件路径: {os.path.abspath(__file__)}")

# 计算并打印src目录路径
current_file = os.path.abspath(__file__)
print(f"当前文件: {current_file}")

# 向上四级目录到src
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
print(f"src目录路径: {src_dir}")

# 添加src目录到Python路径的最前面，避免导入冲突
sys.path.insert(0, src_dir)
print(f"Python路径: {sys.path}")

# 尝试导入模块
try:
    from zzz_od.context.zzz_context import ZContext
    from zzz_od.application.drive_disk_enhance.drive_disk_enhance_app import DriveDiskEnhanceApp
    print("导入成功!")
except Exception as e:
    print(f"导入失败: {e}")
    # 检查src目录是否存在
    print(f"src目录是否存在: {os.path.exists(src_dir)}")
    if os.path.exists(src_dir):
        print(f"src目录内容: {os.listdir(src_dir)}")
    # 检查zzz_od目录是否存在
    zzz_od_path = os.path.join(src_dir, 'zzz_od')
    print(f"zzz_od目录是否存在: {os.path.exists(zzz_od_path)}")
    if os.path.exists(zzz_od_path):
        print(f"zzz_od目录内容: {os.listdir(zzz_od_path)}")
    # 检查application目录是否存在
    app_path = os.path.join(zzz_od_path, 'application')
    print(f"application目录是否存在: {os.path.exists(app_path)}")
    if os.path.exists(app_path):
        print(f"application目录内容: {os.listdir(app_path)}")
    # 检查drive_disk_enhance目录是否存在
    drive_disk_enhance_path = os.path.join(app_path, 'drive_disk_enhance')
    print(f"drive_disk_enhance目录是否存在: {os.path.exists(drive_disk_enhance_path)}")
    if os.path.exists(drive_disk_enhance_path):
        print(f"drive_disk_enhance目录内容: {os.listdir(drive_disk_enhance_path)}")
    raise

if __name__ == '__main__':
    # 创建上下文
    ctx = ZContext()
    
    # 初始化上下文
    print("正在初始化上下文...")
    ctx.init()
    
    # 等待上下文初始化完成
    import time
    start_time = time.time()
    while not ctx.ready_for_application:
        if time.time() - start_time > 30:
            print("上下文初始化超时")
            exit(1)
        time.sleep(1)
    
    # 启动运行上下文
    print("正在启动运行上下文...")
    if not ctx.run_context.start_running():
        print("启动运行上下文失败")
        exit(1)
    
    try:
        # 初始化应用
        app = DriveDiskEnhanceApp(ctx)
        
        # 运行应用
        print("开始运行驱动盘强化应用...")
        result = app.execute()
        
        # 输出结果
        print(f"应用执行结果: {result.success}")
        print(f"状态: {result.status}")
        print(f"数据: {result.data}")
        
        # 获取截图并保存
        # print("正在获取截图...")
        # screenshot = app.screenshot()
        
        # # 保存截图到test目录
        # import cv2
        # import time
        # import os
        
        # # 确保test目录存在
        # test_dir = os.path.join(os.path.dirname(__file__), 'test')
        # if not os.path.exists(test_dir):
        #     os.makedirs(test_dir)
        
        # # 生成文件名
        # timestamp = time.strftime('%Y%m%d_%H%M%S')
        # screenshot_path = os.path.join(test_dir, f'screenshot_{timestamp}.png')
        
        # # 保存截图
        # cv2.imwrite(screenshot_path, screenshot)
        # print(f"截图已保存到: {screenshot_path}")
        
        # # 获取处理后的截图和OCR结果
        # print("\n正在获取处理后的结果...")
        
        # # 检查是否有原始截图
        # if hasattr(app, 'original_screenshot') and app.original_screenshot is not None:
        #     original_path = os.path.join(test_dir, f'original_screenshot_{timestamp}.png')
        #     cv2.imwrite(original_path, app.original_screenshot)
        #     print(f"原始截图已保存到: {original_path}")
        
        # # 检查是否有检测结果
        # if hasattr(app, 'detection_result') and app.detection_result is not None:
        #     detection_info = f"检测结果: {app.detection_result.result}\n状态: {app.detection_result.status}\n数据: {app.detection_result.data}"
        #     detection_path = os.path.join(test_dir, f'detection_result_{timestamp}.txt')
        #     with open(detection_path, 'w', encoding='utf-8') as f:
        #         f.write(detection_info)
        #     print(f"检测结果已保存到: {detection_path}")
        #     print(detection_info)
        
        # # 检查是否有OCR结果
        # if hasattr(app, 'ocr_result') and app.ocr_result is not None:
        #     ocr_path = os.path.join(test_dir, f'ocr_result_{timestamp}.txt')
        #     with open(ocr_path, 'w', encoding='utf-8') as f:
        #         f.write(str(app.ocr_result))
        #     print(f"OCR识别结果已保存到: {ocr_path}")
        #     print(f"OCR识别结果: {app.ocr_result}")
        # else:
        #     print("未获取到OCR识别结果")
    finally:
        # 停止运行上下文
        print("正在停止运行上下文...")
        ctx.run_context.stop_running()
        
        # 清理资源
        print("正在清理资源...")
        ctx.after_app_shutdown()
