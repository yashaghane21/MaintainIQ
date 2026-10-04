import { useEffect } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowDown, ArrowUp, Plus, Save, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FieldError, Input, Label, Select, Textarea } from '@/components/ui/form-controls'
import { Notice } from '@/components/common/States'
import { getErrorMessage } from '@/services/api'
import { PRIORITIES, humanize } from '@/utils/format'

const schema = z.object({
  title: z.string().trim().min(5, 'Title must be at least 5 characters').max(160),
  description: z.string().trim().min(10, 'Description must be at least 10 characters').max(4000),
  priority: z.enum(['low', 'medium', 'high', 'critical']),
  checklist: z.array(z.object({ text: z.string().trim().min(1, 'Checklist item cannot be empty'), done: z.boolean() })).min(1, 'Keep at least one checklist item'),
  technician_notes: z.string().max(4000),
})

export function WorkOrderEditor({ workOrder, onSave, saving = false, saveError = null, readOnly = false, onDirtyChange }) {
  const { register, control, handleSubmit, reset, formState: { errors, isDirty } } = useForm({
    resolver: zodResolver(schema),
    values: {
      title: workOrder.title,
      description: workOrder.description,
      priority: workOrder.priority,
      checklist: workOrder.checklist,
      technician_notes: workOrder.technician_notes || '',
    },
  })
  const checklist = useFieldArray({ control, name: 'checklist' })
  useEffect(() => { onDirtyChange?.(isDirty) }, [isDirty, onDirtyChange])

  const submit = handleSubmit((values) => onSave(values))

  return (
    <form onSubmit={submit} noValidate className="space-y-4" aria-label="Edit work order">
      {saveError && <Notice tone="danger" title="Changes not saved">{getErrorMessage(saveError)}</Notice>}
      <fieldset disabled={readOnly || saving} className="space-y-4">
        <div>
          <Label htmlFor="wo-title" required>Title</Label>
          <Input id="wo-title" aria-invalid={!!errors.title} {...register('title')} />
          <FieldError message={errors.title?.message} />
        </div>
        <div>
          <Label htmlFor="wo-description" required>Description</Label>
          <Textarea id="wo-description" rows={5} aria-invalid={!!errors.description} {...register('description')} />
          <FieldError message={errors.description?.message} />
        </div>
        <div className="sm:w-56">
          <Label htmlFor="wo-priority">Priority</Label>
          <Select id="wo-priority" {...register('priority')}>
            {PRIORITIES.map((p) => <option key={p} value={p}>{humanize(p)}</option>)}
          </Select>
        </div>
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-slate-700">Checklist</legend>
          <ul className="space-y-2">
            {checklist.fields.map((f, idx) => (
              <li key={f.id} className="flex items-start gap-2">
                <input type="checkbox" className="mt-2.5 size-4 rounded border-slate-300" aria-label={`Mark item ${idx + 1} done`} {...register(`checklist.${idx}.done`)} />
                <div className="flex-1">
                  <Input aria-label={`Checklist item ${idx + 1}`} aria-invalid={!!errors.checklist?.[idx]?.text} {...register(`checklist.${idx}.text`)} />
                  <FieldError message={errors.checklist?.[idx]?.text?.message} />
                </div>
                {!readOnly && (
                  <div className="flex">
                    <Button type="button" variant="ghost" size="icon" aria-label={`Move item ${idx + 1} up`} disabled={idx === 0} onClick={() => checklist.move(idx, idx - 1)}><ArrowUp /></Button>
                    <Button type="button" variant="ghost" size="icon" aria-label={`Move item ${idx + 1} down`} disabled={idx === checklist.fields.length - 1} onClick={() => checklist.move(idx, idx + 1)}><ArrowDown /></Button>
                    <Button type="button" variant="ghost" size="icon" aria-label={`Remove item ${idx + 1}`} disabled={checklist.fields.length === 1} onClick={() => checklist.remove(idx)}><Trash2 /></Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
          <FieldError message={errors.checklist?.message || errors.checklist?.root?.message} />
          {!readOnly && (
            <Button type="button" variant="outline" size="sm" className="mt-2" onClick={() => checklist.append({ text: '', done: false })}>
              <Plus /> Add item
            </Button>
          )}
        </fieldset>
        <div>
          <Label htmlFor="wo-notes">Technician notes</Label>
          <Textarea id="wo-notes" rows={3} placeholder="Findings on site, parts needed, safety notes…" {...register('technician_notes')} />
        </div>
      </fieldset>
      {!readOnly && (
        <div className="flex flex-wrap items-center justify-end gap-2">
          {isDirty && <span className="mr-auto text-xs text-amber-700">Unsaved changes</span>}
          <Button type="button" variant="ghost" disabled={!isDirty || saving} onClick={() => reset()}>Discard</Button>
          <Button type="submit" variant="outline" loading={saving} disabled={!isDirty}><Save /> Save changes</Button>
        </div>
      )}
    </form>
  )
}
