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

## 一键启动（旧脚本，继续保留）

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

旧脚本仍适合 macOS/Linux 本地开发和课程演示环境，项目会继续保留：

- `start.sh`：旧的一键启动脚本，同时启动后端和前端。
- `backend-start.sh`：旧的后端单独启动脚本，默认后端端口 `8000`。
- `frontend-start.sh`：旧的前端单独启动脚本，默认前端端口 `5173`。

## 启动脚本说明

### 新增跨平台脚本（推荐）

新增脚本放在 `scripts/` 目录，与旧脚本区分清楚，便于在不同系统和 CI 中使用。

macOS/Linux 推荐：

```bash
bash scripts/start-unix.sh
```

Windows PowerShell 推荐：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-windows.ps1
```

Windows CMD 简化入口：

```cmd
scripts\start-windows.cmd
```

新增启动脚本会自动：

- 识别仓库根目录。
- 检查 Python 3.11+、Node.js 18+、npm 9+。
- 创建或复用后端虚拟环境。
- 安装 `backend/requirements.txt`。
- 前端优先执行 `npm ci`，无 lock 文件时执行 `npm install`。
- 在数据库不存在时初始化题库与知识库数据。
- 使用 `PYTHONPATH=backend python -m uvicorn app.main:app` 启动后端。
- 使用 `npm run dev` 启动前端，并注入 `VITE_API_BASE`。
- `Ctrl+C` 后停止前后端子进程。
- 本地模型服务不可用时只输出提示，不阻断启动。

### 常用环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BACKEND_PORT` | `18500`（新跨平台脚本和 `start.sh`） | 后端端口。`backend-start.sh` 默认 `8000`。 |
| `FRONTEND_PORT` | `5173` | 前端端口。 |
| `START_FRONTEND` | `1` | 设为 `0` 时只启动后端。 |
| `BACKEND_RELOAD` | `0` | 设为 `1` 时后端开启 uvicorn reload。 |
| `VITE_API_BASE` | `http://localhost:${BACKEND_PORT}/api/v1` | 前端请求后端 API 的地址。 |
| `BACKEND_VENV` | 仓库根目录 `.venv` | 后端虚拟环境路径。 |
| `SKIP_INSTALL` | `0` | 设为 `1` 时跳过依赖安装。 |
| `SKIP_DATA_INIT` | `0` | 设为 `1` 时跳过数据初始化。 |
| `AI_INTERVIEW_LLM_PROVIDER` | `mock` | LLM provider，可配置 `mock/openai/ollama`。 |
| `AI_INTERVIEW_ASR_PROVIDER` | `mock` | ASR provider，可配置 `mock/openai/funasr/paddlespeech`。 |
| `AI_INTERVIEW_TTS_PROVIDER` | `mock` | TTS provider，可配置 `mock/openai/paddlespeech`。 |

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

## 常用检查

- 后端接口文档：`http://localhost:18500/docs`（使用 `start.sh`）
- 前端页面：`http://localhost:5173`
- OpenAPI 文件：`openapi/openapi.yaml`
- Postman 集合：`postman/AI-Interview.postman_collection.json`

## 测试与质量检查

### 一键测试脚本

macOS/Linux：

```bash
bash scripts/test-unix.sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test-windows.ps1
```

Windows CMD：

```cmd
scripts\test-windows.cmd
```

测试脚本支持以下环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `RUN_BACKEND_TESTS` | `1` | 是否运行后端 pytest。 |
| `RUN_FRONTEND_TESTS` | `1` | 是否运行前端 Vitest 和 build。 |
| `RUN_E2E` | `1` | 是否运行 Playwright E2E。 |
| `RUN_LINT` | `1` | 是否运行 Ruff 和 ESLint。 |
| `SKIP_INSTALL` | `0` | 设为 `1` 时跳过依赖安装。 |
| `BACKEND_REQUIREMENTS` | `backend/requirements-ci.txt` | 测试脚本默认使用轻量 CI 依赖集。 |

后端单独检查：

```bash
cd backend
python -m pip install -r requirements-ci.txt
cd ..
python -m ruff check backend tests
python -m pytest tests/backend
```

前端单独检查：

```bash
cd frontend
npm ci
npm run lint
npm run test
npm run build
npm run e2e
```

Playwright 如提示浏览器未安装：

```bash
cd frontend
npx playwright install --with-deps chromium
```

说明：`backend/requirements.txt` 保留完整本地能力依赖，包括 Ollama/FunASR/PaddleSpeech 等相关包；`backend/requirements-ci.txt` 用于 CI 和普通单元测试，避免因本地大模型、GPU 或外部服务不可用导致质量门禁不稳定。

## GitHub Actions CI

`.github/workflows/ci.yml` 会在以下场景触发：

- push 到 `main`。
- pull request 到 `main`。
- 手动 `workflow_dispatch`。

CI 当前包含：

- 后端质量门禁：安装 `backend/requirements-ci.txt`、shell 语法检查、数据脚本 dry-run、`ruff check backend tests`、`pytest tests/backend`。
- 前端质量门禁：`npm ci`、`npm run lint`、`npm run test`、`npm run build`、安装 Chromium 并运行 `npm run e2e`。
- Windows 脚本 smoke：解析 PowerShell 脚本，并以跳过安装/检查的方式验证测试脚本入口可执行。

CI 不需要任何真实密钥，也不要求 `AI_INTERVIEW_OPENAI_API_KEY`。默认 provider 使用 `mock`，本地模型服务不可用不会导致 CI 失败。Playwright 失败时会上传 `frontend/playwright-report` 和 `frontend/test-results` artifact，方便查看截图、trace 和错误日志。

## 故障排查

- Python 版本不满足：安装 Python 3.11+，或设置 `PYTHON_BIN` 指向正确解释器。
- Node/npm 版本不满足：安装 Node.js 18+ 和 npm 9+，推荐使用 Node 20。
- Windows PowerShell 执行策略限制：使用 `powershell -ExecutionPolicy Bypass -File .\scripts\start-windows.ps1`。
- Playwright 浏览器未安装：执行 `cd frontend && npx playwright install --with-deps chromium`。
- 本地模型服务不可用：默认 `mock` provider 可运行完整主流程；如使用 `ollama/funasr/paddlespeech`，请先启动或安装对应服务/SDK。健康检查接口为 `/api/v1/admin/providers/health`。
- 端口占用：设置 `BACKEND_PORT` 或 `FRONTEND_PORT`，例如 `BACKEND_PORT=18501 bash scripts/start-unix.sh`。
- 依赖安装过慢：本地完整启动使用 `backend/requirements.txt`；CI 和测试可使用 `backend/requirements-ci.txt`。

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
