_GITHUB_YOLO_RELEASE_BASE = 'https://github.com/OneDragon-Anything/OneDragon-YOLO/releases/download'
_GITEE_YOLO_RELEASE_BASE = 'https://gitee.com/OneDragon-Anything/OneDragon-YOLO/releases/download'


def get_github_model_download_url(release_tag: str) -> str:
    return f'{_GITHUB_YOLO_RELEASE_BASE}/{release_tag}'


def get_gitee_model_download_url(release_tag: str) -> str:
    return f'{_GITEE_YOLO_RELEASE_BASE}/{release_tag}'
