import { useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/form-controls'
import { ErrorState, LoadingRows, Notice, PageHeader } from '@/components/common/States'
import { useReviewer } from '@/context/ReviewerContext'
import { useHealth, useThresholds } from '@/hooks/useApi'
import { API_URL } from '@/services/api'
import { humanize } from '@/utils/format'

function StatusRow({ label, ok, children }) {
  return (
    <div className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <span className="flex items-center gap-2 text-sm text-slate-600">
        {ok ? <CheckCircle2 className="size-4 text-emerald-600" /> : <XCircle className="size-4 text-red-600" />}
        {children}
      </span>
    </div>
  )
}

export default function Settings() {
  const { reviewer, setReviewer } = useReviewer()
  const [name, setName] = useState(reviewer)
  const [saved, setSaved] = useState(false)
  const health = useHealth()
  const thresholds = useThresholds()

  return (
    <>
      <PageHeader title="Settings" description="Reviewer identity, system status and rule configuration." />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Reviewer profile</CardTitle>
              <CardDescription>Demo identity recorded on edits, approvals and rejections. This MVP has no authentication.</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <form className="flex flex-col gap-2 sm:flex-row sm:items-end" onSubmit={(e) => { e.preventDefault(); setReviewer(name); setSaved(true) }}>
              <div className="flex-1">
                <Label htmlFor="reviewer-name">Reviewer name</Label>
                <Input id="reviewer-name" value={name} onChange={(e) => { setName(e.target.value); setSaved(false) }} />
              </div>
              <Button type="submit">Save</Button>
            </form>
            {saved && <p className="mt-2 text-xs text-emerald-700" role="status">Saved as “{reviewer}”.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>System status</CardTitle>
              <CardDescription>Reported live by <span className="font-mono">{API_URL}/api/health</span></CardDescription>
            </div>
          </CardHeader>
          <CardContent className="divide-y divide-slate-100 py-0">
            {health.isLoading && <LoadingRows rows={3} className="py-4" />}
            {health.isError && <ErrorState error={health.error} onRetry={health.refetch} className="my-4" />}
            {health.data && (
              <>
                <StatusRow label="API" ok>{health.data.environment}</StatusRow>
                <StatusRow label="Database" ok={health.data.database.status === 'ok'}>
                  {health.data.database.backend}
                  {!health.data.database.persistent && <Badge tone="amber">not persistent</Badge>}
                </StatusRow>
                <StatusRow label="AI provider" ok={health.data.ai.configured}>
                  {health.data.ai.provider} · {health.data.ai.model}
                  {health.data.ai.is_simulated && <Badge tone="amber">simulated</Badge>}
                </StatusRow>
                <StatusRow label="Retrieval" ok={health.data.retrieval.status === 'ok'}>
                  {health.data.retrieval.embedder} · {health.data.retrieval.vector_store}{health.data.retrieval.indexed_chunks != null && ` · ${health.data.retrieval.indexed_chunks} chunks loaded`}
                </StatusRow>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Threshold profiles</CardTitle>
              <CardDescription>Deterministic rules applied to sensor readings (evaluated without AI).</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {thresholds.isError && <ErrorState error={thresholds.error} onRetry={thresholds.refetch} />}
            {thresholds.data && (
              <>
                <Notice tone="warning" title="Fictional demonstration values">{thresholds.data.disclaimer}</Notice>
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                  {Object.entries(thresholds.data.profiles).map(([key, profile]) => (
                    <div key={key} className="rounded-lg border border-slate-200 p-3">
                      <p className="text-sm font-medium text-slate-900">{profile.label}</p>
                      <table className="mt-2 w-full text-xs">
                        <thead className="text-left text-slate-500">
                          <tr><th className="py-1 font-medium">Sensor</th><th className="py-1 text-right font-medium">Warning &gt;</th><th className="py-1 text-right font-medium">Critical &gt;</th></tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {Object.entries(profile.sensors).map(([s, r]) => (
                            <tr key={s} title={r.description}>
                              <td className="py-1.5">{humanize(s)}</td>
                              <td className="py-1.5 text-right tabular-nums">{r.warning} {r.canonical_unit}</td>
                              <td className="py-1.5 text-right tabular-nums">{r.critical} {r.canonical_unit}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
