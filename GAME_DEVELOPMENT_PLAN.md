# 明日回信（Tomorrow’s Reply）：AI 小镇角色扮演游戏企划

## 1. 项目定位

明日回信（Tomorrow’s Reply）是一款以 Godot 为前端、AI 世界模拟器为后端的像素风角色扮演游戏。玩家通过自然语言创建世界观和核心角色，随后主要与一名主角交流；主角背后存在一个持续运转的 AI 小镇。玩家离线期间，小镇以“游戏日”粒度继续推进，并在下次上线时通过事件摘要、角色变化和来信体现世界没有停止。

首个可玩版本面向中文桌面玩家（macOS/Windows），采用本地单机、单写入者架构：SQLite 是权威状态，Godot 只负责呈现和输入，Python sidecar 负责模拟、持久化、模型调用与 API。MVP 不做多人、语音、实时地图探索、图片实时生成或云端托管。

## 2. 已锁定的 MVP 边界

| 项目 | 决策 |
|---|---|
| 玩家身份 | 外部陪伴者，不在世界内生成玩家 avatar |
| 核心对象 | 1 名主角 + 6–8 名背景 NPC + 5–8 个地点 |
| 世界模板 | 固定 school/classroom walking skeleton，之后再扩展模板 |
| 时间 | 1 个现实日 = 1 个游戏日；每天 4 个时间槽 |
| 离线推进 | 混合 catch-up；最多补算 7 个游戏日，超过后进入 sleep 状态 |
| 玩家影响 | 影响主角下一步选择和关系，不直接编辑世界状态 |
| 交流 | 实时文字聊天、异步信件；v1 不做语音 |
| 世界呈现 | 对话场景和事件时间线优先，地图探索延后 |
| 模型 | 玩家本地提供 API key；通过系统 keyring 保存并直连供应商 |
| 资产 | 预制/程序化像素资产；不做实时 AI 图片生成 |
| 语言 | 中文首发，数据结构和 UI 保留 Unicode/locale 扩展能力 |

## 3. “可测试小步骤”的定义

每个步骤必须满足：

- [ ] 只交付一个可观察行为，预计 0.5–2 个工作日完成。
- [ ] 先写一个会失败的自动化测试，再实现最小代码使其通过。
- [ ] 测试可以在无真实大模型、无网络、无 Godot GUI 的情况下运行；需要外部依赖时提供 FakeClock、FakeLLM、内存/临时 SQLite fixture。
- [ ] 每一步有明确输入、输出、验收阈值，并可独立回滚或提交。
- [ ] 不把“能启动”当作验收，必须验证状态、事件、幂等性或用户可见结果。

执行时只勾选已经实现并通过验收的项目；未勾选项目表示尚未开始或仍有问题。

## 4. 统一测试命令

```bash
python -m pytest -q
python -m pytest tests/playable -q
python -m pytest tests/e2e -q
./scripts/test_game.sh
```

`scripts/test_game.sh` 在本地依次启动临时 SQLite、Python sidecar 和 Godot headless/GUI 测试；真实模型测试单独标记为 `integration`，不阻塞默认测试。

## 5. 分阶段实施计划

### F0：工程前置与测试骨架

- [x] **F0.1 工具链基线**：锁定 CPython 3.14.6（标准 GIL）、pytest 9.1.1、Godot Standard 4.7.1（GDScript）及匹配 export templates、GdUnit4 6.2.0；已在 macOS Apple Silicon 的项目 `.venv` 验证 Python 测试和 Godot 版本/模板。Windows x86_64 与 GdUnit4 addon 验证留给后续 F0.3。
- [x] **F0.2 OpenSpec 变更包**：创建本项目的 change/spec/design/tasks 文档，内容与本企划一致；结构校验通过。
- [x] **F0.3 依赖与目录骨架**：新增 `server/`、`tests/playable/`、`tests/e2e/`、`godot/` 的隔离骨架与精确依赖锁定；导入检查、Godot headless 启动和 GdUnit4 场景测试通过。Windows x86_64 验证留待后续平台切片。
- [x] **F0.4 测试替身**：实现 FakeClock、FakeLLM、固定 school fixture、临时数据库 fixture；同一输入产生同一输出。
- [x] **F0.5 CI/CD quality gate**: GitHub Actions runs locked Python tests,
  strict OpenSpec validation, and vendored GdUnit4/Godot 4.7.1 tests for pull
  requests and updates targeting `develop`. Verified `v*` tags create a GitHub
  Release only when their commit descends from `main`; the first remote run
  passed. See `docs/ci_cd.md`.

- [x] **F0 phase gate**: Within the declared macOS Apple Silicon and Ubuntu CI
  scope, developers can run the locked default suite with stable results.
  Windows x86_64 validation remains a later platform slice.

### D1：领域模型与事件契约

- [ ] **D1.1 时间与 ID**：实现世界日、时间槽、事件 ID、版本号和值对象；边界日期和重复 ID 测试通过。
- [ ] **D1.2 WorldBlueprintV1**：定义世界设定、主角设定、NPC、地点、规则和版本；合法/非法 JSON fixture 验证通过。
- [ ] **D1.3 固定小镇适配器**：从 blueprint 生成 1 主角、6–8 NPC、5–8 地点；数量和引用完整性测试通过。
- [ ] **D1.4 命令/事件 schema**：定义 `CreateWorld`、`PlanDay`、`AdvanceSlot`、`SendMessage`、`SendLetter` 及对应事件；schema 校验拒绝未知必填缺失。
- [ ] **D1.5 Reducer**：事件序列可重建当前投影；同一事件重复应用不会重复改变状态。
- [ ] **D1.6 Replay 工具**：从空库重放完整 fixture 与快照后的尾事件，结果字节级一致。

### S2：SQLite 权威存储与崩溃恢复

- [ ] **S2.1 数据库迁移**：建立 worlds、entities、events、commands、snapshots、outbox、messages、letters 表；迁移可重复执行。
- [ ] **S2.2 乐观版本追加**：expected-version 不匹配时拒绝写入；并发冲突测试通过。
- [ ] **S2.3 命令幂等**：相同 command_id 重试只产生一组事件和一份副作用。
- [ ] **S2.4 事务与 outbox**：事件、投影和 outbox 在同一事务提交；注入崩溃后只能看到完整事务。
- [ ] **S2.5 快照**：每 N 个事件生成快照；快照 + 尾事件 replay 与全量 replay 一致。
- [ ] **S2.6 Repository 抽象**：领域层只依赖接口；SQLite 实现通过契约测试，为未来 Postgres 保留替换点。

### R3：可玩的“游戏日”运行时

- [ ] **R3.1 创建固定世界**：输入固定 blueprint 创建可运行世界并返回 world_id。
- [ ] **R3.2 日计划**：PlanDay 为 4 个时间槽生成主角候选行动和背景 NPC 摘要。
- [ ] **R3.3 场景候选 schema**：每个候选包含参与者、地点、冲突/目标、可见性和预期后果；非法候选自动拒绝。
- [ ] **R3.4 Fake SceneResolver**：用规则替身解析候选场景；同一 seed 得到同一事件。
- [ ] **R3.5 应用场景**：ApplyScene 产生事件、更新关系/日程/记忆，并写入来源事件 ID。
- [ ] **R3.6 ReviewDay**：生成可供玩家阅读的日摘要、角色状态变化和未决线索。
- [ ] **R3.7 幂等 tick/resume**：重复执行同一 tick 或断点恢复不会重复推进；7 日 catch-up 可在临时库完成。

### C4：对话、因果与异步沟通

- [ ] **C4.1 玩家消息命令**：消息持久化、排序、去重；重复请求返回同一 ack。
- [ ] **C4.2 上下文构建**：主角只能看到允许公开的世界事实、近期记忆、关系状态和玩家消息；知识泄漏测试为 0。
- [ ] **C4.3 Fake 回复**：FakeLLM 返回结构化主角回复和影响意图；回复与输入事件建立因果链。
- [ ] **C4.4 影响入队**：玩家建议只进入主角下一选择上下文，不直接修改关系、属性或 NPC 状态。
- [ ] **C4.5 下一计划验证**：同一日结束后，主角选择可以引用玩家影响，也可以基于自身目标拒绝。
- [ ] **C4.6 信件**：玩家离线期间生成 letter；上线后可读、已读状态幂等。
- [ ] **C4.7 主动来信**：主角在满足触发条件时主动写信，并附带可追溯的世界事件来源。

### L5：真实模型与本地 BYOK

- [ ] **L5.1 Provider 接口**：统一 OpenAI-compatible、Anthropic、Gemini 的 chat/structured output 接口；Fake provider 通过相同契约。
- [ ] **L5.2 keyring**：API key 写入 macOS Keychain/Windows Credential Locker；日志、错误和导出均不得出现明文 key。
- [ ] **L5.3 连接测试**：设置页可选择 provider/model、发送最小请求并显示可行动错误。
- [ ] **L5.4 结构化修复**：模型输出 schema 错误时最多一次修复，否则转入安全 fallback 并记录原因。
- [ ] **L5.5 预算与脱敏**：限制每游戏日调用次数和 token；发送前按字段脱敏；超预算时使用规则摘要。

### A6：Python sidecar API

- [ ] **A6.1 健康检查/会话**：`/health`、创建/恢复 world、版本信息接口可用。
- [ ] **A6.2 世界接口**：创建固定世界、读取 snapshot、读取事件时间线；响应 schema 有契约测试。
- [ ] **A6.3 消息/信件接口**：发送消息和信件返回 202 + command_id，重试保持幂等。
- [ ] **A6.4 事件回放**：按 cursor 分页读取事件；断线后可从 cursor 补齐，不依赖实时连接。
- [ ] **A6.5 WebSocket 推送**：仅推送已提交事件；客户端 ack/cursor 后重连无重复可见事件。
- [ ] **A6.6 单写入者屏障**：所有写命令串行进入 runtime；并发写压力测试无版本空洞。

### G7：Godot 薄前端切片

- [ ] **G7.1 工程与字体**：中文字体、窗口、主题、基础像素 UI 在目标平台显示正常。
- [ ] **G7.2 HTTP 客户端**：启动时 health/session 成功；错误可重试并显示状态。
- [ ] **G7.3 WS 客户端**：连接、cursor、重连、回放合并通过 GdUnit4 测试。
- [ ] **G7.4 对话场景**：显示主角立绘/表情、对话气泡、输入框、发送中/失败状态。
- [ ] **G7.5 时间线与信件**：显示离线期间摘要、事件来源和未读信件。
- [ ] **G7.6 端到端薄切片**：Godot 发送消息 → sidecar → FakeLLM → WS/HTTP → UI 展示，在无真实模型时通过。

### O8：离线推进与后台运行

- [ ] **O8.1 墙钟映射**：现实时间映射到游戏日/4 slots；时钟回拨和时区变化有测试。
- [ ] **O8.2 7 日上限**：关闭后计算缺失天数；最多补 7 日，超过后标记 sleep 并停止自动调用。
- [ ] **O8.3 确定性 catch-up**：同一数据库、同一 seed、同一模型替身的 catch-up 与在线逐 slot 结果一致。
- [ ] **O8.4 调用预算**：7 日补算不超过预算；优先规则推进，必要时批量摘要。
- [ ] **O8.5 退出模式**：支持“下次启动补算”和“隐藏窗口后台运行”；状态栏显示运行/暂停/错误。
- [ ] **O8.6 崩溃恢复**：sidecar 被杀后重启可从最后提交 slot 继续，不重复事件。

### M9：记忆、关系与成长可信度

- [ ] **M9.1 记忆分类**：Canonical facts、Beliefs、Episodic memory 分离存储并可引用来源事件。
- [ ] **M9.2 关系状态**：关系维度、变化原因和最近互动可由 reducer 重建。
- [ ] **M9.3 身份锚点**：主角固定价值观、禁忌、目标和说话风格；提示词回归测试保持一致。
- [ ] **M9.4 成长证据**：成长只能由事件证据触发；无证据不得改变长期性格标签。
- [ ] **M9.5 检索与摘要**：按相关性/新鲜度/关系筛选上下文；token 超限时保留身份锚点和最新因果链。
- [ ] **M9.6 评测集**：建立中文 20–30 条长程对话/离线恢复 fixture，评估一致性、因果性和知识边界。

### W10：世界观与角色共创

- [ ] **W10.1 草稿状态机**：输入自由文本后进入 draft → clarify → preview → confirmed；每次变更可回滚。
- [ ] **W10.2 采访流程**：用固定问题补齐世界规则、主角目标、关系边界和禁忌；缺失字段可检测。
- [ ] **W10.3 生成器**：将自由文本转换为 WorldBlueprintV1；schema 验证失败时展示待确认问题。
- [ ] **W10.4 冲突修复**：检测时间、地点、人物关系冲突；自动给出候选修复并要求确认。
- [ ] **W10.5 主角草案**：对话式生成姓名、背景、欲望、恐惧、语气和成长方向；玩家确认后冻结身份锚点。
- [ ] **W10.6 预览/确认**：Godot 展示世界卡、主角卡、NPC/地点列表；确认操作原子化写入 SQLite。
- [ ] **W10.7 资产目录**：从固定 prefab 目录按标签选择背景、角色和表情；缺失资源回退默认资产。
- [ ] **W10.8 提示集回归**：至少 20 条中文创建提示通过生成、校验、预览和确认流程。

### P11：桌面 Alpha 与封闭测试

- [ ] **P11.1 用户数据**：数据库、资产、日志分目录；迁移、备份、导出和删除流程可验证。
- [ ] **P11.2 打包 sidecar**：Godot 启动/关闭 sidecar，握手失败可恢复；不要求用户安装 Python。
- [ ] **P11.3 macOS/Windows**：两平台完成安装、首次启动、keyring、对话、关闭、重启恢复测试。
- [ ] **P11.4 安全检查**：仓库和打包产物 secret scan 通过；日志不含 key 和完整私密上下文。
- [ ] **P11.5 长时间运行**：30 日模拟 soak test 无重复事件、版本空洞或数据库损坏。
- [ ] **P11.6 封闭测试**：8–12 名目标玩家完成创建世界、对话、离线回来、阅读成长摘要；收集定性反馈与量化指标。

### C12：未来云端扩展（不阻塞 MVP）

- [ ] **C12.1 Postgres adapter**：Repository 契约测试在 Postgres 通过；SQLite 仍是桌面权威。
- [ ] **C12.2 多用户隔离**：用户/世界 ownership、RLS、审计日志和迁移演练。
- [ ] **C12.3 Temporal workflow**：将已验证的 idempotent tick 搬到 Temporal schedule/workflow；重试和补偿测试通过。
- [ ] **C12.4 云 API**：无状态 API、对象存储快照、监控、备份、RPO/RTO 验证。
- [ ] **C12.5 云端模型方案**：明确产品管理的云端凭证、计费、限额和隐私协议；不得把本地 BYOK 静默上传。

## 6. 阶段门槛（必须全部通过才能进入下一阶段）

| 状态 | 门槛 | 验收标准 |
|---|---|---|
| [x] | G0 | 默认测试稳定通过；FakeClock/FakeLLM 可复现 |
| [ ] | G1 | 固定世界 blueprint schema 与 replay 一致 |
| [ ] | G2 | 10,000 次重复命令无重复状态变化；崩溃恢复一致 |
| [ ] | G3 | 在线 1 日、离线 7 日、断点恢复结果一致 |
| [ ] | G4 | 玩家消息可影响下一选择但不能直接改状态；来源事件 100% 可追溯 |
| [ ] | G5 | 三家 provider 至少各有一次连接/错误/fallback 测试；key 泄漏为 0 |
| [ ] | G6 | HTTP 回放 + WS 重连完整；事件版本无空洞 |
| [ ] | G7 | Godot 薄切片 E2E 通过；UI 不持有权威状态 |
| [ ] | G8 | 7 日 catch-up 在开发机 <5 秒（FakeLLM）；超过 7 日进入 sleep |
| [ ] | G9 | 长程评测中硬事实矛盾 <5%，知识泄漏 0，成长均有来源事件 |
| [ ] | G10 | 20 条世界创建提示中 ≥95% 可生成合法 blueprint |
| [ ] | G11 | 8–12 名测试者中 ≥70% 能指出主角可信成长；崩溃恢复成功率 100% |

## 7. 关键质量指标

- [ ] 重复命令导致的重复状态变化：0/10,000。
- [ ] 事件版本空洞：0；断线回放完整率：100%。
- [ ] API ack p95：<300ms（不含模型响应）；提交事件到 WS p95：<1s。
- [ ] 快照读取 p95：<500ms；FakeLLM 7 日 catch-up：<5s。
- [ ] 后端模型调用：正常日 ≤3 次，7 日补算 ≤6 次；超预算必须走规则摘要。
- [ ] 结构化输出一次修复成功率 ≥99.5%；失败必须安全降级并可追踪。
- [ ] 私钥/密钥泄漏：0；生产日志不得记录完整私密上下文。
- [ ] 目标玩家对“主角确实成长”的可感知率：封闭测试 ≥70%。

## 8. 明确不提前做的事项

- [ ] G3/G7 之前不开始自由世界生成、全镇开放互动或复杂地图。
- [ ] 幂等 tick 通过前不引入 Temporal。
- [ ] HTTP 回放稳定前不把 WebSocket 当作唯一事实来源。
- [ ] FakeLLM 评测稳定前不进行真实模型压力测试。
- [ ] MVP 不引入 LangGraph/OpenAI Agents SDK、Redis、向量数据库、Kafka、Kubernetes、多人联机、语音或实时图片生成。

## 9. 推荐首个垂直切片

按顺序勾选 D1 → S2 → R3 → C4 → A6 → G7 的最小路径：

- [ ] 固定 school blueprint
- [ ] SQLite 创建世界
- [ ] FakeLLM 运行 1 个游戏日
- [ ] 玩家发送一句话
- [ ] 主角回复并影响下一 slot 选择
- [ ] 关闭 sidecar
- [ ] 重启后补算 1–7 日
- [ ] Godot 显示摘要、成长证据和一封信

```text
固定 school blueprint
  → SQLite 创建世界
  → FakeLLM 运行 1 个游戏日
  → 玩家发送一句话
  → 主角回复并影响下一 slot 选择
  → 关闭 sidecar
  → 重启后补算 1–7 日
  → Godot 显示摘要、成长证据和一封信
```

这条路径通过后，才开始 L5 真实 provider、O8 后台运行、M9 长期记忆和 W10 自由创世。
