# MAS系统智谱AI集成说明

## 概述

已为MAS系统添加智谱AI支持，所有MAS服务（SOA, GRA, SCA, SSA, MMA）现在都支持使用OpenAI GPT或智谱AI。

## 实现方式

### 1. 统一的AI调用模块

创建了 `ai_helper.py` 模块，提供统一的AI调用接口：
- `ask_ai(messages, temperature, tools)`: 统一的AI调用接口
- `ask_ai_json(messages, temperature)`: 返回JSON格式结果

**支持的特性：**
- ✅ OpenAI GPT（支持工具调用）
- ✅ 智谱AI（通过JSON格式实现类似功能）
- ✅ 自动根据环境变量选择AI服务

### 2. 修改的服务

所有MAS服务都已更新：
- **SOA** (`mas/SOA/app.py`): 使用 `ai_helper.ask_ai`
- **GRA** (`mas/GRA/app.py`): 使用 `ai_helper.ask_ai`
- **SCA** (`mas/SCA/app.py`): 使用 `ai_helper.ask_ai`
- **SSA** (`mas/SSA/app.py`): 使用 `ai_helper.ask_ai`
- **MMA** (`mas/MMA/app.py`): 使用 `ai_helper.ask_ai` 和 `ask_ai_json`（特殊处理工具调用）

### 3. 环境变量配置

在 `docker-compose.yml` 中添加了以下环境变量：

```yaml
environment:
  - OPENAI_API_KEY=${OPENAI_API_KEY}
  - AI_SERVER=${AI_SERVER:-OPENAI}  # OPENAI 或 ZHIPU
  - ZHIPU_AI_API_KEY=${ZHIPU_AI_API_KEY:-}
  - ZHIPU_AI_MODEL=${ZHIPU_AI_MODEL:-glm-4}
  - OPENAI_MODEL=${OPENAI_MODEL:-gpt-4.1}
```

### 4. 依赖更新

所有服务的 `requirements.txt` 都已添加 `zhipuai` 依赖。

## 配置方法

### 方法1：使用环境变量文件

在 `mas/.env` 文件中配置：

```bash
# OpenAI配置（默认）
OPENAI_API_KEY=sk-xxx
AI_SERVER=OPENAI
OPENAI_MODEL=gpt-4.1

# 或使用智谱AI
AI_SERVER=ZHIPU
ZHIPU_AI_API_KEY=xxx.xxx
ZHIPU_AI_MODEL=glm-4
```

### 方法2：直接在docker-compose.yml中设置

```yaml
environment:
  - AI_SERVER=ZHIPU
  - ZHIPU_AI_API_KEY=your_zhipu_api_key
  - ZHIPU_AI_MODEL=glm-4
```

## 使用说明

### 切换到智谱AI

1. **设置环境变量：**
   ```bash
   export AI_SERVER=ZHIPU
   export ZHIPU_AI_API_KEY=your_api_key
   export ZHIPU_AI_MODEL=glm-4
   ```

2. **重启MAS服务：**
   ```bash
   cd mas
   docker-compose down
   docker-compose up -d
   ```

### 切换回OpenAI

```bash
export AI_SERVER=OPENAI
# 或直接不设置，默认就是OPENAI
```

## 特殊处理

### MMA服务的工具调用

MMA服务使用OpenAI的工具调用（tools）功能来提取结构化信息。智谱AI不支持工具调用，因此：

- **OpenAI模式：** 使用工具调用，自动提取JSON
- **智谱AI模式：** 在prompt中明确要求JSON格式，然后解析响应

两种模式都能正常工作，返回相同的数据结构。

## 验证

### 检查AI服务配置

查看服务日志，确认使用的AI服务：
```bash
docker-compose logs soa | grep -i "ai\|zhipu\|openai"
```

### 测试功能

1. **创建MAS会话**
2. **发送消息**
3. **检查日志**，确认AI调用成功

## 注意事项

1. **API密钥安全：** 不要将API密钥提交到代码仓库
2. **模型兼容性：** 确保使用的模型支持所需功能
3. **成本考虑：** 智谱AI和OpenAI的定价不同，请根据需求选择
4. **工具调用限制：** 智谱AI不支持工具调用，MMA服务会自动fallback到JSON格式

## 文件清单

### 新增文件
- `mas/ai_helper.py` - 统一的AI调用模块（根目录）
- `mas/SOA/ai_helper.py` - SOA服务的AI模块
- `mas/GRA/ai_helper.py` - GRA服务的AI模块
- `mas/SCA/ai_helper.py` - SCA服务的AI模块
- `mas/SSA/ai_helper.py` - SSA服务的AI模块
- `mas/MMA/ai_helper.py` - MMA服务的AI模块

### 修改文件
- `mas/SOA/app.py` - 使用ai_helper
- `mas/GRA/app.py` - 使用ai_helper
- `mas/SCA/app.py` - 使用ai_helper
- `mas/SSA/app.py` - 使用ai_helper
- `mas/MMA/app.py` - 使用ai_helper（特殊处理工具调用）
- `mas/docker-compose.yml` - 添加环境变量
- `mas/*/requirements.txt` - 添加zhipuai依赖

## 故障排查

### 问题1：智谱AI调用失败

**检查：**
- 环境变量 `ZHIPU_AI_API_KEY` 是否设置
- API密钥是否有效
- 网络连接是否正常

### 问题2：导入错误

**错误：** `ImportError: zhipuai package not installed`

**解决：**
```bash
# 重新构建Docker镜像
docker-compose build
docker-compose up -d
```

### 问题3：MMA工具调用失败（使用智谱AI时）

**说明：** 这是正常的，智谱AI不支持工具调用，会自动fallback到JSON格式提取。

## 总结

✅ **已完成：**
- 所有MAS服务都支持智谱AI
- 统一的AI调用接口
- 环境变量配置
- 依赖更新

✅ **兼容性：**
- 向后兼容，默认使用OpenAI
- 可以通过环境变量轻松切换
