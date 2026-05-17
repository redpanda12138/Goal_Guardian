# MAS系统整合文档总览

## 📋 文档索引

本目录包含MAS系统功能梳理和整合方案的所有文档：

1. **[MAS功能梳理.md](./MAS功能梳理.md)** - 详细梳理MAS系统的6个代理功能
2. **[整合方案分析.md](./整合方案分析.md)** - 分析三种整合方案，推荐最佳方案
3. **[整合实施计划.md](./整合实施计划.md)** - 详细的实施步骤和技术设计

## 🎯 快速了解

### MAS系统是什么？

MAS（Multi-Agent System）是一个健康教练会话自动化管理系统，由6个独立的微服务代理组成：

1. **OA (Orchestration Agent)** - 编排代理，负责协调其他代理
2. **MMA (Memory Manager Agent)** - 记忆管理代理，提取患者信息和SMART目标
3. **SOA (Session Opening Agent)** - 会话开启代理，开始健康教练会话
4. **GRA (Goal Review Agent)** - 目标审查代理，审查患者的SMART目标
5. **SCA (Session Closing Agent)** - 会话关闭代理，结束会话并收集反馈
6. **SSA (Session Summary Agent)** - 会话摘要代理，生成会话摘要

### 整合目标

将MAS系统整合到talkieai-server后端，实现：
- ✅ 统一的API接口
- ✅ 共享的数据库和用户系统
- ✅ 统一的AI服务管理
- ✅ 保持MAS系统的核心功能

### 推荐方案

**完全整合方案**：将MAS的6个代理转换为talkieai-server的内部服务模块

**优势**：
- 统一的数据管理（数据库替代JSON文件）
- 统一的用户认证和授权
- 共享AI服务配置
- 简化部署（单一服务）

## 📊 系统对比

| 特性 | MAS系统 | talkieai-server | 整合后 |
|------|---------|----------------|--------|
| 架构 | 6个微服务 | 单体应用 | 单体应用（模块化） |
| 数据存储 | JSON文件 | SQLite数据库 | SQLite数据库 |
| 用户管理 | patient_id | account系统 | 统一account系统 |
| AI服务 | OpenAI GPT-4.1 | ChatGPT/智谱AI | 统一AI服务 |
| 部署 | Docker Compose | 单一服务 | 单一服务 |

## 🏗️ 整合架构

```
talkieai-server/
├── app/
│   ├── services/
│   │   └── mas/              # MAS服务模块
│   │       ├── orchestration_service.py
│   │       ├── memory_manager_service.py
│   │       ├── session_opening_service.py
│   │       ├── goal_review_service.py
│   │       ├── session_closing_service.py
│   │       └── session_summary_service.py
│   ├── db/
│   │   └── mas_entities.py   # MAS数据库实体
│   ├── api/
│   │   └── mas_routes.py     # MAS API路由
│   └── models/
│       └── mas_models.py     # MAS数据模型
```

## 📅 实施时间表

- **Week 1-2**: 数据库和实体层
- **Week 3-5**: 服务层实现
- **Week 6**: API层实现
- **Week 7**: 定时任务集成
- **Week 8-9**: 测试和优化

**总计**: 约9周完成整合

## 🔑 关键设计决策

### 1. 数据模型
- 使用SQLite数据库替代JSON文件
- 6个新表：patient_info, smart_goal, review_schedule, health_coach_session, session_summary, session_note

### 2. 用户系统集成
- 将MAS的`patient_id`映射到talkieai-server的`account_id`
- 复用现有的用户认证和授权机制

### 3. 定时任务
- 使用APScheduler替代后台线程
- 支持配置化的调度时间

### 4. AI服务
- 使用talkieai-server现有的AI服务
- 统一AI配置和管理

## 📝 主要API端点

### 患者信息管理
- `POST /api/v1/mas/patients/{account_id}/notes` - 提交会话笔记
- `GET /api/v1/mas/patients/{account_id}/info` - 获取患者信息
- `GET /api/v1/mas/patients/{account_id}/goals` - 获取SMART目标

### 会话管理
- `POST /api/v1/mas/sessions/trigger` - 触发会话
- `GET /api/v1/mas/sessions/{account_id}/current` - 获取当前会话
- `POST /api/v1/mas/sessions/{account_id}/message` - 发送消息

### 预约管理
- `GET /api/v1/mas/schedules` - 获取所有预约
- `POST /api/v1/mas/schedules/{account_id}` - 创建/更新预约

## ⚠️ 注意事项

1. **数据迁移**: 需要将现有JSON文件数据迁移到数据库
2. **向后兼容**: 考虑是否需要支持旧的JSON格式
3. **错误处理**: 统一使用talkieai-server的异常处理机制
4. **日志系统**: 使用talkieai-server的日志配置
5. **测试数据**: 准备测试数据用于验证整合

## 🚀 下一步行动

1. 阅读 [MAS功能梳理.md](./MAS功能梳理.md) 了解详细功能
2. 阅读 [整合方案分析.md](./整合方案分析.md) 了解整合方案
3. 阅读 [整合实施计划.md](./整合实施计划.md) 开始实施
4. 按照实施计划逐步完成整合

## 📞 问题反馈

如有问题或建议，请参考相关文档或联系开发团队。

