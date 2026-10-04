import { cn } from '@/utils/cn'

export function Skeleton({ className }) {
  return <div className={cn('animate-pulse rounded-md bg-slate-200/70', className)} />
}
