# 基于 PaddleSpeech 的 TTS 本地部署

## 项目简介
本项目实现了一个基于 PaddleSpeech 预训练模型的文本转语音（TTS）服务。  
提供 FastAPI 接口，输入文本，返回 `wav` 音频文件；支持 Docker 一键部署。

## 环境要求
- Python：`3.10+`
- Docker：推荐使用（主要部署方式）
- 可选：不使用 Docker 时，可本地安装 Python 依赖运行

## 部署方式
### 1）Docker 部署（推荐）
在项目目录（model/paddlespeech）执行：

```bash
docker compose build --no-cache
docker compose up -d
```

查看日志：

```bash
docker compose logs -f tts-api
```

说明：首次运行会自动下载 PaddleSpeech 预训练模型（约 1GB），耗时会明显更长。

### 2）本地运行（可选但不建议）
```bash
pip install -r requirements.txt
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## 使用方法
接口：
- `POST /tts`

请求 JSON 示例：
```json
{
  "text": "你好，欢迎使用语音合成服务。"
}
```

`curl` 示例：
```bash
curl -X POST "http://127.0.0.1:8000/tts" \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，欢迎使用语音合成服务。"}' \
  --output output.wav
```

输出结果：
- 返回 `wav` 音频文件（示例中保存为 `test.wav`）

## 项目结构说明
- `app.py`：FastAPI 服务入口，包含健康检查和 `/tts` 接口。
- `Dockerfile`：构建运行环境并启动 `uvicorn` 服务。
- `docker-compose.yml`：容器编排，映射 `8000:8000`。
- `demo.py`：简单调用示例脚本。
- `start.sh`：一键启动脚本（封装 `docker compose up`）。
