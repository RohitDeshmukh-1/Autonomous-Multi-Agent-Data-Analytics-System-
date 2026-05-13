import { useMemo } from 'react'
import Plot from 'react-plotly.js'
import type { ChartSpec } from '@/api'

interface Props {
  spec: ChartSpec
  title?: string
}

export default function ChartPanel({ spec, title }: Props) {
  const darkLayout = useMemo(() => {
    const base = (spec.plotly_json?.layout ?? {}) as Record<string, unknown>
    return {
      ...base,
      title: title || base.title || '',
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#e2e8f0', family: 'Inter, sans-serif', size: 12 },
      xaxis: { ...((base.xaxis as object) ?? {}), gridcolor: '#374151', linecolor: '#374151', tickfont: { color: '#9ca3af' } },
      yaxis: { ...((base.yaxis as object) ?? {}), gridcolor: '#374151', linecolor: '#374151', tickfont: { color: '#9ca3af' } },
      margin: { l: 50, r: 20, t: 40, b: 50 },
      legend: { font: { color: '#9ca3af' } },
    }
  }, [spec, title])

  if (spec.type === 'table' && spec.data && spec.columns) {
    return (
      <div className="overflow-auto max-h-80">
        <table className="w-full text-xs text-gray-300 border-collapse">
          <thead>
            <tr>
              {spec.columns.map((col) => (
                <th key={col} className="px-3 py-2 text-left text-gray-400 font-semibold bg-gray-800 border-b border-gray-700 whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(spec.data as Record<string, unknown>[]).slice(0, 100).map((row, i) => (
              <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
                {(spec.columns ?? []).map((col) => (
                  <td key={col} className="px-3 py-1.5 whitespace-nowrap font-mono">
                    {String(row[col] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {(spec.data?.length ?? 0) > 100 && (
          <p className="text-xs text-gray-500 px-3 py-2">
            Showing 100 of {spec.data!.length} rows
          </p>
        )}
      </div>
    )
  }

  if (!spec.plotly_json) return null

  return (
    <Plot
      data={spec.plotly_json.data as Plotly.Data[]}
      layout={darkLayout as Partial<Plotly.Layout>}
      config={{ displayModeBar: true, responsive: true, displaylogo: false }}
      style={{ width: '100%', height: '320px' }}
      useResizeHandler
    />
  )
}
