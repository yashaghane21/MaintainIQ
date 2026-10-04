import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IssueForm, toPayload } from '@/components/issues/IssueForm'

const equipment = [
  { equipment_id: 'PUMP-001', name: 'Industrial Water Pump', equipment_type: 'pump', manufacturer: 'AquaFlow', model: 'CP-200' },
]

function setup(props = {}) {
  const onSubmit = vi.fn()
  const user = userEvent.setup()
  render(<IssueForm equipment={equipment} onSubmit={onSubmit} {...props} />)
  return { user, onSubmit }
}

async function fillValid(user) {
  await user.selectOptions(screen.getByLabelText(/^equipment/i), 'PUMP-001')
  await user.type(screen.getByLabelText(/issue description/i), 'Grinding noise from the bearing housing')
  await user.type(screen.getByLabelText('Operating event 1'), 'Vibration alarm at shift start')
}

describe('IssueForm validation', () => {
  it('shows field errors and does not submit when required fields are missing', async () => {
    const { user, onSubmit } = setup()
    await user.click(screen.getByRole('button', { name: /submit issue/i }))

    expect(await screen.findByText('Select the affected equipment')).toBeInTheDocument()
    expect(screen.getByText(/at least 10 characters/i)).toBeInTheDocument()
    expect(screen.getByText(/event must be at least 3 characters/i)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('rejects non-numeric sensor values', async () => {
    const { user, onSubmit } = setup()
    await fillValid(user)
    await user.type(screen.getByLabelText('Temperature'), 'hot')
    await user.click(screen.getByRole('button', { name: /submit issue/i }))

    expect(await screen.findByText('Enter a number or leave blank')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits a payload that omits blank sensors instead of sending zero', async () => {
    const { user, onSubmit } = setup()
    await fillValid(user)
    await user.type(screen.getByLabelText('Vibration'), '9.2')
    await user.click(screen.getByRole('button', { name: /submit issue/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const payload = onSubmit.mock.calls[0][0]
    expect(payload.equipment_id).toBe('PUMP-001')
    expect(payload.operating_events).toEqual([{ description: 'Vibration alarm at shift start', occurred_at: null }])
    expect(payload.sensor_readings).toEqual([{ sensor: 'vibration', value: 9.2, unit: 'mm/s', recorded_at: null }])
  })

  it('can add and remove operating events', async () => {
    const { user } = setup()
    await user.click(screen.getByRole('button', { name: /add event/i }))
    expect(screen.getByLabelText('Operating event 2')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Remove event 2' }))
    expect(screen.queryByLabelText('Operating event 2')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove event 1' })).toBeDisabled()
  })
})

describe('IssueForm loading and error states', () => {
  it('disables submission while saving', () => {
    setup({ isSubmitting: true })
    expect(screen.getByRole('button', { name: /saving issue/i })).toBeDisabled()
  })

  it('shows the API error, keeps entered data and allows retry', async () => {
    const error = { response: { data: { error: { code: 'database_unavailable', message: 'Database is unavailable. The request was not saved.' } } } }
    const { user, onSubmit } = setup({ submitError: error })
    const alert = screen.getByText('The issue was not saved').closest('div')
    expect(within(alert.parentElement).getByText(/Database is unavailable/)).toBeInTheDocument()

    await fillValid(user)
    await user.click(screen.getByRole('button', { name: /retry submission/i }))
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText(/issue description/i)).toHaveValue('Grinding noise from the bearing housing')
  })
})

describe('toPayload', () => {
  it('converts numeric strings and preserves units', () => {
    const sensors = {
      temperature: { value: '194', unit: 'F' },
      pressure: { value: '', unit: 'bar' },
      vibration: { value: '', unit: 'mm/s' },
      operating_hours: { value: '0', unit: 'h' },
    }
    const out = toPayload({ equipment_id: 'X', description: ' desc here ok ', operating_events: [{ description: 'e1', occurred_at: '' }], sensors })
    expect(out.description).toBe('desc here ok')
    // A real zero entered by the user is kept; blanks are dropped.
    expect(out.sensor_readings.map((r) => [r.sensor, r.value, r.unit])).toEqual([['temperature', 194, 'F'], ['operating_hours', 0, 'h']])
  })
})
