# FunASR ASR 本地部署说明

本文档基于你当前目录结构编写：

```text
model/FunASR
├─ app/
├─ cache/
├─ scripts/
├─ funasr_source_code/
├─ docker-compose.yml
├─ Dockerfile
├─ README_DEPLOY.md
└─ requirements-service.txt
```

提供两种启动方式：

- Docker Compose（推荐）
- 无 Docker 本地一键启动脚本

## 1. 环境配置

- 操作系统：Windows / Linux / macOS
- Python：3.10+（本地脚本方式）
- Docker：20+，Docker Compose v2+（容器方式）
- 推荐资源：4 vCPU / 8GB RAM 及以上
- 首次启动会下载模型，需要联网

默认模型：

- ASR：`paraformer-zh`
- VAD：`fsmn-vad`
- 标点：`ct-punc`
- 设备：`cpu`

可通过环境变量覆盖：

- `MODEL_NAME`
- `VAD_MODEL`
- `PUNC_MODEL`
- `DEVICE`
- `BATCH_SIZE_S`

## 2. Docker Compose 部署步骤

在 `model/FunASR` 目录执行：

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f
```

停止服务：

```bash
docker compose down
```

服务地址：

- `http://127.0.0.1:10095`
- 健康检查：`GET /health`

## 3. 无 Docker 本地一键启动

在 `model/FunASR` 目录执行：

### Windows

```powershell
.\scripts\start_local.ps1
```

### Linux/macOS

```bash
bash ./scripts/start_local.sh
```

脚本自动完成：

1. 创建 `.venv`
2. 安装 CPU 版 `torch/torchaudio`
3. 安装本地源码 `funasr_source_code`（`pip install -e`）
4. 安装服务依赖
5. 启动 ASR 服务

## 4. 使用方式

### 4.1 健康检查

```bash
curl http://127.0.0.1:10095/health
```

### 4.2 上传音频文件识别

```bash
curl -X POST "http://127.0.0.1:10095/asr/file" \
  -F "file=@/path/to/your.wav"
```

### 4.3 指定本地路径识别

```bash
curl -X POST "http://127.0.0.1:10095/asr/path" \
  -H "Content-Type: application/json" \
  -d '{"audio_path":"/abs/path/to/your.wav"}'
```

### 4.4 直接使用 SDK 示例

在 `model/FunASR` 目录执行：

```bash
python scripts/sdk_infer.py --audio /path/to/your.wav --device cpu
```

## 5. 常见问题

- 首次启动慢：模型下载导致，属正常。
- 端口冲突：修改 `docker-compose.yml` 端口或脚本启动端口。
- GPU 推理：将 `DEVICE` 改为 `cuda:0` 并安装匹配 CUDA 的 PyTorch。
