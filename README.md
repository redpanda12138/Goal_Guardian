# Goal Guardian / TalkieAI (Health Coach MAS)

本仓库在 [TalkieAI](https://github.com/maioria/chatgpt-talkieai) 基础上演进为 **多智能体健康顾问（MAS）** 应用：用户通过 **Home / Coach / Mine** 与同一 **MAS 会话** 进行健康教练对话，并查看基于 SMART 目标的 **周进度、下次运动安排、回访时间** 等看板信息。

## 功能概览

- **健康顾问聊天**：`GET /mas/sessions/get-or-create` 复用同一会话；对话走 MAS（OA / SOA / GRA / SCA / SSA 等）。
- **Coach 看板**：`GET /mas/coach/dashboard` 聚合目标、进度、下次运动推算与回访状态；`POST /mas/coach/goals/state-event` 记录快捷完成并写入 **状态消息**（`style` 以 `STATE_EVENT:` 开头，与教练对话气泡区分）。
- **前端**：首页与 Coach 页展示看板组件；MAS 聊天页顶部展示紧凑三卡；消息列表支持状态条样式。

## 技术栈

- **后端**：Python 3.11+、FastAPI、SQLAlchemy；语音可选 Whisper（见服务端 `.env`）。
- **前端**：UniApp、Vue 3（可发布 H5 / 小程序 / App）。

## 本地启动

```bash
# 1. 数据库：创建空库，配置 .env 后启动服务（会自动建表并加载默认数据）
git clone <your-fork>
cd talkieai-server
pip install -r requirements.txt
# 配置 .env（可参考 .env.default）
uvicorn app.main:app --host 0.0.0.0 --port 8097

# Whisper 配置示例（talkieai-server/.env）：
# WHISPER_MODEL_PROFILE=medium
# WHISPER_MODEL_PROFILE=offline

# 2. 前端
cd ../talkieai-uniapp
npm install
# 使用 HBuilder 或 CLI 运行到 Web / 小程序
```

## MAS 微服务

若需完整 MAS 链路（MMA/OA/SOA 等），请参考仓库内 `talkieai-server/mas` 与 `start.sh` / Docker 编排，并配置各服务 URL（应用配置中的 `MAS_*_URL`）。

## 许可证

## Instructions
```bash
# 1. Get into WSL terminal
wsl -d Ubuntu-22.04 
# 2. Open MySQL Server
sudo systemctl start mysql
# 3. Get into Python Environment
source talkieai-server/myenv/bin/activate  
(deactivate to exit)
# 4. Start Server
cd talkieai-server/mas
(docker compose stop 
docker-compose down
docker-compose build --no-cache)
docker-compose up -d
cd ..
./start.sh
# 5. Check uvicorn process
ps aux | grep uvicorn
# 6. Kill uvicorn process
pkill -f uvicorn

lsof -i:8098
kill -9 
