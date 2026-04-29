# AI-Interview

AI 模拟面试项目，包含：
- 后端：FastAPI（`backend/`）
- 前端：React + Vite（`frontend/`）

## 环境要求

- Python `>= 3.11`
- Node.js `>= 20`
- npm `>= 9`

## 后端启动

### 1. 安装依赖

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirement.txt
```

### 2. 初始化数据（首次必做）

```bash
python backend/assets/scripts/data/validate_materials.py --strict
python backend/assets/scripts/data/normalize_materials.py
python backend/assets/scripts/data/build_question_bank.py
python backend/assets/scripts/data/build_knowledge_vectorstore.py
```

### 3. 启动服务

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=$(pwd) python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动后访问：
- [http://localhost:8000/docs](http://localhost:8000/docs)

## 前端启动

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务

```bash
npm run dev
```

默认地址：
- [http://localhost:5173](http://localhost:5173)

## 一键启动（推荐）

```bash
./start-dev.sh
```

常用启动参数：
- `START_FRONTEND=0`：只启动后端
- `BACKEND_PORT=8001`：自定义后端端口
- `BACKEND_HOST=127.0.0.1`：自定义后端监听地址
- `BACKEND_RELOAD=1`：开启后端热重载（如本机受限可保持默认关闭）

示例：

```bash
START_FRONTEND=0 BACKEND_PORT=8001 ./start-dev.sh
```

## 常用命令

### 后端测试

```bash
python -m unittest discover -s tests/backend -p "test_*.py"
```

### 前端测试

```bash
cd frontend
npm run test
```
