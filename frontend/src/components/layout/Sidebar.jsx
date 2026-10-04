import { NavLink } from 'react-router-dom'
import { BookOpen, ClipboardList, Cog, Factory, History, LayoutDashboard, PlusCircle, X } from 'lucide-react'
import { cn } from '@/utils/cn'

export const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/equipment', label: 'Equipment', icon: Factory },
  { to: '/report', label: 'Report Issue', icon: PlusCircle },
  { to: '/work-orders', label: 'Work Orders', icon: ClipboardList },
  { to: '/issues', label: 'Issue History', icon: History },
  { to: '/knowledge', label: 'Knowledge Base', icon: BookOpen },
  { to: '/settings', label: 'Settings', icon: Cog },
]

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex size-8 items-center justify-center rounded-lg bg-brand-600 text-white">
        <svg viewBox="0 0 32 32" className="size-5" aria-hidden="true">
          <path d="M8 22V10l8 7 8-7v12" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="leading-tight">
        <p className="text-sm font-semibold text-slate-900">MaintainIQ</p>
        <p className="text-[11px] text-slate-500">Maintenance triage</p>
      </div>
    </div>
  )
}

export function Sidebar({ open, onClose, pendingCount = 0 }) {
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-slate-900/30 lg:hidden" onClick={onClose} aria-hidden="true" />}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
        aria-label="Main navigation"
      >
        <div className="flex h-16 items-center justify-between border-b border-slate-100 px-5">
          <Logo />
          <button className="rounded-md p-1 text-slate-400 hover:bg-slate-100 lg:hidden" onClick={onClose} aria-label="Close navigation">
            <X className="size-5" />
          </button>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto p-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
                )
              }
            >
              <Icon className="size-4" aria-hidden="true" />
              <span className="flex-1">{label}</span>
              {to === '/work-orders' && pendingCount > 0 && (
                <span className="rounded-full bg-amber-100 px-1.5 text-xs font-semibold text-amber-800">{pendingCount}</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-100 p-4 text-[11px] leading-relaxed text-slate-500">
          AI output is advisory. Technicians review and approve every work order.
        </div>
      </aside>
    </>
  )
}
