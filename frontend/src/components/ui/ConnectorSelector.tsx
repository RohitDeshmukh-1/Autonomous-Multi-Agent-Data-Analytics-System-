import { useState, useEffect } from 'react'
import { Database, ChevronDown } from 'lucide-react'
import { getConnectorId, setConnectorId } from '@/session'

const PRESETS = [
  { label: 'Demo DB (Neon)', value: 'neon:public' },
]

interface Props {
  onChange?: (id: string) => void
}

export default function ConnectorSelector({ onChange }: Props) {
  const [value, setValue] = useState(getConnectorId)
  const [open, setOpen] = useState(false)
  const [custom, setCustom] = useState('')

  const options = [...PRESETS]

  function select(v: string) {
    setValue(v)
    setConnectorId(v)
    onChange?.(v)
    setOpen(false)
  }

  function applyCustom() {
    if (custom.trim()) select(custom.trim())
  }

  const label = PRESETS.find((p) => p.value === value)?.label ?? value

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-3 py-1.5 bg-[#0e0e11] border border-neutral-800 rounded-lg text-xs text-neutral-300 hover:bg-neutral-900 transition-colors"
      >
        <Database size={11} className="text-neutral-400" />
        <span className="max-w-48 truncate">{label}</span>
        <ChevronDown size={11} />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1.5 w-72 bg-[#0e0e11] border border-neutral-800 rounded-xl shadow-xl z-50 p-2">
          <p className="text-[10px] text-neutral-500 px-2 mb-1.5 font-semibold uppercase tracking-wide">Presets</p>
          {options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => select(opt.value)}
              className="w-full text-left px-3 py-2 text-sm text-neutral-300 hover:bg-neutral-900 rounded-lg transition-colors"
            >
              {opt.label}
            </button>
          ))}

          <div className="border-t border-neutral-900 mt-2 pt-2">
            <p className="text-[10px] text-neutral-500 px-2 mb-1.5 font-semibold uppercase tracking-wide">Custom connector ID</p>
            <div className="flex gap-2 px-2">
              <input
                value={custom}
                onChange={(e) => setCustom(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && applyCustom()}
                placeholder="csv:https://… or neon:myschema"
                className="flex-1 bg-neutral-950 border border-neutral-800 rounded px-2.5 py-1 text-xs text-neutral-200 placeholder-neutral-700 outline-none focus:border-neutral-700"
              />
              <button onClick={applyCustom} className="btn-primary text-xs px-2.5 py-1">Use</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
