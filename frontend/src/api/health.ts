// 后端健康检查的前端调用。dev 下经 vite proxy：/api/health → 后端 /health。

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

export interface HealthResponse {
  status: string
  db: string
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) {
    throw new Error(`health check failed: HTTP ${res.status}`)
  }
  return (await res.json()) as HealthResponse
}
