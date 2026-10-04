import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle, ClipboardCheck, ClipboardList, Eye, FileSearch, Flag, Gauge, HelpCircle, Lightbulb, ListChecks,
  Loader2, RefreshCw, ScrollText, Sparkles,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button, ButtonLink } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Textarea } from '@/components/ui/form-controls'
import {
  ConfidenceBadge, IssueStatusBadge, PriorityBadge, ProvenanceTag, SimulatedBadge, WorkOrderStatusBadge,
} from '@/components/common/Badges'
import { ErrorState, LoadingRows, Notice, PageHeader } from '@/components/common/States'
import { EvidenceChips, EvidencePanel } from '@/components/issues/EvidencePanel'
import { Section } from '@/components/issues/Section'
import { ThresholdFindings } from '@/components/issues/ThresholdFindings'
import { useAnalyzeIssue, useEvidence, useIssue, useWorkOrder } from '@/hooks/useApi'
import { getErrorMessage } from '@/services/api'
import { formatDateTime } from '@/utils/format'

function AnalyzePanel({ issue, analyze }) {
  const [context, setContext] = useState('')
  const locked = issue.status === 'work_order_approved'
  const hasAnalysis = !!issue.analysis
  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-900">{hasAnalysis ? 'Re-run triage analysis' : 'Run triage analysis'}</p>
            <p className="text-xs text-slate-500">
              {locked
                ? 'This issue has an approved work order; re-analysis is disabled to protect the decision.'
                : 'Retrieves manual evidence and drafts a work order for technician review. Nothing is approved automatically.'}
            </p>
          </div>
          <Button onClick={() => analyze.mutate(context ? { additional_context: context } : {})} loading={analyze.isPending} disabled={locked}>
            {!analyze.isPending && (hasAnalysis ? <RefreshCw /> : <Sparkles />)}
            {analyze.isPending ? 'Analysing…' : hasAnalysis ? 'Re-analyse' : 'Analyse issue'}
          </Button>
        </div>
        {!locked && (
          <Textarea rows={2} className="min-h-0" placeholder="Optional: add context for the analysis (e.g. answers to follow-up questions)"
            value={context} onChange={(e) => setContext(e.target.value)} aria-label="Additional context for analysis" />
        )}
      </CardContent>
    </Card>
  )
}

export default function IssueAnalysis() {
  const { issueId } = useParams()
  const [params, setParams] = useSearchParams()
  const issueQuery = useIssue(issueId)
  const analyze = useAnalyzeIssue(issueId)
  const issue = issueQuery.data
  const analysis = issue?.analysis
  const evidence = useEvidence(issueId, !!analysis)
  const wo = useWorkOrder(issue?.current_work_order?.work_order_id)
  const autoRan = useRef(false)

  // "Run triage analysis" from the report page links here with ?analyze=1.
  useEffect(() => {
    if (params.get('analyze') === '1' && issue && !issue.analysis && !autoRan.current) {
      autoRan.current = true
      setParams({}, { replace: true })
      analyze.mutate({})
    }
  }, [params, issue, analyze, setParams])

  if (issueQuery.isLoading) return <LoadingRows rows={8} />
  if (issueQuery.isError) return <ErrorState error={issueQuery.error} onRetry={issueQuery.refetch} title="Could not load issue" />

  const out = analysis?.output
  const lastAttempt = issue.analysis_history?.at(-1)
  const showFailure = analyze.isError || (issue.status === 'analysis_failed' && lastAttempt?.status === 'failed')

  return (
    <>
      <PageHeader
        title={`Issue ${issue.issue_id}`}
        description={`${issue.equipment_id} · ${issue.equipment_name} · reported ${formatDateTime(issue.created_at)} by ${issue.reported_by}`}
        actions={
          <>
            <IssueStatusBadge status={issue.status} />
            <PriorityBadge priority={issue.priority} />
            <ButtonLink variant="outline" size="sm" to={`/equipment/${issue.equipment_id}`}>View equipment</ButtonLink>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <AnalyzePanel issue={issue} analyze={analyze} />

          {analyze.isPending && (
            <Notice tone="info" icon={Loader2} title="Analysis in progress">
              Retrieving relevant manual sections and generating a structured triage draft. This can take up to a minute with live AI.
            </Notice>
          )}

          {showFailure && !analyze.isPending && (
            <Notice tone="danger" icon={AlertTriangle} title="Analysis failed — the issue is saved">
              <p>{analyze.isError ? getErrorMessage(analyze.error) : lastAttempt?.error?.message}</p>
              <p className="mt-1">No analysis was substituted. Use “Analyse issue” to retry.</p>
            </Notice>
          )}

          {analysis && (
            <Section title="Issue summary" provenance="ai" icon={ScrollText}
              actions={<SimulatedBadge simulated={analysis.is_simulated} />}>
              <p className="text-sm leading-relaxed text-slate-700">{out.summary}</p>
              <p className="mt-3 text-xs text-slate-500">
                Analysis v{analysis.version} · {analysis.provider} / {analysis.model} · {formatDateTime(analysis.completed_at)} · {analysis.duration_ms} ms
              </p>
            </Section>
          )}

          <Section title="Reported observations" provenance="observed" icon={Eye}>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
              {issue.observations.map((o, i) => <li key={i}>{o}</li>)}
            </ul>
          </Section>

          <Section title="Deterministic findings" provenance="rule" icon={Gauge}>
            <ThresholdFindings findings={issue.threshold_findings} disclaimer={issue.threshold_summary?.disclaimer} />
          </Section>

          {out && (
            <>
              <Section title="Possible causes" provenance="ai" icon={Lightbulb}>
                <p className="mb-3 text-xs text-slate-500">Hypotheses to verify — not confirmed diagnoses.</p>
                <ol className="space-y-3">
                  {out.possible_causes.map((c, i) => (
                    <li key={i} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-slate-900">{i + 1}. {c.cause}</span>
                        <ConfidenceBadge confidence={c.confidence} />
                      </div>
                      <p className="mt-1 text-sm text-slate-600">{c.reasoning}</p>
                      <div className="mt-2"><EvidenceChips ids={c.evidence_ids} unverified={c.unverified} /></div>
                    </li>
                  ))}
                </ol>
              </Section>

              <Section title="Follow-up questions" provenance="ai" icon={HelpCircle}>
                {out.follow_up_questions.length ? (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                    {out.follow_up_questions.map((q, i) => <li key={i}>{q}</li>)}
                  </ul>
                ) : <p className="text-sm text-slate-500">No follow-up questions.</p>}
              </Section>

              <Section title="Recommended inspection" provenance="ai" icon={ListChecks}>
                <ol className="space-y-3">
                  {out.inspection_steps.map((s, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">{i + 1}</span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-900">{s.step}</p>
                        <p className="text-sm text-slate-600">{s.reason}</p>
                        <div className="mt-1.5"><EvidenceChips ids={s.evidence_ids} unverified={s.unverified} /></div>
                      </div>
                    </li>
                  ))}
                </ol>
              </Section>

              {out.limitations?.length > 0 && (
                <Notice tone="neutral" title="Limitations">
                  <ul className="list-disc pl-5">{out.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
                </Notice>
              )}
              {analysis.validation_warnings?.length > 0 && (
                <Notice tone="warning" icon={AlertTriangle} title="Guardrail adjustments applied to the AI output">
                  <ul className="list-disc pl-5">{analysis.validation_warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
                </Notice>
              )}

              <Section title="Evidence" icon={FileSearch}>
                {evidence.isError ? <ErrorState error={evidence.error} onRetry={evidence.refetch} /> : evidence.isLoading ? <LoadingRows rows={3} /> : (
                  <EvidencePanel evidence={evidence.data?.evidence} retrieval={evidence.data?.retrieval} />
                )}
              </Section>
            </>
          )}
        </div>

        <aside className="space-y-6">
          {out && (
            <Section title="Suggested priority" provenance="ai" icon={Flag}>
              <PriorityBadge priority={out.suggested_priority} />
              <p className="mt-2 text-sm text-slate-600">{out.priority_reason}</p>
              {out.priority_adjustment && (
                <p className="mt-2 rounded-md bg-blue-50 p-2 text-xs text-blue-900">
                  <ProvenanceTag kind="rule" /> {out.priority_adjustment}
                </p>
              )}
            </Section>
          )}

          <Section title="Draft work order" icon={ClipboardList}>
            {!issue.current_work_order ? (
              <p className="text-sm text-slate-500">A draft is created after a successful analysis.</p>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-slate-600">{issue.current_work_order.work_order_id}</span>
                  <WorkOrderStatusBadge status={issue.current_work_order.approval_status} />
                </div>
                {wo.data && <p className="text-sm font-medium text-slate-900">{wo.data.title}</p>}
                {wo.data?.approval_status === 'approved' && (
                  <div className="rounded-md bg-emerald-50 p-2 text-xs text-emerald-900">
                    <ProvenanceTag kind="technician" /> Approved by {wo.data.reviewer} on {formatDateTime(wo.data.reviewed_at)}
                  </div>
                )}
                <ButtonLink className="w-full" variant={issue.current_work_order.approval_status === 'pending_review' ? 'default' : 'outline'}
                  to={`/work-orders/${issue.current_work_order.work_order_id}`}>
                  <ClipboardCheck /> {issue.current_work_order.approval_status === 'pending_review' ? 'Review draft' : 'Open work order'}
                </ButtonLink>
              </div>
            )}
          </Section>

          <Section title="Analysis history" icon={RefreshCw}>
            {issue.analysis_history?.length ? (
              <ul className="space-y-2 text-sm">
                {[...issue.analysis_history].reverse().map((h) => (
                  <li key={h.version} className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-slate-900">v{h.version} · {h.provider}</p>
                      <p className="text-xs text-slate-500">{formatDateTime(h.completed_at)}</p>
                      {h.error && <p className="text-xs text-red-600">{h.error.message}</p>}
                    </div>
                    <Badge tone={h.status === 'completed' ? 'green' : 'red'}>{h.status}</Badge>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-slate-500">Not analysed yet.</p>}
          </Section>

          <Section title="Status history" icon={ScrollText}>
            <ul className="space-y-2 text-sm">
              {[...issue.status_history].reverse().map((s, i) => (
                <li key={i}>
                  <IssueStatusBadge status={s.status} />
                  <p className="mt-0.5 text-xs text-slate-500">{s.actor} · {formatDateTime(s.at)}</p>
                  {s.note && <p className="text-xs text-slate-600">{s.note}</p>}
                </li>
              ))}
            </ul>
          </Section>
          <p className="px-1 text-xs text-slate-400">
            <Link to="/issues" className="hover:underline">← Back to issue history</Link>
          </p>
        </aside>
      </div>
    </>
  )
}
