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
      <aside className="w-56 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-5 py-5 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-brand-600 rounded-lg flex items-center justify-center">
              <Database size={14} className="text-white" />
            </div>
            <span className="font-semibold text-sm text-gray-100 leading-tight">
              Data Analyst<br />
              <span className="text-gray-500 font-normal">Agent</span>
            </span>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-brand-600/20 text-brand-400'
                    : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-4 border-t border-gray-800 text-xs text-gray-600">
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
