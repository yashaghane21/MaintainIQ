import { lazy } from 'react'
import { Route, Routes } from 'react-router-dom'
import { Compass } from 'lucide-react'
import DashboardLayout from '@/layouts/DashboardLayout'
import { ButtonLink } from '@/components/ui/button'
import { EmptyState } from '@/components/common/States'

// Route-level code splitting: each page (and Recharts on the dashboard) loads on demand.
const page = (load) => lazy(load)
const Dashboard = page(() => import('@/pages/Dashboard'))
const Equipment = page(() => import('@/pages/Equipment'))
const EquipmentDetails = page(() => import('@/pages/EquipmentDetails'))
const ReportIssue = page(() => import('@/pages/ReportIssue'))
const IssueAnalysis = page(() => import('@/pages/IssueAnalysis'))
const IssueHistory = page(() => import('@/pages/IssueHistory'))
const WorkOrders = page(() => import('@/pages/WorkOrders'))
const WorkOrderDetails = page(() => import('@/pages/WorkOrderDetails'))
const KnowledgeBase = page(() => import('@/pages/KnowledgeBase'))
const Settings = page(() => import('@/pages/Settings'))

function NotFound() {
  return <EmptyState icon={Compass} title="Page not found" description="The page you requested does not exist." action={<ButtonLink to="/">Go to overview</ButtonLink>} />
}

export default function App() {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="equipment" element={<Equipment />} />
        <Route path="equipment/:equipmentId" element={<EquipmentDetails />} />
        <Route path="report" element={<ReportIssue />} />
        <Route path="issues" element={<IssueHistory />} />
        <Route path="issues/:issueId" element={<IssueAnalysis />} />
        <Route path="work-orders" element={<WorkOrders />} />
        <Route path="work-orders/:workOrderId" element={<WorkOrderDetails />} />
        <Route path="knowledge" element={<KnowledgeBase />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
