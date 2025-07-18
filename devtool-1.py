import cv2
import numpy as np


def match_template(img, template, scale_step=0.01, min_scale=0.5, max_scale=2.5):
    """
    使用模板匹配找到最佳位置，并动态调整模板大小。
    """
    best_match_value = 0
    best_scale = 1.0
    best_location = None

    current_scale = min_scale
    while current_scale <= max_scale:
        resized_template = cv2.resize(template, (0, 0), fx=current_scale, fy=1)
        result = cv2.matchTemplate(img, resized_template, cv2.TM_CCOEFF_NORMED, mask)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val > best_match_value:
            best_match_value = max_val
            best_scale = current_scale
            best_location = max_loc

        current_scale += scale_step

    return best_location, best_scale, best_match_value


# 读取图片和模板
img = cv2.imread('D:/Code_Work/antec/ZenlessZoneZero-OneDragon/.debug/images/switch_1733588505972.png')
template = cv2.imread('D:/Code_Work/antec/ZenlessZoneZero-OneDragon/assets/template/agent_state/qingyi_3_2/raw.png')
mask = cv2.imread('D:/Code_Work/antec/ZenlessZoneZero-OneDragon/assets/template/agent_state/qingyi_3_2/mask.png')
match_location, best_scale , best_match_value = match_template(img, template)

if match_location is not None:
    resized_template = cv2.resize(template, (0, 0), fx=best_scale, fy=best_scale)
    width, height = resized_template.shape[1], resized_template.shape[0]
    top_left = match_location
    bottom_right = (top_left[0] + width, top_left[1] + height)
    cv2.rectangle(img, top_left, bottom_right, 255, 2)
    print(f"Best match location: ({top_left[0]},{top_left[1]},{bottom_right[0]},{bottom_right[1]})")
    print("Best match scale: ", best_scale)
    print("Best match value: ", best_match_value)
    print("Best match width: ", width)
    print("Best match bottom: ", bottom_right)
    cv2.imshow('Matched Location', img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
else:
    print("No match found.")