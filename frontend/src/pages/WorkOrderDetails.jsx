import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Bot, History, Lock, UserCheck } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PriorityBadge, ProvenanceTag, SimulatedBadge, WorkOrderStatusBadge } from '@/components/common/Badges'
import { ErrorState, LoadingRows, Notice, PageHeader } from '@/components/common/States'
import { AuditLog } from '@/components/workorders/AuditLog'
import { DecisionPanel } from '@/components/workorders/DecisionPanel'
import { WorkOrderEditor } from '@/components/workorders/WorkOrderEditor'
import { useReviewer } from '@/context/ReviewerContext'
import { useApproveWorkOrder, useRejectWorkOrder, useUpdateWorkOrder, useWorkOrder } from '@/hooks/useApi'
import { formatDateTime } from '@/utils/format'

function DraftSnapshot({ title, provenance, snapshot }) {
  return (
    <Card>
      <CardHeader className="items-center">
        <CardTitle>{title}</CardTitle>
        <ProvenanceTag kind={provenance} />
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p className="font-medium text-slate-900">{snapshot.title}</p>
        <PriorityBadge priority={snapshot.priority} />
        <p className="whitespace-pre-line text-slate-600">{snapshot.description}</p>
        <ul className="list-disc pl-5 text-slate-600">
          {snapshot.checklist.map((c, i) => <li key={i}>{c.text}</li>)}
        </ul>
        {snapshot.technician_notes && <p className="text-slate-600"><span className="font-medium">Notes:</span> {snapshot.technician_notes}</p>}
      </CardContent>
    </Card>
  )
}

export default function WorkOrderDetails() {
  const { workOrderId } = useParams()
  const { reviewer } = useReviewer()
  const { data: wo, isLoading, isError, error, refetch } = useWorkOrder(workOrderId)
  const update = useUpdateWorkOrder(workOrderId)
  const approve = useApproveWorkOrder(workOrderId)
  const reject = useRejectWorkOrder(workOrderId)
  const [dirty, setDirty] = useState(false)

  if (isLoading) return <LoadingRows rows={8} />
  if (isError) return <ErrorState error={error} onRetry={refetch} title="Could not load work order" />

  const pending = wo.approval_status === 'pending_review'

  return (
    <>
      <PageHeader
        title={`Work order ${wo.work_order_id}`}
        description={`${wo.equipment_id} · ${wo.equipment_name || ''} · created ${formatDateTime(wo.created_at)}`}
        actions={<><WorkOrderStatusBadge status={wo.approval_status} /><SimulatedBadge simulated={wo.is_simulated} /></>}
      >
        <p className="mt-1 text-sm">
          Linked issue: <Link className="font-medium text-brand-600 hover:underline" to={`/issues/${wo.issue_id}`}>{wo.issue_id}</Link>
          <span className="text-slate-400"> · from analysis v{wo.analysis_version}</span>
        </p>
      </PageHeader>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          {!pending && (
            <Notice tone={wo.approval_status === 'approved' ? 'success' : 'neutral'} icon={wo.approval_status === 'approved' ? UserCheck : Lock}
              title={wo.approval_status === 'approved' ? `Approved by ${wo.reviewer}` : wo.approval_status === 'rejected' ? `Rejected by ${wo.reviewer}` : 'Superseded by a newer analysis'}>
              {wo.reviewed_at && <p>{formatDateTime(wo.reviewed_at)}</p>}
              {wo.decision_reason && <p className="mt-1">Reason: {wo.decision_reason}</p>}
              <p className="mt-1">This work order is locked; decisions are preserved in the audit trail.</p>
            </Notice>
          )}

          <Card>
            <CardHeader className="items-center">
              <CardTitle>{pending ? 'Review and edit draft' : 'Work order'}</CardTitle>
              <ProvenanceTag kind={wo.approval_status === 'approved' ? 'technician' : 'ai'} />
            </CardHeader>
            <CardContent>
              <WorkOrderEditor
                workOrder={wo}
                readOnly={!pending}
                saving={update.isPending}
                saveError={update.error}
                onDirtyChange={setDirty}
                onSave={(values) => update.mutate({ ...values, editor: reviewer })}
              />
              {update.isSuccess && !dirty && <p className="mt-2 text-right text-xs text-emerald-700" role="status">Changes saved.</p>}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <DraftSnapshot title="Original AI draft" provenance="ai" snapshot={wo.original_draft} />
            {wo.approved_version && <DraftSnapshot title="Approved version" provenance="technician" snapshot={wo.approved_version} />}
          </div>
        </div>

        <aside className="space-y-6">
          {pending && (
            <Card>
              <CardHeader><CardTitle>Decision</CardTitle></CardHeader>
              <CardContent>
                <DecisionPanel
                  reviewer={reviewer}
                  hasUnsavedChanges={dirty}
                  onApprove={approve.mutate}
                  onReject={reject.mutate}
                  approving={approve.isPending}
                  rejecting={reject.isPending}
                  error={approve.error || reject.error}
                />
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader className="items-center">
              <CardTitle>Audit trail</CardTitle>
              <History className="size-4 text-slate-400" />
            </CardHeader>
            <CardContent><AuditLog entries={wo.audit_log} /></CardContent>
          </Card>
          <p className="flex items-center gap-1.5 px-1 text-xs text-slate-500">
            <Bot className="size-3.5" /> The AI cannot approve, reject or execute work orders.
          </p>
        </aside>
      </div>
    </>
  )
}
