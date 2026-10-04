import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'

export const keys = {
  health: ['health'],
  dashboard: ['dashboard'],
  thresholds: ['thresholds'],
  equipment: (params) => ['equipment', params ?? {}],
  equipmentOne: (id) => ['equipment', 'detail', id],
  equipmentHistory: (id) => ['equipment', 'history', id],
  issues: (params) => ['issues', params ?? {}],
  issue: (id) => ['issue', id],
  evidence: (id) => ['issue', id, 'evidence'],
  workOrders: (params) => ['work-orders', params ?? {}],
  workOrder: (id) => ['work-order', id],
  documents: ['documents'],
  chunks: (id) => ['documents', id, 'chunks'],
}

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.health, refetchInterval: 60_000 })
export const useDashboard = () => useQuery({ queryKey: keys.dashboard, queryFn: api.dashboard })
export const useThresholds = () => useQuery({ queryKey: keys.thresholds, queryFn: api.thresholds, staleTime: Infinity })

export const useEquipmentList = (params) => useQuery({ queryKey: keys.equipment(params), queryFn: () => api.listEquipment(params) })
export const useEquipment = (id) => useQuery({ queryKey: keys.equipmentOne(id), queryFn: () => api.getEquipment(id), enabled: !!id })
export const useEquipmentHistory = (id) =>
  useQuery({ queryKey: keys.equipmentHistory(id), queryFn: () => api.getEquipmentHistory(id), enabled: !!id })

export const useIssues = (params) => useQuery({ queryKey: keys.issues(params), queryFn: () => api.listIssues(params) })
export const useIssue = (id) => useQuery({ queryKey: keys.issue(id), queryFn: () => api.getIssue(id), enabled: !!id })
export const useEvidence = (id, enabled = true) =>
  useQuery({ queryKey: keys.evidence(id), queryFn: () => api.getEvidence(id), enabled: !!id && enabled })

export const useWorkOrders = (params) => useQuery({ queryKey: keys.workOrders(params), queryFn: () => api.listWorkOrders(params) })
export const useWorkOrder = (id) => useQuery({ queryKey: keys.workOrder(id), queryFn: () => api.getWorkOrder(id), enabled: !!id })

export const useDocuments = () =>
  useQuery({
    queryKey: keys.documents,
    queryFn: () => api.listDocuments(),
    // Poll while any document is still being ingested.
    refetchInterval: (query) =>
      query.state.data?.some((d) => ['pending', 'processing'].includes(d.ingestion_status)) ? 2000 : false,
  })
export const useDocumentChunks = (id) => useQuery({ queryKey: keys.chunks(id), queryFn: () => api.getDocumentChunks(id), enabled: !!id })

/** Invalidate everything an issue/work-order change can affect. */
function useInvalidateOps() {
  const qc = useQueryClient()
  return () =>
    Promise.all(
      [['issue'], ['issues'], ['work-orders'], ['work-order'], ['dashboard'], ['equipment']].map((queryKey) =>
        qc.invalidateQueries({ queryKey }),
      ),
    )
}

export function useCreateIssue() {
  const invalidate = useInvalidateOps()
  return useMutation({ mutationFn: api.createIssue, onSuccess: invalidate })
}

export function useAnalyzeIssue(issueId) {
  const invalidate = useInvalidateOps()
  // Invalidate on error too: the backend records failed attempts on the issue.
  return useMutation({ mutationFn: (body) => api.analyzeIssue(issueId, body), onSettled: invalidate })
}

export function useCreateEquipment() {
  const invalidate = useInvalidateOps()
  return useMutation({ mutationFn: api.createEquipment, onSuccess: invalidate })
}

export function useUpdateWorkOrder(id) {
  const invalidate = useInvalidateOps()
  return useMutation({ mutationFn: (body) => api.updateWorkOrder(id, body), onSuccess: invalidate })
}

export function useApproveWorkOrder(id) {
  const invalidate = useInvalidateOps()
  return useMutation({ mutationFn: (body) => api.approveWorkOrder(id, body), onSettled: invalidate })
}

export function useRejectWorkOrder(id) {
  const invalidate = useInvalidateOps()
  return useMutation({ mutationFn: (body) => api.rejectWorkOrder(id, body), onSettled: invalidate })
}

export function useUploadDocument() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: api.uploadDocument, onSuccess: () => qc.invalidateQueries({ queryKey: keys.documents }) })
}

export function useDocumentAction(action) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: action, onSettled: () => qc.invalidateQueries({ queryKey: keys.documents }) })
}
