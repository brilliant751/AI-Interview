# 在线编程练习模块 PRD

## 背景

当前仓库已经具备：

- 面向问答型题库练习的 `/practice` 领域；
- 基于 SQLite 的用户隔离、练习记录和异步导入基础设施；
- React + FastAPI 的完整前后端链路；
- 可重复执行的数据导入脚本模式。

当前缺口是“在线编程练习”能力：用户无法在 Web 页面内浏览算法题、编写代码、运行自测、提交判题，也无法跨语言保存每道题的代码草稿与提交记录。

## 目标

- 提供独立的“编程练习”入口和题目列表页；
- 持久化一套中文编程题库，并通过可重复执行的脚本导入数据库；
- 提供 Web 代码编辑器，支持 `C++11(g++)`、`Java(JDK21 语法级别)`、`JavaScript(ES6/7)`；
- 支持运行自测与正式提交；
- 保存用户每道题、每种语言的代码草稿与最近执行结果；
- 支持中途退出后恢复进度。

## 非目标

- 本期不做多人协作、排行榜、题解社区；
- 本期不做沙箱容器编排，只使用当前单机进程隔离方案；
- 本期不做复杂作弊检测；
- 本期不做 Python、Go、Rust 等额外语言；
- 本期不接第三方 OJ。

## 用户故事

### 普通用户

- 进入“编程练习”后浏览题目列表；
- 选择题目进入练习页；
- 切换语言并查看对应 starter code；
- 编辑代码时自动保存；
- 点击“运行自测”查看 stdout / stderr / 耗时；
- 点击“提交判题”跑至少 10 个正式测试用例；
- 查看历史提交结果、当前完成状态和上次更新时间。

### 管理/维护侧

- 通过仓库内固定材料文件维护编程题；
- 通过脚本幂等导入数据库；
- 能够重复导入、失败重试和查看报告。

## 核心设计

### 1. 新增独立 `coding_practice` 业务域

不复用现有 `/practice` 单选题练习模型，原因：

- 编程题需要题面、输入输出说明、样例、测试用例、starter code、运行结果和判题状态；
- 单选题的“顺序推进 + 一次性提交答案”模型无法承载多语言草稿与重复运行；
- 独立域更容易控制回归范围。

### 2. 题库事实源采用仓库材料文件

新增材料文件：

- `backend/assets/material/coding/programming_practice_questions.json`

要求：

- 题干必须中文；
- 每题至少 10 个正式测试用例；
- 每题至少 1 个自测用例；
- 包含 C++ / Java / JavaScript starter code。

### 3. 判题执行采用本地受限子进程

后端通过临时目录 + 超时 + 输出长度限制执行：

- `g++ -std=c++11`
- `javac --release 21` + `java`
- `node`

约束：

- 单次编译/执行超时；
- 单次输出长度上限；
- 每次运行使用独立工作目录；
- Java 固定入口类 `Main`。

## 数据模型

### `coding_questions`

- `question_id`
- `slug`
- `title`
- `difficulty`
- `topic_tags`
- `source`
- `prompt_markdown`
- `input_spec`
- `output_spec`
- `constraints_text`
- `sample_cases`
- `judge_cases`
- `self_test_case`
- `starter_codes`
- `created_at`
- `updated_at`

### `coding_sessions`

- `session_id`
- `user_id`
- `question_id`
- `status`：`ACTIVE | SOLVED`
- `last_language`
- `last_opened_at`
- `created_at`
- `updated_at`

### `coding_drafts`

- `draft_id`
- `session_id`
- `user_id`
- `language`
- `source_code`
- `last_run_status`
- `last_submit_status`
- `last_result_payload`
- `updated_at`

### `coding_submissions`

- `submission_id`
- `session_id`
- `user_id`
- `question_id`
- `language`
- `source_code`
- `submit_type`：`RUN | SUBMIT`
- `status`：`PENDING | ACCEPTED | WRONG_ANSWER | COMPILE_ERROR | RUNTIME_ERROR | TIME_LIMIT_EXCEEDED`
- `passed_count`
- `total_count`
- `result_payload`
- `created_at`

## API 草案

- `GET /api/v1/coding-practice/questions`
- `GET /api/v1/coding-practice/questions/{question_id}`
- `POST /api/v1/coding-practice/questions/import`
- `GET /api/v1/coding-practice/records`
- `POST /api/v1/coding-practice/sessions`
- `GET /api/v1/coding-practice/sessions/{session_id}`
- `PUT /api/v1/coding-practice/sessions/{session_id}/draft`
- `POST /api/v1/coding-practice/sessions/{session_id}/run`
- `POST /api/v1/coding-practice/sessions/{session_id}/submit`

## 前端信息架构

- 导航新增：`编程练习`
- 页面：
  - `CodingPracticeListPage`
  - `CodingPracticeSessionPage`

列表页展示：

- 题目标题、难度、标签；
- 最近进度、最近语言、是否已通过；
- “开始练习 / 继续练习”入口。

作答页布局：

- 左侧题面与样例；
- 右侧语言切换 + Monaco Editor；
- 底部运行结果与判题结果；
- 自动保存状态提示。

## 验收标准

- 用户可从网页进入“编程练习”并看到题目列表；
- 导入脚本可将题库材料幂等写入数据库；
- 任一题目可选择 `C++ / Java / JavaScript` 编写代码；
- “运行自测”能返回执行结果；
- “提交判题”至少运行 10 个正式测试用例；
- 草稿自动保存，中途退出后重新进入仍能恢复；
- 每道题的最近代码与最近结果持久化；
- OpenAPI / Postman / README 同步更新。

## 风险与约束

- 当前机器安装的是 `javac 25` / `java 25`，实现上应使用 `--release 21` 保持 JDK21 语法级别兼容；
- 本地子进程执行不是强隔离沙箱，需通过超时、输出长度和工作目录限制降低风险；
- Monaco 需要 Vite worker 配置，否则生产构建会失败。

## DoD

- 功能可用；
- 数据导入脚本可重复执行；
- 关键后端/前端路径有自动化测试；
- 接口文档同步；
- 现有 `/practice` 和 `/interview` 链路无回归。
