import json
import os
import random
import string
from collections import deque
from datetime import datetime, timedelta, timezone

import yaml
from filelock import FileLock

import one_dragon.module.config.server as server_
from one_dragon.module.config.atomicwrites import atomic_write

LANGUAGES = ['zh-CN', 'en-US', 'ja-JP', 'zh-TW', 'es-ES']
SERVER_TO_TIMEZONE = {
    'CN-Official': timedelta(hours=8),
    'CN-Bilibili': timedelta(hours=8),
    'OVERSEA-America': timedelta(hours=-5),
    'OVERSEA-Asia': timedelta(hours=8),
    'OVERSEA-Europe': timedelta(hours=1),
    'OVERSEA-TWHKMO': timedelta(hours=8),
}
DEFAULT_TIME = datetime(2020, 1, 1, 0, 0)


# https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data/15423007
def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)


def filepath_args(filename='args', mod_name='alas'):
    return f'./module/config/argument/{filename}.json'


def filepath_argument(filename):
    return f'./module/config/argument/{filename}.yaml'


def filepath_i18n(lang, mod_name='alas'):
    return os.path.join('./module/config/i18n', f'{lang}.json')


def filepath_config(filename, instance_idx, mod_name='alas'):
    if mod_name == 'alas':
        if str(instance_idx).isdigit():
            return os.path.join('../../config', f"{int(instance_idx):02d}", f'{filename}.json')
        else:
            return os.path.join('../../config', instance_idx, f'{filename}.json')
    else:
        return os.path.join('./config', f'{filename}.{mod_name}.json')


def filepath_code():
    return './module/config/config_generated.py'


def read_file(file):
    """
    Read a file, support both .yaml and .json format.
    Return empty dict if file not exists.

    Args:
        file (str):

    Returns:
        dict, list:
    """
    folder = os.path.dirname(file)
    if not os.path.exists(folder):
        os.mkdir(folder)

    if not os.path.exists(file):
        return {}

    _, ext = os.path.splitext(file)
    lock = FileLock(f"{file}.lock")
    with lock:
        print(f'read: {file}')
        if ext == '.yaml':
            with open(file, mode='r', encoding='utf-8') as f:
                s = f.read()
                data = list(yaml.safe_load_all(s))
                if len(data) == 1:
                    data = data[0]
                if not data:
                    data = {}
                return data
        elif ext == '.json':
            with open(file, mode='r', encoding='utf-8') as f:
                s = f.read()
                return json.loads(s)
        else:
            print(f'Unsupported config file extension: {ext}')
            return {}


def write_file(file, data):
    """
    Write data into a file, supports both .yaml and .json format.

    Args:
        file (str):
        data (dict, list):
    """
    folder = os.path.dirname(file)
    if not os.path.exists(folder):
        os.mkdir(folder)

    _, ext = os.path.splitext(file)
    lock = FileLock(f"{file}.lock")
    with lock:
        print(f'write: {file}')
        if ext == '.yaml':
            with atomic_write(file, overwrite=True, encoding='utf-8', newline='') as f:
                if isinstance(data, list):
                    yaml.safe_dump_all(data, f, default_flow_style=False, encoding='utf-8', allow_unicode=True,
                                       sort_keys=False)
                else:
                    yaml.safe_dump(data, f, default_flow_style=False, encoding='utf-8', allow_unicode=True,
                                   sort_keys=False)
        elif ext == '.json':
            with atomic_write(file, overwrite=True, encoding='utf-8', newline='') as f:
                s = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False, default=str)
                f.write(s)
        else:
            print(f'Unsupported config file extension: {ext}')


def iter_folder(folder, is_dir=False, ext=None):
    """
    Args:
        folder (str):
        is_dir (bool): True to iter directories only
        ext (str): File extension, such as `.yaml`

    Yields:
        str: Absolute path of files
    """
    for file in os.listdir(folder):
        sub = os.path.join(folder, file)
        if is_dir:
            if os.path.isdir(sub):
                yield sub.replace('\\\\', '/').replace('\\', '/')
        elif ext is not None:
            if not os.path.isdir(sub):
                _, extension = os.path.splitext(file)
                if extension == ext:
                    yield os.path.join(folder, file).replace('\\\\', '/').replace('\\', '/')
        else:
            yield os.path.join(folder, file).replace('\\\\', '/').replace('\\', '/')


def alas_template():
    """
        Returns:
            list[str]: Name of all Alas instances, except `template`.
        """
    out = []
    for file in os.listdir('./config'):
        name, extension = os.path.splitext(file)
        if name == 'template' and extension == '.json':
            out.append(f'{name}-src')

    # out.extend(mod_template())

    return out


def alas_instance():
    """
    Returns:
        list[str]: Name of all Alas instances, except `template`.
    """
    out = []
    for file in os.listdir('./config'):
        name, extension = os.path.splitext(file)
        config_name, mod_name = os.path.splitext(name)
        mod_name = mod_name[1:]
        if name != 'template' and extension == '.json' and mod_name == '':
            out.append(name)

    # out.extend(mod_instance())

    if not len(out):
        out = ['src']

    return out


def deep_get(d, keys, default=None):
    # 240 + 30 * depth (ns)
    if type(keys) is str:
        keys = keys.split('.')

    try:
        for k in keys:
            d = d[k]
        return d
    # No such key
    except KeyError:
        return default
    # Input `keys` is not iterable or input `d` is not dict
    except TypeError:
        return default


def deep_set(d, keys, value):
    """
    Set value into dictionary safely, imitating deep_get().
    """
    # 150 * depth (ns)
    if type(keys) is str:
        keys = keys.split('.')

    first = True
    exist = True
    prev_d = None
    prev_k = None
    prev_k2 = None
    try:
        for k in keys:
            if first:
                prev_d = d
                prev_k = k
                first = False
                continue
            try:
                # if key in dict: dict[key] > dict.get > dict.setdefault > try dict[key] except
                if exist and prev_k in d:
                    prev_d = d
                    d = d[prev_k]
                else:
                    exist = False
                    new = {}
                    d[prev_k] = new
                    d = new
            except TypeError:
                # `d` is not dict
                exist = False
                d = {}
                prev_d[prev_k2] = {prev_k: d}

            prev_k2 = prev_k
            prev_k = k
            # prev_k2, prev_k = prev_k, k
    # Input `keys` is not iterable
    except TypeError:
        return

    # Last key, set value
    try:
        d[prev_k] = value
        return
    # Last value `d` is not dict
    except TypeError:
        prev_d[prev_k2] = {prev_k: value}
        return


def deep_pop(d, keys, default=None):
    if type(keys) is str:
        keys = keys.split('.')

    try:
        for k in keys[:-1]:
            d = d[k]
        return d.pop(keys[-1], default)
    # No such key
    except KeyError:
        return default
    # Input `keys` is not iterable or input `d` is not dict
    except TypeError:
        return default
    # Input `keys` out of index
    except IndexError:
        return default
    # Last `d` is not dict
    except AttributeError:
        return default


def deep_default(d, keys, value):
    """
    Set default value into dictionary safely, imitating deep_get().
    Value is set only when the dict doesn't contain such keys.
    """
    if isinstance(keys, str):
        keys = keys.split('.')
    assert type(keys) is list
    if not keys:
        if d:
            return d
        else:
            return value
    if not isinstance(d, dict):
        d = {}
    d[keys[0]] = deep_default(d.get(keys[0], {}), keys[1:], value)
    return d


def deep_iter(data, min_depth=None, depth=3):
    """
    300us on alas.json depth=3 (530+ rows)

    Args:
        data:
        min_depth:
        depth:

    Returns:

    """
    if min_depth is None:
        min_depth = depth
    assert 1 <= min_depth <= depth

    # Equivalent to dict.items()
    try:
        if depth == 1:
            for k, v in data.items():
                yield [k], v
            return
        # Iter first depth
        elif min_depth == 1:
            q = deque()
            for k, v in data.items():
                key = [k]
                if type(v) is dict:
                    q.append((key, v))
                else:
                    yield key, v
        # Iter target depth only
        else:
            q = deque()
            for k, v in data.items():
                key = [k]
                if type(v) is dict:
                    q.append((key, v))
    except AttributeError:
        # `data` is not dict
        return

    # Iter depths
    current = 2
    while current <= depth:
        new_q = deque()
        # max depth
        if current == depth:
            for key, data in q:
                for k, v in data.items():
                    yield key + [k], v
        # in target depth
        elif min_depth <= current < depth:
            for key, data in q:
                for k, v in data.items():
                    subkey = key + [k]
                    if type(v) is dict:
                        new_q.append((subkey, v))
                    else:
                        yield subkey, v
        # Haven't reached min depth
        else:
            for key, data in q:
                for k, v in data.items():
                    subkey = key + [k]
                    if type(v) is dict:
                        new_q.append((subkey, v))
        q = new_q
        current += 1


def parse_value(value, data):
    """
    Convert a string to float, int, datetime, if possible.

    Args:
        value (str):
        data (dict):

    Returns:

    """
    if 'option' in data:
        if value not in data['option']:
            return data['value']
    if isinstance(value, str):
        if value == '':
            return None
        if value == 'true' or value == 'True':
            return True
        if value == 'false' or value == 'False':
            return False
        if '.' in value:
            try:
                return float(value)
            except ValueError:
                pass
        else:
            try:
                return int(value)
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass

    return value


def data_to_type(data, **kwargs):
    """
    | Condition                            | Type     |
    | ------------------------------------ | -------- |
    | `value` is bool                      | checkbox |
    | Arg has `options`                    | select   |
    | Arg has `stored`                     | select   |
    | `Filter` is in name (in data['arg']) | textarea |
    | Rest of the args                     | input    |

    Args:
        data (dict):
        kwargs: Any additional properties

    Returns:
        str:
    """
    kwargs.update(data)
    if isinstance(kwargs.get('value'), bool):
        return 'checkbox'
    elif 'option' in kwargs and kwargs['option']:
        return 'select'
    elif 'stored' in kwargs and kwargs['stored']:
        return 'stored'
    elif 'Filter' in kwargs['arg']:
        return 'textarea'
    else:
        return 'input'


def data_to_path(data):
    """
    Args:
        data (dict):

    Returns:
        str: <func>.<group>.<arg>
    """
    return '.'.join([data.get(attr, '') for attr in ['func', 'group', 'arg']])


def path_to_arg(path):
    """
    Convert dictionary keys in .yaml files to argument names in config.

    Args:
        path (str): Such as `Scheduler.ServerUpdate`

    Returns:
        str: Such as `Scheduler_ServerUpdate`
    """
    return path.replace('.', '_')


def dict_to_kv(dictionary, allow_none=True):
    """
    Args:
        dictionary: Such as `{'path': 'Scheduler.ServerUpdate', 'value': True}`
        allow_none (bool):

    Returns:
        str: Such as `path='Scheduler.ServerUpdate', value=True`
    """
    return ', '.join([f'{k}={repr(v)}' for k, v in dictionary.items() if allow_none or v is not None])


def server_timezone() -> timedelta:
    return SERVER_TO_TIMEZONE.get(server_.server, SERVER_TO_TIMEZONE['CN-Official'])


def server_time_offset() -> timedelta:
    """
    To convert local time to server time:
        server_time = local_time + server_time_offset()
    To convert server time to local time:
        local_time = server_time - server_time_offset()
    """
    return datetime.now(timezone.utc).astimezone().utcoffset() - server_timezone()


def random_normal_distribution_int(a, b, n=3):
    """
    A non-numpy implementation of the `random_normal_distribution_int` in module.base.utils


    Generate a normal distribution int within the interval.
    Use the average value of several random numbers to
    simulate normal distribution.

    Args:
        a (int): The minimum of the interval.
        b (int): The maximum of the interval.
        n (int): The amount of numbers in simulation. Default to 3.

    Returns:
        int
    """
    if a < b:
        output = sum([random.randint(a, b) for _ in range(n)]) / n
        return int(round(output))
    else:
        return b


def ensure_time(second, n=3, precision=3):
    """Ensure to be time.

    Args:
        second (int, float, tuple): time, such as 10, (10, 30), '10, 30'
        n (int): The amount of numbers in simulation. Default to 5.
        precision (int): Decimals.

    Returns:
        float:
    """
    if isinstance(second, tuple):
        multiply = 10 ** precision
        return random_normal_distribution_int(second[0] * multiply, second[1] * multiply, n) / multiply
    elif isinstance(second, str):
        if ',' in second:
            lower, upper = second.replace(' ', '').split(',')
            lower, upper = int(lower), int(upper)
            return ensure_time((lower, upper), n=n, precision=precision)
        if '-' in second:
            lower, upper = second.replace(' ', '').split('-')
            lower, upper = int(lower), int(upper)
            return ensure_time((lower, upper), n=n, precision=precision)
        else:
            return int(second)
    else:
        return second


def get_os_next_reset():
    """
    Get the first day of next month.

    Returns:
        datetime.datetime
    """
    diff = server_time_offset()
    server_now = datetime.now() - diff
    server_reset = (server_now.replace(day=1) + timedelta(days=32)) \
        .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    local_reset = server_reset + diff
    return local_reset


def get_os_reset_remain():
    """
    Returns:
        int: number of days before next opsi reset
    """
    from one_dragon.module.logger import logger

    next_reset = get_os_next_reset()
    now = datetime.now()
    logger.attr('OpsiNextReset', next_reset)

    remain = int((next_reset - now).total_seconds() // 86400)
    logger.attr('ResetRemain', remain)
    return remain


def get_server_next_update(daily_trigger):
    """
    Args:
        daily_trigger (list[str], str): [ "00:00", "12:00", "18:00",]

    Returns:
        datetime.datetime
    """
    if isinstance(daily_trigger, str):
        daily_trigger = daily_trigger.replace(' ', '').split(',')

    diff = server_time_offset()
    local_now = datetime.now()
    trigger = []
    for t in daily_trigger:
        h, m = [int(x) for x in t.split(':')]
        future = local_now.replace(hour=h, minute=m, second=0, microsecond=0) + diff
        s = (future - local_now).total_seconds() % 86400
        future = local_now + timedelta(seconds=s)
        trigger.append(future)
    update = sorted(trigger)[0]
    return update


def get_server_last_update(daily_trigger):
    """
    Args:
        daily_trigger (list[str], str): [ "00:00", "12:00", "18:00",]

    Returns:
        datetime.datetime
    """
    if isinstance(daily_trigger, str):
        daily_trigger = daily_trigger.replace(' ', '').split(',')

    diff = server_time_offset()
    local_now = datetime.now()
    trigger = []
    for t in daily_trigger:
        h, m = [int(x) for x in t.split(':')]
        future = local_now.replace(hour=h, minute=m, second=0, microsecond=0) + diff
        s = (future - local_now).total_seconds() % 86400 - 86400
        future = local_now + timedelta(seconds=s)
        trigger.append(future)
    update = sorted(trigger)[-1]
    return update


def get_server_last_monday_update(daily_trigger):
    """
    Args:
        daily_trigger (list[str], str): [ "00:00", "12:00", "18:00",]

    Returns:
        datetime.datetime
    """
    update = get_server_last_update(daily_trigger)
    diff = update.weekday()
    update = update - timedelta(days=diff)
    return update


def get_server_next_monday_update(daily_trigger):
    """
    Args:
        daily_trigger (list[str], str): [ "00:00", "12:00", "18:00",]

    Returns:
        datetime.datetime
    """
    update = get_server_next_update(daily_trigger)
    diff = (7 - update.weekday()) % 7
    update = update + timedelta(days=diff)
    return update


def nearest_future(future, interval=120):
    """
    Get the neatest future time.
    Return the last one if two things will finish within `interval`.

    Args:
        future (list[datetime.datetime]):
        interval (int): Seconds

    Returns:
        datetime.datetime:
    """
    future = [datetime.fromisoformat(f) if isinstance(f, str) else f for f in future]
    future = sorted(future)
    next_run = future[0]
    for finish in future:
        if finish - next_run < timedelta(seconds=interval):
            next_run = finish

    return next_run


def get_nearest_weekday_date(target):
    """
    Get nearest weekday date starting
    from current date

    Args:
        target (int): target weekday to
                      calculate

    Returns:
        datetime.datetime
    """
    diff = server_time_offset()
    server_now = datetime.now() - diff

    days_ahead = target - server_now.weekday()
    if days_ahead <= 0:
        # Target day has already happened
        days_ahead += 7
    server_reset = (server_now + timedelta(days=days_ahead)) \
        .replace(hour=0, minute=0, second=0, microsecond=0)

    local_reset = server_reset + diff
    return local_reset


def get_server_weekday():
    """
    Returns:
        int: The server's current day of the week
    """
    diff = server_time_offset()
    server_now = datetime.now() - diff
    result = server_now.weekday()
    return result


def random_id(length=32):
    """
    Args:
        length (int):

    Returns:
        str: Random azurstat id.
    """
    return ''.join(random.sample(string.ascii_lowercase + string.digits, length))


def to_list(text, length=1):
    """
    Args:
        text (str): Such as `1, 2, 3`
        length (int): If there's only one digit, return a list expanded to given length,
            i.e. text='3', length=5, returns `[3, 3, 3, 3, 3]`

    Returns:
        list[int]:
    """
    if text.isdigit():
        return [int(text)] * length
    out = [int(letter.strip()) for letter in text.split(',')]
    return out


def type_to_str(typ):
    """
    Convert any types or any objects to a string。
    Remove <> to prevent them from being parsed as HTML tags.

    Args:
        typ:

    Returns:
        str: Such as `int`, 'datetime.datetime'.
    """
    if not isinstance(typ, type):
        typ = type(typ).__name__
    return str(typ)


if __name__ == '__main__':
    get_os_reset_remain()
