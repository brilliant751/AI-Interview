import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom'

import { AppLayout } from '../components/AppLayout'
import { HistoryPage } from '../pages/HistoryPage'
import { InterviewPage } from '../pages/InterviewPage'
import { InterviewPreparePage } from '../pages/InterviewPreparePage'
import { ReportPage } from '../pages/ReportPage'
import { ResumeUploadPage } from '../pages/ResumeUploadPage'

/** 应用路由入口组件。 */
export function AppRouter() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Navigate to="/upload" replace />} />
          <Route path="/upload" element={<ResumeUploadPage />} />
          <Route path="/prepare" element={<InterviewPreparePage />} />
          <Route path="/interview" element={<InterviewPage />} />
          <Route path="/report" element={<ReportPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="*" element={<Navigate to="/upload" replace />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  )
}

