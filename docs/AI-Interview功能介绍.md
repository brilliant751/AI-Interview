# AI-Interview 功能介绍

更新时间：2026-06-27

## 1. 产品定位

AI-Interview 是一个面向求职者的 AI 模拟面试与能力提升平台。系统围绕“简历与岗位准备、AI 面试训练、题库练习、编程练习、面试复盘报告”构建完整训练闭环，帮助用户在真实面试前反复演练岗位相关问题，并沉淀个人练习记录、能力短板和改进建议。

平台同时提供管理端能力，用于维护题库、重建知识库、检查模型与语音 provider 状态，便于在课程演示、本地开发和团队交付场景中持续更新材料数据。

## 2. 用户与权限

### 2.1 普通用户

普通用户可以完成以下操作：

- 注册、登录、退出登录。
- 找回密码并通过重置令牌修改密码。
- 上传、预览、删除个人简历。
- 维护个人岗位描述 JD。
- 创建即时 AI 面试或预约面试。
- 使用文本或语音完成模拟面试。
- 暂停、继续、结束面试。
- 查看历史面试记录、面试回放和面试报告。
- 开始题库练习、查看题库练习记录。
- 开始编程练习、运行自测、提交判题并查看练习记录。

### 2.2 管理员

管理员除普通用户能力外，还可以访问管理菜单：

- 知识库重建：触发材料校验、归一化、题库构建、知识向量化与检索评估任务。
- 题库管理：分页查询题库、按岗位/类别/关键词筛选、上传 Markdown 题库文件、单题录入并触发增量导入。
- Provider 健康检查：查看 ASR、LLM、TTS、向量检索等服务状态。

系统前端通过 `AdminRoute` 限制管理页面访问，只有 `role=admin` 的用户可进入 `/admin/imports` 和 `/admin/questions`。

## 3. 认证与账号体系

认证模块提供完整账号生命周期：

- 注册账号：用户提交邮箱、昵称和密码。密码至少 8 位，且需要同时包含字母和数字。
- 登录账号：登录成功后签发 access token 和 refresh token。
- 自动刷新：前端 HTTP client 在遇到 401 时会使用 refresh token 自动刷新会话，并重放原请求。
- 退出登录：服务端撤销当前 refresh token，前端清空本地会话。
- 忘记密码：提交邮箱后服务端以防枚举方式统一返回 accepted。
- 重置密码：通过有效 reset token 设置新密码，并撤销历史 refresh token。
- 登录限流：后端按邮箱和 IP 维护登录窗口，超过阈值后返回频繁登录错误。
- 审计日志：注册、登录、刷新、退出、找回密码、重置密码都会记录认证事件。

主要接口位于 `/api/v1/auth`：

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `GET /auth/me`

## 4. 首页工作台

登录后进入首页概览页。首页是用户的训练工作台，聚合以下信息：

- 快捷入口：开始新面试、预约面试、继续上次面试、查看报告。
- KPI 卡片：平均得分、完成面试、本周练习、待提升能力等概览指标。
- 最近面试记录：展示岗位、得分、难度、建议和状态。
- 最近预约日历：按当前月份展示待进行预约数量，可跳转完整预约页。
- 能力分析：用进度条和综合得分展示表达、逻辑、专业知识、沟通、抗压等维度。
- 系统状态：轮询 provider 健康接口，展示语音识别、模型服务、向量检索状态。

顶部导航会定时查询当天面试安排；如果当天存在未完成预约，会通过通知提醒用户前往面试大厅。

## 5. 简历管理

简历是 AI 面试的核心输入之一。用户可以在简历管理页完成：

- 上传 `.pdf`、`.doc`、`.docx` 文件。
- 查看简历列表，包括简历 ID、文件名、解析状态、创建时间、最近使用时间。
- 在线预览 PDF 简历。
- 对暂不支持在线渲染的文档提供下载查看入口。
- 删除不再使用的简历。

如果简历被进行中的面试占用，删除操作会被后端拦截，避免破坏历史会话和报告生成链路。

主要接口位于 `/api/v1/resumes`：

- `POST /resumes`
- `GET /resumes`
- `GET /resumes/{resume_id}/file`
- `DELETE /resumes/{resume_id}`

## 6. 岗位库与 JD 管理

岗位库用于把面试问题与目标岗位绑定。系统支持两类 JD：

- 系统预置 JD：由系统内置，用户可以查看但不可删除。
- 用户上传 JD：由用户自行录入，可在后续面试中绑定，也可以删除。

岗位管理页支持：

- 选择常见岗位方向，例如后端开发、前端开发、算法、产品、运营、金融、咨询、风控等。
- 输入自定义岗位方向。
- 按岗位名称搜索 JD。
- 按公司筛选 JD。
- 新增岗位描述，支持标题、公司、正文文本。
- 点击卡片查看岗位描述详情。
- 删除用户上传的岗位描述。

主要接口：

- `GET /api/v1/companies`
- `POST /api/v1/jds`
- `GET /api/v1/jds`
- `DELETE /api/v1/jds/{jd_id}`

## 7. AI 模拟面试

AI 面试是平台的核心功能。用户可以基于简历、岗位方向或指定 JD 创建面试会话，并在面试过程中持续回答 AI 生成的问题。

### 7.1 面试创建

创建面试时可配置：

- 简历：选择已上传的简历。
- 岗位方向：当前支持 `java`、`web` 等岗位域。
- JD 绑定：可按岗位描述创建针对性面试。
- 难度：简单、中等、困难。
- 输入方式：文本或语音。
- 输出方式：文本或语音。
- 面试名称。
- 问题类型：项目、技术、场景。
- 语气配置：选择不同面试官语气 profile。

创建成功后，系统会返回第一道问题，并进入面试答题页。

### 7.2 面试过程

面试页分为信息区、问题区、回答区和历史记录区：

- 信息区展示面试 ID、岗位、难度、状态、简历、面试时长等上下文。
- 问题区展示当前问题、阶段和轮次。
- 文本输出模式直接展示问题文本。
- 语音输出模式会尝试自动播放题目语音，并保留文本辅助查看。
- 回答区根据输入模式切换文本框或录音控件。
- 历史记录区展示已经完成的问答轮次。

文本作答支持倒计时提示。语音作答支持：

- 请求麦克风权限。
- 枚举并选择音频输入设备。
- 自动选择更合适的内建麦克风。
- 题目播放结束后开始思考倒计时。
- 录音最长 3 分钟，到时自动提交。
- 手动开始、停止并提交录音。

### 7.3 问题生成与追问

后端通过 `QuestionWorkflow` 生成下一题。问题生成会综合：

- 当前回答内容。
- 当前阶段。
- 面试难度。
- 历史问答上下文。
- JD 内容。
- 简历内容。
- 检索到的知识库参考片段。

当配置真实 LLM provider 时，系统可调用 OpenAI 兼容接口或 Ollama 生成问题；当 provider 不可用或使用 mock 模式时，会退回模板问题，保证主流程可以继续演示。

典型阶段包括：

- `SELF_INTRO`：自我介绍。
- `PROJECT_DEEP_DIVE`：项目深挖。
- `TECHNICAL`：技术追问。
- `BEHAVIORAL`：行为面试。
- `END`：面试结束。

### 7.4 暂停、恢复与结束

用户可以在面试中：

- 暂停并保存进度。
- 直接访问 `/interview/{interview_id}` 恢复面试状态。
- 结束面试并触发报告生成。
- 面试结束后自动跳转报告详情。

主要接口位于 `/api/v1/interviews`：

- `POST /interviews`
- `GET /interviews/voice-tones`
- `POST /interviews/{interview_id}/turns`
- `POST /interviews/{interview_id}/turns/audio`
- `GET /interviews/{interview_id}/turn-jobs/{job_id}`
- `GET /interviews/{interview_id}/turns`
- `POST /interviews/{interview_id}/pause`
- `POST /interviews/{interview_id}/resume`
- `POST /interviews/{interview_id}/finish`
- `GET /interviews/{interview_id}/status`
- `GET /interviews/{interview_id}/playback`

## 8. 面试预约

预约模块用于提前规划面试练习。用户可以创建单场面试预约，并在预约时间到达后启动面试。

预约创建支持：

- 标题。
- 开始时间。
- 面试时长：20、45、60 分钟。
- 简历。
- 岗位方向或 JD。
- 难度。
- 输入/输出模式。
- 会话名称。
- 问题类型。
- 语气配置。

预约列表支持：

- 分页查询。
- 按状态筛选。
- 按日期范围筛选。
- 查看预约详情。
- 取消预约。
- 到点后开始预约面试。
- 下载 `.ics` 日历文件。
- 跳转 Google Calendar 和 Outlook Calendar。

预约状态包括：

- `scheduled`
- `ready`
- `in_progress`
- `completed`
- `missed`
- `cancelled`

主要接口位于 `/api/v1/interview-schedules`：

- `POST /interview-schedules`
- `GET /interview-schedules`
- `GET /interview-schedules/{schedule_id}`
- `POST /interview-schedules/{schedule_id}/cancel`
- `POST /interview-schedules/{schedule_id}/start`
- `GET /interview-schedules/{schedule_id}/calendar.ics`

## 9. 面试历史与回放

系统会保存用户的面试历史记录。历史页支持分页查看：

- 面试 ID。
- 面试名称。
- 简历文件。
- 岗位方向。
- 难度。
- 状态。
- JD 标题。
- 开始/结束时间。
- 问答轮次数。
- 总分。

用户可以删除历史记录，也可以进入回放页查看单场面试的完整问答过程。回放详情包含：

- 简历信息。
- 岗位、难度、状态、JD、开始/结束时间、持续时长。
- 每一轮问题、回答和时间戳。

主要接口：

- `GET /api/v1/interviews/history`
- `DELETE /api/v1/interviews/history/{interview_id}`
- `GET /api/v1/interviews/{interview_id}/playback`

## 10. 面试报告

用户结束面试后，后端异步生成结构化报告。报告页支持查看单场报告，也支持在没有指定面试 ID 时查看“我的报告”列表。

报告状态包括：

- `GENERATING`：生成中。
- `READY`：已完成。
- `FAILED`：生成失败。

如果报告生成失败，用户可以点击重试。

### 10.1 报告内容

报告详情包括：

- 总分。
- 优势。
- 待改进项。
- 建议。
- 最终推荐结论。
- 维度评分：能力分、匹配分、置信度、关键证据。
- 雷达图：当维度数满足条件时展示能力雷达。
- JD-简历-回答对齐：展示 JD 能力项、优先级、简历证据、回答证据、验证状态和备注。
- 关键问题深度分析：按问题展示题目意图、回答摘要、命中率、深度层级、简历/JD 关联、亮点、缺口和后续追问建议。
- 风险清单。

### 10.2 生成逻辑

后端 `ReportService` 会基于面试轮次、会话信息、简历文本和 JD 快照生成报告：

- 如果配置 OpenAI 兼容 provider 或 Ollama，会尝试通过 LLM 生成结构化 JSON 报告。
- 如果 LLM 不可用，会使用规则回退报告。
- 报告会计算 12 个能力维度，包括技术深度、架构设计、工程质量、性能意识、稳定性与容错、安全与风控、业务理解、问题分析与取舍、沟通表达、协作推进、学习敏捷性、岗位匹配度。
- 报告会根据轮次数估算置信度，并根据平均分给出推荐、有条件推荐或存疑结论。

主要接口：

- `GET /api/v1/report`
- `GET /api/v1/report/{interview_id}`
- `POST /api/v1/report/{interview_id}/retry`

## 11. 题库练习

题库练习用于在不进入完整模拟面试的情况下进行专项刷题。

### 11.1 练习创建

用户可以配置：

- 岗位域：`java` 或 `web`。
- 练习模式：顺序练习或追问占位模式。
- 题目数量。
- 类别过滤：技术、项目、场景、行为。

创建练习后，系统返回当前题目。用户提交答案后，系统会推进下一题；完成全部题目后会进入结束状态。

### 11.2 练习记录

系统保存练习记录，包括：

- 练习 ID。
- 岗位域。
- 模式。
- 状态。
- 总题数。
- 已答题数。
- 创建时间。

用户可以查看单场练习明细，包括每道题的题干、类别、解析、用户答案和答题时间。

主要接口位于 `/api/v1/practice`：

- `POST /practice/sessions`
- `GET /practice/sessions/{practice_id}`
- `POST /practice/sessions/{practice_id}/answers`
- `POST /practice/sessions/{practice_id}/finish`
- `GET /practice/records`
- `GET /practice/overview`
- `GET /practice/sessions/{practice_id}/records`

## 12. 编程练习

编程练习提供类似在线判题的专项训练能力。用户可以从题目列表进入某道题，在浏览器中编写代码，运行自测并提交判题。

### 12.1 题目列表

题目列表展示：

- 题目 ID。
- slug。
- 标题。
- 难度。
- 标签。
- 当前状态：未开始、进行中、已解决。
- 最近使用语言。
- 最新提交状态。
- 对应 session ID。

### 12.2 题目详情与会话

进入题目后，系统创建或恢复练习会话。题目详情包含：

- Markdown 题面。
- 输入说明。
- 输出说明。
- 约束条件。
- 样例用例。
- 自测用例。

前端支持三种语言：

- C++11。
- Java。
- JavaScript。

### 12.3 本地代码执行

后端 `CodeExecutionService` 在临时目录中运行代码：

- C++ 使用 `g++ -std=c++11` 编译。
- Java 默认尝试 `javac --release 21`，如果本地 JDK 不支持会自动降级为普通 `javac`。
- JavaScript 使用 Node.js 执行。
- 单次执行默认 5 秒超时。
- 输出会进行长度裁剪，避免过长输出影响响应。
- 比对输出时会忽略末尾空白差异。

自测只运行自测用例；正式提交运行完整测试用例集合。返回结果包括状态、通过数量、总用例数、消息、失败用例详情和编译输出。

主要接口位于 `/api/v1/coding-practice`：

- `GET /coding-practice/questions`
- `POST /coding-practice/sessions`
- `GET /coding-practice/sessions/{session_id}`
- `POST /coding-practice/sessions/{session_id}/run`
- `POST /coding-practice/sessions/{session_id}/submit`
- `GET /coding-practice/records`

## 13. 管理端：知识库重建

知识库重建用于把项目材料转化为可检索、可用于面试追问的结构化数据。

管理员可以触发材料导入任务，配置：

- 重建模式：全量或增量。
- 岗位域：Java、Web。
- 是否 dry-run。
- 分块模型。
- 嵌入模型。

后端异步执行导入流水线，并提供任务状态查询。完整流水线包括：

1. 材料校验。
2. 材料归一化。
3. 知识分块。
4. 题库构建。
5. 向量库构建。
6. 检索评估。
7. 生成报告文件。

服务端使用幂等键避免重复提交同一任务。全量重建任务运行中时，会拒绝新的全量任务，避免资源冲突。

主要接口：

- `POST /api/v1/admin/imports/materials`
- `GET /api/v1/admin/imports/materials/{task_id}`
- `GET /api/v1/admin/providers/health`

## 14. 管理端：题库管理

题库管理面向管理员维护 Java 和 Web 面试题。

支持能力：

- 分页查看题库。
- 按岗位、类别、关键词筛选。
- 上传 Markdown 题库文件。
- 单题录入。
- 自动生成增量 Markdown 文件。
- 写入材料目录后触发题库增量导入。
- 查询导入任务状态。

题库类别支持：

- 技术。
- 项目。
- 场景。
- 行为。

Markdown 题库有固定结构要求：

- Java 题库题目使用 `## 第 X 题：标题`。
- Web 题库题目使用 `### 第 X 题：标题`。
- 每题必须包含题干、类别、解析。

主要接口：

- `GET /api/v1/practice/questions`
- `POST /api/v1/practice/questions/upload`
- `POST /api/v1/practice/questions`
- `GET /api/v1/practice/questions/import-tasks/{task_id}`

## 15. 语音、模型与降级能力

系统将 ASR、LLM、TTS 封装为可插拔 provider。

### 15.1 ASR

语音识别支持：

- OpenAI 兼容语音识别。
- FunASR 本地 SDK。
- PaddleSpeech 兼容模式。
- Mock 模式。

语音回答既可以从上传音频文件识别，也可以从远端音频 URL 下载后识别。

### 15.2 TTS

语音合成支持：

- OpenAI 兼容 TTS。
- PaddleSpeech 本地 SDK。
- Mock URL。

真实 TTS 会返回浏览器可播放的 data URL。

### 15.3 LLM

问题生成和报告生成支持：

- OpenAI 兼容接口。
- Ollama。
- Mock/模板模式。

### 15.4 降级机制

当真实 provider 不可用时，系统不会直接中断主流程，而是：

- 在前端展示 provider 健康状态。
- 在面试链路元数据中返回 provider 状态、降级标记、trace ID、延迟和生成模式。
- 使用模板问题、mock ASR/TTS 或规则报告保证本地演示和测试可继续运行。

健康检查接口：

- `GET /api/v1/admin/providers/health`

## 16. 数据资产与材料目录

项目内置材料主要位于 `backend/assets/material/`：

- Java 面试题库：`backend/assets/material/java/java-interview/`
- Java 知识库：`backend/assets/material/java/java-knowledge/`
- Web 面试题库：`backend/assets/material/web/interview.md`
- Web 知识库：`backend/assets/material/web/knowledge.md`
- 编程练习题库：`backend/assets/material/coding/programming_practice_questions.json`

归一化、题库构建、向量库构建和报告输出主要位于：

- `backend/assets/data/normalized/`
- `backend/assets/data/chroma/`
- `backend/assets/data/reports/`
- `backend/assets/data/sqlite/interview.db`

项目同时在根目录 `data/` 中保留部分数据、报告和脚本产物，用于开发、演示或数据处理。

## 17. 前端页面地图

公开页面：

- `/`：欢迎页。
- `/login`：登录。
- `/register`：注册。
- `/forgot-password`：找回密码。
- `/reset-password`：重置密码。

登录后页面：

- `/overview`：首页概览。
- `/resumes`：简历管理。
- `/upload`：简历上传入口。
- `/schedules`：面试预约。
- `/interview`：AI 面试大厅/新建面试。
- `/interview/:interviewId`：指定面试会话。
- `/history`：面试历史。
- `/history/:interviewId`：面试回放。
- `/report`：我的报告列表。
- `/report/:interviewId`：报告详情。
- `/jobs`：岗位库。
- `/practice`：题库练习准备。
- `/practice/:practiceId`：题库练习会话。
- `/practice/:practiceId/records`：单场题库练习记录。
- `/coding-practice`：编程练习题目列表。
- `/coding-practice/:sessionId`：编程练习会话。

管理员页面：

- `/admin/imports`：知识库重建。
- `/admin/questions`：题库管理。

## 18. 典型使用流程

### 18.1 新用户完成一次 AI 面试

1. 注册账号并登录。
2. 上传个人简历。
3. 在岗位库中选择或新增目标 JD。
4. 进入 AI 面试页。
5. 选择简历、岗位或 JD、难度、输入/输出模式、问题类型。
6. 创建面试会话。
7. 逐轮回答 AI 问题。
8. 根据需要暂停或继续。
9. 结束面试。
10. 查看生成中的报告。
11. 报告完成后查看总分、维度评分、证据、建议和风险清单。

### 18.2 用户预约未来面试

1. 上传或选择简历。
2. 进入面试预约页。
3. 设置预约时间、时长、岗位、难度、输入/输出模式。
4. 创建预约。
5. 下载 `.ics` 或跳转 Google/Outlook Calendar。
6. 到时间后从首页通知、预约列表或面试大厅开始预约面试。

### 18.3 用户做专项练习

1. 进入题库练习。
2. 选择岗位域、模式、题量和类别。
3. 创建练习。
4. 按题提交答案。
5. 完成后查看练习记录和单场明细。

### 18.4 用户做编程练习

1. 进入编程练习列表。
2. 选择题目。
3. 在浏览器内选择 C++、Java 或 JavaScript。
4. 编写代码。
5. 运行自测。
6. 提交正式判题。
7. 查看编译错误、运行错误、超时、错误答案或通过结果。

### 18.5 管理员更新题库和知识库

1. 登录管理员账号。
2. 进入题库管理，上传 Markdown 或录入单题。
3. 查看导入任务状态。
4. 如需更新知识库，进入知识库重建页。
5. 选择全量或增量、岗位域、模型配置。
6. 触发导入任务并查看进度。
7. 通过报告文件检查构建结果。

## 19. 运行与集成说明

推荐在 Windows 上使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-windows.ps1
```

推荐在 macOS/Linux 上使用：

```bash
bash scripts/start-unix.sh
```

默认地址：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:18500`
- 后端 Swagger：`http://localhost:18500/docs`

如果单独启动旧后端脚本，后端默认可能运行在 `8000`。此时前端启动前需要显式设置：

```powershell
$env:VITE_API_BASE="http://localhost:8000/api/v1"
npm run dev
```

否则前端会继续请求默认的 `http://localhost:18500/api/v1`，浏览器侧可能出现 `Network Error`。

## 20. 技术栈概览

前端：

- React 18。
- Vite。
- TypeScript。
- Ant Design。
- React Router。
- TanStack Query。
- Zustand。
- Monaco Editor。
- Playwright 与 Vitest。

后端：

- Python 3.11+。
- FastAPI。
- Uvicorn。
- Pydantic。
- SQLite。
- Chroma 数据目录。
- LangGraph。
- OpenAI 兼容接口。
- Ollama。
- FunASR。
- PaddleSpeech。

本地编程判题依赖：

- Node.js。
- `g++`。
- `javac` / `java`。

## 21. 当前边界与注意事项

- 首页部分 KPI 和最近记录存在演示数据，真实报告和历史列表以对应接口为准。
- 前端 API 地址依赖 `VITE_API_BASE`，前后端分开启动时需要确认端口一致。
- 完整本地语音能力依赖 FunASR、PaddleSpeech 或 OpenAI 兼容服务配置；未配置时可用 mock/模板模式完成主流程。
- 编程练习判题在本地临时目录执行代码，适合本地教学和演示；如果面向公网用户，需要额外引入更严格的沙箱隔离。
- 知识库全量重建会调用多段数据处理脚本，运行时间和本地模型/嵌入服务状态相关。
- 报告生成有 LLM 与规则回退两条路径，真实评估质量取决于面试轮次数、简历/JD 信息完整度以及 provider 配置。

