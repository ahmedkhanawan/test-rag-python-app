import { Route, Routes } from 'react-router-dom'
import MainLayout from './layouts/MainLayout.jsx'
import ChatPage from './pages/ChatPage.jsx'
import HomePage from './pages/HomePage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<HomePage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
