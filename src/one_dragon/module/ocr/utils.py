import itertools

from pponnxcr.predict_system import BoxedResult

from one_dragon.module.base.utils import area_center, area_in_area, area_offset


def area_distance(area1, area2):
    """
    Get the distance of 2 area center

    Args:
        area1: (upper_left_x, upper_left_y, bottom_right_x, bottom_right_y)
        area2: (upper_left_x, upper_left_y, bottom_right_x, bottom_right_y)

    Returns:
        float:
    """
    x1, y1 = area_center(area1)
    x2, y2 = area_center(area2)
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


def area_cross_area(area1, area2, thres_x=20, thres_y=20):
    """
    Args:
        area1: (upper_left_x, upper_left_y, bottom_right_x, bottom_right_y).
        area2: (upper_left_x, upper_left_y, bottom_right_x, bottom_right_y).
        thres_x:
        thres_y:

    Returns:
        bool:
    """
    # https://www.yiiven.cn/rect-is-intersection.html
    xa1, ya1, xa2, ya2 = area1
    xb1, yb1, xb2, yb2 = area2
    return abs(xb2 + xb1 - xa2 - xa1) <= xa2 - xa1 + xb2 - xb1 + thres_x * 2 \
        and abs(yb2 + yb1 - ya2 - ya1) <= ya2 - ya1 + yb2 - yb1 + thres_y * 2


def _merge_area(area1, area2):
    xa1, ya1, xa2, ya2 = area1
    xb1, yb1, xb2, yb2 = area2
    return min(xa1, xb1), min(ya1, yb1), max(xa2, xb2), max(ya2, yb2)


def _merge_boxed_result(left: BoxedResult, right: BoxedResult) -> BoxedResult:
    left.box = _merge_area(left.box, right.box)
    left.ocr_text = left.ocr_text + right.ocr_text
    return left


def merge_result_button(
        results: list[BoxedResult],
        left_func: callable,
        right_func: callable,
        text_func: callable
) -> list[BoxedResult]:
    """
    Args:
        results:
        left_func: Function that inputs ocr_text (str) and outputs bool
            True means mark as left text
        right_func:
        text_func: Function that inputs left_text (str) right_text (str) and outputs text (str)
    """
    left = None
    right = None
    for result in results:
        if left_func(result.ocr_text):
            left = result
        elif right_func(result.ocr_text):
            right = result

    text = text_func(
        left.ocr_text if left is not None else '',
        right.ocr_text if right is not None else ''
    )
    if left is not None:
        if right is not None:
            results.remove(right)
            left.box = _merge_area(left.box, right.box)
            left.ocr_text = text
        else:
            left.ocr_text = text
    else:
        if right is not None:
            right.ocr_text = text
        else:
            pass
    return results


def merge_buttons(buttons: list[BoxedResult], thres_x=20, thres_y=20) -> list[BoxedResult]:
    """
    Args:
        buttons:
        thres_x: Merge results with horizontal box distance <= `thres_x`
        thres_y: Merge results with vertical box distance <= `thres_y`

    Returns:

    """
    if thres_x <= 0 and thres_y <= 0:
        return buttons

    dic_button = {button.box: button for button in buttons}
    set_merged = set()
    for left, right in itertools.combinations(dic_button.items(), 2):
        left_box, left = left
        right_box, right = right
        if area_cross_area(left.box, right.box, thres_x=thres_x, thres_y=thres_y):
            left = _merge_boxed_result(left, right)
            dic_button[left_box] = left
            dic_button[right_box] = left
            set_merged.add(right_box)

    return [button for box, button in dic_button.items() if box not in set_merged]


# def pair_buttons(
#         group1: list["OcrResultButton"],
#         group2: list["OcrResultButton"],
#         relative_area: tuple[int, int, int, int]
# ) -> t.Generator["OcrResultButton", "OcrResultButton"]:
#     pass

def pair_buttons(group1, group2, relative_area):
    """
    Pair buttons in group1 with those in group2 in the relative_area.

    Args:
        group1 (list[OcrResultButton], Iterable[OcrResultButton]):
        group2 (list[OcrResultButton], Iterable[OcrResultButton]):
        relative_area (tuple[int, int, int, int]):

    Yields:
        OcrResultButton, OcrResultButton:
    """
    for button1 in group1:
        area = area_offset(relative_area, offset=button1.area[:2])
        combine = [(area_distance(area, b.area), b) for b in group2 if area_in_area(b.area, area, threshold=0)]
        combine = sorted(combine, key=lambda x: x[0])
        for _, button2 in combine[:1]:
            yield button1, button2


def split_and_pair_buttons(buttons, split_func, relative_area):
    """
    Pair buttons in group1 with those in group2 in the relative_area.

    Args:
        buttons (list[OcrResultButton]):
        split_func (callable):
            A function that accepts an OcrResultButton object returns a bool,
            button that has a True return join group1, False join group2.
        relative_area (tuple[int, int, int, int]):

    Yields:
        OcrResultButton, OcrResultButton:
    """
    group1 = [button for button in buttons if split_func(button)]
    group2 = [button for button in buttons if not split_func(button)]
    for ret in pair_buttons(group1, group2, relative_area):
        yield ret


def split_and_pair_button_attr(buttons, split_func, relative_area):
    """
    Pair buttons in group1 with those in group2 in the relative_area,
    and treat group2 as the BUTTON attribute of group1.

    Args:
        buttons (list[OcrResultButton]):
        split_func (callable):
            A function that accepts an OcrResultButton object returns a bool,
            button that has a True return join group1, False join group2.
        relative_area (tuple[int, int, int, int]):

    Yields:
        OcrResultButton:
    """
    for button1, button2 in split_and_pair_buttons(buttons, split_func, relative_area):
        button1.button = button2.button
        yield button1
