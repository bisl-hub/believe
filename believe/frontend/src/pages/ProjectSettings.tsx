import { useState, useEffect } from 'react'
import { useProject } from '../lib/ProjectContext'
import api from '../lib/axios'
import { Save, UserPlus, FolderEdit, Trash2, ShieldAlert } from 'lucide-react'

interface UserResponse {
    id: number;
    email: string;
    is_active: boolean;
}

export default function ProjectSettings() {
    const { currentProject, refreshProjects } = useProject()

    const [name, setName] = useState('')
    const [description, setDescription] = useState('')
    const [isSaving, setIsSaving] = useState(false)

    const [inviteEmail, setInviteEmail] = useState('')
    const [isInviting, setIsInviting] = useState(false)

    const [members, setMembers] = useState<UserResponse[]>([])
    const [isLoadingMembers, setIsLoadingMembers] = useState(false)

    const fetchMembers = async () => {
        if (!currentProject) return
        setIsLoadingMembers(true)
        try {
            const res = await api.get(`/projects/${currentProject.id}/members`)
            setMembers(res.data)
        } catch (err) {
            console.error(err)
        } finally {
            setIsLoadingMembers(false)
        }
    }

    // Sync state with current project
    useEffect(() => {
        if (currentProject) {
            setName(currentProject.name)
            setDescription(currentProject.description || '')
            fetchMembers()
        }
    }, [currentProject])

    const handleUpdateProject = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!currentProject) return

        setIsSaving(true)
        try {
            await api.put(`/projects/${currentProject.id}`, {
                name,
                description
            })
            await refreshProjects()
            alert("Project updated successfully!")
        } catch (err: any) {
            console.error(err)
            alert("Failed to update project")
        } finally {
            setIsSaving(false)
        }
    }

    const handleInviteUser = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!currentProject) return

        setIsInviting(true)
        try {
            await api.post(`/projects/${currentProject.id}/invite`, { email: inviteEmail })
            alert(`Successfully invited ${inviteEmail}`)
            setInviteEmail('')
            fetchMembers()
        } catch (err: any) {
            console.error(err)
            alert(err.response?.data?.detail || "Failed to invite user")
        } finally {
            setIsInviting(false)
        }
    }

    const handleDeleteProject = async () => {
        if (!currentProject) return
        const confirmDelete = window.confirm(`Are you sure you want to delete the project '${currentProject.name}'? This action cannot be undone and will destroy all associated data.`)

        if (confirmDelete) {
            try {
                await api.delete(`/projects/${currentProject.id}`)
                window.location.href = '/' // Force full refresh to clear context and fall back
            } catch (err: any) {
                console.error(err)
                alert(err.response?.data?.detail || "Failed to delete project")
            }
        }
    }

    if (!currentProject) {
        return (
            <div className="flex items-center justify-center h-64 text-slate-500">
                No project selected.
            </div>
        )
    }

    return (
        <div className="max-w-4xl mx-auto space-y-8">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 mb-2">Project Settings</h1>
                <p className="text-slate-500">Manage your workspace configuration and team members.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                {/* Left Column: General Settings */}
                <div className="space-y-8">
                    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                        <div className="flex items-center gap-3 mb-6 border-b border-slate-100 pb-4">
                            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
                                <FolderEdit size={24} />
                            </div>
                            <h2 className="text-lg font-semibold text-slate-800">General Information</h2>
                        </div>

                        <form onSubmit={handleUpdateProject} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Project Name</label>
                                <input
                                    type="text"
                                    required
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                                <textarea
                                    rows={4}
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors resize-none"
                                    placeholder="Describe your project's goals..."
                                />
                            </div>

                            <div className="pt-2">
                                <button
                                    type="submit"
                                    disabled={isSaving}
                                    className="flex items-center justify-center gap-2 w-full px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-medium text-sm rounded-lg transition-colors disabled:opacity-50"
                                >
                                    <Save size={16} />
                                    {isSaving ? 'Saving Changes...' : 'Save Changes'}
                                </button>
                            </div>
                        </form>
                    </div>

                    <div className="bg-red-50 p-6 rounded-xl border border-red-200 shadow-sm mt-8">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-2 bg-red-100 text-red-600 rounded-lg">
                                <ShieldAlert size={24} />
                            </div>
                            <h2 className="text-lg font-semibold text-red-800">Danger Zone</h2>
                        </div>
                        <p className="text-red-600 text-sm mb-6">
                            Once you delete a project, there is no going back. Please be certain.
                        </p>
                        <button
                            onClick={handleDeleteProject}
                            className="flex items-center justify-center gap-2 w-full px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-medium text-sm rounded-lg transition-colors shadow-sm"
                        >
                            <Trash2 size={16} />
                            Delete Project
                        </button>
                    </div>
                </div>

                {/* Right Column: Team Management */}
                <div className="space-y-8">
                    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                        <div className="flex items-center gap-3 mb-6 border-b border-slate-100 pb-4">
                            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
                                <UserPlus size={24} />
                            </div>
                            <h2 className="text-lg font-semibold text-slate-800">Team Members</h2>
                        </div>

                        <div className="mb-6">
                            <h3 className="text-sm font-semibold text-slate-700 mb-3">Current Members</h3>
                            {isLoadingMembers ? (
                                <div className="text-sm text-slate-500">Loading members...</div>
                            ) : (
                                <ul className="space-y-2">
                                    {members.map(member => (
                                        <li key={member.id} className="flex items-center gap-2 text-sm text-slate-600 bg-slate-50 px-3 py-2 rounded-lg border border-slate-100">
                                            <span className={`w-2 h-2 rounded-full ${member.is_active ? 'bg-emerald-500' : 'bg-slate-300'}`}></span>
                                            {member.email}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>

                        <h3 className="text-sm font-semibold text-slate-700 mb-3 border-t border-slate-100 pt-4">Invite New Member</h3>
                        <p className="text-slate-500 text-sm mb-6">
                            Invite a colleague to collaborate on this workspace. They must already have a registered account.
                        </p>

                        <form onSubmit={handleInviteUser} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Email Address</label>
                                <input
                                    type="email"
                                    required
                                    value={inviteEmail}
                                    onChange={(e) => setInviteEmail(e.target.value)}
                                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-colors"
                                    placeholder="colleague@example.com"
                                />
                            </div>

                            <div className="pt-2">
                                <button
                                    type="submit"
                                    disabled={isInviting || !inviteEmail}
                                    className="flex items-center justify-center gap-2 w-full px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm rounded-lg transition-colors disabled:opacity-50"
                                >
                                    <UserPlus size={16} />
                                    {isInviting ? 'Sending Invite...' : 'Send Invitation'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>

            </div>
        </div>
    )
}
