import { forwardRef } from 'react'
import { cva } from 'class-variance-authority'
import { Link } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { cn } from '@/utils/cn'

export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-brand-600 text-white shadow-sm hover:bg-brand-700',
        outline: 'border border-slate-200 bg-white text-slate-700 shadow-sm hover:bg-slate-50',
        ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
        destructive: 'bg-red-600 text-white shadow-sm hover:bg-red-700',
        success: 'bg-emerald-600 text-white shadow-sm hover:bg-emerald-700',
        link: 'text-brand-600 underline-offset-4 hover:underline px-0',
      },
      size: {
        default: 'h-9 px-4',
        sm: 'h-8 px-3 text-xs',
        lg: 'h-10 px-5',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export const Button = forwardRef(function Button({ className, variant, size, loading = false, disabled, children, ...props }, ref) {
  return (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} disabled={disabled || loading} {...props}>
      {loading && <Loader2 className="animate-spin" aria-hidden="true" />}
      {children}
    </button>
  )
})

/** A react-router Link styled as a button (avoids nesting <button> inside <a>). */
export function ButtonLink({ className, variant, size, ...props }) {
  return <Link className={cn(buttonVariants({ variant, size }), className)} {...props} />
}
