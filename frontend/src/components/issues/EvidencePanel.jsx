import { BookOpen, FileText, Gauge, History, MessageSquareText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/common/States'
import { cn } from '@/utils/cn'

const TYPE_META = {
  MANUAL: { label: 'Manual', icon: BookOpen, tone: 'blue' },
  OPERATING_EVENT: { label: 'Operating event', icon: History, tone: 'slate' },
  SENSOR_RULE: { label: 'Sensor rule', icon: Gauge, tone: 'amber' },
  USER_REPORT: { label: 'User report', icon: MessageSquareText, tone: 'slate' },
}

export function scrollToEvidence(id) {
  const el = document.getElementById(`evidence-${id}`)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.classList.add('ring-2', 'ring-brand-500')
  setTimeout(() => el.classList.remove('ring-2', 'ring-brand-500'), 1600)
}

/** Clickable evidence references. Missing evidence is shown as an unverified hypothesis, never hidden. */
export function EvidenceChips({ ids, unverified }) {
  if (unverified || !ids?.length) {
    return <Badge tone="red" title="No evidence supports this item">Unverified hypothesis — no supporting evidence</Badge>
  }
  return (
    <div className="flex flex-wrap gap-1">
      {ids.map((id) => (
        <button key={id} type="button" onClick={() => scrollToEvidence(id)}
          className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-600 hover:bg-brand-50 hover:text-brand-700">
          {id}
        </button>
      ))}
    </div>
  )
}

export function EvidencePanel({ evidence, retrieval }) {
  if (!evidence?.length) return <EmptyState icon={FileText} title="No evidence yet" description="Evidence is collected when the issue is analysed." />
  const manualCount = evidence.filter((e) => e.evidence_type === 'MANUAL').length
  return (
    <div className="space-y-3">
      {retrieval && retrieval.status !== 'ok' && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <strong>No manual evidence used:</strong> {retrieval.message || 'Retrieval returned no relevant content.'}
        </p>
      )}
      {retrieval?.status === 'ok' && (
        <p className="text-xs text-slate-500">
          {manualCount} manual excerpt(s) retrieved by semantic search. Relevance scores measure text similarity only — they are not diagnostic probabilities.
        </p>
      )}
      <ul className="space-y-3">
        {evidence.map((e) => {
          const meta = TYPE_META[e.evidence_type]
          const Icon = meta.icon
          return (
            <li key={e.evidence_id} id={`evidence-${e.evidence_id}`} className={cn('rounded-lg border border-slate-200 p-3 transition-shadow')}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-semibold text-slate-700">{e.evidence_id}</span>
                <Badge tone={meta.tone}><Icon className="size-3" /> {meta.label}</Badge>
                <span className="text-sm font-medium text-slate-900">{e.title}</span>
                {e.retrieval_score != null && (
                  <span className="ml-auto text-xs text-slate-500" title="Cosine similarity between issue text and this excerpt">
                    text relevance {e.retrieval_score.toFixed(2)}
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Source: {e.source}
                {e.chunk_id && <> · chunk <span className="font-mono">{e.chunk_id}</span></>}
              </p>
              <blockquote className="mt-2 whitespace-pre-line border-l-2 border-slate-200 pl-3 text-sm text-slate-700">{e.excerpt}</blockquote>
              {e.referenced_by?.length > 0 ? (
                <div className="mt-2 text-xs text-slate-500">
                  Supports:{' '}
                  {e.referenced_by.map((r, i) => (
                    <span key={i} className="mr-2 inline-block">
                      <span className="font-medium text-slate-700">{r.type === 'cause' ? 'Cause' : 'Step'}</span> “{r.text}”
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-xs text-slate-400">Not cited by any recommendation.</p>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
