import { Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import MainLayout from './layouts/MainLayout.jsx'
import AdminDashboardPage from './pages/AdminDashboardPage.jsx'
import AdminDocumentsPage from './pages/AdminDocumentsPage.jsx'
import ChatPage from './pages/ChatPage.jsx'
import EvaluationPage from './pages/EvaluationPage.jsx'
import HomePage from './pages/HomePage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'
import RetrievalPlaygroundPage from './pages/RetrievalPlaygroundPage.jsx'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<MainLayout />}>
          <Route index element={<HomePage />} />
          {/* One route (optional param) so ChatPage is not remounted after the first answer */}
          <Route path="chat/:conversationId?" element={<ChatPage />} />
          <Route path="login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="admin" element={<AdminDashboardPage />} />
            <Route path="admin/documents" element={<AdminDocumentsPage />} />
            <Route path="admin/retrieval" element={<RetrievalPlaygroundPage />} />
            <Route path="admin/evaluation" element={<EvaluationPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
