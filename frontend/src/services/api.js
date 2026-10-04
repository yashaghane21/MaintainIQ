import axios from 'axios'

export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export const http = axios.create({
  baseURL: API_URL,
  timeout: 120_000, // AI analysis can take a while
})

/** Normalise backend/network errors into a user-facing message. */
export function getErrorMessage(error, fallback = 'Something went wrong. Please try again.') {
  if (!error) return fallback
  if (error.code === 'ECONNABORTED') return 'The request timed out. Please try again.'
  if (!error.response) return `Cannot reach the MaintainIQ API at ${API_URL}. Check that the backend is running.`
  const body = error.response.data?.error
  if (body?.code === 'validation_error' && Array.isArray(body.details) && body.details.length) {
    return body.details.map((d) => `${d.field || 'request'}: ${d.message}`).join('; ')
  }
  return body?.message || fallback
}

export function getErrorCode(error) {
  return error?.response?.data?.error?.code
}

const data = (promise) => promise.then((r) => r.data)
const clean = (params) => Object.fromEntries(Object.entries(params || {}).filter(([, v]) => v !== '' && v != null))

export const api = {
  health: () => data(http.get('/api/health')),
  dashboard: () => data(http.get('/api/dashboard/summary')),
  thresholds: () => data(http.get('/api/thresholds')),

  listEquipment: (params) => data(http.get('/api/equipment', { params: clean(params) })),
  getEquipment: (id) => data(http.get(`/api/equipment/${encodeURIComponent(id)}`)),
  getEquipmentHistory: (id) => data(http.get(`/api/equipment/${encodeURIComponent(id)}/history`)),
  createEquipment: (body) => data(http.post('/api/equipment', body)),

  listIssues: (params) => data(http.get('/api/issues', { params: clean(params) })),
  getIssue: (id) => data(http.get(`/api/issues/${encodeURIComponent(id)}`)),
  createIssue: (body) => data(http.post('/api/issues', body)),
  analyzeIssue: (id, body) => data(http.post(`/api/issues/${encodeURIComponent(id)}/analyze`, body || {})),
  getEvidence: (id) => data(http.get(`/api/issues/${encodeURIComponent(id)}/evidence`)),

  listWorkOrders: (params) => data(http.get('/api/work-orders', { params: clean(params) })),
  getWorkOrder: (id) => data(http.get(`/api/work-orders/${encodeURIComponent(id)}`)),
  updateWorkOrder: (id, body) => data(http.patch(`/api/work-orders/${encodeURIComponent(id)}`, body)),
  approveWorkOrder: (id, body) => data(http.post(`/api/work-orders/${encodeURIComponent(id)}/approve`, body)),
  rejectWorkOrder: (id, body) => data(http.post(`/api/work-orders/${encodeURIComponent(id)}/reject`, body)),

  listDocuments: (params) => data(http.get('/api/knowledge', { params: clean(params) })),
  getDocumentChunks: (id) => data(http.get(`/api/knowledge/${encodeURIComponent(id)}/chunks`)),
  uploadDocument: (formData) => data(http.post('/api/knowledge/upload', formData)),
  reindexDocument: (id) => data(http.post(`/api/knowledge/${encodeURIComponent(id)}/reindex`)),
  deleteDocument: (id) => data(http.delete(`/api/knowledge/${encodeURIComponent(id)}`)),
  searchKnowledge: (body) => data(http.post('/api/knowledge/search', body)),
}
