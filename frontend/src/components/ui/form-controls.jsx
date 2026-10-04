import { forwardRef } from 'react'
import { cn } from '@/utils/cn'

const base =
  'w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-xs placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:bg-slate-50 aria-[invalid=true]:border-red-400 aria-[invalid=true]:ring-red-100'

export const Input = forwardRef(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn(base, 'h-9', className)} {...props} />
})

export const Textarea = forwardRef(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cn(base, 'min-h-24 py-2 leading-relaxed', className)} {...props} />
})

export const Select = forwardRef(function Select({ className, children, ...props }, ref) {
  return (
    <select ref={ref} className={cn(base, 'h-9 pr-8', className)} {...props}>
      {children}
    </select>
  )
})

export function Label({ className, children, required, ...props }) {
  return (
    <label className={cn('mb-1.5 block text-sm font-medium text-slate-700', className)} {...props}>
      {children}
      {required && <span className="ml-0.5 text-red-500" aria-hidden="true">*</span>}
    </label>
  )
}

export function FieldError({ id, message }) {
  if (!message) return null
  return (
    <p id={id} role="alert" className="mt-1 text-xs text-red-600">
      {message}
    </p>
  )
}

export function FieldHint({ children }) {
  return <p className="mt-1 text-xs text-slate-500">{children}</p>
}
