import { useState, useCallback } from 'react'
import { Upload, CheckCircle, XCircle, Database } from 'lucide-react'
import { uploadFile, setConnectorId } from '@/api'
import clsx from 'clsx'

type Status = 'idle' | 'uploading' | 'success' | 'error'

export default function UploadPage() {
  const [status, setStatus] = useState<Status>('idle')
  const [connectorId, setLocalConnectorId] = useState('')
  const [tablesIngested, setTablesIngested] = useState(0)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  async function handleFile(file: File) {
    setStatus('uploading')
    setError('')
    try {
      const result = await uploadFile(file)
      setLocalConnectorId(result.connector_id)
      setTablesIngested(result.tables_ingested)
      setConnectorId(result.connector_id) // persist to session
      setStatus('success')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed')
      setStatus('error')
    }
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }, [])

  return (
    <div className="flex flex-col h-full">
      <header className="px-5 py-3 border-b border-gray-800 bg-gray-900 flex-shrink-0">
        <h1 className="text-sm font-semibold text-gray-100">Upload Data</h1>
        <p className="text-xs text-gray-500 mt-0.5">Supports CSV and SQLite files up to 50 MB</p>
      </header>

      <div className="flex-1 overflow-y-auto p-5 max-w-2xl mx-auto w-full">
        {/* Drop zone */}
        <label
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={clsx(
            'block w-full border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all',
            dragging ? 'border-brand-500 bg-brand-600/10' : 'border-gray-700 hover:border-gray-500 bg-gray-900',
            status === 'uploading' && 'pointer-events-none opacity-70'
          )}
        >
          <input type="file" accept=".csv,.sqlite,.db" onChange={onInputChange} className="hidden" />

          {status === 'uploading' && (
            <div className="flex flex-col items-center gap-3">
              <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-gray-400 text-sm">Uploading and indexing schema…</p>
            </div>
          )}

          {status === 'idle' && (
            <div className="flex flex-col items-center gap-3">
              <Upload size={36} className="text-gray-600" />
              <p className="text-gray-300 font-medium">Drop a file here or click to browse</p>
              <p className="text-gray-500 text-sm">.csv · .sqlite · .db</p>
            </div>
          )}

          {status === 'success' && (
            <div className="flex flex-col items-center gap-3">
              <CheckCircle size={36} className="text-emerald-400" />
              <p className="text-gray-200 font-medium">Upload successful!</p>
              <p className="text-gray-400 text-sm">{tablesIngested} table{tablesIngested !== 1 ? 's' : ''} indexed</p>
              <div className="mt-2 bg-gray-800 rounded-lg px-4 py-2 flex items-center gap-2">
                <Database size={14} className="text-brand-400" />
                <code className="text-xs text-brand-300 font-mono">{connectorId}</code>
              </div>
              <p className="text-xs text-gray-500 mt-1">Connector ID saved — now go to Chat to query your data</p>
            </div>
          )}

          {status === 'error' && (
            <div className="flex flex-col items-center gap-3">
              <XCircle size={36} className="text-red-400" />
              <p className="text-gray-200 font-medium">Upload failed</p>
              <p className="text-red-400 text-sm">{error}</p>
              <button onClick={() => setStatus('idle')} className="btn-ghost text-sm mt-1">Try again</button>
            </div>
          )}
        </label>

        {/* Info cards */}
        <div className="grid grid-cols-2 gap-4 mt-6">
          {[
            { title: 'CSV files', desc: 'Your CSV is loaded into in-memory SQLite and queried with SQL.' },
            { title: 'SQLite files', desc: 'All tables in your .db file are available for querying immediately.' },
          ].map(({ title, desc }) => (
            <div key={title} className="card p-4">
              <h3 className="text-sm font-semibold text-gray-200 mb-1">{title}</h3>
              <p className="text-xs text-gray-500">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
