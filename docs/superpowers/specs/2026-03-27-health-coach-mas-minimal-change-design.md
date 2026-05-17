# 健康顾问方向（MAS）最小改动设计文档

## 1. 文档目的

在尽量少改动现有 `talkieai-server` 与 `talkieai-uniapp` 架构的前提下，将产品能力收敛到“健康顾问”主线，并参考 Bloom 的交互形态，完成以下目标：

- 保持现有一级页面层级与导航结构不变。
- 允许 `Coach` 页面做较大改造，作为目标驾驶舱。
- `Home` 与 `Coach` 都可进入同一个健康顾问会话（同一 session）。
- `Home` 增强为 “进入对话 + 上下文三卡”（下次运动安排/今日计划/本周进度）。
- 强区分 MAS 对话消息与状态更新消息。

## 2. 设计约束（已确认）

- 仅保留健康顾问方向能力；语言学习相关能力后续逐步取缔。
- 一级入口保持现状，健康顾问双入口为 `Home + Coach`。
- `Home/Coach` 进入聊天页时复用同一 MAS session。
- SMART 判定口径采用 `S/M/A` 三维，映射：
  - `SMART`
  - `Partially SMART`
  - `Not SMART`
- “下次运动安排”真值源优先使用 SMART 目标推算。
- 消息强区分采用不迁移数据库方案（先用现有字段承载）。

## 3. 参考基线

- Bloom 公开仓库与系统说明（交互模式参考）：[StanfordHCI/Bloom](https://github.com/StanfordHCI/Bloom)
- MAS 论文/汇总资料（流程分工与调度参考）：
  - `177_Multimodal_Agentic_System_.pdf`
  - `Dissertation.pdf`
- 飞书文档导出来源（并行参考）：[Feishu Wiki](https://my.feishu.cn/wiki/YgVBwYI4Did8EnkZdizcTMq6nah)

## 4. 当前系统映射（基于仓库现状）

### 4.1 后端现状

- 主应用路由：`app/main.py` 已挂载 `mas_routes`。
- MAS 网关：`app/api/mas_routes.py` + `app/services/mas/mas_gateway_service.py`。
- 6 代理现状：`mas/OA`, `mas/MMA`, `mas/SOA`, `mas/GRA`, `mas/SCA`, `mas/SSA`。
- MAS 会话与普通会话并存：`ChatService` 已支持 `session.type == "MAS"` 分支。

### 4.2 前端现状

- 一级导航保持 `Home / Coach / Mine`。
- 聊天页与练习页已存在，适合承接健康顾问流程，不必新增一级页面。

## 5. 目标信息架构

## 5.1 Home（轻入口）

- 提供“Start/Continue Chatting With Coach”入口，跳转聊天页。
- 依照已有前端链接后端展示健康顾问概览三卡：
  - 本周目标完成情况统计 （Weekly Progress）
  - 下次运动安排（Next Workout, 通过 MAS SMART 推算得出）
    - 时间、时长和活动（和下方同步）
  - 活动计划
    - 内容包括图标、日期和时间（准备至少五十个卡通版常见运动图标，根据计划活动切换）
    - “Modify” 按钮可以修改预定时间和频率
    - “Mark Complete” 按钮标记已完成来同步到 “Weekly Progress”

## 5.2 Coach（入口看板，按当前结构）

采用当前已实现的双标签页结构：

- 顶部标签：`Goals / Profile`
- `Goals` 视图（入口看板主体）：
  - `Next review` 条：显示下一次回访时间
  - `Latest summary` 卡：展示最近一次会话摘要（无数据时展示占位文案）
  - `Goals` 列表：逐条展示目标内容、SMART 标签与完成状态
  - `Weekly Review`（轻量周度复盘）：
    - 本周计划数、完成数、完成率、较上周变化
    - 周一到周日完成分布图（Mon-Sun）
  - `Overall Review`（总体复盘图表）：
    - 默认显示近 `5` 周，支持切换 `5 / 10 / 全部`
    - 展示完成率趋势图、计划 vs 完成图、累计完成趋势图
  - 每个目标提供快捷动作：
    - `Mark complete`：标记完成并触发状态事件刷新
    - `Discuss in chat`：跳转健康顾问聊天补充/调整目标
  - 底部主操作：`Continue Health Coach Chat`
- `Profile` 视图：
  - 展示患者基础信息（如偏好名、兴趣、家庭/朋友/旅行等字段）

## 5.3 Chat（统一会话页）

- 保持二级页，不提升为一级导航。
- 会话消息与状态消息强区分显示。

## 6. 消息模型强区分（不改表结构）

## 6.1 类型定义

- 对话消息（conversation）
  - 来源：`user / soa / gra / sca`
  - 计入会话语义与 turn_index 语境
- 状态消息（state_event）
  - 来源：系统动作回执（完成/改期/进度刷新）
  - 不应驱动代理轮次推进

## 6.2 最小实现策略

复用 `MessageEntity`，不新增表：

- 使用 `style` 字段标记状态消息类型，例如：
  - `STATE_EVENT:goal_completed`
  - `STATE_EVENT:goal_rescheduled`
  - `STATE_EVENT:progress_refreshed`
  - `STATE_EVENT:next_workout_changed`

前端渲染规则：

- `style` 以 `STATE_EVENT:` 开头 => 状态消息样式（系统条）
- 其他 => 普通对话气泡

## 7. SMART 推算与看板指标定义

## 7.1 SMART 口径

- 采用 `S/M/A` 三维评分。
- 标签映射：
  - `S=1,M=1,A=1` => `SMART`
  - 三维中恰好两项为 1 => `Partially SMART`
  - 否则 => `Not SMART`

## 7.2 下次运动安排推算（next_workout）

输入：

- 当前 SMART 目标列表
- 当前时间与时区
- 已完成/跳过状态记录

优先级：

1. 未完成且最近可执行目标
2. 多候选时按可执行性与低风险优先
3. 今日无候选则回退到下一自然日最近项
4. 无可推算项则返回空状态并提示创建/更新目标

## 7.3 看板指标

- `today_plan`: 今日完成数/待完成数（供 Home 三卡）
- `weekly_progress`: 本周完成数/总目标数/完成率（供 Home 三卡）
- `next_review_time`: OA 预约时间与触发状态
- `weekly_review`（Coach 轻量周度复盘）：
  - `week_range`
  - `planned_count`
  - `completed_count`
  - `completion_rate`
  - `vs_last_week_rate`（无历史可隐藏）
  - `weekday_distribution`（Mon-Sun）
- `overall_review`（Coach 总体复盘）：
  - `window`: `5 | 10 | all`（默认 `5`）
  - `kpi`: `planned_total / completed_total / completion_rate`
  - `completion_rate_trend`（按周）
  - `plan_vs_done_trend`（按周）
  - `cumulative_progress_trend`（累计）

## 7.4 前端看板渲染规范（一页）

### 7.4.1 组件层级（Coach / Goals）

页面结构按以下顺序渲染，禁止调整顺序以避免用户认知漂移：

1. `NextReviewCard`
2. `LatestSummaryCard`
3. `GoalsList`
4. `WeeklyReviewCard`（含 Mon-Sun 分布图）
5. `OverallReviewCard`（含窗口切换与趋势图）
6. `ContinueChatAction`

组件职责边界：
- `NextReviewCard`：仅显示下一次回访时间，不展示趋势数据。
- `LatestSummaryCard`：仅展示文字摘要，不重复图表与详细数值。
- `GoalsList`：仅展示目标条目与目标动作（`Mark complete` / `Discuss in chat`）。
- `WeeklyReviewCard`：仅展示“本周”指标与周内分布。
- `OverallReviewCard`：仅展示跨周趋势与总体 KPI。

### 7.4.2 加载态与空态

统一状态优先级：`loading > error(with_cache) > empty > ready`

- `loading`：
  - 首次进入 Coach/Goals 时，`WeeklyReviewCard` 与 `OverallReviewCard` 显示骨架屏。
  - `GoalsList` 使用现有加载占位，不阻塞页面滚动。
- `error(with_cache)`：
  - 请求失败但存在本地快照时，展示快照并显示 `Last updated at HH:mm`。
  - 卡片右上角显示轻量提示 `Data may be outdated`。
- `empty`：
  - `WeeklyReviewCard`：当 `planned_count=0`，显示 “No plans this week yet”。
  - `OverallReviewCard`：当窗口内无历史周数据，显示 “No historical data for this range”。
  - 空态不隐藏卡片容器，保持版面稳定。
- `ready`：
  - 按字段完整渲染；缺失字段按最小可用渲染（隐藏对应子模块，不报错）。

### 7.4.3 交互与刷新规则

- 筛选交互（`OverallReviewCard`）：
  - 选项固定：`5 / 10 / 全部`。
  - 默认激活 `5`（近5周）。
  - 切换后仅刷新 `OverallReviewCard` 数据，不触发整页重载。
  - 切换保持幂等：重复点击当前选项不重复请求。
- 统一刷新触发：
  - 进入页面 `onShow`
  - 用户下拉刷新
  - `Mark complete` 成功
  - `state-event` 成功回执
- 刷新范围：
  - `Mark complete`：刷新 `GoalsList + WeeklyReviewCard + OverallReviewCard`。
  - `Modify`：刷新 `NextReviewCard + WeeklyReviewCard + OverallReviewCard`。

### 7.4.4 展示一致性与格式规范

- 时间维度：
  - 周维度统一以本地时区自然周显示（Mon-Sun）。
  - `week_range` 显示格式统一为 `MMM D - MMM D`。
- 数值格式：
  - 百分比统一保留 `1` 位小数；无数据不显示 `0.0%` 伪值。
  - `vs_last_week_rate` 正负号显式展示（如 `+6.2%` / `-3.1%`）。
- 图表规则：
  - `WeeklyReviewCard`：仅允许 7 列分布图（Mon-Sun），不增加次级图例。
  - `OverallReviewCard`：最多 3 张图（完成率趋势、计划vs完成、累计趋势），禁止继续叠加新图。
- 与 Home 三卡/Chat 摘要去重：
  - Home 三卡只显示快照主值；Coach 看板承担解释性图表。
  - Chat 顶部摘要不展示趋势图，避免重复信息与视觉竞争。

## 8. 后端最小改动接口设计

## 8.1 复用接口（不改）

- `GET /mas/patients/goals`
- `GET /mas/patients/next_review_time`
- `GET /mas/sessions/current`
- `GET /mas/sessions/summaries`
- `GET /mas/sessions/get-or-create`

## 8.2 新增薄接口（建议）

### A. `GET /mas/coach/dashboard`

用途：一次性返回 `Home` 三卡、`Chat` 顶栏摘要与 `Coach` 入口看板所需聚合数据。

返回建议字段：

- `next_workout`
- `today_plan`
- `weekly_progress`
- `next_review_time`
- `weekly_review`
- `overall_review`
- `session_status`

### B. `POST /mas/coach/goals/state-event`

用途：接收前端快捷动作并落盘状态事件。

处理建议：

1. 更新目标进度账本（可先存于现有缓存实体，避免迁移）
2. 写入状态消息（`style=STATE_EVENT:*`）
3. 返回最新 `dashboard` 结果

## 9. 三条关键交互流

## 9.1 Home/Coach 进入 Chat

1. 用户点击健康顾问入口
2. 获取或创建 MAS 会话（同一 account 复用同一会话）
3. 拉取 dashboard 数据
4. 渲染聊天页顶部摘要卡（由 dashboard 字段驱动）并进入对话

## 9.2 Coach 快捷动作联动

1. 用户在 `Goals` 列表点击“Mark complete”
2. 调用 `state-event`
3. 生成状态消息
4. 刷新 Coach 入口看板相关数据（目标完成态、Weekly Review、Overall Review、下次运动）

## 9.3 周回顾闭环

1. OA 到期触发或手动触发回顾
2. SOA 开场 -> GRA 复盘 -> SCA 收尾
3. SSA 生成摘要，Coach/Home 可查看最近摘要

## 10. 实施计划与验收

## 第 1 步：后端聚合与状态消息

- 产出：`dashboard` + `state-event` + 消息 style 回传
- 验收：状态事件可写入并可见，dashboard 可稳定返回 Home/Chat/Coach 所需聚合数据

## 第 2 步：Coach 入口看板对齐当前结构

- 产出：Coach 双标签页（`Goals / Profile`）与 Goals 视图的  
  `Next review + Latest summary + Goals 列表 + Weekly Review（含 Mon-Sun 分布） + Overall Review（默认近5周，可切换5/10/全部） + Continue Chat`
- 验收：Coach 页可独立完成目标查看、标记完成、进入聊天、查看 Profile 信息，并可查看周度分布与总体趋势图表

## 第 3 步： `Home` 三卡与消息分流

- 产出：`Home` 页三卡与状态消息样式分流
- 验收：状态消息不干扰对话体验，且三卡实时同步

## 11. 范围外（当前阶段不做）

- 一级导航重构
- 大规模数据库迁移
- Ambient 花园类复杂视觉反馈
- 全量通知策略重做

## 12. 风险与回退

- 风险：SMART 文案非结构化导致推算误差
  - 回退：无可推算时显示空态并引导复盘
- 风险：状态消息与对话消息混淆
  - 回退：严格 `STATE_EVENT:` 前缀与前端样式兜底
- 风险：多端入口导致状态不同步
  - 回退：统一以 `dashboard` 聚合接口为前端真值源

## 13. 结论

本方案在不打破现有系统架构的前提下，将健康顾问能力集中在 `Coach` 看板与 `Chat` 上下文联动中，实现 Bloom 风格的“对话 + 计划进度”体验；同时通过最小改动接口与状态消息标记机制，兼顾可落地性与后续扩展空间。
