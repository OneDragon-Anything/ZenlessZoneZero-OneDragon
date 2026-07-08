# 相关仓库

> 本项目是多仓库协作:主仓是业务代码,配套仓 / 数据集 / 官网分开维护。本页统一列出,供开发者和 AI agent 了解全貌与各自落点。
>
> 贡献者类型:组织/项目成员有主仓 push 权可直接 clone;**外部贡献者需 fork 后 clone**,提 PR 回主仓(详见 [quickstart §①](quickstart.md))。
>
> 本地布局:测试仓须 clone 到**主仓根目录内**(见下);yolo 训练仓 / 数据集 / 官网建议放在**与主仓同一父目录**(如 `../OneDragon-YOLO`、`../dataset`、`../onedragon-anything.github.io`)。

## 总览

| 项 | 类型 | 位置 | 用途 | 何时去动 |
|---|---|---|---|---|
| 主仓 | git | [`OneDragon-Anything/ZenlessZoneZero-OneDragon`](https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon) | 业务代码、GUI、文档 | 日常开发 |
| 测试仓 | git | [`OneDragon-Anything/zzz-od-test`](https://github.com/OneDragon-Anything/zzz-od-test) | 测试代码 + 画面截图存档 | 跑/改测试、加截图 |
| yolo 训练仓 | git | [`OneDragon-Anything/OneDragon-YOLO`](https://github.com/OneDragon-Anything/OneDragon-YOLO) | YOLO 模型训练 + release 发布 | 训练/发模型 |
| 数据集 | 非git(ModelScope) | 见下 | YOLO 训练数据 | 训练时拉取 |
| 官网 blog | git | [`onedragon-anything.github.io`](https://github.com/OneDragon-Anything/onedragon-anything.github.io) | 官网 / 用户向文档站(Pages) | 改官网内容 |

## 测试仓 `zzz-od-test`

- **clone 到主仓根目录**(同名 `zzz-od-test/`),主仓 `.gitignore` 忽略它;IDE 设为 `Test Sources Root`。跑/改测试、画面截图存档(`screens/`)都在这。
- ⚠️ **提交坑**:主仓 `git add zzz-od-test/...` 会被 `.gitignore` **静默跳过**,须 `git -C zzz-od-test` 提交(详见 [testing/ §4](../testing/README.md))。
- 外部贡献者同样 **fork 后 clone**;测试改动随主仓 PR **同分支名**一起提(CI 按分支名匹配 clone 测试仓)。
- **AI agent**:Grep/Glob 默认尊重 `.gitignore`,**不会自动搜** `zzz-od-test/`——查/改测试须 `Read`/`grep` 显式指定路径。

## yolo 训练仓 `OneDragon-YOLO`

- 训练游戏内 YOLO 目标检测模型(迷失之地交互入口、闪光分类、枯壤境界等),代码在 `src/one_dragon_yolo/zzz/<玩法>/`。
- **发布**:模型打包成 `<模型名>.zip`,以 release tag `zzz_model` 发布到 `OneDragon-Anything/OneDragon-YOLO`;主仓按需下载消费。
- 训练流程文档**待补充**;各玩法模型文档(如 [迷失之地检测模型](../zzz/application/lost_void/det_model.md))记录其在主仓的来源与消费链路。

## 数据集

- 训练数据**非 git 仓**,托管在 [ModelScope](https://modelscope.cn)(如 [`DoctorReid/ZZZ-LostVoidDet-Dataset`](https://modelscope.cn/models/DoctorReid/ZZZ-LostVoidDet-Dataset)),按 `<玩法>-Dataset` 命名;本地按数据集名建目录(如 `dataset/ZZZ-LostVoidDet-Dataset/`)。
- 已知:SR-ObjectDet / ZZZ-FlashClassify / ZZZ-LostVoidDet / ZZZ-WitheredDomainDet。
- 完整清单与托管入口**以训练仓为准**(本文不逐一维护,避免随新增过时)。

## 官网 blog `onedragon-anything.github.io`

- 官网与用户向文档站([onedragon-anything.github.io](https://onedragon-anything.github.io/),GitHub Pages org 站);新手入门指南、公告、致谢名单等用户内容在此维护。
- 本地建议 clone 到与主仓**同一父目录**(`../onedragon-anything.github.io`)。
