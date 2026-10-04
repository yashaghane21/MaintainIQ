import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReviewerProvider } from '@/context/ReviewerContext'

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, api: { listEquipment: vi.fn(), createIssue: vi.fn(), getIssue: vi.fn(), analyzeIssue: vi.fn(), getEvidence: vi.fn(), getWorkOrder: vi.fn() } }
})

const { api } = await import('@/services/api')
const { default: ReportIssue } = await import('@/pages/ReportIssue')
const { default: IssueAnalysis } = await import('@/pages/IssueAnalysis')

function renderAt(path, routePath, element) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ReviewerProvider initialReviewer="Test Reviewer">
        <MemoryRouter initialEntries={[path]}>
          <Routes><Route path={routePath} element={element} /></Routes>
        </MemoryRouter>
      </ReviewerProvider>
    </QueryClientProvider>,
  )
}

const pump = { equipment_id: 'PUMP-001', name: 'Industrial Water Pump', equipment_type: 'pump', manufacturer: 'AquaFlow', model: 'CP-200' }
const networkError = Object.assign(new Error('Network Error'), { response: { status: 503, data: { error: { code: 'database_unavailable', message: 'Database is unavailable. The request was not saved.' } } } })

beforeEach(() => vi.clearAllMocks())

describe('ReportIssue page', () => {
  it('shows a loading state, then an error with retry on failure, then success', async () => {
    const user = userEvent.setup()
    api.listEquipment.mockResolvedValue([pump])
    api.createIssue.mockRejectedValueOnce(networkError).mockResolvedValueOnce({
      issue_id: 'ISS-1', equipment_id: 'PUMP-001', threshold_summary: { highest_severity: 'critical' },
    })
    renderAt('/report?equipment=PUMP-001', '/report', <ReportIssue />)

    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
    await user.type(await screen.findByLabelText(/issue description/i), 'Loud grinding noise from pump')
    await user.type(screen.getByLabelText('Operating event 1'), 'Alarm at 06:00')
    await user.click(screen.getByRole('button', { name: /submit issue/i }))

    expect(await screen.findByText('The issue was not saved')).toBeInTheDocument()
    expect(screen.getByText(/Database is unavailable/)).toBeInTheDocument()
    expect(screen.getByLabelText(/issue description/i)).toHaveValue('Loud grinding noise from pump')

    await user.click(screen.getByRole('button', { name: /retry submission/i }))
    expect(await screen.findByText('Issue ISS-1 recorded')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /run triage analysis/i })).toHaveAttribute('href', '/issues/ISS-1?analyze=1')
    expect(api.createIssue).toHaveBeenCalledTimes(2)
  })
})

describe('IssueAnalysis page', () => {
  const issue = {
    issue_id: 'ISS-2', equipment_id: 'PUMP-001', equipment_name: 'Pump', reported_by: 'Tech', created_at: '2026-01-01T00:00:00Z',
    status: 'reported', priority: null, description: 'Noise', observations: ['Reported symptom: Noise'],
    threshold_findings: [{ rule_id: 'PUMP.VIBRATION.CRITICAL', sensor: 'vibration', status: 'evaluated', severity: 'critical',
      observed_value: 9, observed_unit: 'mm/s', normalized_value: 9, threshold_value: 8, unit: 'mm/s', explanation: '9 mm/s exceeds the critical threshold of 8 mm/s.', is_stale: false }],
    threshold_summary: { highest_severity: 'critical', disclaimer: 'Fictional values' },
    analysis: null, analysis_history: [], status_history: [{ status: 'reported', actor: 'Tech', at: '2026-01-01T00:00:00Z' }],
    current_work_order: null,
  }

  it('shows the AI failure clearly and keeps the issue', async () => {
    const user = userEvent.setup()
    api.getIssue.mockResolvedValue(issue)
    api.analyzeIssue.mockRejectedValue({ response: { status: 502, data: { error: { code: 'ai_provider_error', message: 'Gemini request failed (ServerError 503).' } } } })
    renderAt('/issues/ISS-2', '/issues/:issueId', <IssueAnalysis />)

    expect(await screen.findByText('Issue ISS-2')).toBeInTheDocument()
    expect(screen.getByText('9 mm/s exceeds the critical threshold of 8 mm/s.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /analyse issue/i }))
    expect(await screen.findByText(/Analysis failed — the issue is saved/)).toBeInTheDocument()
    expect(screen.getByText(/Gemini request failed/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /analyse issue/i })).toBeEnabled() // retry possible
  })
})
