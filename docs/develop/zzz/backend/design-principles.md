# MCP Server 设计规范 —— agent 能力视角

> 本规范是 zzz_od backend 对 **MCP 适配器**(服务 AI 智能体)的设计纲领:从「智能体能做什么 / 做不到什么」推导 MCP tool 该提供什么、怎么设计。
> 现状 spec 见同目录 [architecture.md](architecture.md) / [mcp.md](mcp.md);本文件是指导它们演进的方法论。HTTP `/game/*` 适配器服务前端(给人用,无智能体能力),其设计(含事件桥)**不在本规范范围**。

## 为什么需要这份规范

本项目**源码运行**(不是打包 exe 给 MCP 目标用户),接入的 AI 编码工具(Claude Code 等)不仅通过 MCP 拿能力,还能**直接读源码、读运行时文件、执行命令、看截图、改文件**。这改变了「MCP 该暴露什么」的边界 —— 很多信息需求智能体自己就能满足,不必做成 tool。

本规范把现有 `mcp.md`「MCP 只做感知,编码 / 调试交给 AI」的雏形系统化为可执行原则,并融合 Anthropic《[Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents)》与 MCP《[Design Principles](https://modelcontextprotocol.io/community/design-principles)》的官方最佳实践,作为现有 tool、本次新增、路线图(run-as-service 等)的共同准绳。

**适用前提**:MCP 面向**源码运行的技术用户**(已装 dev 组含 `mcp`)。普通 GUI 用户走打包 exe、不经本层。

## 1. 智能体能做什么(源码运行前提下)

接入本项目的智能体(以 Claude Code 为代表)默认具备:

| 能力 | 说明 | 例 |
|---|---|---|
| 读源码 | Read / Grep / Glob | 读 `OpenAndEnterGame` 知进游戏经哪些节点 |
| 读运行时文件 | 日志 / 截图 / 配置在工作目录 | `.log/log.txt`(按天轮转)、`.debug/` PNG、YAML |
| 执行命令 | shell(Bash) | git / uv / grep / tail / `python -c` |
| 看图 | vision | 读 PNG 理解画面 |
| 改文件 | Edit / Write | 改代码 |
| 用工具 | 项目已配 | LSP(pyright)、context7、skills |

覆盖本地 + 远程 SSH(智能体在 Session 0 有 shell)。

## 2. 智能体做不到什么(必须经 MCP / backend)

| 能力 | 为什么 |
|---|---|
| 操作活的游戏运行时 | 点击 / 进游戏要 controller + 交互桌面 Session 1,活的 `ZContext` 在 server 进程 |
| 读 server 内存态 | 运行态、operation `current_node`、控制器就绪态 —— 只在 server 内存 |
| 实时取游戏画面 | `controller.get_screenshot` 要 server 调(取完落盘智能体才能看) |
| 跑加载的模型 | OCR / YOLO onnx session 在 server,`gpu_executor` 单线程串行;智能体不能并发直调 |

## 3. 设计原则

### P1. 只暴露「活的运行时能力」
MCP 提供:操作游戏、读内存态、跑模型、收敛校验地改配置。**不提供**:静态信息(源码 / 文档 / 日志文件 / 截图文件)—— 智能体自己读。
(MCP《Design Principles》**capability over compensation**:别为「模型当前不会读日志」就硬塞 `read_log` tool —— 模型会变强,永久结构是债。)

### P2. 按知识归属分工(领域事实 vs 通用推理)
判断「一条信息归 server 还是智能体」,看它**依赖什么知识**:
- **依赖游戏领域知识 / server 独占能力(CV、screen info、运行时状态、校验)→ server 给**。智能体看截图不懂游戏语义、读不到 server 内存态 —— 这些「**领域事实 / 运行时事实**」server 要主动识别并返回(画面是什么、当前流程节点、运行状态、校验结果)。
- **依赖通用推理 / 可读资源(语言、vision、读源码 / 文档 / 日志 / 截图)→ 智能体做**。OCR 文字含义、截图视觉细节、下一步决策、跨工具排错,都是智能体的职责。

server 给「**事实**」,智能体做「**决策 + 通用理解**」。server **不**替智能体做决策(下一步点哪),但**给足领域事实**让它能决策。

例子:OCR 全文 + 坐标 ✅(原始数据);**「当前画面 = login_screen」✅(领域事实,server 经 screen info 识别后给)**;「下一步该点登录按钮」❌(决策,智能体做)。

### P3. 操作 vs 观察分离
操作类 tool 改状态(进游戏 / 停止 / reload / 改配置),观察类只读(窗口 / 截图 / 运行态)。副作用两种标注:
- **docstring** 文字说明(给智能体读);
- **MCP tool annotations**(`destructiveHint` / `openWorldHint` 等机器可读,官方推荐)。

### P4. 不复制智能体已有的能力(选对 tool)
少而精,每个 tool 清晰独立目的;合并高频链式操作成单 tool。判断标准:**「智能体自己能做?能 → 不做 MCP」**。
(Anthropic choosing right tools:don't merely wrap existing functionality;地址簿用 `search_contacts` 而非 `list_contacts`。)

### P5. 操作游戏 / 模型推理 / 用户配置 一律经 MCP(收敛)
- 操作游戏 → MCP(独占 controller);
- 模型推理(OCR / YOLO)→ MCP(`gpu_executor` 串行,智能体不自调 onnx);
- 改用户配置 → MCP(**校验收敛在一处**,不被绕过)。
配置虽是磁盘持久态,但「写」经 MCP 以收敛校验。(底层都走 backend 方法,MCP / HTTP 共享。)

### P6. 返回智能体友好
- **语义化字段**,避免 cryptic 技术标识符(`name` / `image_url` 而非 `uuid` / `mime_type`);自然语言名比 id 好;
- 带**定位锚点**(时间戳 / 路径)让智能体关联日志 / 截图 / 源码;
- 大返回用 `response_format`(concise / detailed) enum 让智能体控详略;或分页 / 过滤 / 截断 + 合理默认(Claude Code tool response 限 25000 tokens);
- **错误要 actionable**(给正确格式示例),不要 opaque traceback。

### P7. 三层协同(MCP / 智能体自身 / skill)
能力分工写进 **skill**,指引智能体何时用哪层。例「调试失败运行」:`get_run_status` 拿状态 + 失败定位 → 要深入 tail 日志 → 要视觉 `capture` + vision。

### P8. 长耗时操作的运行态必须暴露
运行态(在跑吗 / 跑到哪 / 结果 / 中断后)是活内存态,智能体无法自感 → 必须暴露(`get_run_status` / `stop_run` / `block` 参数)。

### P9. docstring 是筛选 prompt
docstring 是智能体在众多 tool 里**选对工具**的依据,必须明确说清「能做什么 + 关键约束 + 副作用」,把**隐式上下文**(查询格式 / 术语 / 资源关系)显式化,参数**无歧义命名**(`user_id` 非 `user`)。但 context 有限,**不啰嗦** —— 准确说清即可。
(Anthropic prompt-engineering descriptions:think how you'd describe the tool to a new hire。)

### P10. 命名空间(namespacing)
tool 按服务 / 资源分组前缀(如 `game_*` / `run_*`),帮智能体在多 server 多 tool 时选对。

### P11. backend 共享能力,MCP / HTTP 对称暴露
运行态、操作、查询等能力属 **backend 收敛层**(`ZzzBackendContext`),MCP 和 HTTP 两个适配器**对称暴露**(各自序列化,调同一 backend 方法)。**别把能力写死在 MCP 适配器** —— 否则 HTTP 侧缺对称能力,且跨适配器状态割裂(HTTP 触发的运行 MCP 查不到)。判断:一个能力若两个适配器的消费者都用 → 放 backend 共享;只 MCP 用 → 才放 MCP 适配器。

### P12. 设计考虑全景,而非只看当前
判断字段 / 能力 / 接口该不该有,看**后续全景(成熟形态)**下是否必要,不只看当前用不用得到。与 YAGNI 的边界:
- 全景下必要 **且不可从已有信息派生** → 保留(即使当前暂不用);
- 可从已有信息派生 → 不存(派生,避免双源);
- 臆想的未来、无明确演进路径 → 不加(YAGNI)。

例:`RunSlot.app`(operation 标识):运行中可从 `current_op.display_name` 派生,但**终态 `current_op` 销毁**,要存 app 才知道「上次跑的什么」。全景(多 operation)下必要、不可全程派生 → 保留;「当前单 operation」不是删除理由(那是看当前,非全景)。

### P13. 观察类工具可选持久化观测样本
观察类 tool(如 `analyze_screen`)默认只在内存处理观测(截图 → OCR / 匹配),**不落盘**。但调用方若想对**同一帧**做二次分析(典型:喂给 vision double-check),重新取观测 = 第二次截图、且画面可能已变。故观察类 tool 可**可选地**把已取的观测样本顺手持久化并回传路径(例 `analyze_screen(save_image=True)` → `screenshot_path`),供调用方复用 —— **默认关闭、opt-in**,避免无谓落盘。
(与 P6「返回智能体友好」协同:路径锚点让智能体关联观测样本;与 P3「操作 vs 观察分离」协同:持久化是观察的可选副作用,docstring 标注,不改变观察语义。)

## 4. 能力分配总表

| 需求 | 智能体自己 | MCP | skill |
|---|:---:|:---:|:---:|
| 理解 operation 做什么 | ✅ 读源码 | — | — |
| 操作游戏 / 触发 operation | ❌ | ✅ | — |
| 运行状态 / 进度 / 失败定位 | ❌ 内存态 | ✅ `get_run_status` | ✅ 组合 |
| 读日志过程 | ✅ tail | ❌ 不做 | ✅ 路径 + 过滤 |
| 看截图细节 | ✅ vision | ✅ `capture` 取图 | ✅ 组合 |
| OCR / YOLO 推理 | ❌ 串行约束 | ✅ `analyze` | — |
| 改用户配置 | ❌ 校验收敛 | ✅ | — |

## 5. 新增 MCP tool 的开发方法论

新增一个对外能力时,按此流程判断与设计:

1. **该不该做 tool?**(P1 / P4 / P5)—— 智能体自己能做 → 不做;是活运行时 / 内存态 / 模型推理 / 配置校验 → 做;能合并进已有 tool(高频链式)→ 合并。
2. **操作还是观察?**(P3)→ 决定 docstring 标注 + annotations。
3. **返回设计**(P2 / P6):返哪些语义化字段?会不会超 token(`response_format` / 分页 / 截断)?错误怎么 actionable?要不要锚点(时间戳 / 路径)关联日志 / 截图?
4. **docstring**(P9):能否让智能体一眼选对?隐式上下文显式化没?参数命名无歧义?
5. **命名**(P10):前缀分组对齐。
6. **复核**:对照下方官方最佳实践 + 工具迭代法(原型 → eval → 与智能体协作优化)。

## 6. 官方最佳实践出处

- Anthropic《[Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents)》:choosing right tools / namespacing / returning meaningful context / token efficiency / prompt-engineering descriptions;以及「原型 → 评测(eval)→ 与智能体协作优化」的迭代法。
- MCP《[Design Principles](https://modelcontextprotocol.io/community/design-principles)》:**capability over compensation**、composability。

## 相关

- 现状 spec:[architecture.md](architecture.md) / [mcp.md](mcp.md) / [http.md](http.md)
- 智能体接入:[../setup/ai_coding.md](../setup/ai_coding.md)
- harness 方法论(分层类比):[../harness/context_layering.md](../harness/context_layering.md)
