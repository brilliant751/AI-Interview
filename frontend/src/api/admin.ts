import { apiClient } from './client'

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
