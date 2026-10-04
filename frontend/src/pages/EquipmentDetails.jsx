import { Link, useParams } from 'react-router-dom'
import { ClipboardList, PlusCircle } from 'lucide-react'
import { ButtonLink } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EquipmentStatusBadge, IssueStatusBadge, PriorityBadge, WorkOrderStatusBadge } from '@/components/common/Badges'
import { EmptyState, ErrorState, LoadingRows, PageHeader } from '@/components/common/States'
import { useEquipmentHistory } from '@/hooks/useApi'
import { EQUIPMENT_TYPES, formatDate, formatDateTime, timeAgo } from '@/utils/format'

function Detail({ label, children }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-slate-900">{children || '—'}</dd>
    </div>
  )
}

export default function EquipmentDetails() {
  const { equipmentId } = useParams()
  const { data, isLoading, isError, error, refetch } = useEquipmentHistory(equipmentId)

  if (isLoading) return <LoadingRows rows={6} />
  if (isError) return <ErrorState error={error} onRetry={refetch} title="Could not load equipment" />
  const { equipment: e, issues, work_orders: workOrders, timeline } = data

  return (
    <>
      <PageHeader
        title={`${e.equipment_id} — ${e.name}`}
        description={`${EQUIPMENT_TYPES[e.equipment_type] || e.equipment_type}${e.location ? ` · ${e.location}` : ''}`}
        actions={<ButtonLink to={`/report?equipment=${e.equipment_id}`}><PlusCircle /> Report issue</ButtonLink>}
      />

      <Card className="mb-6">
        <CardContent>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <Detail label="Status"><EquipmentStatusBadge status={e.status} /></Detail>
            <Detail label="Manufacturer">{e.manufacturer}</Detail>
            <Detail label="Model">{e.model}</Detail>
            <Detail label="Installed">{formatDate(e.installation_date)}</Detail>
            <Detail label="Open issues">{String(e.open_issue_count)}</Detail>
            <Detail label="Last issue">{e.last_issue_at ? timeAgo(e.last_issue_at) : 'None'}</Detail>
          </dl>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Card>
            <CardHeader><CardTitle>Issue history</CardTitle></CardHeader>
            {issues.length === 0 ? (
              <CardContent><EmptyState title="No issues reported" description="This asset has no reported issues." /></CardContent>
            ) : (
              <ul className="divide-y divide-slate-100">
                {issues.map((i) => (
                  <li key={i.issue_id}>
                    <Link to={`/issues/${i.issue_id}`} className="flex flex-col gap-2 px-5 py-3 hover:bg-slate-50 sm:flex-row sm:items-center">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{i.description}</p>
                        <p className="text-xs text-slate-500">{i.issue_id} · {formatDateTime(i.created_at)}</p>
                      </div>
                      <div className="flex gap-2"><PriorityBadge priority={i.priority} /><IssueStatusBadge status={i.status} /></div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader><CardTitle>Work orders</CardTitle></CardHeader>
            {workOrders.length === 0 ? (
              <CardContent><EmptyState icon={ClipboardList} title="No work orders" description="Work orders are drafted after an issue is analysed." /></CardContent>
            ) : (
              <ul className="divide-y divide-slate-100">
                {workOrders.map((w) => (
                  <li key={w.work_order_id}>
                    <Link to={`/work-orders/${w.work_order_id}`} className="flex flex-col gap-2 px-5 py-3 hover:bg-slate-50 sm:flex-row sm:items-center">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{w.title}</p>
                        <p className="text-xs text-slate-500">{w.work_order_id} · {w.reviewer ? `reviewed by ${w.reviewer}` : 'not reviewed'}</p>
                      </div>
                      <div className="flex gap-2"><PriorityBadge priority={w.priority} /><WorkOrderStatusBadge status={w.approval_status} /></div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <Card>
          <CardHeader><CardTitle>Maintenance timeline</CardTitle></CardHeader>
          <CardContent>
            {timeline.length === 0 ? (
              <p className="text-sm text-slate-500">No recorded activity.</p>
            ) : (
              <ol className="relative space-y-4 border-l border-slate-200 pl-4">
                {timeline.map((t, idx) => (
                  <li key={idx} className="relative">
                    <span className={`absolute -left-[21px] top-1.5 size-2.5 rounded-full ring-2 ring-white ${t.kind === 'issue' ? 'bg-blue-500' : 'bg-emerald-500'}`} />
                    <p className="text-sm font-medium text-slate-900">{t.text}</p>
                    <p className="text-xs text-slate-500">
                      <Link className="hover:underline" to={t.kind === 'issue' ? `/issues/${t.ref}` : `/work-orders/${t.ref}`}>{t.ref}</Link>
                      {' · '}{t.actor} · {formatDateTime(t.at)}
                    </p>
                    {t.note && <p className="mt-0.5 text-xs text-slate-600">{t.note}</p>}
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
