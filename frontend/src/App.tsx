import { Routes, Route, Navigate } from 'react-router-dom'
import { Step1Page } from './pages/Step1Page'
import { Step2Page } from './pages/Step2Page'
import { Step3Page } from './pages/Step3Page'
import { Step4Page } from './pages/Step4Page'
import { SettingsPage } from './pages/SettingsPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Step1Page />} />
      <Route path="/upload" element={<Navigate to="/" replace />} />
      <Route path="/edit/:taskId" element={<Step2Page />} />
      <Route path="/confirm/:taskId" element={<Step3Page />} />
      <Route path="/result/:taskId" element={<Step4Page />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
