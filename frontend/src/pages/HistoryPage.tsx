import { useState, useEffect } from 'react'
import { Clock, Trash2, Code2 } from 'lucide-react'
import { getHistory, deleteHistoryRecord } from '@/api'
import type { HistoryRecord } from '@/api'
import { getSessionId } from '@/session'
import clsx from 'clsx'

export default function HistoryPage() {
  const [records, setRecords] = useState<HistoryRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    getHistory(getSessionId())
      .then(setRecords)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  async function handleDelete(id: string) {
    await deleteHistoryRecord(id)
    setRecords((r) => r.filter((x) => x.id !== id))
  }

  return (
    <div className="flex flex-col h-full">
      <header className="px-5 py-3 border-b border-gray-800 bg-gray-900 flex-shrink-0">
        <h1 className="text-sm font-semibold text-gray-100">Query History</h1>
        <p className="text-xs text-gray-500 mt-0.5">Current session · {records.length} queries</p>
      </header>

      <div className="flex-1 overflow-y-auto p-5 space-y-2">
        {loading && (
          <div className="flex items-center justify-center h-40">
            <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!loading && records.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <Clock size={40} className="text-gray-700 mb-4" />
            <p className="text-gray-400 font-medium">No history yet</p>
            <p className="text-gray-600 text-sm mt-1">Queries will appear here after you run them.</p>
          </div>
        )}

        {records.map((rec) => (
          <div key={rec.id} className="card overflow-hidden">
            <button
              onClick={() => setExpanded((v) => (v === rec.id ? null : rec.id))}
              className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-gray-800/40 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-200 truncate">{rec.user_query}</p>
                <div className="flex items-center gap-3 mt-1">
                  <span className={clsx('badge', rec.code_type === 'sql' ? 'badge-sql' : 'badge-pandas')}>
                    {rec.code_type}
                  </span>
                  {rec.latency_ms && (
                    <span className="text-xs text-gray-500 flex items-center gap-1">
                      <Clock size={10} /> {rec.latency_ms}ms
                    </span>
                  )}
                  <span className="text-xs text-gray-600">{rec.created_at}</span>
                </div>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); handleDelete(rec.id) }}
                className="text-gray-700 hover:text-red-400 transition-colors flex-shrink-0 mt-0.5"
              >
                <Trash2 size={14} />
              </button>
            </button>

            {expanded === rec.id && rec.insight_text && (
              <div className="px-4 pb-4 border-t border-gray-800">
                <p className="text-sm text-gray-300 mt-3 leading-relaxed">{rec.insight_text}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
