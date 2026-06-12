import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import Layout from '@/components/layout/Layout'
import ProtectedRoute from '@/components/layout/ProtectedRoute'
import AdminRoute from '@/components/layout/AdminRoute'
import StaffOrAdminRoute from '@/components/layout/StaffOrAdminRoute'
import { Spinner } from '@/components/ui'
import ErrorBoundary from '@/components/ui/ErrorBoundary'
import { LanguageProvider } from '@/lib/i18n'

const LoginPage          = lazy(() => import('@/pages/LoginPage'))
const RegisterPage       = lazy(() => import('@/pages/RegisterPage'))
const DashboardPage      = lazy(() => import('@/pages/DashboardPage'))
const TicketListPage     = lazy(() => import('@/pages/TicketListPage'))
const NewTicketPage      = lazy(() => import('@/pages/NewTicketPage'))
const TicketDetailPage   = lazy(() => import('@/pages/TicketDetailPage'))
const ProjectsPage       = lazy(() => import('@/pages/ProjectsPage'))
const ProjectDetailPage  = lazy(() => import('@/pages/ProjectDetailPage'))
const ServicesPage       = lazy(() => import('@/pages/ServicesPage'))
const NotificationsPage      = lazy(() => import('@/pages/NotificationsPage'))
const SubscriptionDashboard  = lazy(() => import('@/pages/SubscriptionDashboard'))
const SubscriptionDetailPage = lazy(() => import('@/components/SubscriptionDetail'))

const InvoicesPage       = lazy(() => import('@/pages/InvoicesPage'))
const AdminInvoicesPage  = lazy(() => import('@/pages/admin/InvoicesPage'))

const ChangePasswordPage = lazy(() => import('@/pages/ChangePasswordPage'))
const AccountSecurityPage = lazy(() => import('@/pages/AccountSecurityPage'))
const ProfilePage = lazy(() => import('@/pages/ProfilePage'))

// Admin pages
const OrganizationsPage  = lazy(() => import('@/pages/admin/OrganizationsPage'))
const UsersPage          = lazy(() => import('@/pages/admin/UsersPage'))
const SlaPoliciesPage    = lazy(() => import('@/pages/admin/SlaPoliciesPage'))
const ItemsPage          = lazy(() => import('@/pages/admin/ItemsPage'))
const SubscriptionsPage  = lazy(() => import('@/pages/admin/SubscriptionsPage'))
const SetupWizard              = lazy(() => import('@/pages/admin/SetupWizard'))
const StaffAssignmentsPage     = lazy(() => import('@/pages/admin/StaffAssignmentsPage'))
const AnalyticsDashboard       = lazy(() => import('@/pages/admin/AnalyticsDashboard'))
const SystemStatusPage         = lazy(() => import('@/pages/admin/SystemStatusPage'))
const EmailOutboxPage          = lazy(() => import('@/pages/admin/EmailOutboxPage'))

function PageFallback() {
  return (
    <div className="flex items-center justify-center h-full min-h-[200px]">
      <Spinner className="w-6 h-6" />
    </div>
  )
}

function ProtectedLayout({ children }) {
  return (
    <ProtectedRoute>
      <Layout>
        <Suspense fallback={<PageFallback />}>
          {children}
        </Suspense>
      </Layout>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <LanguageProvider>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ErrorBoundary>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/login"    element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/"                 element={<ProtectedLayout><DashboardPage /></ProtectedLayout>} />
          <Route path="/tickets"          element={<ProtectedLayout><TicketListPage /></ProtectedLayout>} />
          <Route path="/tickets/new"      element={<ProtectedLayout><NewTicketPage /></ProtectedLayout>} />
          <Route path="/tickets/:id"      element={<ProtectedLayout><TicketDetailPage /></ProtectedLayout>} />
          <Route path="/projects"         element={<ProtectedLayout><ProjectsPage /></ProtectedLayout>} />
          <Route path="/projects/:id"     element={<ProtectedLayout><ProjectDetailPage /></ProtectedLayout>} />
          <Route path="/services"         element={<ProtectedLayout><ServicesPage /></ProtectedLayout>} />
          <Route path="/notifications"    element={<ProtectedLayout><NotificationsPage /></ProtectedLayout>} />
          <Route path="/subscriptions"    element={<ProtectedLayout><SubscriptionDashboard /></ProtectedLayout>} />
          <Route path="/subscriptions/:name" element={<ProtectedLayout><SubscriptionDetailPage /></ProtectedLayout>} />
          <Route path="/invoices"         element={<ProtectedLayout><InvoicesPage /></ProtectedLayout>} />
          <Route path="/change-password" element={<ProtectedLayout><ChangePasswordPage /></ProtectedLayout>} />
          <Route path="/account/security" element={<ProtectedLayout><AccountSecurityPage /></ProtectedLayout>} />
          <Route path="/profile"         element={<ProtectedLayout><ProfilePage /></ProtectedLayout>} />
          <Route path="/preferences"     element={<ProtectedLayout><ProfilePage /></ProtectedLayout>} />

          {/* Admin-only routes */}
          <Route path="/admin/organizations" element={
            <ProtectedLayout>
              <AdminRoute><OrganizationsPage /></AdminRoute>
            </ProtectedLayout>
          } />
          <Route path="/admin/users" element={
            <ProtectedLayout>
              <AdminRoute><UsersPage /></AdminRoute>
            </ProtectedLayout>
          } />
          <Route path="/admin/sla" element={
            <ProtectedLayout>
              <AdminRoute><SlaPoliciesPage /></AdminRoute>
            </ProtectedLayout>
          } />
          <Route path="/admin/items" element={
            <ProtectedLayout>
              <AdminRoute><ItemsPage /></AdminRoute>
            </ProtectedLayout>
          } />
          <Route path="/admin/subscriptions" element={
            <ProtectedLayout>
              <AdminRoute><SubscriptionsPage /></AdminRoute>
            </ProtectedLayout>
          } />
          <Route path="/admin/invoices" element={
            <ProtectedLayout>
              <AdminRoute><AdminInvoicesPage /></AdminRoute>
            </ProtectedLayout>
          } />
          <Route path="/admin/setup" element={
            <ProtectedLayout>
              <AdminRoute><SetupWizard /></AdminRoute>
            </ProtectedLayout>
          } />
          <Route path="/admin/staff-assignments" element={
            <ProtectedLayout>
              <AdminRoute><StaffAssignmentsPage /></AdminRoute>
            </ProtectedLayout>
          } />
          <Route path="/admin/analytics" element={
            <ProtectedLayout>
              <StaffOrAdminRoute><AnalyticsDashboard /></StaffOrAdminRoute>
            </ProtectedLayout>
          } />
          <Route path="/admin/system" element={
            <ProtectedLayout>
              <AdminRoute><SystemStatusPage /></AdminRoute>
            </ProtectedLayout>
          } />
          <Route path="/admin/email-outbox" element={
            <ProtectedLayout>
              <AdminRoute><EmailOutboxPage /></AdminRoute>
            </ProtectedLayout>
          } />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      </ErrorBoundary>
    </BrowserRouter>
    </LanguageProvider>
  )
}
