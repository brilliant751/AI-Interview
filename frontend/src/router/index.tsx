import { Navigate, Route, BrowserRouter, Routes, useLocation } from 'react-router-dom'

import { AppLayout } from '../components/AppLayout'
import { WelcomeGate } from '../components/WelcomeGate'
import { useAuthStore } from '../stores/authStore'
import { AdminImportsPage } from '../pages/AdminImportsPage'
import { CodingPracticeListPage } from '../pages/CodingPracticeListPage'
import { CodingPracticeSessionPage } from '../pages/CodingPracticeSessionPage'
import { ForgotPasswordPage } from '../pages/ForgotPasswordPage'
import { HistoryPage } from '../pages/HistoryPage'
import { HomeOverviewPage } from '../pages/HomeOverviewPage'
import { InterviewPage } from '../pages/InterviewPage'
import { InterviewPlaybackPage } from '../pages/InterviewPlaybackPage'
import { InterviewSchedulePage } from '../pages/InterviewSchedulePage'
import { JobManagePage } from '../pages/JobManagePage'
import { LoginPage } from '../pages/LoginPage'
import { PracticePreparePage } from '../pages/PracticePreparePage'
import { PracticeRecordsPage } from '../pages/PracticeRecordsPage'
import { PracticeSessionPage } from '../pages/PracticeSessionPage'
import { QuestionBankManagePage } from '../pages/QuestionBankManagePage'
import { RegisterPage } from '../pages/RegisterPage'
import { ReportPage } from '../pages/ReportPage'
import { ResetPasswordPage } from '../pages/ResetPasswordPage'
import { ResumeUploadPage } from '../pages/ResumeUploadPage'
import { ResumeManagePage } from '../pages/ResumeManagePage'

// 路由设计说明：
// 1. 未登录用户只能访问登录、注册、忘记密码和重置密码页面。
// 2. 登录后的主功能统一套 AppLayout，侧边栏和顶部用户菜单保持一致。
// 3. 管理端页面额外使用 AdminRoute，避免普通用户通过地址栏直接访问。
// 4. 面试、练习、报告等页面通过 URL 参数恢复上下文，支持刷新和分享内部链接。
// 5. 根路径根据登录状态自动跳转，减少用户进入空白首页的可能。

/** 通用登录保护路由。 */
function ProtectedRoute(props: { children: JSX.Element }) {
  // 保存当前 pathname 到 location.state.from，便于登录页后续扩展“登录后回跳”。
  const location = useLocation()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return props.children
}

/** 管理权限路由。 */
function AdminRoute(props: { children: JSX.Element }) {
  // 管理页面是前端展示层保护，真正权限仍由后端 require_admin 决定。
  // 这里的跳转主要减少普通用户看到无权限页面的机会。
  const user = useAuthStore((state) => state.user)
  if (!user || user.role !== 'admin') {
    return <Navigate to="/overview" replace />
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
          {/* 默认入口根据登录态分流，避免访问 / 时出现无内容页面。 */}
          <Route path="/" element={isAuthenticated ? <Navigate to="/overview" replace /> : <WelcomeGate />} />
          <Route
            path="/overview"
            element={
              <ProtectedRoute>
                <HomeOverviewPage />
              </ProtectedRoute>
            }
          />
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
                <Navigate to="/overview" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/schedules"
            element={
              <ProtectedRoute>
                <InterviewSchedulePage />
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
            path="/interview/:interviewId"
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
            path="/report/:interviewId"
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
            path="/jobs"
            element={
              <ProtectedRoute>
                <JobManagePage />
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
            path="/practice"
            element={
              <ProtectedRoute>
                <PracticePreparePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/coding-practice"
            element={
              <ProtectedRoute>
                <CodingPracticeListPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/coding-practice/:sessionId"
            element={
              <ProtectedRoute>
                <CodingPracticeSessionPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/practice/:practiceId"
            element={
              <ProtectedRoute>
                <PracticeSessionPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/practice/:practiceId/records"
            element={
              <ProtectedRoute>
                <PracticeRecordsPage />
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
          <Route
            path="/admin/questions"
            element={
              <ProtectedRoute>
                <AdminRoute>
                  <QuestionBankManagePage />
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
