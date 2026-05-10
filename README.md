# AI-Interview

AI 模拟面试平台。

## 新增能力

- 题库练习：用户可直接从网站进入题库练习，按岗位、模式、题量和类别抽题，使用文字连续作答。
- 题库管理：管理员可在网站分页查看题库、按关键词筛选、上传 Markdown 题库文件、单题表单录入，并触发题库导入任务。

## 环境要求

- Python 3.11+
- Node.js 18+
- npm 9+

## 一键启动

在仓库根目录执行：

```bash
bash ./start.sh
```

脚本会自动：

- 创建后端虚拟环境并安装依赖
- 安装前端依赖
- 在数据库不存在时初始化数据
- 同时启动后端和前端

启动后访问：

- 后端：`http://localhost:8000`
- 前端：`http://localhost:5173`

按 `Ctrl+C` 可同时停止两个服务。

## 安装依赖

### 后端

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 前端

```bash
cd frontend
npm install
```

## 首次初始化数据

在仓库根目录执行：

```bash
python backend/assets/scripts/data/validate_materials.py --strict
python backend/assets/scripts/data/normalize_materials.py
python backend/assets/scripts/data/build_question_bank.py
python backend/assets/scripts/data/build_knowledge_vectorstore.py
```

## 启动后端

在仓库根目录执行：

```bash
PYTHONPATH=backend python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

后端默认地址：`http://localhost:8000`

常用环境变量：

- `AI_INTERVIEW_DB_PATH`：默认 `backend/assets/data/sqlite/interview.db`
- `AI_INTERVIEW_CHROMA_DIR`：默认 `backend/assets/data/chroma`
- `AI_INTERVIEW_USER_TOKEN`：默认 `user-token`
- `AI_INTERVIEW_ADMIN_TOKEN`：默认 `admin-token`

## 启动前端

在 `frontend` 目录执行：

```bash
npm run dev
```

前端默认地址：`http://localhost:5173`

如需覆盖后端 API 地址，可在启动前设置：

```bash
VITE_API_BASE=http://localhost:8000/api/v1 npm run dev
```

## 常用检查

- 后端接口文档：`http://localhost:8000/docs`
- 前端页面：`http://localhost:5173`
- OpenAPI 文件：`openapi/openapi.yaml`
- Postman 集合：`postman/AI-Interview.postman_collection.json`

## 题库管理格式要求

- Java 题库文件：题目 heading 使用 `## 第 X 题：标题`，小节使用 `### 题干 / ### 类别 / ### 解析`
- Web 题库文件：题目 heading 使用 `### 第 X 题：标题`，小节使用 `#### 题干 / #### 类别 / #### 解析`
- 类别枚举只允许：`技术 / 项目 / 场景 / 行为`
- 管理端上传接口：`POST /api/v1/practice/questions/upload`
- 管理端单题录入接口：`POST /api/v1/practice/questions`
- 管理端导入任务查询接口：`GET /api/v1/practice/questions/import-tasks/{task_id}`

## 本地模型模式

- 默认面试链路可配置本地模型：`ollama / funasr / paddlespeech`
- FunASR 与 PaddleSpeech 采用后端 SDK 进程内直连，不再依赖外部 HTTP `/health` 服务
- 语音输入支持真实文件上传，不再只依赖音频 URL
- 当本地服务不可用时，系统会显式降级为模板模式，并在前端展示 provider 状态
- 常用健康检查：`/api/v1/admin/providers/health`
