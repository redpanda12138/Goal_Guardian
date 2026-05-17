# MAS系统功能梳理文档

## 系统概述

MAS（Multi-Agent System）是一个基于微服务架构的多代理系统，用于健康教练会话的自动化管理。系统由6个独立的FastAPI服务组成，通过HTTP接口进行通信。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    OA (Orchestration Agent)            │
│              编排代理 - 端口: 8006                      │
│  - 定时任务调度（每小时检查）                            │
│  - 代理间协调                                           │
│  - 会话状态管理                                         │
└─────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────┐    ┌──────────┐    ┌──────────┐
│   MMA    │    │   SOA     │    │   GRA    │
│ 记忆管理 │    │ 会话开启  │    │ 目标审查 │
│ 端口8001 │    │ 端口8002  │    │ 端口8003 │
└──────────┘    └──────────┘    └──────────┘
        │               │               │
        └───────────────┼───────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────┐    ┌──────────┐    ┌──────────┐
│   SCA    │    │   SSA    │    │          │
│ 会话关闭 │    │ 会话摘要 │    │          │
│ 端口8004 │    │ 端口8005 │    │          │
└──────────┘    └──────────┘    └──────────┘
```

## 各代理功能详解

### 1. OA (Orchestration Agent) - 编排代理
**端口**: 8006  
**职责**: 系统核心协调器

**主要功能**:
- **定时任务调度**:
  - 每小时检查一次（整点执行）
  - 检查`review_schedule.json`中的预约时间
  - 当到达预约时间时，自动触发SOA开始会话
  - 每天午夜（00:00）触发MMA提取新会话笔记

- **会话状态管理**:
  - 维护`goal_reviews.json`文件，记录所有会话的聊天历史
  - 接收各代理的消息并统一保存
  - 管理会话的turn_index（轮次索引）

- **代理协调**:
  - 根据会话进度触发下一个代理（SOA → GRA → SCA → SSA）
  - 处理代理间的消息传递

- **API端点**:
  - `POST /new_sessions`: 接收MMA发送的新会话信息，更新预约时间表
  - `POST /receive_message`: 接收代理发送的消息，保存到goal_reviews.json
  - `POST /trigger_agent`: 手动触发指定代理

**数据文件**:
- `memory/review_schedule.json`: 患者预约时间表
- `memory/goal_reviews.json`: 会话聊天历史记录

---

### 2. MMA (Memory Manager Agent) - 记忆管理代理
**端口**: 8001  
**职责**: 从健康教练会话笔记中提取结构化信息

**主要功能**:
- **患者信息提取**:
  - 从会话笔记中提取患者偏好名称（preferred_name）
  - 提取兴趣爱好（hobbies）
  - 提取家庭信息（family）
  - 提取朋友信息（friends）
  - 提取旅行信息（travel）

- **SMART目标提取**:
  - 从会话笔记中提取每周SMART目标
  - 过滤掉长期目标，只保留短期、具体的周目标
  - 去重和规范化目标文本

- **会话元数据管理**:
  - 维护`session_metadata_mock.json`，记录所有会话的元数据
  - 维护`session_notes_mock.json`，存储结构化的患者信息
  - 维护`weekly_smart_goals_mock.json`，存储提取的SMART目标

- **API端点**:
  - `POST /extract`: 接收会话笔记列表，提取信息并保存
  - `GET /patient_notes/{patient_id}`: 获取指定患者的结构化信息
  - `GET /patient_goals/{patient_id}`: 获取指定患者的最新SMART目标

**数据文件**:
- `memory/session_metadata_mock.json`: 会话元数据
- `memory/session_notes_mock.json`: 患者结构化信息
- `memory/weekly_smart_goals_mock.json`: SMART目标列表

**AI模型**: GPT-4.1（用于信息提取）

---

### 3. SOA (Session Opening Agent) - 会话开启代理
**端口**: 8002  
**职责**: 开启健康教练会话，进行开场对话

**主要功能**:
- **会话开启**:
  - 从MMA获取患者信息（偏好名称等）
  - 生成开场问候语（询问能量水平）
  - 使用GPT生成自然的对话内容

- **对话流程管理**:
  - Turn 1: 问候并询问能量水平
  - Turn 2: 如果用户给出数字，询问含义；如果是情绪，询问原因
  - Turn 3: 共情回应，询问上周的积极健康时刻
  - Turn 4: 积极回应，询问轻量级后续问题
  - Turn 5: 积极回应，不告别
  - Turn 6: 触发GRA（目标审查代理）

- **API端点**:
  - `POST /trigger`: 被OA触发，开始新会话
  - `POST /receive_message`: 接收用户消息，生成回复

**数据文件**:
- `memory/soa_conversations.json`: SOA会话记录

**AI模型**: GPT-4.1（用于对话生成）

---

### 4. GRA (Goal Review Agent) - 目标审查代理
**端口**: 8003  
**职责**: 审查患者的SMART目标

**主要功能**:
- **目标展示**:
  - 从MMA获取患者的最新SMART目标列表
  - 向患者展示目标并询问要审查哪个目标
  - 如果没有目标，提示患者需要设置目标

- **目标审查对话**:
  - Turn 7: 展示目标列表，询问要审查哪个
  - Turn 8: 询问目标相关的积极体验
  - Turn 9: 询问目标相关的挑战和学习
  - Turn 10: 询问目标成功率的自我评分（0-100%）
  - Turn 11: 询问选择该评分的原因
  - Turn 12: 肯定患者的反思，结束目标审查
  - Turn 13: 触发SCA（会话关闭代理）

- **API端点**:
  - `POST /trigger`: 被OA触发，开始目标审查
  - `POST /receive_message`: 接收用户消息，生成回复

**数据文件**:
- `memory/gra_conversations.json`: GRA会话记录

**AI模型**: GPT-4.1（用于对话生成）

---

### 5. SCA (Session Closing Agent) - 会话关闭代理
**端口**: 8004  
**职责**: 关闭会话，收集反馈

**主要功能**:
- **会话关闭**:
  - 感谢患者参与会话
  - 询问反馈和建议
  - 告知下次会话时间（一周后，上午9点）

- **对话流程**:
  - Turn 14: 感谢并询问反馈
  - Turn 15: 感谢反馈，告知下次会话时间，结束会话
  - 触发SSA（会话摘要代理）

- **API端点**:
  - `POST /trigger`: 被OA触发，开始会话关闭
  - `POST /receive_message`: 接收用户消息，生成回复

**数据文件**:
- `memory/sca_conversations.json`: SCA会话记录

**AI模型**: GPT-4.1（用于对话生成）

---

### 6. SSA (Session Summary Agent) - 会话摘要代理
**端口**: 8005  
**职责**: 生成会话摘要

**主要功能**:
- **摘要生成**:
  - 接收完整的会话聊天历史
  - 使用GPT生成会话摘要
  - 保存摘要到文件

- **API端点**:
  - `POST /trigger`: 被OA触发，生成会话摘要
    - 接收参数: `patient_id`, `chat_history`

**数据文件**:
- `memory/session_summaries.json`: 会话摘要记录

**AI模型**: GPT-4.1（用于摘要生成）

---

## 数据流

### 1. 新会话笔记处理流程
```
健康教练笔记 → MMA/extract → 提取信息 → 更新文件 → 通知OA → 更新预约表
```

### 2. 定时会话触发流程
```
OA定时检查 → 发现预约时间 → 触发SOA → 开始会话 → GRA → SCA → SSA → 完成
```

### 3. 会话消息流转
```
用户消息 → OA/receive_message → 保存到goal_reviews.json
         → 转发到当前代理/receive_message → GPT生成回复 → 发送到OA → 保存
```

## 技术特点

1. **微服务架构**: 每个代理独立运行，可单独部署和扩展
2. **文件存储**: 使用JSON文件存储数据（非数据库）
3. **HTTP通信**: 代理间通过HTTP REST API通信
4. **定时任务**: OA使用后台线程实现定时检查
5. **状态管理**: 通过turn_index管理会话进度
6. **AI集成**: 所有代理使用OpenAI GPT-4.1模型

## 部署方式

- **Docker Compose**: 所有服务通过docker-compose.yml统一管理
- **独立端口**: 每个服务占用独立端口（8001-8006）
- **环境变量**: 需要配置OPENAI_API_KEY
- **数据持久化**: 通过Docker volumes挂载memory和logs目录

## 与talkieai-server的差异

| 特性 | MAS系统 | talkieai-server |
|------|---------|----------------|
| 架构 | 微服务（6个独立服务） | 单体应用 |
| 数据存储 | JSON文件 | SQLite数据库 |
| 通信方式 | HTTP REST API | 内部函数调用 |
| 用户管理 | 无（使用patient_id） | 完整的账户系统 |
| 会话管理 | 基于文件的状态管理 | 数据库实体管理 |
| AI模型 | 仅OpenAI GPT-4.1 | 支持ChatGPT和智谱AI |
| 功能定位 | 健康教练会话自动化 | 语言学习对话系统 |

