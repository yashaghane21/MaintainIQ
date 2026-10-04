import { Link, useSearchParams } from 'react-router-dom'
import { History, X } from 'lucide-react'
import { Button, ButtonLink } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input, Label, Select } from '@/components/ui/form-controls'
import { IssueStatusBadge, PriorityBadge, SeverityBadge } from '@/components/common/Badges'
import { EmptyState, ErrorState, LoadingRows, PageHeader } from '@/components/common/States'
import { useEquipmentList, useIssues } from '@/hooks/useApi'
import { ISSUE_STATUSES, PRIORITIES, formatDateTime, humanize } from '@/utils/format'

const FILTER_KEYS = ['equipment_id', 'priority', 'status', 'date_from', 'date_to', 'search']

export default function IssueHistory() {
  const [params, setParams] = useSearchParams()
  const filters = Object.fromEntries(FILTER_KEYS.map((k) => [k, params.get(k) || '']))
  const { data, isLoading, isError, error, refetch } = useIssues(filters)
  const equipment = useEquipmentList()
  const active = FILTER_KEYS.some((k) => filters[k])

  const set = (key, value) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  return (
    <>
      <PageHeader title="Issue history" description="All reported issues with their analysis and review status."
        actions={<ButtonLink to="/report">Report issue</ButtonLink>} />

      <Card className="mb-4 grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-6">
        <div className="lg:col-span-2">
          <Label htmlFor="f-search">Search</Label>
          <Input id="f-search" placeholder="Description or issue ID" value={filters.search} onChange={(e) => set('search', e.target.value)} />
        </div>
        <div>
          <Label htmlFor="f-equipment">Equipment</Label>
          <Select id="f-equipment" value={filters.equipment_id} onChange={(e) => set('equipment_id', e.target.value)}>
            <option value="">All</option>
            {(equipment.data || []).map((e) => <option key={e.equipment_id} value={e.equipment_id}>{e.equipment_id}</option>)}
          </Select>
        </div>
        <div>
          <Label htmlFor="f-priority">Priority</Label>
          <Select id="f-priority" value={filters.priority} onChange={(e) => set('priority', e.target.value)}>
            <option value="">All</option>
            {PRIORITIES.map((p) => <option key={p} value={p}>{humanize(p)}</option>)}
          </Select>
        </div>
        <div>
          <Label htmlFor="f-status">Status</Label>
          <Select id="f-status" value={filters.status} onChange={(e) => set('status', e.target.value)}>
            <option value="">All</option>
            {ISSUE_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-2 lg:col-span-1 lg:grid-cols-1">
          <div>
            <Label htmlFor="f-from">From</Label>
            <Input id="f-from" type="date" value={filters.date_from} onChange={(e) => set('date_from', e.target.value)} />
          </div>
          <div>
            <Label htmlFor="f-to">To</Label>
            <Input id="f-to" type="date" value={filters.date_to} onChange={(e) => set('date_to', e.target.value)} />
          </div>
        </div>
        {active && (
          <div className="sm:col-span-2 lg:col-span-6">
            <Button variant="ghost" size="sm" onClick={() => setParams({}, { replace: true })}><X /> Clear filters</Button>
          </div>
        )}
      </Card>

      {isError && <ErrorState error={error} onRetry={refetch} />}
      {isLoading && <LoadingRows rows={6} />}
      {data?.length === 0 && (
        <EmptyState icon={History} title={active ? 'No issues match these filters' : 'No issues reported yet'}
          description={active ? 'Try widening the filters.' : 'Reported issues will be listed here.'} />
      )}
      {data?.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3">Issue</th>
                  <th className="px-5 py-3">Equipment</th>
                  <th className="px-5 py-3">Rule severity</th>
                  <th className="px-5 py-3">Priority</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Reported</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.map((i) => (
                  <tr key={i.issue_id} className="hover:bg-slate-50">
                    <td className="max-w-sm px-5 py-3">
                      <Link to={`/issues/${i.issue_id}`} className="font-medium text-slate-900 hover:text-brand-600">{i.issue_id}</Link>
                      <p className="truncate text-xs text-slate-500">{i.description}</p>
                    </td>
                    <td className="px-5 py-3 text-slate-600">{i.equipment_id}</td>
                    <td className="px-5 py-3"><SeverityBadge severity={i.threshold_summary?.highest_severity} /></td>
                    <td className="px-5 py-3"><PriorityBadge priority={i.priority} /></td>
                    <td className="px-5 py-3"><IssueStatusBadge status={i.status} /></td>
                    <td className="px-5 py-3 text-slate-600">{formatDateTime(i.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  )
}
