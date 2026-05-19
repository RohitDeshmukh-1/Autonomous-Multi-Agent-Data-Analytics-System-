import { useState, useEffect } from 'react'
import { Activity, Zap, AlertTriangle, Clock, RefreshCw } from 'lucide-react'
import { getMetrics } from '@/api'
import type { MetricsData } from '@/api'

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<MetricsData | null>(null)
  const [loading, setLoading] = useState(true)

  async function refresh() {
    setLoading(true)
    try {
      const data = await getMetrics()
      setMetrics(data)
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  useEffect(() => { refresh() }, [])

  // Auto-refresh every 10s
  useEffect(() => {
    const interval = setInterval(refresh, 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between px-5 py-3 border-b border-neutral-900 bg-[#09090b] flex-shrink-0">
        <div>
          <h1 className="text-sm font-semibold text-neutral-100">System Metrics</h1>
          <p className="text-xs text-neutral-500 mt-0.5">Real-time observability dashboard</p>
        </div>
        <button onClick={refresh} className="btn-ghost text-xs">
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-5">
        {!metrics ? (
          <div className="flex items-center justify-center h-40">
            <div className="w-6 h-6 border-2 border-neutral-200 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="space-y-6 max-w-4xl mx-auto">
            {/* Top stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                label="Total Queries"
                value={metrics.total_queries.toString()}
                icon={<Activity size={18} className="text-brand-400" />}
              />
              <StatCard
                label="Avg Latency"
                value={`${metrics.latency.avg_ms}ms`}
                icon={<Clock size={18} className="text-cyan-400" />}
                sub={`p95: ${metrics.latency.p95_ms}ms · p99: ${metrics.latency.p99_ms}ms`}
              />
              <StatCard
                label="Cache Hit Rate"
                value={`${(metrics.cache.hit_ratio * 100).toFixed(1)}%`}
                icon={<Zap size={18} className="text-amber-400" />}
                sub={`${metrics.cache.hits} hits / ${metrics.cache.misses} misses`}
              />
              <StatCard
                label="Self-Correction Rate"
                value={`${(metrics.self_correction.correction_rate * 100).toFixed(1)}%`}
                icon={<AlertTriangle size={18} className="text-orange-400" />}
                sub={`${metrics.self_correction.queries_needing_correction} queries fixed`}
              />
            </div>

            {/* Intent breakdown */}
            <div className="card p-4">
              <h3 className="text-sm font-semibold text-gray-200 mb-3">Intent Distribution</h3>
              <div className="flex gap-3 flex-wrap">
                {Object.entries(metrics.intents).map(([intent, count]) => (
                  <div key={intent} className="flex items-center gap-2 bg-[#0e0e11] border border-neutral-800/80 rounded-lg px-3 py-1.5">
                    <span className={`badge ${intent === 'sql' ? 'badge-sql' : intent === 'pandas' ? 'badge-pandas' : 'bg-neutral-800 text-neutral-300 border-neutral-700'}`}>
                      {intent}
                    </span>
                    <span className="text-xs text-neutral-400 font-mono">{count}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Error breakdown */}
            {Object.keys(metrics.errors).length > 0 && (
              <div className="card p-4">
                <h3 className="text-sm font-semibold text-neutral-200 mb-3">Error Distribution</h3>
                <div className="space-y-2">
                  {Object.entries(metrics.errors).map(([err, count]) => (
                    <div key={err} className="flex items-center justify-between bg-[#0e0e11] border border-neutral-800/80 rounded-lg px-3 py-2">
                      <span className="text-sm text-red-300 font-mono text-[11px]">{err}</span>
                      <span className="text-xs text-neutral-400 font-mono">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Uptime */}
            <div className="text-xs text-gray-600 text-center">
              Uptime: {formatUptime(metrics.uptime_seconds)}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, icon, sub }: { label: string; value: string; icon: React.ReactNode; sub?: string }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500 font-medium">{label}</span>
        {icon}
      </div>
      <p className="text-2xl font-bold text-gray-100">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return `${h}h ${m}m ${s}s`
}
