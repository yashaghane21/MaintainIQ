import { useFieldArray, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { AlertCircle, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldError, FieldHint, Input, Label, Select, Textarea } from '@/components/ui/form-controls'
import { Notice } from '@/components/common/States'
import { getErrorMessage } from '@/services/api'
import { EQUIPMENT_TYPES, SENSORS } from '@/utils/format'

const optionalNumber = z
  .string()
  .trim()
  .refine((v) => v === '' || (!Number.isNaN(Number(v)) && Number.isFinite(Number(v))), 'Enter a number or leave blank')

export const issueSchema = z.object({
  equipment_id: z.string().min(1, 'Select the affected equipment'),
  description: z.string().trim().min(10, 'Describe the problem in at least 10 characters').max(4000),
  operating_events: z
    .array(z.object({ description: z.string().trim().min(3, 'Event must be at least 3 characters'), occurred_at: z.string().optional() }))
    .min(1, 'Add at least one recent operating event'),
  sensors: z.object(Object.fromEntries(SENSORS.map((s) => [s.key, z.object({ value: optionalNumber, unit: z.string() })]))),
  readings_taken_at: z.string().optional(),
})

const defaultSensors = Object.fromEntries(SENSORS.map((s) => [s.key, { value: '', unit: s.units[0] }]))

/** Convert form values to the API payload. Blank sensor values are omitted — never sent as zero. */
export function toPayload(values) {
  const recordedAt = values.readings_taken_at ? new Date(values.readings_taken_at).toISOString() : null
  return {
    equipment_id: values.equipment_id,
    description: values.description.trim(),
    operating_events: values.operating_events.map((e) => ({
      description: e.description.trim(),
      occurred_at: e.occurred_at ? new Date(e.occurred_at).toISOString() : null,
    })),
    sensor_readings: SENSORS.filter((s) => values.sensors[s.key].value !== '').map((s) => ({
      sensor: s.key,
      value: Number(values.sensors[s.key].value),
      unit: values.sensors[s.key].unit,
      recorded_at: recordedAt,
    })),
  }
}

export function IssueForm({ equipment = [], defaultEquipmentId = '', onSubmit, isSubmitting = false, submitError = null }) {
  const {
    register, control, handleSubmit, watch, formState: { errors },
  } = useForm({
    resolver: zodResolver(issueSchema),
    defaultValues: {
      equipment_id: defaultEquipmentId,
      description: '',
      operating_events: [{ description: '', occurred_at: '' }],
      sensors: defaultSensors,
      readings_taken_at: '',
    },
  })
  const events = useFieldArray({ control, name: 'operating_events' })
  const selected = equipment.find((e) => e.equipment_id === watch('equipment_id'))
  const submit = handleSubmit((values) => onSubmit(toPayload(values)))

  return (
    <form onSubmit={submit} noValidate className="space-y-6" aria-label="Report equipment issue">
      {submitError && (
        <Notice tone="danger" icon={AlertCircle} title="The issue was not saved">
          <p>{getErrorMessage(submitError)}</p>
          <p className="mt-1">Your entries are preserved. </p>
          <Button type="button" variant="outline" size="sm" className="mt-2" onClick={submit} loading={isSubmitting}>
            <RefreshCw /> Retry submission
          </Button>
        </Notice>
      )}

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Problem report</CardTitle>
            <CardDescription>Describe what you observed. Only facts — the analysis comes later.</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <div>
            <Label htmlFor="equipment_id" required>Equipment</Label>
            <Select id="equipment_id" aria-invalid={!!errors.equipment_id} aria-describedby="equipment_id-error" {...register('equipment_id')}>
              <option value="">Select equipment…</option>
              {equipment.map((e) => (
                <option key={e.equipment_id} value={e.equipment_id}>
                  {e.equipment_id} — {e.name}
                </option>
              ))}
            </Select>
            <FieldError id="equipment_id-error" message={errors.equipment_id?.message} />
            {selected && <FieldHint>{EQUIPMENT_TYPES[selected.equipment_type]} · {selected.manufacturer} {selected.model}</FieldHint>}
          </div>

          <div>
            <Label htmlFor="description" required>Issue description</Label>
            <Textarea id="description" rows={4} placeholder="e.g. Grinding noise from the drive-end bearing, housing hot to touch…"
              aria-invalid={!!errors.description} aria-describedby="description-error" {...register('description')} />
            <FieldError id="description-error" message={errors.description?.message} />
          </div>

          <fieldset>
            <legend className="mb-1.5 text-sm font-medium text-slate-700">
              Recent operating events<span className="ml-0.5 text-red-500" aria-hidden="true">*</span>
            </legend>
            <FieldHint>Alarms, restarts, maintenance, process changes — anything that happened recently.</FieldHint>
            <div className="mt-2 space-y-2">
              {events.fields.map((f, idx) => (
                <div key={f.id} className="flex flex-col gap-2 sm:flex-row sm:items-start">
                  <div className="flex-1">
                    <Input placeholder={`Event ${idx + 1}`} aria-label={`Operating event ${idx + 1}`}
                      aria-invalid={!!errors.operating_events?.[idx]?.description} {...register(`operating_events.${idx}.description`)} />
                    <FieldError message={errors.operating_events?.[idx]?.description?.message} />
                  </div>
                  <Input type="datetime-local" className="sm:w-56" aria-label={`When event ${idx + 1} occurred (optional)`}
                    {...register(`operating_events.${idx}.occurred_at`)} />
                  <Button type="button" variant="ghost" size="icon" aria-label={`Remove event ${idx + 1}`}
                    onClick={() => events.remove(idx)} disabled={events.fields.length === 1}>
                    <Trash2 />
                  </Button>
                </div>
              ))}
            </div>
            <FieldError message={errors.operating_events?.message || errors.operating_events?.root?.message} />
            <Button type="button" variant="outline" size="sm" className="mt-2" onClick={() => events.append({ description: '', occurred_at: '' })}>
              <Plus /> Add event
            </Button>
          </fieldset>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Sensor readings <span className="font-normal text-slate-500">(optional)</span></CardTitle>
            <CardDescription>Leave blank if not measured. Blank readings are reported as missing — never treated as zero.</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {SENSORS.map((s) => (
              <div key={s.key}>
                <Label htmlFor={`sensor-${s.key}`}>{s.label}</Label>
                <div className="flex gap-2">
                  <Input id={`sensor-${s.key}`} inputMode="decimal" placeholder="—" aria-invalid={!!errors.sensors?.[s.key]?.value}
                    {...register(`sensors.${s.key}.value`)} />
                  <Select className="w-24" aria-label={`${s.label} unit`} {...register(`sensors.${s.key}.unit`)}>
                    {s.units.map((u) => <option key={u} value={u}>{u}</option>)}
                  </Select>
                </div>
                <FieldError message={errors.sensors?.[s.key]?.value?.message} />
              </div>
            ))}
          </div>
          <div className="sm:w-1/2">
            <Label htmlFor="readings_taken_at">Readings taken at</Label>
            <Input id="readings_taken_at" type="datetime-local" {...register('readings_taken_at')} />
            <FieldHint>Used to flag stale measurements. Leave blank if unknown.</FieldHint>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" size="lg" loading={isSubmitting}>
          {isSubmitting ? 'Saving issue…' : 'Submit issue'}
        </Button>
      </div>
    </form>
  )
}
