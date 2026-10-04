import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WorkOrderEditor } from '@/components/workorders/WorkOrderEditor'
import { DecisionPanel } from '@/components/workorders/DecisionPanel'

const workOrder = {
  title: 'Inspect PUMP-001 bearings',
  description: 'Inspect the drive-end bearing housing for wear.',
  priority: 'high',
  checklist: [{ text: 'Apply lockout/tagout', done: false }, { text: 'Inspect bearings', done: false }],
  technician_notes: '',
}

describe('WorkOrderEditor', () => {
  it('edits title, priority and checklist and saves the edited values', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(<WorkOrderEditor workOrder={workOrder} onSave={onSave} />)

    const save = screen.getByRole('button', { name: /save changes/i })
    expect(save).toBeDisabled() // nothing changed yet

    const title = screen.getByLabelText(/^title/i)
    await user.clear(title)
    await user.type(title, 'Replace drive-end bearing')
    await user.selectOptions(screen.getByLabelText('Priority'), 'critical')
    await user.click(screen.getByRole('button', { name: /add item/i }))
    await user.type(screen.getByLabelText('Checklist item 3'), 'Record vibration after restart')
    await user.type(screen.getByLabelText('Technician notes'), 'Confirmed noise on site')
    await user.click(save)

    expect(onSave).toHaveBeenCalledWith({
      title: 'Replace drive-end bearing',
      description: workOrder.description,
      priority: 'critical',
      checklist: [...workOrder.checklist, { text: 'Record vibration after restart', done: false }],
      technician_notes: 'Confirmed noise on site',
    })
  })

  it('validates edits before saving', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(<WorkOrderEditor workOrder={workOrder} onSave={onSave} />)
    await user.clear(screen.getByLabelText(/^title/i))
    await user.type(screen.getByLabelText(/^title/i), 'Fix')
    await user.click(screen.getByRole('button', { name: /save changes/i }))
    expect(await screen.findByText(/at least 5 characters/i)).toBeInTheDocument()
    expect(onSave).not.toHaveBeenCalled()
  })

  it('is read-only after a decision', () => {
    render(<WorkOrderEditor workOrder={workOrder} onSave={vi.fn()} readOnly />)
    expect(screen.getByLabelText(/^title/i)).toBeDisabled()
    expect(screen.queryByRole('button', { name: /save changes/i })).not.toBeInTheDocument()
  })
})

describe('DecisionPanel approval confirmation', () => {
  it('does not approve until the technician confirms in the dialog', async () => {
    const user = userEvent.setup()
    const onApprove = vi.fn()
    render(<DecisionPanel reviewer="Alex Tech" onApprove={onApprove} onReject={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: /^approve$/i }))
    expect(screen.getByRole('dialog', { name: /approve this work order/i })).toBeInTheDocument()
    expect(onApprove).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: /yes, approve/i }))
    expect(onApprove).toHaveBeenCalledWith({ reviewer: 'Alex Tech', confirm: true }, expect.any(Object))
  })

  it('cancelling the dialog does not approve', async () => {
    const user = userEvent.setup()
    const onApprove = vi.fn()
    render(<DecisionPanel reviewer="Alex Tech" onApprove={onApprove} onReject={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: /^approve$/i }))
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(onApprove).not.toHaveBeenCalled()
  })

  it('requires a rejection reason', async () => {
    const user = userEvent.setup()
    const onReject = vi.fn()
    render(<DecisionPanel reviewer="Alex Tech" onApprove={vi.fn()} onReject={onReject} />)
    await user.click(screen.getByRole('button', { name: /^reject$/i }))
    await user.click(screen.getByRole('button', { name: /yes, reject/i }))
    expect(screen.getByText(/reason of at least 5 characters/i)).toBeInTheDocument()
    expect(onReject).not.toHaveBeenCalled()

    await user.type(screen.getByLabelText(/rejection reason/i), 'Electrical fault, not mechanical')
    await user.click(screen.getByRole('button', { name: /yes, reject/i }))
    expect(onReject).toHaveBeenCalledWith(
      { reviewer: 'Alex Tech', reason: 'Electrical fault, not mechanical', confirm: true }, expect.any(Object),
    )
  })

  it('blocks decisions while there are unsaved edits', () => {
    render(<DecisionPanel reviewer="Alex" onApprove={vi.fn()} onReject={vi.fn()} hasUnsavedChanges />)
    expect(screen.getByRole('button', { name: /^approve$/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /^reject$/i })).toBeDisabled()
  })
})
