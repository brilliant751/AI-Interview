# Agent1 需求与接口设计：面试创建必须绑定 JD（2026-05-20）

## 1. 需求摘要
将“创建面试会话”从“可选绑定 JD”改为“必须绑定 JD”，确保题目生成始终有明确岗位上下文。

## 2. 范围定义（In/Out）
- In Scope
  - 后端创建面试接口 `POST /api/v1/interviews`：`jd_id` 必填。
  - 前端创建面试入口（准备页与面试页）必须先选择 JD 才能提交。
  - 更新接口契约文档（OpenAPI/Postman）。
- Out of Scope
  - JD 上传、删除、列表逻辑。
  - 历史会话与回放结构。

## 3. 接口定义
- 接口：`POST /api/v1/interviews`
- 请求体变化：`jd_id` 由可选改为必填。
- 错误约束：
  - `JD_400_REQUIRED`：当服务层检测到空 `jd_id`（兜底校验）
  - `422`：请求体缺失 `jd_id`（模型校验）
  - 保留原有 `JD_404_NOT_FOUND` / `JD_403_FORBIDDEN` / `JD_409_ROLE_MISMATCH`

## 4. 数据模型草案
- `InterviewCreateRequest.jd_id`：`string`，必填，最小长度 1。

## 5. 前端交互与状态约束
- 创建面试表单必须包含 JD 选择项。
- 岗位方向变更时清空已选 JD，避免方向不匹配。
- 无 JD 时给出明确提示“请选择岗位 JD”。

## 6. 非功能需求
- 不增加额外网络写压力；JD 列表查询仅在创建弹窗打开时触发。
- 错误码与提示语保持中文一致性。

## 7. 验收标准（Given-When-Then）
- Given 用户未选择 JD，When 提交创建面试，Then 前端阻止提交并提示必须选择 JD。
- Given 请求缺少 `jd_id`，When 调用 `POST /interviews`，Then 返回 422。
- Given `jd_id` 为空字符串，When 调用创建，Then 返回 `JD_400_REQUIRED`。
- Given `jd_id` 有效且岗位匹配，When 创建面试，Then 返回 200 且会话绑定该 JD。

## 8. 风险与待确认项
- 风险：历史自动化测试用例大量依赖“无 jd_id 创建”，需要批量更新。
- 风险：前端有双入口创建面试，若只改一处会出现行为不一致。

## 9. 落盘信息
- `devdocs/agent1-interview-jd-required-prd-20260520.md`
