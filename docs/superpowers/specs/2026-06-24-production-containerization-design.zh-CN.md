# 生产环境容器化设计

## 目标

将主 FastAPI 后端和六个 MAS 服务打包为可部署的生产 Docker 服务。
默认支持仅使用 CPU 的 Linux 服务器，并通过额外的 Compose 覆盖文件选择性启用 NVIDIA GPU。

## 总体架构

Nginx 是唯一公网入口，将 HTTPS 请求转发到 Backend 容器的 8098 端口。
Backend 和全部 MAS 容器位于同一个 Docker 私有网络中。
Backend 通过 http://mma:8000 等 Docker 服务名访问 MAS，不再使用宿主机 localhost 端口。

Backend 和所有 MAS 服务共用同一个 Neon DATABASE_URL 以及同一套 AI 服务配置。
正式服务器最终只公开 Nginx 的 80 和 443 端口。
第一阶段先验证应用容器栈，不包含 Nginx 和证书配置。

## 新增文件

- talkieai-server/Dockerfile：构建主后端 CPU 基线镜像。
- talkieai-server/.dockerignore：排除密钥、虚拟环境、运行文件、日志、上传内容和 Whisper 权重。
- docker-compose.prod.yml：定义 Backend 和六个 MAS 服务。
- docker-compose.gpu.yml：为 Backend 增加可选的 NVIDIA GPU 配置。
- talkieai-server/.env.production.example：不包含真实密钥的生产环境变量模板。
- .gitignore：排除服务器真实配置 talkieai-server/.env.production。

## 主后端镜像

Backend 使用 Python 3.10，与现有 MAS 镜像和已经验证的 WSL 环境保持一致。
镜像安装音频处理所需的系统库、安装 talkieai-server/requirements.txt、复制应用源码，
并以前台进程方式在 8098 端口启动 Uvicorn。

镜像不包含：

- Neon 或 AI 密钥
- 本地 Python 虚拟环境
- 约 5.7 GB 的 Whisper 模型
- 运行日志
- 用户上传或生成的文件

## Whisper 模型策略

CPU 模式为默认基线。
服务器上的模型目录以只读 Volume 挂载到容器固定路径，
并通过 WHISPER_MODEL_PATH 指向该路径。

可选 GPU Compose 文件只为 Backend 增加 NVIDIA 设备请求，
不会复制整套服务配置。
没有安装 NVIDIA Container Toolkit 的服务器只使用 docker-compose.prod.yml。

Whisper 模型未挂载时，不阻止聊天、MAS、数据库和 AI 功能启动；
只有语音转写接口报告模型不可用。

## 服务与网络

生产容器栈包括：

- Backend：内部端口 8098
- MMA、SOA、GRA、SCA、SSA、OA：内部端口 8000

MAS 端口不发布到公网或宿主机。
Backend 使用以下环境变量访问 MAS：

- MAS_MMA_URL=http://mma:8000
- MAS_SOA_URL=http://soa:8000
- MAS_GRA_URL=http://gra:8000
- MAS_SCA_URL=http://sca:8000
- MAS_SSA_URL=http://ssa:8000
- MAS_OA_URL=http://oa:8000

所有服务使用 restart: unless-stopped。
健康检查通过 Python 请求各服务的 OpenAPI 地址，因此 slim 镜像不需要额外安装 curl。

## 数据持久化

Neon 保存业务表和 MAS memory 文档。
Docker Volume 保存 Backend 的上传文件和生成文件。
Whisper 权重由服务器目录只读挂载。
应用日志输出到 stdout 和 stderr，交由 Docker 日志轮转管理。
由于现有 MAS 启动命令仍写本地日志，必要的 MAS 日志目录继续挂载。

## 环境变量与密钥

talkieai-server/.env.production 只存在于服务器，并由 Compose 加载。
Git 中只保留不含密钥的 .env.production.example。

生产环境必须使用新的随机 TOKEN_SECRET。
由于旧 ZhipuAI Key 曾出现在 Git 历史中，生产部署前必须轮换 Key。

Backend 与 MAS 从同一环境文件读取 Neon 和 AI 配置。
生产环境继续设置 MAS_MEMORY_REQUIRE_DATABASE=true，禁止回退到本地 JSON。

## 启动顺序与故障处理

MAS 服务先启动并通过健康检查，随后启动 Backend。
OA 定时调度只由 Backend 启动，避免重复执行任务。

- Neon 不可用：依赖数据库的请求失败并记录错误，不伪造成功。
- MAS 不可用：Backend 返回代理服务错误，不影响其他独立服务。
- AI 额度不足或服务异常：沿用现有 AI 异常处理。
- Whisper 权重缺失：仅禁用语音转写。
- GPU 不可用：只启动 CPU Compose，不加载 GPU 覆盖文件。

## 验证标准

实施完成后必须验证：

1. Backend 镜像构建成功，且不复制密钥或模型。
2. 使用示例环境变量时，生产 Compose 能正确解析。
3. 本地生产模拟中七个服务全部变为 healthy。
4. Backend 能通过 Docker 服务名访问六个 MAS。
5. Backend 和 MAS 均能完成 Neon 数据库回环。
6. 有可用额度时，最小 ZhipuAI 请求成功。
7. 不安装 NVIDIA 工具时，CPU 容器栈可以启动。
8. GPU 覆盖文件能通过 Compose 配置检查。
9. 真实环境文件、模型、日志和上传内容不会进入 Git。

## 本阶段不包含

- 在真实服务器上安装和配置 Nginx、域名及 TLS。
- 选择云服务商或服务器规格。
- 将 Whisper 拆成独立服务。
- 创建后台管理平台。
- 重写 Git 历史。
