# SQLite 配置存储

> 相关代码：`one_dragon.base.config.sqlite_operator.SqliteConnection`、`one_dragon.base.config.sqlite_operator.SqliteRepository`、`one_dragon.base.config.user_config_storage.UserConfigStorage`、`one_dragon.base.config.user_config.UserConfig`、`one_dragon.base.operation.application.application_config.ApplicationConfig`

SQLite 目前用于承载运行时用户配置，目标是逐步替代散落在 `config/` 下的用户 YAML 文件。

环境配置、项目配置、样例配置、路线/模板等仍按原有文件体系读取；只有明确继承 `UserConfig` 或 `ApplicationConfig` 的配置会进入 SQLite。

## 存储位置

数据库文件位于工作目录：

```text
config/config.db
```

SQLite WAL 相关文件也在同目录生成：

```text
config/config.db-wal
config/config.db-shm
```

这些文件属于用户本地数据，已加入 `.gitignore`，不应提交到仓库。

## 表结构

当前只使用一张键值表：

```text
config_content
├── path       TEXT 主键
├── content    TEXT，JSON 字符串
└── timestamp  DATETIME，写入或更新配置时刷新
```

`content` 中保存的是 JSON 文本，不保存 YAML。读取后由 `UserConfig` 解析为 `dict`，写入时再序列化为 JSON。

## Key 规则

`path` 是配置的逻辑路径，规则与旧版 `config/` 目录结构保持接近。

全局用户配置：

```text
custom
model
one_dragon
```

实例级用户配置：

```text
<instance_idx % 10>/game
<instance_idx % 10>/game_account
<instance_idx % 10>/team
```

应用配置：

```text
<instance_idx % 10>/<group_id>/<app_id>
```

应用运行记录：

```text
<instance_idx % 10>/app_run_record/<app_id>
```

当前 key 仍沿用单数字实例前缀，扩展到 10 个以上实例前，需要先调整 key 规则并提供旧数据迁移。

## 分层设计

SQLite 模块分为连接层和数据访问层，避免业务配置类直接管理 engine/session，也方便后续增加更多表。

连接层：

- 负责创建和持有 SQLAlchemy engine。
- 负责创建 `scoped_session`。
- 负责数据库初始化、建表、WAL PRAGMA、checkpoint 和 dispose。
- 由 `UserConfig` 统一初始化和关闭，`OneDragonEnvContext` 只触发生命周期入口。

数据访问层：

- `SqliteRepository` 负责通用 session 和事务执行模板。
- 具体存储类继承 `SqliteRepository`，不手写 `with session`，只传入具体表操作。
- 当前 `UserConfigStorage` 直接访问 `config_content` 表。
- 后续新增表时，增加新的存储类，不把多表逻辑继续堆到同一个类里。

配置层：

- `UserConfigStorage` 统一封装配置读写、迁移、exists、删除。
- `UserConfig` 只负责配置 key、JSON 序列化、旧 YAML 迁移流程和字段访问。
- `ApplicationConfig` 继承 `UserConfig`，沿用同一套访问层。
- `YamlConfig`、`JsonConfig` 等文件型配置不接入 SQLite。

## 初始化与关闭

SQLite 资源由 `UserConfig` 类级统一创建并回收，不在模块内使用全局 `SQLITE_OPERATOR` 实例。

`OneDragonEnvContext.__init__()` 只触发用户配置存储初始化：

```python
UserConfig.init_config_storage()
```

初始化时会：

- 创建 `config/` 目录。
- 创建 SQLAlchemy engine。
- 开启 WAL 模式。
- 设置 `busy_timeout = 5000`。
- 创建 `config_content` 表。

应用退出时由 `OneDragonEnvContext.after_app_shutdown()` 调用：

```python
UserConfig.close_config_storage(checkpoint=True)
```

关闭数据库连接，并执行 WAL checkpoint。

具体配置实例不负责关闭数据库资源。

## UserConfig

`UserConfig` 是 SQLite 用户配置基类。

适用场景：

- 用户会在界面或运行时修改的配置。
- 默认值可以由代码里的 property 定义。
- 不需要读取 sample 文件作为默认配置。

典型写法：

```python
from one_dragon.base.config.user_config import UserConfig


class DemoConfig(UserConfig):

    def __init__(self, instance_idx: int):
        super().__init__(
            'demo',
            instance_idx=instance_idx,
        )

    @property
    def enabled(self) -> bool:
        return self.get('enabled', True)

    @enabled.setter
    def enabled(self, new_value: bool) -> None:
        self.update('enabled', new_value)
```

常用接口：

- `get(prop, default)`：读取字段，缺失时返回默认值。
- `update(key, value, save=True)`：更新字段，默认立即保存。
- `save()`：将当前 `data` 写入 SQLite。
- `delete()`：删除当前配置 key。
- `is_file_exists`：判断当前 key 是否已经持久化。
- `get_prop_adapter()`：为 GUI setting card 创建配置适配器。

`UserConfig` 通过 `UserConfigStorage` 统一访问配置存储。具体配置类不传 repository，只关心配置字段；`ApplicationConfig` 也只调用 `UserConfig` 的内部封装，不直接操作 repository。

## ApplicationConfig

应用配置应继承 `ApplicationConfig`，不要直接继承 `UserConfig`。

应用配置维度是：

```text
app_id + instance_idx + group_id
```

也就是同一个应用在不同账号、不同应用组中可以有不同配置。

典型写法：

```python
from one_dragon.base.operation.application.application_config import ApplicationConfig


class CoffeeConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        super().__init__(
            'coffee',
            instance_idx,
            group_id,
        )

    @property
    def choose_way(self) -> str:
        return self.get('choose_way', 'none')

    @choose_way.setter
    def choose_way(self, new_value: str) -> None:
        self.update('choose_way', new_value)
```

工厂中通过 `create_config()` 暴露：

```python
def create_config(self, instance_idx: int, group_id: str) -> ApplicationConfig:
    return CoffeeConfig(instance_idx, group_id)
```

第三方插件同样可以使用 `ApplicationConfig`。插件配置的隔离依赖 `APP_ID`，因此插件的 `APP_ID` 必须全局唯一。

## YAML 迁移

为了兼容旧版本配置，`UserConfig` 会在首次读取时按以下顺序加载：

1. 读取 SQLite 中当前 key。
2. 如果配置改名，读取 `backup_module_name` 对应的 SQLite key。
3. 如果仍不存在，读取 `backup_module_name` 对应的旧 YAML。
4. 如果仍不存在，读取当前模块名对应的旧 YAML。
5. 成功读取 YAML 后，写入 SQLite，并删除原 YAML 文件。

`ApplicationConfig` 还保留一段应用配置专用兼容逻辑：

```text
config/<实例>/<app_id>.yml
→ config/<实例>/<group_id>/<app_id>.yml
→ SQLite: <实例>/<group_id>/<app_id>
```

这是为了兼容应用分组引入前的旧路径。

## 默认值策略

SQLite 用户配置不再依赖 sample 文件。

新增字段时，在 property 的 `get()` 默认值中声明默认行为：

```python
@property
def retry_times(self) -> int:
    return self.get('retry_times', 3)
```

只有确实需要分发只读样例数据的场景，才继续使用 `YamlConfig(..., read_sample_only=True)` 等文件型配置。

## 设计边界

- 不要把路线、模板、截图标注、自动战斗脚本等结构化资源迁入 `UserConfig`，这些内容仍应保留在文件系统中。
- 不要在配置类构造函数中做复杂业务初始化；构造函数可能触发旧 YAML 迁移和文件删除。
- 不要直接操作 `config/config.db`；业务代码通过 `UserConfig`、`ApplicationConfig` 或具体存储类封装访问。
- 不要在 `sqlite_operator.py` 中新增全局 Repository 或全局连接实例；用户配置统一通过 `UserConfig` 内部存储入口访问。
- 新增表时新增对应存储类，不要把多表访问继续塞进 `UserConfigStorage`。
- 插件卸载不会自动删除 SQLite 配置。重装插件时可以复用旧配置；如需彻底清理，应由插件管理功能按 `APP_ID` 显式删除。

## 测试建议

涉及 SQLite 配置改动时，至少覆盖以下场景：

- 新用户无 SQLite、无 YAML 时，读取代码默认值。
- 旧 YAML 存在时，首次读取会迁移到 SQLite。
- `backup_module_name` 改名迁移。
- `ApplicationConfig` 从无 group 旧路径迁移。
- `is_mock=True` 时不进行任何 IO。
- 插件应用通过 `create_config()` 返回 `ApplicationConfig` 子类后，能按 `instance_idx` 和 `group_id` 隔离配置。
