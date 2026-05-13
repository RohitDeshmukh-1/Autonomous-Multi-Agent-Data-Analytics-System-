import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, RefreshCw, FileDown } from 'lucide-react'
import { v4 as uuidv4 } from 'uuid'
import { streamQuery, savePanel, downloadReport } from '@/api'
import type { QueryResponse, TraceEvent } from '@/api'
import { getSessionId, newSession, getUserId, getConnectorId } from '@/session'
import ChatMessage from '@/components/dashboard/ChatMessage'
import AgentTrace from '@/components/dashboard/AgentTrace'
import ConnectorSelector from '@/components/ui/ConnectorSelector'

interface Message {
  id: string
  query: string
  response: QueryResponse
  traceEvents: TraceEvent[]
}

const SUGGESTIONS = [
  'What are the top 5 products by total revenue?',
  'Show monthly order volume for the past year',
  'Which region has the highest average order value?',
  'List customers with more than 5 orders',
]

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [liveTrace, setLiveTrace] = useState<TraceEvent[]>([])
  const [sessionId, setSessionId] = useState(getSessionId)
  const [connector, setConnector] = useState(getConnectorId)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamText, liveTrace])

  const submit = useCallback(async (query: string) => {
    if (!query.trim() || loading) return
    setInput('')
    setLoading(true)
    setStreamText('')
    setLiveTrace([])

    const userId = getUserId()
    let finalResponse: QueryResponse | null = null
    let accText = ''
    const traceEvents: TraceEvent[] = []

    try {
      for await (const event of streamQuery({ user_query: query, connector_id: connector, session_id: sessionId, user_id: userId })) {
        if (event.type === 'trace') {
          const te = event as unknown as TraceEvent
          traceEvents.push(te)
          setLiveTrace([...traceEvents])
        } else if (event.done) {
          finalResponse = event as unknown as QueryResponse
          finalResponse.insight_text = accText
          // Merge trace events
          if (event.trace_summary?.events) {
            traceEvents.push(...(event.trace_summary.events as TraceEvent[]))
          }
        } else if (event.token) {
          accText += event.token
          setStreamText(accText)
        }
      }
    } catch (err) {
      console.error(err)
      finalResponse = {
        session_id: sessionId, intent: 'sql', generated_code: '', code_type: 'sql',
        execution_result: [], insight_text: 'An error occurred. Please try again.',
        chart_spec: null, from_cache: false, latency_ms: 0, correction_attempts: 0,
        history_id: null, anomalies: [], trace: [],
      }
    }

    if (finalResponse) {
      setMessages((m) => [...m, {
        id: uuidv4(),
        query,
        response: finalResponse!,
        traceEvents,
      }])
    }
    setStreamText('')
    setLiveTrace([])
    setLoading(false)
  }, [loading, connector, sessionId])

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(input) }
  }

  function handleNewSession() {
    setSessionId(newSession())
    setMessages([])
  }

  async function handlePin(resp: QueryResponse, query: string) {
    if (!resp.chart_spec) return
    try {
      await savePanel({
        user_id: getUserId(), session_id: sessionId,
        title: query.slice(0, 60), chart_spec: resp.chart_spec,
        query, dashboard_id: null,
      })
      alert('Chart pinned to dashboard!')
    } catch { alert('Failed to pin chart') }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="flex items-center justify-between px-5 py-3 border-b border-gray-800 bg-gray-900 flex-shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold text-gray-100">Chat</h1>
          <ConnectorSelector onChange={setConnector} />
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleNewSession} className="btn-ghost text-xs">
            <RefreshCw size={13} /> New Session
          </button>
          <button
            onClick={() => downloadReport(sessionId, getUserId())}
            disabled={messages.length === 0}
            className="btn-ghost text-xs"
          >
            <FileDown size={13} /> Export PDF
          </button>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-6 space-y-6">
        {messages.length === 0 && !loading && (
          <div className="max-w-xl mx-auto mt-12">
            <h2 className="text-xl font-semibold text-gray-200 text-center mb-2">Ask anything about your data</h2>
            <p className="text-sm text-gray-500 text-center mb-8">Connected to: <span className="text-brand-400">{connector}</span></p>
            <div className="grid grid-cols-1 gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => submit(s)}
                  className="text-left px-4 py-3 card hover:border-brand-600/50 hover:bg-gray-800/50 text-sm text-gray-400 hover:text-gray-200 transition-all"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            query={msg.query}
            response={msg.response}
            traceEvents={msg.traceEvents}
            onPin={handlePin}
          />
        ))}

        {loading && (
          <div className="space-y-3">
            {/* Live trace while processing */}
            {liveTrace.length > 0 && (
              <AgentTrace events={liveTrace} isLive />
            )}

            <ChatMessage
              query={input || '…'}
              response={{
                session_id: sessionId, intent: '', generated_code: '', code_type: 'sql',
                execution_result: [], insight_text: '', chart_spec: null, from_cache: false,
                latency_ms: 0, correction_attempts: 0, history_id: null, anomalies: [], trace: [],
              }}
              streamingText={streamText}
              isStreaming
            />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="flex-shrink-0 px-5 py-4 border-t border-gray-800 bg-gray-900">
        <div className="flex items-end gap-3 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 focus-within:border-brand-500 transition-colors">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your data…"
            className="flex-1 bg-transparent text-sm text-gray-100 placeholder-gray-500 resize-none outline-none max-h-32"
          />
          <button
            onClick={() => submit(input)}
            disabled={!input.trim() || loading}
            className="flex-shrink-0 w-8 h-8 bg-brand-600 hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg flex items-center justify-center transition-colors"
          >
            {loading
              ? <RefreshCw size={14} className="text-white animate-spin" />
              : <Send size={14} className="text-white" />}
          </button>
        </div>
        <p className="text-xs text-gray-600 mt-2 text-center">Press Enter to send · Shift+Enter for new line · Follow-up queries supported</p>
      </div>
    </div>
  )
}
