import { useState } from 'react'
import { CheckCircle2, ShieldCheck, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FieldError, Input, Label, Textarea } from '@/components/ui/form-controls'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { Notice } from '@/components/common/States'
import { getErrorMessage } from '@/services/api'

/**
 * Approve / reject a work order. Both actions require an explicit confirmation dialog;
 * only then is `confirm: true` sent to the API together with the reviewer identity.
 */
export function DecisionPanel({ reviewer, onApprove, onReject, approving, rejecting, error, hasUnsavedChanges = false }) {
  const [mode, setMode] = useState(null) // 'approve' | 'reject' | null
  const [name, setName] = useState(reviewer)
  const [reason, setReason] = useState('')
  const [touched, setTouched] = useState(false)

  const nameError = name.trim().length < 2 ? 'Enter the reviewer name' : null
  const reasonError = reason.trim().length < 5 ? 'Give a reason of at least 5 characters' : null

  const close = () => { setMode(null); setTouched(false) }
  const confirmApprove = () => {
    setTouched(true)
    if (nameError) return
    onApprove({ reviewer: name.trim(), confirm: true }, { onSuccess: close })
  }
  const confirmReject = () => {
    setTouched(true)
    if (nameError || reasonError) return
    onReject({ reviewer: name.trim(), reason: reason.trim(), confirm: true }, { onSuccess: close })
  }

  return (
    <div className="space-y-3">
      <Notice tone="info" icon={ShieldCheck} title="Technician review required">
        The AI only drafts this work order. It is not actionable until a qualified technician approves it.
      </Notice>
      {hasUnsavedChanges && <p className="text-xs text-amber-700">Save or discard your edits before making a decision.</p>}
      <div className="grid grid-cols-2 gap-2">
        <Button variant="success" onClick={() => setMode('approve')} disabled={hasUnsavedChanges}><CheckCircle2 /> Approve</Button>
        <Button variant="destructive" onClick={() => setMode('reject')} disabled={hasUnsavedChanges}><XCircle /> Reject</Button>
      </div>

      <ConfirmDialog
        open={mode === 'approve'}
        onOpenChange={(o) => !o && close()}
        title="Approve this work order?"
        description="The current version will be recorded as the approved version with your name and a timestamp. This decision cannot be changed afterwards."
        confirmLabel="Yes, approve"
        confirmVariant="success"
        onConfirm={confirmApprove}
        loading={approving}
      >
        {error && mode === 'approve' && <Notice tone="danger" className="mb-3">{getErrorMessage(error)}</Notice>}
        <Label htmlFor="approve-reviewer" required>Reviewer</Label>
        <Input id="approve-reviewer" value={name} onChange={(e) => setName(e.target.value)} aria-invalid={touched && !!nameError} />
        <FieldError message={touched ? nameError : null} />
      </ConfirmDialog>

      <ConfirmDialog
        open={mode === 'reject'}
        onOpenChange={(o) => !o && close()}
        title="Reject this work order?"
        description="The draft will be marked rejected and kept in the audit trail. The issue stays open and can be re-analysed."
        confirmLabel="Yes, reject"
        confirmVariant="destructive"
        onConfirm={confirmReject}
        loading={rejecting}
      >
        {error && mode === 'reject' && <Notice tone="danger" className="mb-3">{getErrorMessage(error)}</Notice>}
        <div className="space-y-3">
          <div>
            <Label htmlFor="reject-reviewer" required>Reviewer</Label>
            <Input id="reject-reviewer" value={name} onChange={(e) => setName(e.target.value)} aria-invalid={touched && !!nameError} />
            <FieldError message={touched ? nameError : null} />
          </div>
          <div>
            <Label htmlFor="reject-reason" required>Rejection reason</Label>
            <Textarea id="reject-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} aria-invalid={touched && !!reasonError} />
            <FieldError message={touched ? reasonError : null} />
          </div>
        </div>
      </ConfirmDialog>
    </div>
  )
}
