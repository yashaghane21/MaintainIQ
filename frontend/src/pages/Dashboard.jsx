import { AlertOctagon, ClipboardList, Factory, PlusCircle, Wrench } from 'lucide-react'
import { ButtonLink } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState, PageHeader } from '@/components/common/States'
import {
  ActivityChart, EquipmentStatusOverview, KpiCard, PriorityDistribution, RecentDecisions, RecentIssues,
} from '@/components/dashboard/DashboardWidgets'
import { useDashboard } from '@/hooks/useApi'

export default function Dashboard() {
  const { data, isLoading, isError, error, refetch } = useDashboard()

  return (
    <>
      <PageHeader
        title="Operations overview"
        description="Live maintenance status across registered equipment."
        actions={<ButtonLink to="/report"><PlusCircle /> Report issue</ButtonLink>}
      />

      {isError && <ErrorState error={error} onRetry={refetch} className="mb-6" />}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-32" />)}
        </div>
      ) : data ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="Total equipment" value={data.kpis.total_equipment} icon={Factory} to="/equipment" hint="Registered assets" />
            <KpiCard label="Open issues" value={data.kpis.open_issues} icon={Wrench} tone="slate" to="/issues" hint="Not yet resolved by an approved work order" />
            <KpiCard label="High priority issues" value={data.kpis.high_priority_issues} icon={AlertOctagon} tone="red" to="/issues?priority=high" hint="Open issues rated high or critical" />
            <KpiCard label="Pending work orders" value={data.kpis.pending_work_orders} icon={ClipboardList} tone="amber" to="/work-orders?status=pending_review" hint="Awaiting technician review" />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <div className="xl:col-span-2"><ActivityChart data={data.activity} /></div>
            <PriorityDistribution data={data.priority_distribution} />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <div className="xl:col-span-2"><RecentIssues issues={data.recent_issues} /></div>
            <div className="space-y-6">
              <EquipmentStatusOverview data={data.equipment_status} />
              <RecentDecisions decisions={data.recent_decisions} />
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
