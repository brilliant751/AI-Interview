# 测试策略说明

本文档说明 AI-Interview 当前测试体系的覆盖范围、测试分层和新增测试时的注意事项。

## 1. 测试目标

测试的主要目标不是追求形式上的覆盖率，而是保护关键业务流程：

- 用户能注册、登录、刷新 token、退出登录。
- 用户只能访问自己的简历、JD、面试、练习记录。
- 面试状态机不能非法跳转。
- 面试轮次提交能异步处理。
- LLM/TTS/ASR 失败时有可理解的降级。
- 报告在 LLM 不可用时仍能生成规则回退结果。
- 题库练习不能重复提交同一题。
- 编程练习不能访问他人的 session。
- 数据脚本能稳定处理材料文件。
- 前端 API helper 不能悄悄改错路径或参数名。

## 2. 后端测试分层

后端测试分为三类：

### 2.1 纯单元测试

纯单元测试不启动 FastAPI，不访问真实数据库，不依赖外部模型。

适合测试：

- 状态机规则。
- 字符串清理。
- JSON 解码。
- 报告规则评分。
- prompt 辅助函数。
- hash embedding。

优点：

- 执行快。
- 定位准。
- 不受环境依赖影响。

新增位置示例：

- `tests/backend/test_interview_state_rules.py`
- `tests/backend/test_report_service_rules.py`
- `tests/backend/test_question_workflow_units.py`
- `tests/backend/test_repository_json_decoders.py`
- `tests/backend/test_embedding_utils.py`

### 2.2 服务层测试

服务层测试可以使用临时仓储或 stub 对象，验证业务规则。

适合测试：

- AuthService 登录限流。
- PracticeService 顺序答题。
- CodingPracticeService session 权限。
- InterviewScheduleService 时间判断。
- ReportService fallback 报告。

服务层测试应避免真实 OpenAI、Ollama、FunASR、PaddleSpeech 调用。

### 2.3 集成测试

集成测试使用 FastAPI `TestClient`，覆盖 HTTP 路由、Pydantic 模型、服务层和 SQLite。

适合测试：

- 认证主流程。
- 面试主流程。
- 预约主流程。
- 题库练习流程。
- 编程练习流程。
- 管理端导入接口。

集成测试必须使用临时数据库。不要使用开发数据库路径。

## 3. 后端测试隔离

`tests/backend/conftest.py` 默认做了以下隔离：

- 设置 `AI_INTERVIEW_APP_ENV=dev`。
- 设置 LLM/ASR/TTS provider 为 `mock`。
- 将数据库路径指向 `tmp_path/test.db`。
- 将 Chroma 目录指向临时目录。
- 打开 dev static token 兼容模式。
- 每个测试前后清理 settings 缓存。

这意味着大多数后端测试不需要手动配置 provider。

如果测试要覆盖正式 JWT 流程，可以在测试内关闭：

```python
os.environ["AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN"] = "false"
get_settings.cache_clear()
```

## 4. 前端测试分层

前端测试分为：

### 4.1 纯工具测试

适合测试：

- 日期格式化。
- 日历网格。
- store 状态更新。
- API helper 参数序列化。

这类测试不渲染页面，运行稳定。

### 4.2 组件测试

适合测试：

- ProviderHealthBanner。
- AppLayout。
- 表单页面。
- 练习准备页。
- 预约页。

组件测试通常需要：

- `MemoryRouter`
- `QueryClientProvider`
- API mock
- Zustand store 初始化

### 4.3 页面行为测试

页面行为测试关注用户路径：

- 登录成功跳转。
- 忘记密码提交邮箱。
- 重置密码读取 URL token。
- 创建练习后跳转。
- 创建预约后刷新列表。
- 开始预约后写入面试 store。

页面测试不应该访问真实后端。

## 5. React Query 测试注意事项

React Query 测试建议创建独立 QueryClient：

```tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
})
```

原因：

- 避免失败请求自动重试导致测试变慢。
- 避免测试之间共享缓存。
- 让断言时序更可控。

## 6. Zustand 测试注意事项

测试 store 前应重置状态：

```ts
useInterviewStore.getState().reset()
usePracticeStore.getState().reset()
useCodingPracticeStore.getState().reset()
useAuthStore.getState().clearSession()
```

认证 store 还应清理 localStorage：

```ts
window.localStorage.clear()
```

## 7. API Helper 测试注意事项

API helper 测试可以 spy `apiClient.get/post/delete`：

```ts
const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: {} })
```

重点断言：

- URL 是否正确。
- params 是否正确。
- payload 是否正确。
- FormData 字段是否正确。
- responseType 是否正确。
- timeout 是否正确。

不建议在 API helper 测试中启动真实服务。

## 8. Provider 测试注意事项

Provider 测试不要调用真实模型。

推荐做法：

- mock `httpx.Client.post`
- mock SDK 初始化方法。
- mock SDK 推理结果。
- 验证异常是否转换成 `ApiError`。

要覆盖：

- 成功路径。
- 超时路径。
- 返回空结果。
- SDK 初始化失败。
- 健康检查失败。

## 9. 数据脚本测试注意事项

数据脚本测试要使用临时目录。

推荐测试点：

- Markdown 解析。
- JSONL 写入。
- dry-run 不写真实数据库。
- upsert 幂等。
- 报告文件结构。
- hash fallback。

不要让测试覆盖真实 `data/` 输出。

## 10. 不推荐的测试方式

以下方式风险较高：

- 测试中访问真实 OpenAI/Ollama 服务。
- 测试中依赖本机已经安装 g++、javac、node。
- 测试中写入真实开发数据库。
- 测试中依赖当前日期而不固定时间。
- 测试中共享全局 QueryClient。
- 测试中不清理 localStorage。
- 测试中依赖执行顺序。

## 11. 建议新增测试清单

后续如果继续补测试，可以优先补：

- ReportPage 的 `GENERATING/FAILED/READY` 三种状态。
- JobManagePage 的 JD 创建和删除。
- ResumeManagePage 的上传和预览。
- InterviewPage 的轮次 job 轮询。
- InterviewSchedulePage 的 missed/ready 状态展示。
- MaterialImportService 的 idempotency 行为。
- InterviewRepository 的预约查询和历史查询。
- AuthService 的 refresh token 替换链。

## 12. 提交前检查

提交前建议执行：

```bash
python -m py_compile $(find backend/app scripts/data data/scripts tests/backend -name '*.py')
git diff --check
```

如果前端依赖已安装，再执行：

```bash
cd frontend
npm run build
npm run test
```

如果后端依赖完整，再执行：

```bash
pytest tests/backend
```

