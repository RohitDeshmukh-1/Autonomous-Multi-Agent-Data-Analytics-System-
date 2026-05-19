import { useState } from 'react'
import { Database, BarChart2, AlertTriangle, Search } from 'lucide-react'
import { getProfile } from '@/api'
import type { ProfileData } from '@/api'
import { getConnectorId } from '@/session'
import clsx from 'clsx'

export default function ProfilePage() {
  const [loading, setLoading] = useState(false)
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [error, setError] = useState('')
  const [connector, setConnector] = useState(getConnectorId())

  async function runProfile() {
    setLoading(true)
    setError('')
    try {
      const data = await getProfile(connector)
      setProfile(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Profile failed')
    }
    setLoading(false)
  }

  return (
    <div className="flex flex-col h-full">
      <header className="px-5 py-3 border-b border-neutral-900 bg-[#09090b] flex-shrink-0">
        <h1 className="text-sm font-semibold text-neutral-100">Data Profiler</h1>
        <p className="text-xs text-neutral-500 mt-0.5">One-click dataset analysis with type inference, distributions, and correlations</p>
      </header>

      <div className="flex-1 overflow-y-auto p-5">
        {/* Profile trigger */}
        <div className="max-w-3xl mx-auto">
          <div className="card p-6 text-center mb-6">
            <Database size={28} className="text-neutral-400 mx-auto mb-3" />
            <h2 className="text-lg font-semibold text-neutral-200 mb-2">Profile Your Dataset</h2>
            <p className="text-xs text-neutral-500 mb-4">
              Analyze column types, missing values, distributions, and correlations.
            </p>

            <div className="flex items-center gap-3 max-w-md mx-auto">
              <input
                value={connector}
                onChange={(e) => setConnector(e.target.value)}
                placeholder="neon:public"
                className="flex-1 bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 outline-none focus:border-neutral-700"
              />
              <button
                onClick={runProfile}
                disabled={loading}
                className="btn-primary"
              >
                {loading ? <div className="w-4 h-4 border-2 border-neutral-950 border-t-transparent rounded-full animate-spin" /> : <Search size={14} />}
                Profile
              </button>
            </div>
            {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
          </div>

          {/* Profile results */}
          {profile && (
            <div className="space-y-6">
              {/* Overview */}
              <div className="grid grid-cols-3 gap-4">
                <div className="card p-4 text-center">
                  <p className="text-2xl font-bold text-gray-100">{profile.total_tables}</p>
                  <p className="text-xs text-gray-500">Tables</p>
                </div>
                <div className="card p-4 text-center">
                  <p className="text-2xl font-bold text-gray-100">{profile.total_columns}</p>
                  <p className="text-xs text-gray-500">Columns</p>
                </div>
                <div className="card p-4 text-center">
                  <p className="text-2xl font-bold text-gray-100">
                    {profile.tables.reduce((sum, t) => sum + (t.row_count || 0), 0).toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500">Total Rows</p>
                </div>
              </div>

              {/* Per-table profiles */}
              {profile.tables.map((table) => (
                <div key={table.name} className="card p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Database size={13} className="text-neutral-400" />
                      <h3 className="text-sm font-semibold text-neutral-200">{table.name}</h3>
                    </div>
                    <span className="text-xs text-neutral-500">
                      {table.row_count?.toLocaleString()} rows · {table.column_count} columns
                    </span>
                  </div>

                  {/* Column profiles */}
                  <div className="overflow-auto">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className="text-neutral-500">
                          <th className="px-3 py-2 text-left bg-[#0e0e11]">Column</th>
                          <th className="px-3 py-2 text-left bg-[#0e0e11]">Type</th>
                          <th className="px-3 py-2 text-left bg-[#0e0e11]">Nulls</th>
                          <th className="px-3 py-2 text-left bg-[#0e0e11]">Unique</th>
                          <th className="px-3 py-2 text-left bg-[#0e0e11]">Stats / Top Values</th>
                        </tr>
                      </thead>
                      <tbody>
                        {table.columns.map((col) => (
                          <tr key={col.name} className="border-t border-neutral-900">
                            <td className="px-3 py-2 text-neutral-200 font-mono">{col.name}</td>
                            <td className="px-3 py-2">
                              <span className="badge badge-sql">
                                {col.inferred_type || col.type}
                              </span>
                            </td>
                            <td className="px-3 py-2">
                              <span className={clsx(
                                'text-neutral-300',
                                col.null_rate > 0.3 && 'text-amber-400 font-semibold'
                              )}>
                                {(col.null_rate * 100).toFixed(1)}%
                              </span>
                            </td>
                            <td className="px-3 py-2 text-neutral-300 font-mono">
                              {col.unique_count}
                              <span className="text-neutral-600 ml-1">({col.cardinality})</span>
                            </td>
                            <td className="px-3 py-2 text-neutral-400">
                              {col.stats ? (
                                <span className="font-mono text-[11px]">
                                  μ={col.stats.mean} · σ={col.stats.std} · [{col.stats.min}, {col.stats.max}]
                                </span>
                              ) : col.top_values ? (
                                <div className="flex gap-1 flex-wrap">
                                  {col.top_values.slice(0, 3).map((tv) => (
                                    <span key={tv.value} className="badge badge-pandas">
                                      {tv.value.slice(0, 20)} ({tv.count})
                                    </span>
                                  ))}
                                </div>
                              ) : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Correlations */}
                  {table.correlations.length > 0 && (
                    <div className="border-t border-neutral-900 pt-3">
                      <h4 className="text-xs font-semibold text-neutral-400 mb-2 flex items-center gap-1">
                        <BarChart2 size={12} /> Correlations
                      </h4>
                      <div className="flex gap-2 flex-wrap">
                        {table.correlations.map((c, i) => (
                          <div key={i} className="badge badge-pandas">
                            {c.column_a} ↔ {c.column_b}: {c.correlation.toFixed(3)}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
