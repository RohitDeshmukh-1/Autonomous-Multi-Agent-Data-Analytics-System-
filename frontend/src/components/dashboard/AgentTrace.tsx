import { useMemo } from 'react'
import { CheckCircle, XCircle, Loader2, Clock } from 'lucide-react'
import clsx from 'clsx'
import type { TraceEvent } from '@/api'

interface Props {
  events: TraceEvent[]
  isLive?: boolean
}

const NODE_LABELS: Record<string, string> = {
  intent_router: 'Intent Router',
  memory_retriever: 'Memory Retrieval',
  query_planner: 'Query Planner',
  sql_generator: 'SQL Generator',
  pandas_generator: 'Pandas Generator',
  safety_validator: 'Safety Check',
  executor: 'Executor',
  error_classifier: 'Error Classifier',
  self_corrector: 'Self Corrector',
  insight_synthesizer: 'Insight Synthesis',
  anomaly_detector: 'Anomaly Detection',
  visualizer: 'Visualizer',
  memory_updater: 'Memory Update',
}

const NODE_COLORS: Record<string, string> = {
  intent_router: 'from-violet-500 to-purple-600',
  memory_retriever: 'from-blue-500 to-cyan-500',
  query_planner: 'from-cyan-500 to-teal-500',
  sql_generator: 'from-teal-500 to-emerald-500',
  pandas_generator: 'from-emerald-500 to-green-500',
  safety_validator: 'from-amber-500 to-orange-500',
  executor: 'from-orange-500 to-red-500',
  error_classifier: 'from-red-500 to-rose-500',
  self_corrector: 'from-rose-500 to-pink-500',
  insight_synthesizer: 'from-pink-500 to-fuchsia-500',
  anomaly_detector: 'from-fuchsia-500 to-purple-500',
  visualizer: 'from-purple-500 to-indigo-500',
  memory_updater: 'from-indigo-500 to-blue-500',
}

export default function AgentTrace({ events, isLive }: Props) {
  const nodes = useMemo(() => {
    const nodeMap = new Map<string, { status: string; latency_ms: number; tokens: number }>()
    for (const e of events) {
      if (e.type !== 'trace') continue
      const prev = nodeMap.get(e.node)
      if (!prev || e.status === 'completed' || e.status === 'failed') {
        nodeMap.set(e.node, {
          status: e.status,
          latency_ms: e.latency_ms || prev?.latency_ms || 0,
          tokens: e.tokens_used || prev?.tokens || 0,
        })
      }
    }
    return nodeMap
  }, [events])

  const totalMs = useMemo(
    () => Array.from(nodes.values()).reduce((sum, n) => sum + n.latency_ms, 0),
    [nodes]
  )

  if (nodes.size === 0) return null

  return (
    <div className="card p-3 space-y-2">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Agent Pipeline {isLive && <Loader2 size={10} className="inline ml-1 animate-spin text-brand-400" />}
        </span>
        <span className="flex items-center gap-1 text-xs text-gray-500">
          <Clock size={10} /> {totalMs}ms total
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {Array.from(nodes.entries()).map(([node, info]) => {
          const label = NODE_LABELS[node] || node
          const gradient = NODE_COLORS[node] || 'from-gray-500 to-gray-600'

          return (
            <div
              key={node}
              className={clsx(
                'group relative flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-default',
                info.status === 'completed' && 'bg-gray-800/80 text-gray-200',
                info.status === 'started' && 'bg-gray-800/80 text-brand-400 animate-pulse',
                info.status === 'failed' && 'bg-red-900/30 text-red-300',
              )}
            >
              {/* Gradient accent bar */}
              <div className={clsx('w-1 h-4 rounded-full bg-gradient-to-b', gradient)} />

              {info.status === 'completed' && <CheckCircle size={11} className="text-emerald-400" />}
              {info.status === 'started' && <Loader2 size={11} className="animate-spin" />}
              {info.status === 'failed' && <XCircle size={11} className="text-red-400" />}

              <span>{label}</span>

              {info.latency_ms > 0 && (
                <span className="text-gray-500 ml-0.5">{info.latency_ms}ms</span>
              )}

              {/* Hover tooltip */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-50">
                <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-xl whitespace-nowrap">
                  <p className="font-semibold text-gray-100">{label}</p>
                  <p className="text-gray-400">Status: {info.status}</p>
                  {info.latency_ms > 0 && <p className="text-gray-400">Latency: {info.latency_ms}ms</p>}
                  {info.tokens > 0 && <p className="text-gray-400">Tokens: {info.tokens}</p>}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
