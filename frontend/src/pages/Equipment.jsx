import { Link, useSearchParams } from 'react-router-dom'
import { ChevronRight, Factory, Search } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Input, Select } from '@/components/ui/form-controls'
import { EquipmentStatusBadge } from '@/components/common/Badges'
import { EmptyState, ErrorState, LoadingRows, PageHeader } from '@/components/common/States'
import { AddEquipmentDialog } from '@/components/equipment/AddEquipmentDialog'
import { useEquipmentList } from '@/hooks/useApi'
import { EQUIPMENT_TYPES, formatDate, timeAgo } from '@/utils/format'

export default function Equipment() {
  const [params, setParams] = useSearchParams()
  const filters = { search: params.get('search') || '', equipment_type: params.get('type') || '', status: params.get('status') || '' }
  const { data, isLoading, isError, error, refetch } = useEquipmentList(filters)

  const update = (key, value) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  return (
    <>
      <PageHeader title="Equipment" description="Registered assets, their status and open issues." actions={<AddEquipmentDialog />} />

      <Card className="mb-4 flex flex-col gap-3 p-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <Input className="pl-9" placeholder="Search by ID, name, manufacturer, location…" value={filters.search}
            onChange={(e) => update('search', e.target.value)} aria-label="Search equipment" />
        </div>
        <Select className="sm:w-48" value={filters.equipment_type} onChange={(e) => update('type', e.target.value)} aria-label="Filter by type">
          <option value="">All types</option>
          {Object.entries(EQUIPMENT_TYPES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </Select>
        <Select className="sm:w-44" value={filters.status} onChange={(e) => update('status', e.target.value)} aria-label="Filter by status">
          <option value="">All statuses</option>
          {['operational', 'degraded', 'down', 'maintenance'].map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
      </Card>

      {isError && <ErrorState error={error} onRetry={refetch} />}
      {isLoading && <LoadingRows rows={5} />}
      {data && data.length === 0 && (
        <EmptyState icon={Factory} title="No equipment found" description="Adjust the filters or add a new asset." />
      )}

      {data && data.length > 0 && (
        <Card className="overflow-hidden">
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3">Equipment</th>
                  <th className="px-5 py-3">Type</th>
                  <th className="px-5 py-3">Manufacturer / model</th>
                  <th className="px-5 py-3">Installed</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3 text-right">Open issues</th>
                  <th className="px-5 py-3"><span className="sr-only">Open</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.map((e) => (
                  <tr key={e.equipment_id} className="hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <Link to={`/equipment/${e.equipment_id}`} className="font-medium text-slate-900 hover:text-brand-600">{e.equipment_id}</Link>
                      <p className="text-xs text-slate-500">{e.name}{e.location ? ` · ${e.location}` : ''}</p>
                    </td>
                    <td className="px-5 py-3 text-slate-600">{EQUIPMENT_TYPES[e.equipment_type] || e.equipment_type}</td>
                    <td className="px-5 py-3 text-slate-600">{e.manufacturer}<span className="text-slate-400"> · </span>{e.model}</td>
                    <td className="px-5 py-3 text-slate-600">{formatDate(e.installation_date)}</td>
                    <td className="px-5 py-3"><EquipmentStatusBadge status={e.status} /></td>
                    <td className="px-5 py-3 text-right">
                      <span className="font-medium tabular-nums">{e.open_issue_count}</span>
                      {e.last_issue_at && <p className="text-xs text-slate-500">last {timeAgo(e.last_issue_at)}</p>}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Link to={`/equipment/${e.equipment_id}`} aria-label={`Open ${e.equipment_id}`} className="text-slate-400 hover:text-slate-700">
                        <ChevronRight className="size-4" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="divide-y divide-slate-100 md:hidden">
            {data.map((e) => (
              <li key={e.equipment_id}>
                <Link to={`/equipment/${e.equipment_id}`} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-slate-900">{e.equipment_id}</p>
                    <p className="truncate text-xs text-slate-500">{e.name} · {e.open_issue_count} open issue(s)</p>
                  </div>
                  <EquipmentStatusBadge status={e.status} />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  )
}
