# AI-Interview

AI 模拟面试平台。

## 新增能力

- 题库练习：用户可直接从网站进入题库练习，按岗位、模式、题量和类别抽题，使用文字连续作答。
- 题库管理：管理员可在网站分页查看题库、按关键词筛选、上传 Markdown 题库文件、单题表单录入，并触发题库导入任务。
- 编程练习：用户可进入“编程练习”列表，选择题目后在网页端使用 C++11、Java、JavaScript 编写代码，编辑器默认提供示例模板，支持自测运行与正式判题。

## 环境要求

- Python 3.11+
- Node.js 18+
- npm 9+
- `g++`（支持 `-std=c++11`）
- `javac` / `java`（编译使用 `--release 21`）

## 一键启动

在仓库根目录执行：

```bash
bash ./start.sh
```

脚本会自动：

- 创建后端虚拟环境并安装依赖
- 安装前端依赖
- 在数据库不存在时初始化数据
- 检查本地模型服务可达性（Ollama/FunASR/PaddleSpeech）
- 同时启动后端和前端

启动后访问：

- 后端：`http://localhost:18500`
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
python backend/assets/scripts/data/import_coding_practice_questions.py
python backend/assets/scripts/data/build_knowledge_vectorstore.py
```

## 启动后端

在仓库根目录执行：

```bash
PYTHONPATH=backend python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

后端默认地址：`http://localhost:8000`
通过根目录 `start.sh` 一键启动时，后端默认地址：`http://localhost:18500`

常用环境变量：

- `AI_INTERVIEW_DB_PATH`：默认 `backend/assets/data/sqlite/interview.db`
- `AI_INTERVIEW_CHROMA_DIR`：默认 `backend/assets/data/chroma`
- `AI_INTERVIEW_USER_TOKEN`：默认 `user-token`
- `AI_INTERVIEW_ADMIN_TOKEN`：默认 `admin-token`
- `AI_INTERVIEW_LLM_PROVIDER`：默认 `mock`，接入 GLM 可设为 `openai`
- `AI_INTERVIEW_LLM_MODEL`：例如 `glm-4.7-flash`
- `AI_INTERVIEW_PROVIDER_BASE_URL`：兼容 OpenAI API 的地址，例如 `https://open.bigmodel.cn/api/paas/v4/`
- `AI_INTERVIEW_OPENAI_API_KEY`：兼容 OpenAI API 的密钥（可填写智谱 BigModel Key）

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

若使用一键启动脚本，默认前端会自动注入：

```bash
VITE_API_BASE=http://localhost:18500/api/v1
```

## 启动脚本环境变量

- `BACKEND_PORT`：后端端口（`start.sh` 默认 `18500`，`backend-start.sh` 默认 `8000`）
- `FRONTEND_PORT`：前端端口，默认 `5173`
- `START_FRONTEND`：是否启动前端，默认 `1`（可设为 `0` 只启动后端）
- `BACKEND_RELOAD`：是否开启后端自动重载，默认 `0`
- `BACKEND_VENV`：后端虚拟环境路径，默认仓库根目录下 `.venv`

## 常用检查

- 后端接口文档：`http://localhost:18500/docs`（使用 `start.sh`）
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

## 编程练习数据与接口

- 编程题材料文件：`backend/assets/material/coding/programming_practice_questions.json`
- 编程题导入脚本：`python backend/assets/scripts/data/import_coding_practice_questions.py`
- 题目列表接口：`GET /api/v1/coding-practice/questions`
- 创建/恢复会话接口：`POST /api/v1/coding-practice/sessions`
- 会话详情接口不返回题解代码，编辑器默认模板仅在前端本地注入，不持久化用户代码
- 运行自测接口：`POST /api/v1/coding-practice/sessions/{session_id}/run`
- 正式判题接口：`POST /api/v1/coding-practice/sessions/{session_id}/submit`
- 记录列表接口：`GET /api/v1/coding-practice/records`

## 本地模型模式

- 默认面试链路可配置本地模型：`ollama / funasr / paddlespeech`
- FunASR 与 PaddleSpeech 采用后端 SDK 进程内直连，不再依赖外部 HTTP `/health` 服务
- 语音输入支持真实文件上传，不再只依赖音频 URL
- 当本地服务不可用时，系统会显式降级为模板模式，并在前端展示 provider 状态
- 常用健康检查：`/api/v1/admin/providers/health`
