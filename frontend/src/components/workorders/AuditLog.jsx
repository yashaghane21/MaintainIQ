import { formatDateTime, humanize } from '@/utils/format'

const DOT = { created: 'bg-violet-500', edited: 'bg-blue-500', approved: 'bg-emerald-500', rejected: 'bg-red-500', superseded: 'bg-slate-400' }

function renderValue(v) {
  if (Array.isArray(v)) return `${v.length} checklist item(s)`
  if (v === '' || v == null) return '(empty)'
  const s = String(v)
  return s.length > 80 ? `${s.slice(0, 80)}…` : s
}

export function AuditLog({ entries }) {
  return (
    <ol className="relative space-y-4 border-l border-slate-200 pl-4">
      {[...entries].reverse().map((e, i) => (
        <li key={i} className="relative">
          <span className={`absolute -left-[21px] top-1.5 size-2.5 rounded-full ring-2 ring-white ${DOT[e.action] || 'bg-slate-400'}`} />
          <p className="text-sm font-medium text-slate-900">{humanize(e.action)}</p>
          <p className="text-xs text-slate-500">{e.actor} · {formatDateTime(e.at)}</p>
          {e.note && <p className="mt-0.5 text-xs text-slate-600">{e.note}</p>}
          {e.changes && (
            <ul className="mt-1 space-y-0.5 text-xs text-slate-600">
              {Object.entries(e.changes).map(([field, c]) => (
                <li key={field}>
                  <span className="font-medium">{humanize(field)}:</span>{' '}
                  <span className="text-slate-400 line-through">{renderValue(c.from)}</span> → {renderValue(c.to)}
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ol>
  )
}
