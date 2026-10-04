import { useSearchParams } from 'react-router-dom'
import { CheckCircle2, Sparkles } from 'lucide-react'
import { Button, ButtonLink } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { SeverityBadge } from '@/components/common/Badges'
import { ErrorState, LoadingRows, PageHeader } from '@/components/common/States'
import { IssueForm } from '@/components/issues/IssueForm'
import { useCreateIssue, useEquipmentList } from '@/hooks/useApi'

export default function ReportIssue() {
  const [params] = useSearchParams()
  const equipment = useEquipmentList()
  const create = useCreateIssue()

  if (create.isSuccess) {
    const issue = create.data
    return (
      <>
        <PageHeader title="Issue saved" />
        <Card className="mx-auto max-w-2xl">
          <CardContent className="flex flex-col items-center py-10 text-center">
            <CheckCircle2 className="size-10 text-emerald-500" aria-hidden="true" />
            <h2 className="mt-3 text-lg font-semibold">Issue {issue.issue_id} recorded</h2>
            <p className="mt-1 max-w-md text-sm text-slate-500">
              The report is saved for {issue.equipment_id}. Deterministic threshold rules have already been evaluated.
            </p>
            <div className="mt-3 flex items-center gap-2 text-sm text-slate-600">
              Highest rule severity: <SeverityBadge severity={issue.threshold_summary.highest_severity} />
            </div>
            <div className="mt-6 flex flex-col gap-2 sm:flex-row">
              <ButtonLink to={`/issues/${issue.issue_id}?analyze=1`}><Sparkles /> Run triage analysis</ButtonLink>
              <ButtonLink variant="outline" to={`/issues/${issue.issue_id}`}>View issue</ButtonLink>
              <Button variant="ghost" onClick={() => create.reset()}>Report another</Button>
            </div>
          </CardContent>
        </Card>
      </>
    )
  }

  return (
    <>
      <PageHeader title="Report an issue" description="Record an equipment problem. The issue is saved first; triage analysis runs as a separate step." />
      <div className="mx-auto max-w-3xl">
        {equipment.isError && <ErrorState error={equipment.error} onRetry={equipment.refetch} title="Could not load equipment list" className="mb-4" />}
        {equipment.isLoading ? (
          <LoadingRows rows={6} />
        ) : (
          <IssueForm
            equipment={equipment.data || []}
            defaultEquipmentId={params.get('equipment') || ''}
            onSubmit={(payload) => create.mutate(payload)}
            isSubmitting={create.isPending}
            submitError={create.error}
          />
        )}
      </div>
    </>
  )
}
