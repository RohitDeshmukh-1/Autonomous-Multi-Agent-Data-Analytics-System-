import { Outlet, NavLink } from 'react-router-dom'
import { BarChart2, MessageSquare, Clock, Upload, Database, Activity, Search } from 'lucide-react'
import clsx from 'clsx'

const nav = [
  { to: '/chat',      icon: MessageSquare, label: 'Chat' },
  { to: '/dashboard', icon: BarChart2,     label: 'Dashboard' },
  { to: '/profile',   icon: Search,        label: 'Data Profiler' },
  { to: '/history',   icon: Clock,         label: 'History' },
  { to: '/upload',    icon: Upload,        label: 'Upload Data' },
  { to: '/metrics',   icon: Activity,      label: 'Metrics' },
]

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-[#09090b] border-r border-neutral-900 flex flex-col">
        <div className="px-5 py-5 border-b border-neutral-900">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-neutral-100 rounded flex items-center justify-center">
              <Database size={13} className="text-neutral-950" />
            </div>
            <span className="font-semibold text-sm text-neutral-100 leading-tight">
              Data Analyst<br />
              <span className="text-neutral-500 font-normal">Agent</span>
            </span>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1.5">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 border',
                  isActive
                    ? 'bg-[#0f0f11] text-neutral-100 border-neutral-800'
                    : 'text-neutral-400 hover:text-neutral-100 hover:bg-[#0f0f11]/50 border-transparent hover:border-neutral-900'
                )
              }
            >
              <Icon size={15} className="flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-4 border-t border-neutral-900 text-[10px] font-mono tracking-tight text-neutral-600">
          v2.0.0 · Groq + Railway
        </div>

      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden flex flex-col">
        <Outlet />
      </main>
    </div>
  )
}
