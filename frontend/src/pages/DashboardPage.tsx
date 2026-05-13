import { useState, useEffect } from 'react'
import { Trash2, BarChart2 } from 'lucide-react'
import { getPanels, deletePanel } from '@/api'
import type { Panel } from '@/api'
import { getUserId } from '@/session'
import ChartPanel from '@/components/dashboard/ChartPanel'

export default function DashboardPage() {
  const [panels, setPanels] = useState<Panel[]>([])
  const [loading, setLoading] = useState(true)
  const userId = getUserId()

  useEffect(() => {
    getPanels(userId)
      .then(setPanels)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [userId])

  async function handleDelete(panelId: string) {
    await deletePanel(panelId, userId)
    setPanels((p) => p.filter((x) => x.id !== panelId))
  }

  return (
    <div className="flex flex-col h-full">
      <header className="px-5 py-3 border-b border-gray-800 bg-gray-900 flex-shrink-0">
        <h1 className="text-sm font-semibold text-gray-100">Dashboard</h1>
        <p className="text-xs text-gray-500 mt-0.5">Pinned charts from your sessions</p>
      </header>

      <div className="flex-1 overflow-y-auto p-5">
        {loading && (
          <div className="flex items-center justify-center h-40">
            <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!loading && panels.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <BarChart2 size={40} className="text-gray-700 mb-4" />
            <p className="text-gray-400 font-medium">No pinned charts yet</p>
            <p className="text-gray-600 text-sm mt-1">
              Ask a question in Chat, then click <strong>Pin</strong> on a chart.
            </p>
          </div>
        )}

        {!loading && panels.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {panels.map((panel) => (
              <div key={panel.id} className="card p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-medium text-gray-200 leading-snug">{panel.title}</h3>
                    <p className="text-xs text-gray-500 mt-0.5">{panel.query.slice(0, 80)}</p>
                  </div>
                  <button
                    onClick={() => handleDelete(panel.id)}
                    className="text-gray-600 hover:text-red-400 transition-colors ml-2 flex-shrink-0"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                <ChartPanel spec={panel.chart_spec} />
                <p className="text-xs text-gray-600 mt-2">
                  {new Date(panel.created_at).toLocaleDateString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
