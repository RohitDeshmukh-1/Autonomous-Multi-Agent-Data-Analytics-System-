import { useState } from 'react'
import { ChevronDown, ChevronUp, Clock, Zap, Pin, AlertTriangle, Code, Activity } from 'lucide-react'
import clsx from 'clsx'
import ChartPanel from '@/components/dashboard/ChartPanel'
import AgentTrace from '@/components/dashboard/AgentTrace'
import type { QueryResponse, TraceEvent } from '@/api'

interface Props {
  query: string
  response: QueryResponse
  streamingText?: string
  isStreaming?: boolean
  onPin?: (resp: QueryResponse, query: string) => void
  traceEvents?: TraceEvent[]
}

export default function ChatMessage({ query, response, streamingText, isStreaming, onPin, traceEvents }: Props) {
  const [showCode, setShowCode] = useState(false)
  const [showTrace, setShowTrace] = useState(false)
  const [showExplain, setShowExplain] = useState(false)

  const displayText = isStreaming ? (streamingText ?? '') : response.insight_text
  const anomalies = (response as any).anomalies || []
  const trace = traceEvents || (response as any).trace || []
  const queryPlan = (response as any).query_plan || (response as any).trace_summary?.query_plan

  return (
    <div className="space-y-3">
      {/* User bubble */}
      <div className="flex justify-end">
        <div className="max-w-xl bg-brand-600/20 border border-brand-600/30 rounded-2xl rounded-tr-sm px-4 py-3 text-sm text-gray-100">
          {query}
        </div>
      </div>

      {/* Agent response */}
      <div className="flex gap-3">
        <div className="w-7 h-7 flex-shrink-0 bg-brand-600 rounded-full flex items-center justify-center text-xs font-bold text-white mt-1">
          AI
        </div>
        <div className="flex-1 space-y-3">
          {/* Insight text */}
          <div className="card px-4 py-3 text-sm text-gray-200 leading-relaxed">
            {displayText || (isStreaming ? <span className="animate-pulse text-gray-400">Thinking…</span> : '—')}
            {isStreaming && displayText && <span className="inline-block w-1 h-4 bg-brand-500 animate-pulse ml-0.5" />}
          </div>

          {/* Anomaly callouts */}
          {!isStreaming && anomalies.length > 0 && (
            <div className="card border-amber-800/50 bg-amber-950/20 px-4 py-3 space-y-2">
              <div className="flex items-center gap-2 text-amber-400 text-xs font-semibold">
                <AlertTriangle size={13} />
                Did you know?
              </div>
              {anomalies.map((a: string, i: number) => (
                <p key={i} className="text-sm text-amber-200/80 leading-relaxed"
                   dangerouslySetInnerHTML={{
                     __html: a.replace(/\*\*(.*?)\*\*/g, '<strong class="text-amber-300">$1</strong>')
                              .replace(/`(.*?)`/g, '<code class="text-amber-400 bg-amber-900/30 px-1 rounded">$1</code>')
                   }}
                />
              ))}
            </div>
          )}

          {/* Chart */}
          {!isStreaming && response.chart_spec && (
            <div className="card p-3">
              <ChartPanel spec={response.chart_spec} />
            </div>
          )}

          {/* Agent trace (collapsible) */}
          {!isStreaming && trace.length > 0 && showTrace && (
            <AgentTrace events={trace} />
          )}

          {/* Explainability panel */}
          {!isStreaming && showExplain && (
            <div className="card p-4 space-y-3">
              <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Query Explanation</h4>

              {queryPlan && (
                <div className="space-y-1">
                  <p className="text-xs text-gray-500">Approach</p>
                  <p className="text-sm text-gray-200">{queryPlan.approach || '—'}</p>
                  {queryPlan.tables && (
                    <div className="flex gap-1.5 mt-1">
                      {queryPlan.tables.map((t: string) => (
                        <span key={t} className="badge bg-gray-800 text-gray-300">{t}</span>
                      ))}
                    </div>
                  )}
                  {queryPlan.complexity && (
                    <span className={clsx(
                      'badge mt-1',
                      queryPlan.complexity === 'simple' && 'bg-emerald-900/40 text-emerald-300',
                      queryPlan.complexity === 'medium' && 'bg-amber-900/40 text-amber-300',
                      queryPlan.complexity === 'complex' && 'bg-red-900/40 text-red-300',
                    )}>
                      {queryPlan.complexity}
                    </span>
                  )}
                </div>
              )}

              {response.correction_attempts > 0 && (
                <div className="border-t border-gray-800 pt-2 space-y-1">
                  <p className="text-xs text-gray-500">Self-Correction</p>
                  <p className="text-sm text-orange-300">
                    The agent fixed its own code {response.correction_attempts} time{response.correction_attempts > 1 ? 's' : ''} before producing the correct result.
                  </p>
                </div>
              )}

              {response.execution_result && response.execution_result.length > 0 && (
                <div className="border-t border-gray-800 pt-2">
                  <p className="text-xs text-gray-500 mb-1">Raw Data Preview ({response.execution_result.length} rows)</p>
                  <div className="overflow-auto max-h-40">
                    <table className="w-full text-xs text-gray-300 border-collapse">
                      <thead>
                        <tr>
                          {Object.keys(response.execution_result[0]).map(col => (
                            <th key={col} className="px-2 py-1 text-left text-gray-500 bg-gray-800/50 border-b border-gray-800 whitespace-nowrap">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {response.execution_result.slice(0, 10).map((row, i) => (
                          <tr key={i} className="border-b border-gray-800/50">
                            {Object.values(row).map((val, j) => (
                              <td key={j} className="px-2 py-1 whitespace-nowrap font-mono">
                                {String(val ?? '')}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Footer row */}
          {!isStreaming && (
            <div className="flex items-center gap-2 px-1 flex-wrap">
              {/* Badges */}
              <span className={clsx('badge', response.code_type === 'sql' ? 'badge-sql' : 'badge-pandas')}>
                {response.code_type.toUpperCase()}
              </span>
              {response.from_cache && <span className="badge badge-cache"><Zap size={10} className="mr-1" />cached</span>}
              {response.correction_attempts > 0 && (
                <span className="badge bg-orange-900/40 text-orange-300">
                  {response.correction_attempts} fix{response.correction_attempts > 1 ? 'es' : ''}
                </span>
              )}

              <span className="flex items-center gap-1 text-xs text-gray-500 ml-auto">
                <Clock size={11} /> {response.latency_ms}ms
              </span>

              {/* Toggle buttons */}
              <button
                onClick={() => setShowTrace(v => !v)}
                className={clsx('btn-ghost text-xs py-1', showTrace && 'text-brand-400')}
              >
                <Activity size={12} /> Trace
              </button>

              <button
                onClick={() => setShowExplain(v => !v)}
                className={clsx('btn-ghost text-xs py-1', showExplain && 'text-brand-400')}
              >
                <AlertTriangle size={12} /> Explain
              </button>

              <button
                onClick={() => setShowCode((v) => !v)}
                className={clsx('btn-ghost text-xs py-1', showCode && 'text-brand-400')}
              >
                <Code size={12} />
                {showCode ? 'Hide' : 'Code'}
              </button>

              {/* Pin to dashboard */}
              {onPin && response.chart_spec && (
                <button onClick={() => onPin(response, query)} className="btn-ghost text-xs py-1">
                  <Pin size={12} /> Pin
                </button>
              )}
            </div>
          )}

          {/* Code block */}
          {showCode && response.generated_code && (
            <pre className="bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 text-xs font-mono text-green-300 overflow-auto max-h-64 whitespace-pre-wrap">
              {response.generated_code}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}
