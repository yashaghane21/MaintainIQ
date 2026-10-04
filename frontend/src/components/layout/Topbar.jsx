import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Bell, ChevronRight, Menu, Search, UserCircle2 } from 'lucide-react'
import { useReviewer } from '@/context/ReviewerContext'
import { useIssues, useWorkOrders } from '@/hooks/useApi'
import { timeAgo } from '@/utils/format'
import { NAV_ITEMS } from './Sidebar'

const SEGMENT_LABELS = Object.fromEntries(NAV_ITEMS.map((n) => [n.to.replace('/', ''), n.label]))

function Breadcrumbs() {
  const { pathname } = useLocation()
  const parts = pathname.split('/').filter(Boolean)
  const crumbs = [{ to: '/', label: 'Overview' }]
  parts.forEach((part, i) => {
    crumbs.push({ to: '/' + parts.slice(0, i + 1).join('/'), label: SEGMENT_LABELS[part] || decodeURIComponent(part) })
  })
  return (
    <nav aria-label="Breadcrumb" className="hidden min-w-0 items-center gap-1 text-sm md:flex">
      {crumbs.map((c, i) => (
        <span key={c.to} className="flex min-w-0 items-center gap-1">
          {i > 0 && <ChevronRight className="size-3.5 shrink-0 text-slate-300" aria-hidden="true" />}
          {i === crumbs.length - 1 ? (
            <span className="truncate font-medium text-slate-900" aria-current="page">{c.label}</span>
          ) : (
            <Link to={c.to} className="truncate text-slate-500 hover:text-slate-900">{c.label}</Link>
          )}
        </span>
      ))}
    </nav>
  )
}

function Notifications() {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const pending = useWorkOrders({ status: 'pending_review' })
  const failed = useIssues({ status: 'analysis_failed', limit: 5 })
  const items = [
    ...(failed.data || []).map((i) => ({ key: i.issue_id, to: `/issues/${i.issue_id}`, title: `Analysis failed: ${i.issue_id}`, sub: i.equipment_name, at: i.updated_at })),
    ...(pending.data || []).map((w) => ({ key: w.work_order_id, to: `/work-orders/${w.work_order_id}`, title: `Review needed: ${w.work_order_id}`, sub: w.title, at: w.created_at })),
  ]

  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button
        className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
        onClick={() => setOpen((o) => !o)}
        aria-label={`Notifications (${items.length})`}
        aria-expanded={open}
      >
        <Bell className="size-5" />
        {items.length > 0 && <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-red-500" />}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-slate-200 bg-white shadow-lg">
          <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Notifications</div>
          <ul className="max-h-80 overflow-y-auto py-1">
            {items.length === 0 && <li className="px-4 py-6 text-center text-sm text-slate-500">You're all caught up.</li>}
            {items.map((item) => (
              <li key={item.key}>
                <Link to={item.to} onClick={() => setOpen(false)} className="block px-4 py-2.5 hover:bg-slate-50">
                  <p className="text-sm font-medium text-slate-900">{item.title}</p>
                  <p className="truncate text-xs text-slate-500">{item.sub} · {timeAgo(item.at)}</p>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function Topbar({ onMenu }) {
  const navigate = useNavigate()
  const { reviewer } = useReviewer()
  const [query, setQuery] = useState('')

  const submit = (e) => {
    e.preventDefault()
    if (query.trim()) navigate(`/issues?search=${encodeURIComponent(query.trim())}`)
  }

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6">
      <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden" onClick={onMenu} aria-label="Open navigation">
        <Menu className="size-5" />
      </button>
      <Breadcrumbs />
      <div className="ml-auto flex items-center gap-2">
        <form onSubmit={submit} role="search" className="relative hidden sm:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search issues…"
            aria-label="Search issues"
            className="h-9 w-56 rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-sm focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-100 lg:w-72"
          />
        </form>
        <Notifications />
        <Link to="/settings" className="flex items-center gap-2 rounded-lg p-1.5 pr-2 hover:bg-slate-100" title="Reviewer profile (demo)">
          <UserCircle2 className="size-6 text-slate-400" aria-hidden="true" />
          <span className="hidden text-sm font-medium text-slate-700 md:inline">{reviewer}</span>
        </Link>
      </div>
    </header>
  )
}
