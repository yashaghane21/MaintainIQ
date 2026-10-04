import { cn } from '@/utils/cn'

export function Card({ className, ...props }) {
  return <div className={cn('rounded-xl border border-slate-200 bg-white shadow-xs', className)} {...props} />
}

export function CardHeader({ className, ...props }) {
  return <div className={cn('flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4', className)} {...props} />
}

export function CardTitle({ className, ...props }) {
  return <h2 className={cn('text-sm font-semibold text-slate-900', className)} {...props} />
}

export function CardDescription({ className, ...props }) {
  return <p className={cn('mt-0.5 text-xs text-slate-500', className)} {...props} />
}

export function CardContent({ className, ...props }) {
  return <div className={cn('px-5 py-4', className)} {...props} />
}
