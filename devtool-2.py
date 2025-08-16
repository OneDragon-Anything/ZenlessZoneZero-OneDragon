import cv2

# 读取图片
image = cv2.imread('D:\downloads\Compressed\ZenlessZoneZero-OneDragon-1.1.4\ZenlessZoneZero-OneDragon\.debug\images\switch_1733667121440.png')

# 给定的两个坐标点，这里假设为左上角和右下角的坐标
# 格式为(x, y)
x1, y1, x2, y2 = 502, 270, 580, 310

# 两个点
point1 = (x1, y1)
point2 = (x2, y2)

# 在图片上绘制长方形，参数依次为：图片，左上角坐标，右下角坐标，颜色，线条粗细
# 颜色使用BGR格式，例如(255, 0, 0)代表蓝色
# -1表示填充整个长方形
cv2.rectangle(image, point1, point2, (255, 0, 0), 2)

# 显示图片
cv2.imshow('Image with Rectangle', image)

# 等待按键后关闭所有窗口
cv2.waitKey(0)
cv2.destroyAllWindows()

# 如果需要保存图片
# cv2.imwrite('path_to_save_image.jpg', image)