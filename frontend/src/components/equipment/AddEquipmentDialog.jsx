import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { FieldError, Input, Label, Select } from '@/components/ui/form-controls'
import { Notice } from '@/components/common/States'
import { useCreateEquipment } from '@/hooks/useApi'
import { getErrorMessage } from '@/services/api'
import { EQUIPMENT_TYPES } from '@/utils/format'

const schema = z.object({
  equipment_id: z.string().trim().regex(/^[A-Z0-9][A-Z0-9_-]{2,39}$/, 'Use 3–40 uppercase letters, digits, "-" or "_" (e.g. PUMP-006)'),
  name: z.string().trim().min(2, 'Name is required'),
  equipment_type: z.enum(['pump', 'hvac', 'conveyor_motor']),
  manufacturer: z.string().trim().min(1, 'Manufacturer is required'),
  model: z.string().trim().min(1, 'Model is required'),
  installation_date: z.string().optional(),
  location: z.string().trim().optional(),
  status: z.enum(['operational', 'degraded', 'down', 'maintenance']),
})

export function AddEquipmentDialog() {
  const [open, setOpen] = useState(false)
  const create = useCreateEquipment()
  const { register, handleSubmit, reset, formState: { errors } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { equipment_type: 'pump', status: 'operational' },
  })

  const onSubmit = (values) =>
    create.mutate(
      { ...values, installation_date: values.installation_date || null, location: values.location || null },
      { onSuccess: () => { reset(); setOpen(false) } },
    )

  const field = (name, label, props = {}) => (
    <div>
      <Label htmlFor={name} required={props.required}>{label}</Label>
      <Input id={name} aria-invalid={!!errors[name]} {...register(name)} {...props} />
      <FieldError message={errors[name]?.message} />
    </div>
  )

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) create.reset() }}>
      <Button onClick={() => setOpen(true)}><Plus /> Add equipment</Button>
      <DialogContent title="Add equipment" description="Register a new asset. Threshold rules are applied by equipment type.">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {create.isError && <Notice tone="danger" title="Could not save equipment">{getErrorMessage(create.error)}</Notice>}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {field('equipment_id', 'Equipment ID', { placeholder: 'PUMP-006', required: true })}
            {field('name', 'Name', { placeholder: 'Booster Pump', required: true })}
            <div>
              <Label htmlFor="equipment_type" required>Type</Label>
              <Select id="equipment_type" {...register('equipment_type')}>
                {Object.entries(EQUIPMENT_TYPES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </Select>
            </div>
            <div>
              <Label htmlFor="status">Status</Label>
              <Select id="status" {...register('status')}>
                {['operational', 'degraded', 'down', 'maintenance'].map((s) => <option key={s} value={s}>{s}</option>)}
              </Select>
            </div>
            {field('manufacturer', 'Manufacturer', { required: true })}
            {field('model', 'Model', { required: true })}
            {field('installation_date', 'Installation date', { type: 'date' })}
            {field('location', 'Location')}
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" loading={create.isPending}>Save equipment</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
