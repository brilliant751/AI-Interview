import { apiClient } from './client'

// 管理端 API 契约：
// 1. 知识库/题库材料导入是异步任务，触发后通过 task_id 查询进度。
// 2. idempotencyKey 由页面按按钮操作生成，避免管理员重复点击创建多份任务。
// 3. provider health 用于首页或管理页展示外部模型服务状态。
// 4. 管理端接口依赖后端管理员鉴权，前端这里只负责传递请求。

/** 导入触发请求。 */
export interface TriggerMaterialImportPayload {
  rebuild_mode: 'full' | 'incremental'
  roles: Array<'java' | 'web'>
  dry_run: boolean
  chunk_model: string
  embedding_model: string
}

/** 导入触发响应。 */
export interface TriggerMaterialImportResponse {
  task_id: string
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'PARTIAL_SUCCESS'
  stage: string
  progress: number
  idempotency_hit: boolean
}

/** 导入任务状态响应。 */
export interface ImportTaskResponse {
  task_id: string
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'PARTIAL_SUCCESS'
  stage: string
  progress: number
  rebuild_mode: 'full' | 'incremental'
  roles: Array<'java' | 'web'>
  dry_run: boolean
  last_error: string
  report_path: string
}

/** 触发材料导入任务。 */
export async function triggerMaterialImport(
  payload: TriggerMaterialImportPayload,
  idempotencyKey?: string,
): Promise<TriggerMaterialImportResponse> {
  // 当页面传入幂等键时覆盖默认请求头，确保同一次导入按钮操作可重复安全重试。
  const headers: Record<string, string> = {}
  if (idempotencyKey) {
    headers['X-Idempotency-Key'] = idempotencyKey
  }
  const { data } = await apiClient.post<TriggerMaterialImportResponse>('/admin/imports/materials', payload, {
    headers,
  })
  return data
}

/** 查询导入任务状态。 */
export async function getImportTask(taskId: string): Promise<ImportTaskResponse> {
  const { data } = await apiClient.get<ImportTaskResponse>(`/admin/imports/materials/${taskId}`)
  return data
}

/** Provider 健康项。 */
export interface ProviderHealthItem {
  status: 'UP' | 'DOWN' | 'DEGRADED'
  provider: string
  model: string
  latency_ms: number
  error_message: string
}

/** Provider 健康响应。 */
export interface ProviderHealthResponse {
  overall: 'UP' | 'DOWN' | 'DEGRADED'
  providers: Record<string, ProviderHealthItem>
}

/** 获取 provider 健康状态。 */
export async function fetchProviderHealth(): Promise<ProviderHealthResponse> {
  const { data } = await apiClient.get<ProviderHealthResponse>('/admin/providers/health')
  return data
}
