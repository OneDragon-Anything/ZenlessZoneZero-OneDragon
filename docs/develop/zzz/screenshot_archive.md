# 截图存档(screens/)

> 统一管理游戏画面截图,供**测试 fixture** + **文档溯源**。存测试仓 `zzz-od-test`(不影响普通用户、不进 app 安装面)。

## 游戏知识库生态
归档截图不是孤立的——它是 screen-onboarding 流程的产物之一,与以下配套:
- **画面文档** `docs/game/screens/<screen>.md` —— 子态/特征/可交互元素/识别快照;frontmatter `source_image: _<id>` 溯源原始截图。
- **screen_info** `assets/game_data/screen_info/<screen>.yml` —— area 定义(template/text,匹配用)。
- **截图存档** `zzz-od-test/screens/<screen>/<state>.webp` —— 归档代表截图(测试 fixture,webp 版)。

三者从同一张截图产出。`source_image` id(`.debug/images/`)用于文档溯源;`screens/` 可读名用于测试取图(`test_context.mock_screen('打开游戏', 'ready')`,API 见 [testing/README](../testing/README.md))。

## 结构
`zzz-od-test/screens/<screen_name>/<state>.webp`,镜像 `docs/game/screens/`:
```
screens/
  打开游戏/{ready,loading,退出登录弹窗,账号确认,...,登录成功}.webp
  加载画面/港口工厂旧址.webp
  大世界/普通.webp
  ...
```

## 格式约定
- **webp q90**(有损):比 PNG 省 ~94%(~150KB/张 vs ~2.2MB);已验**整屏识别**无损(conf 损耗 <0.006)。⚠️ **裁模板用原图 PNG**——小区域对 lossy 更敏感,artifacts 放大 → 模板 conf 降。
- **1080p 原生不缩放**:同 screen_info `pc_rect` 坐标——喂 offline analyze / 流程测试时坐标才对得上。
- **文件名 = 子态可读名**(`ready.webp`、`账号密码登录.webp`)。
- **冒号 → 下划线**:`警告:游戏前详阅` → 目录用 `警告_游戏前详阅`(Windows 目录名禁冒号)。

## 加图流程
1. **抓图**:MCP `capture_game_screen` 或真机截图。
2. **转 webp q90**:`cv2.imencode('.webp', img, [cv2.IMWRITE_WEBP_QUALITY, 90])` + `ndarray.tofile(path)`(**非 `cv2.imwrite`**——Windows 中文路径会挂;`cv2_utils.read_image`/`save_image` 已兼容)。
3. **放**:`zzz-od-test/screens/<screen_name>/<state>.webp`。
4. **更新溯源**:`docs/game/screens/<screen>.md` frontmatter `source_image` + `zzz-od-test/screens/README.md` 索引。

## 已归档 / 待补
见 `zzz-od-test/screens/README.md`。
