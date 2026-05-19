import { useState, useCallback } from 'react'
import { Upload, CheckCircle, XCircle, Database, Shield, Key, Globe, Layers } from 'lucide-react'
import { uploadFile, setConnectorId, connectDatabase } from '@/api'
import clsx from 'clsx'

type Status = 'idle' | 'uploading' | 'success' | 'error'

export default function UploadPage() {
  const [activeTab, setActiveTab] = useState<'file' | 'database'>('file')
  const [status, setStatus] = useState<Status>('idle')
  const [connectorId, setLocalConnectorId] = useState('')
  const [tablesIngested, setTablesIngested] = useState(0)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  // Database Connection States
  const [dbUrl, setDbUrl] = useState('')
  const [schemaName, setSchemaName] = useState('public')

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

  async function handleConnectDb(e: React.FormEvent) {
    e.preventDefault()
    if (!dbUrl.trim()) return
    setStatus('uploading')
    setError('')
    try {
      const result = await connectDatabase(dbUrl, schemaName)
      setLocalConnectorId(result.connector_id)
      setTablesIngested(result.tables_ingested)
      setConnectorId(result.connector_id) // persist to session
      setStatus('success')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Database connection failed')
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

  function resetState() {
    setStatus('idle')
    setError('')
    setLocalConnectorId('')
    setTablesIngested(0)
  }

  return (
    <div className="flex flex-col h-full bg-[#09090b]">
      <header className="px-5 py-3 border-b border-neutral-900 bg-[#09090b] flex-shrink-0 flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-neutral-100">Ingest Data</h1>
          <p className="text-xs text-neutral-500 mt-0.5">Upload local analytical files or securely connect cloud relational databases</p>
        </div>
      </header>

      {/* Tabs Selector */}
      <div className="px-5 pt-3 border-b border-neutral-900 bg-[#09090b]/50 flex gap-4">
        <button
          onClick={() => { setActiveTab('file'); resetState(); }}
          className={clsx(
            'pb-2.5 text-xs font-medium border-b-2 transition-colors',
            activeTab === 'file' ? 'border-neutral-200 text-neutral-100' : 'border-transparent text-neutral-500 hover:text-neutral-300'
          )}
        >
          Upload Local Files
        </button>
        <button
          onClick={() => { setActiveTab('database'); resetState(); }}
          className={clsx(
            'pb-2.5 text-xs font-medium border-b-2 transition-colors',
            activeTab === 'database' ? 'border-neutral-200 text-neutral-100' : 'border-transparent text-neutral-500 hover:text-neutral-300'
          )}
        >
          Connect Cloud Database
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6 max-w-2xl mx-auto w-full">
        {status === 'success' ? (
          <div className="card p-8 text-center flex flex-col items-center gap-3 bg-[#0e0e11] border border-neutral-800 rounded-xl">
            <CheckCircle size={32} className="text-neutral-200" />
            <p className="text-neutral-100 font-medium text-base">Connection Successful!</p>
            <p className="text-neutral-400 text-xs">{tablesIngested} table{tablesIngested !== 1 ? 's' : ''} successfully indexed into semantic memory.</p>
            
            <div className="mt-4 bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2.5 flex items-center gap-2 max-w-md w-full">
              <Database size={13} className="text-neutral-400 flex-shrink-0" />
              <code className="text-xs text-neutral-300 font-mono truncate flex-1 text-left">{connectorId}</code>
            </div>
            
            <div className="flex items-center gap-2 mt-2 bg-neutral-950/60 border border-neutral-900 px-3 py-1.5 rounded-lg text-[10px] text-neutral-500 max-w-md leading-relaxed">
              <Shield size={12} className="text-neutral-600 flex-shrink-0" />
              <span>Tokenized connection string stored securely in local browser session state.</span>
            </div>
            
            <button onClick={resetState} className="btn-secondary text-xs mt-4">Connect Another Source</button>
          </div>
        ) : status === 'error' ? (
          <div className="card p-8 text-center flex flex-col items-center gap-3 bg-[#0e0e11] border border-neutral-800 rounded-xl">
            <XCircle size={32} className="text-neutral-400" />
            <p className="text-neutral-100 font-medium text-base">Connection Failed</p>
            <div className="bg-red-950/10 border border-red-900/30 rounded-lg p-3 text-left max-w-md w-full">
              <p className="text-xs text-red-400 font-mono leading-relaxed break-words">{error}</p>
            </div>
            <button onClick={resetState} className="btn-secondary text-xs mt-4">Try Again</button>
          </div>
        ) : activeTab === 'file' ? (
          <div className="space-y-6">
            {/* File drop zone */}
            <label
              onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={clsx(
                'block w-full border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all',
                dragging ? 'border-neutral-200 bg-neutral-900/50' : 'border-neutral-800 hover:border-neutral-700 bg-[#0e0e11]',
                status === 'uploading' && 'pointer-events-none opacity-70'
              )}
            >
              <input type="file" accept=".csv,.sqlite,.db" onChange={onInputChange} className="hidden" />

              {status === 'uploading' && (
                <div className="flex flex-col items-center gap-3">
                  <div className="w-10 h-10 border-2 border-neutral-200 border-t-transparent rounded-full animate-spin" />
                  <p className="text-neutral-400 text-sm">Uploading and indexing schema…</p>
                </div>
              )}

              {status === 'idle' && (
                <div className="flex flex-col items-center gap-3">
                  <Upload size={32} className="text-neutral-600" />
                  <p className="text-neutral-300 font-medium">Drop a file here or click to browse</p>
                  <p className="text-neutral-500 text-sm font-mono">.csv · .sqlite · .db</p>
                </div>
              )}
            </label>

            {/* Info cards */}
            <div className="grid grid-cols-2 gap-4">
              {[
                { title: 'CSV ingestion', desc: 'CSVs are imported into a sandbox-safe, fast in-memory SQLite runtime.' },
                { title: 'SQLite support', desc: 'Direct, zero-setup profiling of complete SQLite relational databases.' },
              ].map(({ title, desc }) => (
                <div key={title} className="card p-4">
                  <h3 className="text-xs font-semibold text-neutral-200 mb-1">{title}</h3>
                  <p className="text-[11px] text-neutral-500 leading-relaxed">{desc}</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <form onSubmit={handleConnectDb} className="card p-6 bg-[#0e0e11] border border-neutral-800 rounded-xl space-y-4">
              <div className="flex items-center gap-3 pb-3 border-b border-neutral-900">
                <Database size={18} className="text-neutral-400" />
                <div>
                  <h2 className="text-sm font-semibold text-neutral-200">Connect PostgreSQL Server</h2>
                  <p className="text-[11px] text-neutral-500">Links any AWS, GCP, Azure, Railway, or on-premise instance</p>
                </div>
              </div>

              {/* URL Input */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-neutral-400 flex items-center justify-between">
                  <span>CONNECTION STRING (URI)</span>
                  <span className="text-[10px] text-neutral-600 font-mono">postgresql://</span>
                </label>
                <input
                  type="password"
                  value={dbUrl}
                  onChange={(e) => setDbUrl(e.target.value)}
                  placeholder="postgresql://user:password@host:5432/database?sslmode=require"
                  required
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-xs text-neutral-200 outline-none focus:border-neutral-700 transition-colors placeholder-neutral-700 font-mono"
                />
              </div>

              {/* Schema Name */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-neutral-400">SCHEMA NAME</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={schemaName}
                    onChange={(e) => setSchemaName(e.target.value)}
                    placeholder="public"
                    required
                    className="w-40 bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-xs text-neutral-200 outline-none focus:border-neutral-700 transition-colors font-mono"
                  />
                  <div className="flex-1 bg-neutral-950/40 border border-neutral-900 rounded-lg px-3 py-2 text-[10px] text-neutral-500 flex items-center gap-2">
                    <Layers size={12} className="text-neutral-600" />
                    <span>Schema tables are dynamically resolved on the fly.</span>
                  </div>
                </div>
              </div>

              {/* Security Shield Callout */}
              <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-3 flex gap-3">
                <Shield size={16} className="text-neutral-400 flex-shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <h4 className="text-[11px] font-semibold text-neutral-300">How Connection Security is Guaranteed</h4>
                  <p className="text-[10px] text-neutral-500 leading-relaxed">
                    <strong>Symmetric Encryption:</strong> Connection parameters are encrypted in the backend using a server-side symmetric key prior to transmission. Plaintext keys are never stored, logged, or exposed.
                  </p>
                  <p className="text-[10px] text-neutral-500 leading-relaxed">
                    <strong>Isolated Read-Only Access:</strong> The agent automatically enforces read-only session variables (`readonly=True`) for custom database connections. This isolates different client sessions and shields your system from any write or alteration commands.
                  </p>
                </div>
              </div>

              <button
                type="submit"
                disabled={status === 'uploading' || !dbUrl.trim()}
                className="w-full btn-primary py-2 text-xs flex items-center justify-center gap-2"
              >
                {status === 'uploading' ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-neutral-950 border-t-transparent rounded-full animate-spin" />
                    Validating Credentials & Ingesting Schema...
                  </>
                ) : (
                  <>
                    <Key size={12} />
                    Securely Link & Query Database
                  </>
                )}
              </button>
            </form>

            <div className="grid grid-cols-3 gap-4 text-center">
              {[
                { label: 'Public Network', val: 'Ensure the database permits connections from outside networks.' },
                { label: 'ReadOnly User', val: 'Recommended: use a Postgres user that has SELECT-only grants.' },
                { label: 'SSL Mode Active', val: 'Enforced automatically: append ?sslmode=require if needed.' },
              ].map(({ label, val }) => (
                <div key={label} className="p-3 bg-neutral-950/40 border border-neutral-900 rounded-lg">
                  <h4 className="text-[10px] font-semibold text-neutral-400 mb-1">{label}</h4>
                  <p className="text-[9px] text-neutral-600 leading-relaxed">{val}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
