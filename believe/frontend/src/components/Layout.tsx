import { useState, useRef, useEffect } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { Beaker, History, LogOut, Settings, Sliders, Database, FolderPlus, ChevronDown, Check } from 'lucide-react'
import clsx from 'clsx'
import { useProject } from '../lib/ProjectContext'
import api from '../lib/axios'

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { projects, currentProject, refreshProjects, isLoading } = useProject()

  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectDesc, setNewProjectDesc] = useState('')

  const navItems = [
    { name: 'Analysis', path: 'analysis', icon: Beaker },
    { name: 'History', path: 'history', icon: History },
    { name: 'Datasets', path: 'datasets', icon: Database },
    { name: 'Configuration', path: 'configs', icon: Sliders },
    { name: 'Project Settings', path: 'settings', icon: Settings },
  ]

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await api.post('/projects', { name: newProjectName, description: newProjectDesc })
      await refreshProjects()
      if (res.data) {
        navigate(`/${res.data.id}/analysis`)
      }
      setShowCreateModal(false)
      setNewProjectName('')
      setNewProjectDesc('')
    } catch (err) {
      alert("Failed to create project")
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
      </div>
    )
  }

  return (
    <div className="h-screen overflow-hidden bg-slate-50 text-slate-900 flex relative">
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col z-10 overflow-y-auto">
        <div className="p-6 border-b border-slate-200">
          <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-teal-400 bg-clip-text text-transparent mb-6">
            Believe
          </h1>

          {/* Project Selector */}
          <div className="mb-2 px-1">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Current Project</span>
          </div>
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg hover:border-slate-300 transition-colors text-sm"
            >
              <span className="font-semibold text-slate-700 truncate mr-2">
                {currentProject?.name || "Select Project"}
              </span>
              <ChevronDown size={16} className="text-slate-500 shrink-0" />
            </button>

            {isDropdownOpen && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 shadow-lg rounded-lg py-1 max-h-60 overflow-y-auto">
                <div className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                  Your Workspaces
                </div>
                {projects.map(p => (
                  <button
                    key={p.id}
                    onClick={() => {
                      navigate(`/${p.id}/analysis`)
                      setIsDropdownOpen(false)
                    }}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 flex items-center justify-between"
                  >
                    <span className="truncate text-slate-700">{p.name}</span>
                    {currentProject?.id === p.id && <Check size={14} className="text-blue-600 shrink-0" />}
                  </button>
                ))}
                <div className="border-t border-slate-100 mt-1 pt-1">
                  <button
                    onClick={() => {
                      setShowCreateModal(true)
                      setIsDropdownOpen(false)
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-blue-600 hover:bg-blue-50 flex items-center gap-2"
                  >
                    <FolderPlus size={14} />
                    New Project
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname.startsWith(item.path)
            return (
              <Link
                key={item.path}
                to={item.path}
                className={clsx(
                  "flex items-center gap-3 px-4 py-3 rounded-lg transition-colors",
                  isActive
                    ? "bg-blue-50 text-blue-600"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                )}
              >
                <Icon size={20} />
                <span className="font-medium">{item.name}</span>
              </Link>
            )
          })}
        </nav>

        <div className="p-4 border-t border-slate-200">
          <button
            onClick={() => {
              localStorage.removeItem('token');
              window.location.href = '/login';
            }}
            className="flex items-center gap-3 px-4 py-3 w-full text-slate-600 hover:text-red-500 hover:bg-slate-50 rounded-lg transition-colors"
          >
            <LogOut size={20} />
            <span className="font-medium">Sign Out</span>
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto bg-slate-50 relative z-0">
        <div className="p-8 max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>

      {/* Modals */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-md p-6">
            <h3 className="text-xl font-bold text-slate-900 mb-4">Create New Project</h3>
            <form onSubmit={handleCreateProject}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Project Name</label>
                  <input
                    type="text"
                    required
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g. Cancer Research"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Description (Optional)</label>
                  <textarea
                    value={newProjectDesc}
                    onChange={(e) => setNewProjectDesc(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Brief description of this workspace"
                    rows={3}
                  />
                </div>
              </div>
              <div className="mt-6 flex gap-3 justify-end">
                {projects.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                )}
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                >
                  Create Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
