import { Navigate, Route, BrowserRouter, Routes, useLocation } from 'react-router-dom'

import { AppLayout } from '../components/AppLayout'
import { useAuthStore } from '../stores/authStore'
import { AdminImportsPage } from '../pages/AdminImportsPage'
import { ForgotPasswordPage } from '../pages/ForgotPasswordPage'
import { HistoryPage } from '../pages/HistoryPage'
import { InterviewPage } from '../pages/InterviewPage'
import { InterviewPlaybackPage } from '../pages/InterviewPlaybackPage'
import { InterviewPreparePage } from '../pages/InterviewPreparePage'
import { LoginPage } from '../pages/LoginPage'
import { RegisterPage } from '../pages/RegisterPage'
import { ReportPage } from '../pages/ReportPage'
import { ResetPasswordPage } from '../pages/ResetPasswordPage'
import { ResumeUploadPage } from '../pages/ResumeUploadPage'
import { ResumeManagePage } from '../pages/ResumeManagePage'

/** 通用登录保护路由。 */
function ProtectedRoute(props: { children: JSX.Element }) {
  const location = useLocation()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return props.children
}

/** 管理权限路由。 */
function AdminRoute(props: { children: JSX.Element }) {
  const user = useAuthStore((state) => state.user)
  if (!user || user.role !== 'admin') {
    return <Navigate to="/prepare" replace />
  }
  return props.children
}

/** 应用路由入口组件。 */
export function AppRouter() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Navigate to={isAuthenticated ? '/prepare' : '/login'} replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route
            path="/resumes"
            element={
              <ProtectedRoute>
                <ResumeManagePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/upload"
            element={
              <ProtectedRoute>
                <ResumeUploadPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/prepare"
            element={
              <ProtectedRoute>
                <InterviewPreparePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/interview"
            element={
              <ProtectedRoute>
                <InterviewPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/report"
            element={
              <ProtectedRoute>
                <ReportPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/history"
            element={
              <ProtectedRoute>
                <HistoryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/history/:interviewId"
            element={
              <ProtectedRoute>
                <InterviewPlaybackPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/imports"
            element={
              <ProtectedRoute>
                <AdminRoute>
                  <AdminImportsPage />
                </AdminRoute>
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  )
}
