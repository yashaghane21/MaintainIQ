import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { getErrorMessage } from '@/services/api'
import { cn } from '@/utils/cn'

export function PageHeader({ title, description, actions, children }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
        {children}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function EmptyState({ icon: Icon = Inbox, title, description, action, className }) {
  return (
    <div className={cn('flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 px-6 py-10 text-center', className)}>
      <div className="mb-3 rounded-full bg-slate-100 p-3 text-slate-400">
        <Icon className="size-5" aria-hidden="true" />
      </div>
      <p className="text-sm font-medium text-slate-900">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, title = 'Could not load data', onRetry, className }) {
  return (
    <div role="alert" className={cn('flex flex-col items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 sm:flex-row sm:items-center', className)}>
      <AlertTriangle className="size-5 shrink-0 text-red-600" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-red-800">{title}</p>
        <p className="mt-0.5 text-sm text-red-700">{getErrorMessage(error)}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw /> Retry
        </Button>
      )}
    </div>
  )
}

export function LoadingRows({ rows = 4, className }) {
  return (
    <div className={cn('space-y-3', className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  )
}

export function Notice({ tone = 'info', icon: Icon, title, children, className }) {
  const tones = {
    info: 'border-blue-200 bg-blue-50 text-blue-900',
    warning: 'border-amber-200 bg-amber-50 text-amber-900',
    danger: 'border-red-200 bg-red-50 text-red-900',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    neutral: 'border-slate-200 bg-slate-50 text-slate-700',
  }
  return (
    <div className={cn('flex gap-3 rounded-lg border p-3 text-sm', tones[tone], className)}>
      {Icon && <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />}
      <div className="min-w-0">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn(title && 'mt-0.5', 'opacity-90')}>{children}</div>}
      </div>
    </div>
  )
}
