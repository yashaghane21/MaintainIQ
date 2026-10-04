import { Clock } from 'lucide-react'
import { SeverityBadge } from '@/components/common/Badges'
import { humanize } from '@/utils/format'

const fmt = (v) => (v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 }))

export function ThresholdFindings({ findings, disclaimer }) {
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="text-left text-xs text-slate-500">
            <tr className="border-b border-slate-100">
              <th className="py-2 pr-3 font-medium">Sensor</th>
              <th className="py-2 pr-3 font-medium">Observed</th>
              <th className="py-2 pr-3 font-medium">Threshold</th>
              <th className="py-2 pr-3 font-medium">Result</th>
              <th className="py-2 font-medium">Explanation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {findings.map((f, idx) => (
              <tr key={`${f.rule_id}-${idx}`} className="align-top">
                <td className="py-2.5 pr-3">
                  <p className="font-medium text-slate-900">{humanize(f.sensor)}</p>
                  <p className="font-mono text-[11px] text-slate-400">{f.rule_id}</p>
                </td>
                <td className="py-2.5 pr-3 tabular-nums">
                  {f.observed_value == null ? <span className="text-slate-400">not provided</span> : `${fmt(f.observed_value)} ${f.observed_unit || ''}`}
                  {f.normalized_value != null && f.observed_unit && f.observed_unit !== f.unit && (
                    <p className="text-xs text-slate-500">= {fmt(f.normalized_value)} {f.unit}</p>
                  )}
                </td>
                <td className="py-2.5 pr-3 tabular-nums">{f.threshold_value == null ? '—' : `${fmt(f.threshold_value)} ${f.unit}`}</td>
                <td className="py-2.5 pr-3">
                  <div className="flex flex-col items-start gap-1">
                    <SeverityBadge severity={f.severity} />
                    {f.status !== 'evaluated' && <span className="text-xs text-slate-500">{humanize(f.status)}</span>}
                    {f.is_stale && <span className="flex items-center gap-1 text-xs text-amber-700"><Clock className="size-3" /> Stale</span>}
                  </div>
                </td>
                <td className="py-2.5 text-slate-600">{f.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {disclaimer && <p className="mt-3 text-xs text-slate-500">{disclaimer}</p>}
    </div>
  )
}
