import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowRight, Table2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/common/States'
import { EquipmentStatusBadge, IssueStatusBadge, PriorityBadge, WorkOrderStatusBadge } from '@/components/common/Badges'
import { humanize, timeAgo } from '@/utils/format'

// Validated two-slot categorical palette (blue, orange) and fixed status colours for ordinal priority.
const SERIES = { issues: '#2a78d6', decisions: '#eb6834' }
const PRIORITY_COLORS = { critical: '#d03b3b', high: '#ec835a', medium: '#fab219', low: '#94a3b8', unassessed: '#cbd5e1' }

export function KpiCard({ label, value, icon: Icon, hint, to, tone = 'blue' }) {
  const tones = { blue: 'bg-blue-50 text-blue-600', amber: 'bg-amber-50 text-amber-600', red: 'bg-red-50 text-red-600', slate: 'bg-slate-100 text-slate-600' }
  const body = (
    <Card className="h-full p-5 transition-colors hover:border-slate-300">
      <div className="flex items-start justify-between">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <span className={`rounded-lg p-2 ${tones[tone]}`}>
          <Icon className="size-4" aria-hidden="true" />
        </span>
      </div>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </Card>
  )
  return to ? <Link to={to} className="block">{body}</Link> : body
}

export function PriorityDistribution({ data }) {
  const rows = ['critical', 'high', 'medium', 'low', 'unassessed'].map((k) => ({ key: k, value: data[k] || 0 }))
  const max = Math.max(1, ...rows.map((r) => r.value))
  const total = rows.reduce((s, r) => s + r.value, 0)
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Open issues by priority</CardTitle>
          <CardDescription>{total} open issue{total === 1 ? '' : 's'}</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        {total === 0 ? (
          <EmptyState title="No open issues" description="Reported issues will appear here by priority." className="py-6" />
        ) : (
          <ul className="space-y-3">
            {rows.map((r) => (
              <li key={r.key} className="grid grid-cols-[88px_1fr_28px] items-center gap-3 text-sm">
                <span className="text-slate-600">{humanize(r.key)}</span>
                <div className="h-2.5 rounded-full bg-slate-100" title={`${humanize(r.key)}: ${r.value}`}>
                  <div className="h-2.5 rounded-full" style={{ width: `${(r.value / max) * 100}%`, background: PRIORITY_COLORS[r.key] }} />
                </div>
                <span className="text-right font-medium tabular-nums text-slate-900">{r.value}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function ActivityTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-slate-900">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2 text-slate-600">
          <span className="size-2 rounded-sm" style={{ background: p.color }} /> {p.name}: <span className="font-medium text-slate-900">{p.value}</span>
        </p>
      ))}
    </div>
  )
}

export function ActivityChart({ data }) {
  const [asTable, setAsTable] = useState(false)
  const rows = data.map((d) => ({ ...d, label: new Date(d.date + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) }))
  const empty = rows.every((r) => !r.issues_reported && !r.work_orders_decided)
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Maintenance activity</CardTitle>
          <CardDescription>Issues reported and work orders decided, last 14 days</CardDescription>
        </div>
        <button onClick={() => setAsTable((t) => !t)} className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100" aria-pressed={asTable}>
          <Table2 className="size-3.5" /> {asTable ? 'Chart' : 'Table'}
        </button>
      </CardHeader>
      <CardContent>
        {empty ? (
          <EmptyState title="No activity yet" description="Activity appears once issues are reported or work orders reviewed." className="py-8" />
        ) : asTable ? (
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500">
                <tr><th className="py-1 font-medium">Date</th><th className="py-1 text-right font-medium">Issues reported</th><th className="py-1 text-right font-medium">Work orders decided</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r) => (
                  <tr key={r.date}><td className="py-1.5">{r.label}</td><td className="text-right tabular-nums">{r.issues_reported}</td><td className="text-right tabular-nums">{r.work_orders_decided}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="h-64" role="img" aria-label="Bar chart of issues reported and work orders decided per day">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} barGap={2} margin={{ top: 8, right: 4, left: -24, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#64748b' }} interval="preserveStartEnd" minTickGap={16} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                <Tooltip content={<ActivityTooltip />} cursor={{ fill: '#f1f5f9' }} />
                <Legend iconType="square" iconSize={8} wrapperStyle={{ fontSize: 12 }} formatter={(value) => <span style={{ color: '#475569' }}>{value}</span>} />
                <Bar dataKey="issues_reported" name="Issues reported" fill={SERIES.issues} radius={[4, 4, 0, 0]} maxBarSize={14} />
                <Bar dataKey="work_orders_decided" name="Work orders decided" fill={SERIES.decisions} radius={[4, 4, 0, 0]} maxBarSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function EquipmentStatusOverview({ data }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0)
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Equipment status</CardTitle>
          <CardDescription>{total} registered asset{total === 1 ? '' : 's'}</CardDescription>
        </div>
        <Link to="/equipment" className="text-xs font-medium text-brand-600 hover:underline">View all</Link>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3">
        {Object.entries(data).map(([status, count]) => (
          <Link key={status} to={`/equipment?status=${status}`} className="rounded-lg border border-slate-100 p-3 hover:bg-slate-50">
            <EquipmentStatusBadge status={status} />
            <p className="mt-2 text-2xl font-semibold tabular-nums">{count}</p>
          </Link>
        ))}
      </CardContent>
    </Card>
  )
}

export function RecentIssues({ issues }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Recent equipment issues</CardTitle>
          <CardDescription>Latest reports across all assets</CardDescription>
        </div>
        <Link to="/issues" className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline">
          Issue history <ArrowRight className="size-3" />
        </Link>
      </CardHeader>
      {issues.length === 0 ? (
        <CardContent>
          <EmptyState title="No issues reported" description="When a technician reports a problem it will appear here." action={<Link to="/report" className="text-sm font-medium text-brand-600 hover:underline">Report an issue</Link>} />
        </CardContent>
      ) : (
        <ul className="divide-y divide-slate-100">
          {issues.map((i) => (
            <li key={i.issue_id}>
              <Link to={`/issues/${i.issue_id}`} className="flex flex-col gap-2 px-5 py-3 hover:bg-slate-50 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-900">{i.description}</p>
                  <p className="text-xs text-slate-500">{i.equipment_id} · {i.equipment_name} · {timeAgo(i.created_at)}</p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <PriorityBadge priority={i.priority} />
                  <IssueStatusBadge status={i.status} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export function RecentDecisions({ decisions }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Recent technician decisions</CardTitle>
          <CardDescription>Approvals and rejections</CardDescription>
        </div>
      </CardHeader>
      {decisions.length === 0 ? (
        <CardContent><p className="text-sm text-slate-500">No work orders have been reviewed yet.</p></CardContent>
      ) : (
        <ul className="divide-y divide-slate-100">
          {decisions.map((d) => (
            <li key={d.work_order_id}>
              <Link to={`/work-orders/${d.work_order_id}`} className="block px-5 py-3 hover:bg-slate-50">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-medium text-slate-900">{d.title}</p>
                  <WorkOrderStatusBadge status={d.approval_status} />
                </div>
                <p className="mt-0.5 text-xs text-slate-500">{d.reviewer} · {timeAgo(d.reviewed_at)}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
