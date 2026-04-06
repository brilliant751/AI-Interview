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
python -m pip install --upgrade pip
pip install fastapi uvicorn pydantic pydantic-settings chromadb langchain langgraph
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
PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
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
