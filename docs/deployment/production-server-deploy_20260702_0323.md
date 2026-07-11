# Goal Guardian 生产服务器部署手册

生成时间：2026-07-02 03:23 Asia/Shanghai

## 目标架构

生产部署采用普通 Linux 服务器运行 Docker Compose，数据库使用 Neon/Postgres。

```text
Mobile App / Web Client
        |
        | HTTPS
        v
Nginx or Caddy on server
        |
        | http://127.0.0.1:8098
        v
backend container
        |
        | Docker internal network
        v
MMA / SOA / GRA / SCA / SSA / OA containers
        |
        | DATABASE_URL
        v
Neon Postgres
```

生产 Compose 默认只把后端绑定到服务器本机回环地址，避免直接把 `8098` 暴露到公网。公网访问应通过 Nginx 或 Caddy 反向代理到后端。

## 服务器要求

建议最低配置：

- CPU：2 vCPU 起步，推荐 4 vCPU
- 内存：4 GB 起步，推荐 8 GB
- 磁盘：40 GB 起步
- 系统：Ubuntu 22.04 LTS 或 24.04 LTS

如果在服务器上运行 Whisper 或其它较重模型，优先选择更高内存和更大磁盘。

## 服务器基础安装

```bash
sudo apt update
sudo apt install -y git ca-certificates curl nginx
```

安装 Docker 与 Compose plugin：

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker
docker version
docker compose version
```

防火墙建议只开放 SSH、HTTP、HTTPS：

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

## 拉取项目

```bash
git clone https://github.com/redpanda12138/Goal_Guardian.git
cd Goal_Guardian
git checkout codex/production-containerization
```

后续合并到 `main` 后，服务器可改为 checkout `main`。

## 配置生产环境变量

在服务器创建：

```bash
cp talkieai-server/.env.production.example talkieai-server/.env.production
nano talkieai-server/.env.production
```

至少确认这些配置：

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/DB?sslmode=require
TOKEN_SECRET=replace-with-random-256-bit-secret
ZHIPU_AI_API_KEY=replace-with-rotated-production-key

TEMP_SAVE_FILE_PATH=/app/files
WHISPER_MODEL_PATH=/models/whisper
WHISPER_MODEL_HOST_PATH=/opt/goal-guardian/models/whisper-small-sing2eng-translate
WHISPER_MODEL_PROFILE=small-sing2eng

BACKEND_HOST_BIND=127.0.0.1
BACKEND_HOST_PORT=8098

MAS_MEMORY_REQUIRE_DATABASE=true
MAS_OA_SCHEDULER_ENABLED=true
```

说明：

- `DATABASE_URL` 使用同一个 Neon/Postgres 连接串，backend 和 MAS 都会读取它。
- `MAS_MEMORY_REQUIRE_DATABASE=true` 表示生产环境不允许静默回退到本地 JSON memory。
- `BACKEND_HOST_BIND=127.0.0.1` 表示后端只允许服务器本机访问，由反向代理暴露 HTTPS。
- 如果确实要临时直接暴露端口，可以设置 `BACKEND_HOST_BIND=0.0.0.0`，但不推荐长期这样做。
- `PYTORCH_GPU_INDEX_URL` 和 `PYTORCH_GPU_WHEEL_SUFFIX` 默认留空；只有构建 GPU 镜像时才填写真实 CUDA wheel 配置。

## 准备 Whisper 模型目录

生产 Compose 不把 Whisper 模型打进镜像，而是从服务器本地目录只读挂载。

示例：

```bash
sudo mkdir -p /opt/goal-guardian/models/whisper-small-sing2eng-translate
sudo chown -R "$USER":"$USER" /opt/goal-guardian
```

把模型文件放到 `.env.production` 中 `WHISPER_MODEL_HOST_PATH` 指向的目录。

## 启动生产栈

```bash
docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml up -d --build
```

查看状态：

```bash
docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml ps
```

预期 7 个服务均为 healthy：

- `backend`
- `mma`
- `soa`
- `gra`
- `sca`
- `ssa`
- `oa`

## 配置 Nginx 反向代理

假设域名是 `api.example.com`，创建配置：

```bash
sudo nano /etc/nginx/sites-available/goal-guardian
```

内容：

```nginx
server {
    listen 80;
    server_name api.example.com;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:8098;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 30s;
        proxy_send_timeout 300s;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/goal-guardian /etc/nginx/sites-enabled/goal-guardian
sudo nginx -t
sudo systemctl reload nginx
```

配置 HTTPS 可使用 Certbot：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.example.com
```

## 验证部署

本机后端验证：

```bash
curl http://127.0.0.1:8098/openapi.json
```

公网 HTTPS 验证：

```bash
curl https://api.example.com/openapi.json
```

数据库连接验证：

```bash
docker exec goal-guardian-backend-1 python -c "import os; from sqlalchemy import create_engine, text; engine=create_engine(os.environ['DATABASE_URL'], pool_pre_ping=True); print(engine.connect().execute(text('select 1')).scalar())"
```

MAS 内网连通验证：

```bash
docker exec goal-guardian-backend-1 python -c "import urllib.request; services=['mma','soa','gra','sca','ssa','oa']; [print(s, urllib.request.urlopen(f'http://{s}:8000/openapi.json', timeout=5).status) for s in services]"
```

## 常用运维命令

查看日志：

```bash
docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml logs -f backend
docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml logs -f mma
```

重启：

```bash
docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml restart
```

更新代码并重新部署：

```bash
git pull
docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml ps
```

停止：

```bash
docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml down
```

## 数据与文件边界

已经接入 Neon/Postgres：

- 后端 SQLAlchemy 数据表
- MAS memory JSON 的生产存储

仍在服务器本地：

- 上传文件、语音、图片：`backend-files` Docker volume，对应容器内 `/app/files`
- Whisper 模型：`WHISPER_MODEL_HOST_PATH` 只读挂载到 `/models/whisper`
- Docker logs：通过 Docker 管理

后续如果需要多服务器或更强可靠性，建议把上传文件迁移到对象存储，例如 S3、Cloudflare R2 或其它兼容服务。

## 回滚

查看最近提交：

```bash
git log --oneline -10
```

切回指定提交并重建：

```bash
git checkout <commit-sha>
docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml up -d --build
```

如果只是容器异常，可先重启：

```bash
docker compose --env-file talkieai-server/.env.production -f docker-compose.prod.yml restart
```

## 手机 App 配置

手机端 API Base URL 应配置为 HTTPS 域名：

```text
https://api.example.com
```

不要配置为：

```text
http://127.0.0.1:8098
```

`127.0.0.1` 在手机上代表手机自己，不是服务器。
