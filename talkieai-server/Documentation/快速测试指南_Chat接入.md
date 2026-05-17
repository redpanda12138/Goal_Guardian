# Chat接入MAS快速测试指南

## 一、准备工作

### 1. 启动服务

```bash
# 1. 启动MAS服务
cd mas
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 2. 启动talkieai-server
cd ../talkieai-server
uvicorn app.main:app --host 0.0.0.0 --port 8097
```

### 2. 获取JWT Token

```bash
curl -X POST "http://localhost:8097/api/v1/account/visitor-login" \
  -H "Content-Type: application/json" \
  -d '{
    "fingerprint": "test_fingerprint_12345"
  }'
```

保存返回的token。

## 二、测试MAS对话

### 步骤1：创建MAS会话

```bash
curl -X POST "http://localhost:8097/api/v1/sessions/mas" \
  -H "X-Token: {your_jwt_token}" \
  -H "Content-Type: application/json"
```

**响应示例**:
```json
{
  "code": "200",
  "status": "SUCCESS",
  "data": {
    "id": "session_xyz789",
    "type": "MAS",
    "account_id": "user_abc123",
    "is_default": 1
  }
}
```

保存返回的session_id。

### 步骤2：获取问候语（触发SOA）

```bash
curl -X GET "http://localhost:8097/api/v1/sessions/{session_id}/greeting" \
  -H "X-Token: {your_jwt_token}"
```

**响应示例**:
```json
{
  "code": "200",
  "status": "SUCCESS",
  "data": {
    "id": "message_123",
    "content": "Hi Daniel! It's great to see you today. How are you feeling right now, especially in terms of your energy?",
    "role": "ASSISTANT"
  }
}
```

### 步骤3：发送第一条消息

```bash
curl -X POST "http://localhost:8097/api/v1/sessions/{session_id}/chat" \
  -H "X-Token: {your_jwt_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我今天的能量水平是7分"
  }'
```

**响应示例**:
```json
{
  "code": "200",
  "status": "SUCCESS",
  "data": {
    "id": "message_456",
    "content": "That's great! Can you tell me more about what that 7 means to you?",
    "send_message_id": "message_455",
    "session_id": "session_xyz789"
  }
}
```

### 步骤4：继续对话

重复步骤3，发送更多消息，系统会自动根据turn_index路由到不同的代理（SOA → GRA → SCA）。

## 三、测试Practice页面

### 步骤1：查看Goal Review

```bash
curl -X GET "http://localhost:8097/api/v1/mas/patients/goals" \
  -H "X-Token: {your_jwt_token}"
```

**响应示例**:
```json
{
  "code": "200",
  "status": "SUCCESS",
  "data": {
    "preferred_name": "Daniel",
    "smart_goals": [
      "Homecook dinner on the weekend, once per week",
      "Increase the duration of jogging to 45 minutes, once per week"
    ]
  }
}
```

### 步骤2：查看Setting

```bash
curl -X GET "http://localhost:8097/api/v1/mas/patients/info" \
  -H "X-Token: {your_jwt_token}"
```

**响应示例**:
```json
{
  "code": "200",
  "status": "SUCCESS",
  "data": {
    "preferred_name": "Daniel",
    "hobbies": ["photography"],
    "family": ["eldest son recently started university overseas"],
    "friends": [],
    "travel": ["family trip to Penang"]
  }
}
```

## 四、前端测试

### 1. 创建MAS会话

在前端代码中：
```typescript
import chatRequest from "@/api/chat";

// 创建MAS会话
chatRequest.sessionMasCreate().then((data) => {
  const sessionId = data.data.id;
  // 跳转到chat页面
  uni.navigateTo({
    url: `/pages/chat/index?sessionId=${sessionId}`
  });
});
```

### 2. 在Chat页面对话

- 打开MAS会话后，会自动获取问候语
- 发送消息时，后端自动转发到MAS服务
- 界面保持原有样式，无需修改

### 3. 在Practice页面查看

- 进入practice页面
- 自动加载Goal Review和Setting数据
- 切换标签页查看不同信息

## 五、完整对话流程示例

### Python测试脚本

```python
import requests
import json
import time

BASE_URL = "http://localhost:8097/api/v1"
TOKEN = "your_jwt_token_here"

headers = {
    "X-Token": TOKEN,
    "Content-Type": "application/json"
}

# 1. 创建MAS会话
print("1. 创建MAS会话...")
response = requests.post(
    f"{BASE_URL}/sessions/mas",
    headers=headers
)
session_data = response.json()
session_id = session_data["data"]["id"]
print(f"Session ID: {session_id}")

# 2. 获取问候语
print("\n2. 获取问候语...")
response = requests.get(
    f"{BASE_URL}/sessions/{session_id}/greeting",
    headers=headers
)
print(json.dumps(response.json(), indent=2, ensure_ascii=False))

# 等待一下
time.sleep(2)

# 3. 发送第一条消息
print("\n3. 发送第一条消息...")
response = requests.post(
    f"{BASE_URL}/sessions/{session_id}/chat",
    headers=headers,
    json={"message": "我今天的能量水平是7分"}
)
print(json.dumps(response.json(), indent=2, ensure_ascii=False))

# 4. 查看Goal Review
print("\n4. 查看Goal Review...")
response = requests.get(
    f"{BASE_URL}/mas/patients/goals",
    headers=headers
)
print(json.dumps(response.json(), indent=2, ensure_ascii=False))

# 5. 查看Setting
print("\n5. 查看Setting...")
response = requests.get(
    f"{BASE_URL}/mas/patients/info",
    headers=headers
)
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
```

## 六、常见问题

### Q1: 创建MAS会话后没有问候语？

**解决**:
1. 确保MAS服务已启动
2. 调用 `GET /sessions/{session_id}/greeting` 触发SOA
3. 检查OA服务日志

### Q2: 发送消息后没有回复？

**解决**:
1. 检查MAS服务健康状态：`GET /api/v1/mas/health`
2. 查看talkieai-server日志
3. 检查patient_id是否正确映射

### Q3: Practice页面没有数据？

**解决**:
1. 确保已经完成至少一次健康教练会话
2. 确保已经提交过会话笔记（触发MMA提取）
3. 检查API返回的数据格式

## 七、验证清单

- [ ] MAS服务已启动（8001-8006端口）
- [ ] talkieai-server已启动
- [ ] 已获取JWT token
- [ ] 成功创建MAS会话
- [ ] 成功获取问候语
- [ ] 成功发送消息并收到回复
- [ ] Practice页面显示Goal Review
- [ ] Practice页面显示Setting
