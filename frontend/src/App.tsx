import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import api from './lib/axios'
import Login from './pages/Login'
import Analysis from './pages/Analysis'
import JobDetail from './pages/JobDetail'
import History from './pages/History'
import Datasets from './pages/Datasets'
import Configs from './pages/Configs'
import ProjectSettings from './pages/ProjectSettings'
import ApiDocs from './pages/ApiDocs'
import Layout from './components/Layout'
import { ProjectProvider } from './lib/ProjectContext'

// Protected Route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('token')

  if (!token) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function RootRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    api.get('/projects').then(res => {
      if (res.data.length > 0) {
        const id = localStorage.getItem('currentProjectId') || res.data[0].id;
        const validId = res.data.find((p: any) => p.id === parseInt(id.toString())) ? id : res.data[0].id;
        navigate(`/${validId}/analysis`, { replace: true });
      } else {
        // Temporary fallback if completely empty
        navigate('/1/analysis', { replace: true });
      }
    }).catch(() => {
      localStorage.removeItem('token');
      navigate('/login', { replace: true });
    })
  }, [navigate]);
  return <div className="min-h-screen bg-slate-50 flex items-center justify-center">Loading Workspace...</div>;
}

function App() {
  return (
    <Routes>
      <Route path="/api-docs" element={<ApiDocs />} />
      <Route path="/login" element={<Login />} />
      <Route path="/" element={
        <ProtectedRoute>
          <RootRedirect />
        </ProtectedRoute>
      } />
      <Route path="/:projectId" element={
        <ProtectedRoute>
          <ProjectProvider>
            <Layout />
          </ProjectProvider>
        </ProtectedRoute>
      }>
        <Route index element={<Navigate to="analysis" replace />} />
        <Route path="analysis" element={<Analysis />} />
        <Route path="history" element={<History />} />
        <Route path="datasets" element={<Datasets />} />
        <Route path="configs" element={<Navigate to="analysis" replace />} />
        <Route path="configs/:tab" element={<Configs />} />
        <Route path="settings" element={<ProjectSettings />} />
        <Route path="jobs/:id" element={<JobDetail />} />
      </Route>
    </Routes>
  )
}

export default App
