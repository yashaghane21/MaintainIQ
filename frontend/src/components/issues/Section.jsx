import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ProvenanceTag } from '@/components/common/Badges'

/** A titled analysis section with a provenance tag (observed / rule / AI / technician). */
export function Section({ id, title, provenance, icon: Icon, children, actions }) {
  return (
    <Card id={id}>
      <CardHeader className="flex-wrap items-center">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="size-4 text-slate-400" aria-hidden="true" />}
          <CardTitle>{title}</CardTitle>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {actions}
          {provenance && <ProvenanceTag kind={provenance} />}
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}
