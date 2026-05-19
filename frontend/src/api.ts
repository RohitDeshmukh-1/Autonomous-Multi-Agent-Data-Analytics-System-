const BASE = import.meta.env.VITE_API_BASE_URL || ''

export interface QueryRequest {
  user_query: string
  connector_id: string
  session_id: string
  user_id?: string
}

export interface TraceEvent {
  type: 'trace'
  node: string
  status: 'started' | 'completed' | 'failed'
  latency_ms: number
  tokens_used: number
  metadata: Record<string, unknown>
}

export interface QueryResponse {
  session_id: string
  intent: string
  generated_code: string
  code_type: string
  execution_result: Record<string, unknown>[]
  insight_text: string
  chart_spec: ChartSpec | null
  from_cache: boolean
  latency_ms: number
  correction_attempts: number
  history_id: string | null
  anomalies: string[]
  trace: TraceEvent[]
  query_plan?: { tables?: string[]; approach?: string; complexity?: string }
  trace_summary?: {
    total_latency_ms: number
    total_tokens: number
    nodes_executed: number
    events: TraceEvent[]
  }
}

export interface ChartSpec {
  type: string
  plotly_json?: { data: unknown[]; layout: unknown }
  data?: Record<string, unknown>[]
  columns?: string[]
}

export interface HistoryRecord {
  id: string
  session_id: string
  user_query: string
  code_type: string
  insight_text: string | null
  latency_ms: number | null
  retry_count: number | null
  created_at: string
}

export interface Panel {
  id: string
  user_id: string
  session_id: string
  dashboard_id: string | null
  title: string
  chart_spec: ChartSpec
  query: string
  created_at: string
}

export interface MetricsData {
  uptime_seconds: number
  total_queries: number
  latency: { p50_ms: number; p95_ms: number; p99_ms: number; avg_ms: number }
  cache: { hits: number; misses: number; hit_ratio: number }
  self_correction: { avg_retries: number; queries_needing_correction: number; correction_rate: number }
  tokens: { total: number; avg_per_query: number }
  intents: Record<string, number>
  errors: Record<string, number>
}

export interface ProfileData {
  connector_id: string
  total_tables: number
  total_columns: number
  tables: {
    name: string
    row_count: number
    column_count: number
    columns: {
      name: string
      type: string
      null_count: number
      null_rate: number
      unique_count: number
      cardinality: string
      inferred_type?: string
      stats?: { count: number; mean: number; median: number; min: number; max: number; std: number }
      histogram?: { range: string; count: number }[]
      top_values?: { value: string; count: number; frequency: number }[]
    }[]
    correlations: { column_a: string; column_b: string; correlation: number; strength: string }[]
  }[]
}

// ── Query ──────────────────────────────────────────────────────────────────────

export async function runQuery(req: QueryRequest): Promise<QueryResponse> {
  const res = await fetch(`${BASE}/api/query/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`Query failed: ${await res.text()}`)
  return res.json()
}

export type StreamEvent = { token?: string; type?: string } & Partial<QueryResponse> & { done?: boolean }

export async function* streamQuery(req: QueryRequest): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}/api/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`Stream failed: ${await res.text()}`)
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { yield JSON.parse(line.slice(6)) } catch { /* ignore */ }
      }
    }
  }
}

// ── History ────────────────────────────────────────────────────────────────────

export async function getHistory(sessionId: string): Promise<HistoryRecord[]> {
  const res = await fetch(`${BASE}/api/history/${sessionId}`)
  if (!res.ok) throw new Error('History fetch failed')
  return res.json()
}

export async function deleteHistoryRecord(id: string): Promise<void> {
  await fetch(`${BASE}/api/history/${id}`, { method: 'DELETE' })
}

// ── Upload ─────────────────────────────────────────────────────────────────────

export { setConnectorId } from '@/session'

export async function uploadFile(file: File, userId = 'anonymous'): Promise<{ connector_id: string; tables_ingested: number }> {
  const form = new FormData()
  form.append('file', file)
  form.append('user_id', userId)
  const res = await fetch(`${BASE}/api/upload/file`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(`Upload failed: ${await res.text()}`)
  return res.json()
}

export async function connectDatabase(url: string, schemaName = 'public'): Promise<{ connector_id: string; tables_ingested: number }> {
  const res = await fetch(`${BASE}/api/upload/connect-db`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, schema_name: schemaName }),
  })
  if (!res.ok) {
    let errMsg = 'Connection failed'
    try {
      const data = await res.json()
      errMsg = data.detail || errMsg
    } catch {
      errMsg = await res.text() || errMsg
    }
    throw new Error(errMsg)
  }
  return res.json()
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export async function getPanels(userId: string): Promise<Panel[]> {
  const res = await fetch(`${BASE}/api/dashboard/panel/${userId}`)
  if (!res.ok) throw new Error('Panels fetch failed')
  return res.json()
}

export async function savePanel(panel: Omit<Panel, 'id' | 'created_at'>): Promise<string> {
  const res = await fetch(`${BASE}/api/dashboard/panel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(panel),
  })
  if (!res.ok) throw new Error('Save panel failed')
  const d = await res.json()
  return d.panel_id
}

export async function deletePanel(panelId: string, userId: string): Promise<void> {
  await fetch(`${BASE}/api/dashboard/panel/${panelId}?user_id=${userId}`, { method: 'DELETE' })
}

// ── Report ────────────────────────────────────────────────────────────────────

export async function downloadReport(sessionId: string, userId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/report/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, user_id: userId }),
  })
  if (!res.ok) throw new Error('Report generation failed')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `report-${sessionId.slice(0, 8)}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export async function getMetrics(): Promise<MetricsData> {
  const res = await fetch(`${BASE}/api/metrics/`)
  if (!res.ok) throw new Error('Metrics fetch failed')
  return res.json()
}

// ── Profile ───────────────────────────────────────────────────────────────────

export async function getProfile(connectorId: string): Promise<ProfileData> {
  const res = await fetch(`${BASE}/api/profile/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ connector_id: connectorId }),
  })
  if (!res.ok) throw new Error('Profile failed')
  return res.json()
}
