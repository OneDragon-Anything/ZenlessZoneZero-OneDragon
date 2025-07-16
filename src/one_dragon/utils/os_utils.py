import sys

import datetime
import os
from functools import lru_cache


def join_dir_path_with_mk(path: str, *subs) -> str:
    """
    拼接目录路径和子目录
    如果拼接后的目录不存在 则创建
    :param path: 目录路径
    :param subs: 子目录路径 可以传入多个表示多级
    :return: 拼接后的子目录路径
    """
    target_path = path
    for sub in subs:
        if sub is None:
            continue
        target_path = os.path.join(target_path, sub)
        if not os.path.exists(target_path):
            os.mkdir(target_path)
    return target_path


def get_path_under_work_dir(*sub_paths: str) -> str:
    """
    获取当前工作目录下的子目录路径
    :param sub_paths: 子目录路径 可以传入多个表示多级
    :return: 拼接后的子目录路径
    """
    return join_dir_path_with_mk(get_work_dir(), *sub_paths)


@lru_cache
def run_in_exe() -> bool:
    """
    当前是否在exe中运行
    :return:
    """
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


@lru_cache
def get_work_dir() -> str:
    """
    返回项目根目录的路径
    :return: 项目根目录
    """
    if run_in_exe():
        return os.getcwd()
    dir_path: str = os.path.abspath(__file__)
    up_times = 4
    for _ in range(up_times):
        dir_path = os.path.dirname(dir_path)
    return dir_path


def get_env(key: str) -> str:
    """
    获取环境变量
    :param key: key
    :return: value
    """
    return os.environ.get(key)


def get_env_def(key: str, dft: str) -> str:
    """
    获取环境变量 获取不到时使用默认值
    :param key: key
    :param dft: 默认值
    :return: value
    """
    val = get_env(key)
    return val if val is not None else dft


def now_timestamp_str() -> str:
    """
    返回当前时间字符串
    :return: 例如 20230915220515
    """
    current_time = datetime.datetime.now()
    return current_time.strftime("%Y%m%d%H%M%S")


def get_dt(utc_offset: int = None) -> str:
    """
    返回给定UTC偏移下当前日期字符串
    默认返回本机时间所对应的日期
    :param utc_offset: 时区与UTC之间的偏移
    :return: 例如 20230915
    """
    timezone = None
    if utc_offset is not None:
        timezone = datetime.timezone(datetime.timedelta(hours=utc_offset))
    current_time = datetime.datetime.now(tz=timezone)
    return current_time.strftime("%Y%m%d")


def add_dt_offset(dt: str, day_offset: int = None) -> str:
    """
    根据一个日期，获取对应星期天的日期
    :param dt: 日期 yyyyMMdd 格式
    :param day_offset: 天偏移量
    :return: 星期天日期 yyyyMMdd 格式
    """
    date = datetime.datetime.strptime(dt, "%Y%m%d")
    if day_offset is not None:
        date = date + datetime.timedelta(days=day_offset)
    return date.strftime("%Y%m%d")


def get_sunday_dt(dt: str) -> str:
    """
    根据一个日期，获取对应星期天的日期
    :param dt: 日期 yyyyMMdd 格式
    :return: 星期天日期 yyyyMMdd 格式
    """
    date = datetime.datetime.strptime(dt, "%Y%m%d")
    weekday = date.weekday()  # 0表示星期一，6表示星期天
    days_to_sunday = 6 - weekday
    sunday_date = date + datetime.timedelta(days=days_to_sunday)
    return sunday_date.strftime("%Y%m%d")


def get_monday_dt(dt: str) -> str:
    """
    根据一个日期，获取对应星期一的日期
    :param dt: 日期 yyyyMMdd 格式
    :return: 星期天日期 yyyyMMdd 格式
    """
    date = datetime.datetime.strptime(dt, "%Y%m%d")
    weekday = date.weekday()  # 0表示星期一，6表示星期天
    sunday_date = date + datetime.timedelta(days=-weekday)
    return sunday_date.strftime("%Y%m%d")


def is_monday(dt: str) -> bool:
    """
    是否星期一
    :param dt:
    :return:
    """
    date = datetime.datetime.strptime(dt, "%Y%m%d")
    weekday = date.weekday()  # 0表示星期一，6表示星期天
    return weekday == 0


def get_current_day_of_week(utc_offset: int = None) -> int:
    """
    获取当前星期几 1~7
    :return:
    """
    dt = get_dt(utc_offset)
    date = datetime.datetime.strptime(dt, "%Y%m%d")
    return date.weekday() + 1


def dt_day_diff(dt_1: str, dt_2: str) -> int:
    """
    计算两个dt之间相差多少天
    :param dt_1: 被减数
    :param dt_2: 减数
    :return:
    """
    date1 = datetime.datetime.strptime(dt_1, "%Y%m%d")
    date2 = datetime.datetime.strptime(dt_2, "%Y%m%d")
    diff = date1 - date2
    return diff.days


def clear_outdated_debug_files(days: int = 1):
    """
    清理过期的调试临时文件
    :return:
    """
    directory = get_path_under_work_dir('.debug')
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=days)

    for root, dirs, files in os.walk(directory):
        for file in files:
            path = os.path.join(root, file)
            stat = os.stat(path)
            modified_time = datetime.datetime.fromtimestamp(stat.st_mtime)
            if modified_time < cutoff:
                os.remove(path)
