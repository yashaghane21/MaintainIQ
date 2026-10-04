export function formatDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function formatDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleDateString(undefined, { dateStyle: 'medium' })
}

export function timeAgo(value) {
  if (!value) return '—'
  const seconds = Math.round((Date.now() - new Date(value).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const units = [
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ]
  for (const [unit, size] of units) {
    if (seconds >= size) {
      const n = Math.floor(seconds / size)
      return `${n} ${unit}${n > 1 ? 's' : ''} ago`
    }
  }
  return 'just now'
}

export const humanize = (value) => (value ? String(value).replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) : '—')

export const EQUIPMENT_TYPES = {
  pump: 'Industrial pump',
  hvac: 'HVAC unit',
  conveyor_motor: 'Conveyor motor',
}

export const SENSORS = [
  { key: 'temperature', label: 'Temperature', units: ['C', 'F', 'K'] },
  { key: 'pressure', label: 'Pressure', units: ['bar', 'psi', 'kPa'] },
  { key: 'vibration', label: 'Vibration', units: ['mm/s', 'in/s'] },
  { key: 'operating_hours', label: 'Operating hours', units: ['h'] },
]

export const PRIORITIES = ['low', 'medium', 'high', 'critical']

export const ISSUE_STATUSES = ['reported', 'analysis_failed', 'awaiting_review', 'work_order_approved', 'work_order_rejected']

export const WORK_ORDER_STATUSES = ['pending_review', 'approved', 'rejected', 'superseded']
