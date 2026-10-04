import { Link, useSearchParams } from 'react-router-dom'
import { ClipboardList } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Select } from '@/components/ui/form-controls'
import { PriorityBadge, SimulatedBadge, WorkOrderStatusBadge } from '@/components/common/Badges'
import { EmptyState, ErrorState, LoadingRows, PageHeader } from '@/components/common/States'
import { useEquipmentList, useWorkOrders } from '@/hooks/useApi'
import { PRIORITIES, WORK_ORDER_STATUSES, humanize, timeAgo } from '@/utils/format'

export default function WorkOrders() {
  const [params, setParams] = useSearchParams()
  const filters = { status: params.get('status') || '', priority: params.get('priority') || '', equipment_id: params.get('equipment') || '' }
  const { data, isLoading, isError, error, refetch } = useWorkOrders(filters)
  const equipment = useEquipmentList()

  const set = (key, value) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  return (
    <>
      <PageHeader title="Work orders" description="AI-drafted work orders. Every draft requires technician approval." />
      <Card className="mb-4 grid grid-cols-1 gap-3 p-3 sm:grid-cols-3">
        <Select value={filters.status} onChange={(e) => set('status', e.target.value)} aria-label="Filter by status">
          <option value="">All statuses</option>
          {WORK_ORDER_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
        </Select>
        <Select value={filters.priority} onChange={(e) => set('priority', e.target.value)} aria-label="Filter by priority">
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{humanize(p)}</option>)}
        </Select>
        <Select value={filters.equipment_id} onChange={(e) => set('equipment', e.target.value)} aria-label="Filter by equipment">
          <option value="">All equipment</option>
          {(equipment.data || []).map((e) => <option key={e.equipment_id} value={e.equipment_id}>{e.equipment_id}</option>)}
        </Select>
      </Card>

      {isError && <ErrorState error={error} onRetry={refetch} />}
      {isLoading && <LoadingRows rows={5} />}
      {data?.length === 0 && (
        <EmptyState icon={ClipboardList} title="No work orders" description="Work orders are drafted when an issue is analysed." />
      )}
      {data?.length > 0 && (
        <Card className="divide-y divide-slate-100 overflow-hidden">
          {data.map((w) => (
            <Link key={w.work_order_id} to={`/work-orders/${w.work_order_id}`} className="flex flex-col gap-2 px-5 py-4 hover:bg-slate-50 md:flex-row md:items-center">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-900">{w.title}</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {w.work_order_id} · {w.equipment_id} · issue {w.issue_id} · created {timeAgo(w.created_at)}
                  {w.reviewer && ` · reviewed by ${w.reviewer}`}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {w.is_simulated && <SimulatedBadge simulated />}
                <PriorityBadge priority={w.priority} />
                <WorkOrderStatusBadge status={w.approval_status} />
              </div>
            </Link>
          ))}
        </Card>
      )}
    </>
  )
}
