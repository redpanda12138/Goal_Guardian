# 方案二Chat接入MAS实施说明

## 一、修改概述

本次修改将MAS系统集成到现有的chat对话系统中，实现了：
1. ✅ 在对话界面可以直接与MAS进行健康教练对话
2. ✅ 在practice页面显示用户的Goal Review（SMART目标）和Setting（患者信息）
3. ✅ 保留原有对话逻辑，通过注释和标注清晰区分

## 二、后端修改详情

### 2.1 修改文件：`app/api/session_routes.py`

#### 新增接口
```python
@router.post("/sessions/mas")
def create_mas_session(...):
    """创建MAS健康教练会话"""
```

#### 修改接口
```python
@router.post("/sessions/{session_id}/chat")
def chat_api(...):
    """
    发送消息
    
    MAS模式：如果session类型为MAS，则转发到MAS服务
    原逻辑：保留原有的CHAT和TOPIC类型对话逻辑
    """
    if session.type == 'MAS':
        # ========== MAS对话模式 ==========
        return ApiResponse(data=chat_service.send_mas_session_message(...))
    else:
        # ========== 原有对话逻辑（保留） ==========
        return ApiResponse(data=chat_service.send_session_message(...))
```

### 2.2 修改文件：`app/services/chat_service.py`

#### 修改方法：`get_session_greeting()`
- 添加MAS类型判断
- 如果是MAS类型，触发SOA开始会话并获取问候语
- 保留原有CHAT和TOPIC逻辑

#### 新增方法：`send_mas_session_message()`
**功能**：
- 获取patient_id（通过account_id映射）
- 获取当前会话状态和turn_index
- 根据turn_index判断当前代理（SOA/GRA/SCA）
- 发送消息到对应的MAS服务
- 获取助手回复并保存到数据库

**关键逻辑**：
```python
# 根据turn_index判断代理
if current_turn_index <= 6:
    # SOA阶段
elif current_turn_index <= 13:
    # GRA阶段
else:
    # SCA阶段
```

#### 修改方法：`create_session()`
- 添加`session_type`参数，支持指定会话类型
- 默认类型仍为"CHAT"（保持向后兼容）

#### 新增方法：`create_mas_session()`
- 便捷方法，创建type为"MAS"的会话

**保留的方法**：
- `send_session_message()` - 完全保留，用于CHAT和TOPIC类型
- 所有其他原有方法都保留

### 2.3 代码标注

所有新增代码都标注了：
```python
# ========== MAS对话模式 ==========
```

所有保留的原有代码都标注了：
```python
# ========== 原有逻辑（保留） ==========
```

## 三、前端修改详情

### 3.1 新增文件：`src/api/mas.ts`

**功能**：封装所有MAS相关的API调用

**包含的API**：
- 患者信息管理
- 会话管理
- 预约管理
- 健康检查

### 3.2 修改文件：`src/pages/practice/index.vue`

#### 标签页修改
- "Review" → "Goal Review"（显示SMART目标）
- "Setting" → "Setting"（显示患者信息）

#### Goal Review标签页
**显示内容**：
- 用户的SMART目标列表
- 从MAS服务获取：`GET /api/v1/mas/patients/goals`

**数据来源**：
```typescript
masRequest.getPatientGoals()
// 返回: { smart_goals: ["Goal 1", "Goal 2", ...] }
```

#### Setting标签页
**显示内容**：
- Preferred Name（偏好名称）
- Hobbies（兴趣爱好）
- Family（家庭信息）
- Friends（朋友信息）
- Travel（旅行信息）

**数据来源**：
```typescript
masRequest.getPatientInfo()
// 返回: { preferred_name, hobbies, family, friends, travel }
```

#### 保留的代码
- 原有的wordList、sentenceList等代码已注释保留
- 如需恢复原有功能，取消注释即可

### 3.3 Chat页面（无需修改）

**说明**：
- `src/pages/chat/index.vue` 无需修改
- 后端自动判断session类型并路由到MAS服务
- 前端保持原有界面和交互

## 四、使用流程

### 4.1 创建MAS会话

**方式1：通过API创建**
```bash
POST /api/v1/sessions/mas
Headers: X-Token: {jwt_token}
```

**方式2：直接创建（需要前端调用）**
```typescript
// 前端可以添加创建MAS会话的按钮
chatRequest.sessionCreate({ type: 'MAS' })
```

### 4.2 开始对话

1. 用户打开MAS类型的session
2. 如果没有消息，调用 `GET /sessions/{session_id}/greeting`
3. 后端自动触发SOA开始会话
4. 返回第一条问候消息

### 4.3 发送消息

1. 用户在chat界面发送消息
2. 前端调用 `POST /sessions/{session_id}/chat`
3. 后端判断session类型为MAS
4. 转发消息到对应的MAS服务（SOA/GRA/SCA）
5. 获取助手回复并返回
6. 前端显示对话内容

### 4.4 查看Goal Review和Setting

1. 用户进入practice页面
2. 自动加载数据：
   - Goal Review：`GET /api/v1/mas/patients/goals`
   - Setting：`GET /api/v1/mas/patients/info`
3. 切换标签页查看不同信息

## 五、数据流

### 5.1 对话流程

```
用户发送消息
    ↓
前端: POST /sessions/{session_id}/chat
    ↓
后端: 判断session.type == 'MAS'
    ↓
后端: send_mas_session_message()
    ↓
获取patient_id (account_id映射)
    ↓
获取当前turn_index
    ↓
判断代理 (SOA/GRA/SCA)
    ↓
发送到MAS服务
    ↓
获取助手回复
    ↓
保存到数据库
    ↓
返回给前端
    ↓
前端显示消息
```

### 5.2 Practice页面数据流

```
用户进入practice页面
    ↓
加载Goal Review数据
    GET /api/v1/mas/patients/goals
    ↓
加载Setting数据
    GET /api/v1/mas/patients/info
    ↓
显示在对应标签页
```

## 六、关键配置

### 6.1 Session类型

数据库 `message_session` 表的 `type` 字段现在支持：
- `CHAT` - 原有自由聊天（保留）
- `TOPIC` - 原有话题聊天（保留）
- `MAS` - MAS健康教练对话（新增）

### 6.2 MAS服务地址

在 `.env` 文件中配置（可选）：
```env
MAS_MMA_URL=http://localhost:8001
MAS_SOA_URL=http://localhost:8002
MAS_GRA_URL=http://localhost:8003
MAS_SCA_URL=http://localhost:8004
MAS_SSA_URL=http://localhost:8005
MAS_OA_URL=http://localhost:8006
```

## 七、测试步骤

### 7.1 测试MAS对话

1. **创建MAS会话**
```bash
POST /api/v1/sessions/mas
Headers: X-Token: {token}
```

2. **获取问候语**
```bash
GET /api/v1/sessions/{session_id}/greeting
Headers: X-Token: {token}
```

3. **发送消息**
```bash
POST /api/v1/sessions/{session_id}/chat
Headers: X-Token: {token}
Body: { "message": "我今天的能量水平是7分" }
```

### 7.2 测试Practice页面

1. **查看Goal Review**
   - 进入practice页面
   - 切换到"Goal Review"标签
   - 应该显示SMART目标列表

2. **查看Setting**
   - 切换到"Setting"标签
   - 应该显示患者信息

## 八、注意事项

1. **MAS服务必须启动**：确保MAS服务（8001-8006端口）已启动
2. **Session类型**：创建session时必须指定type为"MAS"
3. **异步处理**：MAS服务调用是异步的，需要等待处理完成
4. **错误处理**：如果MAS服务不可用，会返回错误信息
5. **数据同步**：MAS数据存储在JSON文件，不会自动同步到数据库

## 九、回滚方案

如果需要回滚到原有逻辑：

1. **后端**：
   - 注释掉MAS相关的代码分支
   - 恢复原有的`create_session()`方法

2. **前端**：
   - 取消practice页面的注释，恢复原有代码
   - 删除`src/api/mas.ts`文件

## 十、文件清单

### 修改的文件
- `talkieai-server/app/api/session_routes.py` - 添加MAS路由判断和创建接口
- `talkieai-server/app/services/chat_service.py` - 添加MAS对话方法
- `talkieai-uniapp/src/pages/practice/index.vue` - 修改为显示MAS数据

### 新增的文件
- `talkieai-uniapp/src/api/mas.ts` - MAS API封装

### 保留的文件
- 所有原有chat相关代码都保留，只是添加了MAS分支

## 十一、API端点总结

### MAS相关API
- `POST /api/v1/sessions/mas` - 创建MAS会话（新增）
- `POST /api/v1/sessions/{session_id}/chat` - 发送消息（支持MAS类型）
- `GET /api/v1/sessions/{session_id}/greeting` - 获取问候语（支持MAS类型）
- `GET /api/v1/mas/patients/goals` - 获取SMART目标
- `GET /api/v1/mas/patients/info` - 获取患者信息

### 原有API（保留）
- 所有原有的chat和session相关API都保留
- 功能完全不变，只是添加了MAS类型支持
