import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/ui/Layout'
import ChatPage from '@/pages/ChatPage'
import DashboardPage from '@/pages/DashboardPage'
import HistoryPage from '@/pages/HistoryPage'
import UploadPage from '@/pages/UploadPage'
import MetricsPage from '@/pages/MetricsPage'
import ProfilePage from '@/pages/ProfilePage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
      </Route>
    </Routes>
  )
}
