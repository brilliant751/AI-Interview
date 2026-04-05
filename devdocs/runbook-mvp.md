# AI Interview MVP Runbook

## 1. 目标

本手册用于规范 MVP 环境的初始化、发布、回滚与故障排查流程，确保后端接口与数据管道可重复执行、可审计、可恢复。

## 2. 运行前检查

1. Python 版本：`>= 3.11`
2. 核心目录存在：
   - `assets/material/`
   - `assets/scripts/data/`
   - `backend/app/`
3. 环境变量准备（可选，未配置则使用默认值）：
   - `AI_INTERVIEW_DB_PATH`
   - `AI_INTERVIEW_CHROMA_DIR`
   - `AI_INTERVIEW_USER_TOKEN`
   - `AI_INTERVIEW_ADMIN_TOKEN`

## 3. 首次初始化

1. 执行数据门禁与构建：

```bash
python assets/scripts/data/validate_materials.py --strict
python assets/scripts/data/normalize_materials.py
python assets/scripts/data/build_question_bank.py
python assets/scripts/data/build_knowledge_vectorstore.py
```

2. 验证产物：
   - `assets/data/normalized/*.jsonl`
   - `assets/data/sqlite/interview.db`
   - `assets/data/chroma/kb_*/knowledge_index.jsonl`
   - `assets/data/reports/*.json`

## 4. 启动后端服务

```bash
PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 8000
```

健康检查建议：
1. 访问 `http://localhost:8000/docs` 确认 OpenAPI 正常
2. 使用 `postman/AI-Interview.postman_collection.json` 跑通最小流程：
   - 上传简历
   - 创建面试
   - 提交轮次
   - 结束面试
   - 查询报告

## 5. 发布流程（MVP）

1. 本地/CI 执行质量门禁：
- `python -m compileall backend/app assets/scripts/data tests/backend`
   - `python -m unittest discover -s tests/backend -p "test_*.py"`
2. 数据脚本 dry-run 必须通过：
   - `validate_materials --strict`
   - `normalize_materials --dry-run`
   - `build_question_bank --dry-run`
   - `build_knowledge_vectorstore --dry-run`
3. 合并发布后，按第 3 节执行一次正式数据构建。

## 6. 回滚策略

### 6.1 代码回滚

1. 回滚到上一个稳定版本代码。
2. 重启后端服务并验证 `/docs` 与核心接口。

### 6.2 数据回滚

1. 备份当前数据目录（推荐）：
   - `assets/data/sqlite/`
   - `assets/data/chroma/`
2. 恢复上一个稳定快照。
3. 若仅题库有问题，可重新执行：

```bash
python assets/scripts/data/normalize_materials.py
python assets/scripts/data/build_question_bank.py
```

4. 若知识索引有问题，可重新执行：

```bash
python assets/scripts/data/build_knowledge_vectorstore.py
```

## 7. 常见故障处理

1. `AUTH_401`：检查 `Authorization: Bearer <token>` 与环境变量令牌一致性。
2. `STATE_409`：检查会话阶段是否正确（例如已结束后仍提交轮次）。
3. 报告长期为 `GENERATING`：检查是否已调用结束接口，并查看 `interview_reports` 记录。
4. 索引为空：确认已先执行 `normalize_materials.py`，并检查 `assets/data/normalized/*_knowledge.jsonl` 是否存在。

## 8. 运维审计建议

1. 保留每次数据构建的 `assets/data/reports/*.json`。
2. 发布单记录以下信息：
   - 代码版本
   - 执行人
   - 执行时间
   - 构建命令与结果摘要
3. 生产故障修复后，补充一次复盘并更新本手册。
