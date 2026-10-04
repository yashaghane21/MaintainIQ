import { Button } from '@/components/ui/button'
import { Dialog, DialogContent } from '@/components/ui/dialog'

/** Generic confirmation dialog. `children` can hold extra inputs (e.g. a rejection reason). */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  confirmVariant = 'default',
  onConfirm,
  loading = false,
  confirmDisabled = false,
  children,
}) {
  return (
    <Dialog open={open} onOpenChange={(next) => !loading && onOpenChange(next)}>
      <DialogContent title={title} description={description}>
        {children}
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Cancel
          </Button>
          <Button variant={confirmVariant} onClick={onConfirm} loading={loading} disabled={confirmDisabled}>
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
