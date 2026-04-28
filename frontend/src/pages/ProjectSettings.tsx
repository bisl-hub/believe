import { useState, useEffect } from 'react'
import { useProject } from '../lib/ProjectContext'
import api from '../lib/axios'
import { Save, UserPlus, FolderEdit, Trash2, ShieldAlert, Key, Copy, Eye, EyeOff, Plus, X } from 'lucide-react'

interface UserResponse {
    id: number;
    email: string;
    is_active: boolean;
}

interface ApiKey {
    id: number;
    name: string;
    key_prefix: string;
    is_active: boolean;
    created_at: string;
    last_used_at: string | null;
}

interface ApiKeyCreated extends ApiKey {
    key: string;
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

    // API Keys state
    const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
    const [isLoadingKeys, setIsLoadingKeys] = useState(false)
    const [newKeyName, setNewKeyName] = useState('')
    const [isCreatingKey, setIsCreatingKey] = useState(false)
    const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null)
    const [showKeyValue, setShowKeyValue] = useState(false)
    const [copiedKey, setCopiedKey] = useState(false)

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

    const fetchApiKeys = async () => {
        if (!currentProject) return
        setIsLoadingKeys(true)
        try {
            const res = await api.get(`/projects/${currentProject.id}/api-keys`)
            setApiKeys(res.data)
        } catch (err) {
            console.error(err)
        } finally {
            setIsLoadingKeys(false)
        }
    }

    useEffect(() => {
        if (currentProject) {
            setName(currentProject.name)
            setDescription(currentProject.description || '')
            fetchMembers()
            fetchApiKeys()
        }
    }, [currentProject])

    const handleUpdateProject = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!currentProject) return

        setIsSaving(true)
        try {
            await api.put(`/projects/${currentProject.id}`, { name, description })
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
        const confirmDelete = window.confirm(
            `Are you sure you want to delete the project '${currentProject.name}'? This action cannot be undone and will destroy all associated data.`
        )
        if (confirmDelete) {
            try {
                await api.delete(`/projects/${currentProject.id}`)
                window.location.href = '/'
            } catch (err: any) {
                console.error(err)
                alert(err.response?.data?.detail || "Failed to delete project")
            }
        }
    }

    const handleCreateApiKey = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!currentProject || !newKeyName.trim()) return
        setIsCreatingKey(true)
        try {
            const res = await api.post(`/projects/${currentProject.id}/api-keys`, { name: newKeyName.trim() })
            setCreatedKey(res.data)
            setNewKeyName('')
            setShowKeyValue(true)
            fetchApiKeys()
        } catch (err: any) {
            console.error(err)
            alert(err.response?.data?.detail || "Failed to create API key")
        } finally {
            setIsCreatingKey(false)
        }
    }

    const handleDeleteApiKey = async (keyId: number) => {
        if (!currentProject) return
        if (!window.confirm("Revoke this API key? All integrations using it will stop working immediately.")) return
        try {
            await api.delete(`/projects/${currentProject.id}/api-keys/${keyId}`)
            fetchApiKeys()
        } catch (err: any) {
            alert(err.response?.data?.detail || "Failed to revoke API key")
        }
    }

    const handleCopyKey = () => {
        if (!createdKey) return
        navigator.clipboard.writeText(createdKey.key)
        setCopiedKey(true)
        setTimeout(() => setCopiedKey(false), 2000)
    }

    const formatDate = (iso: string | null) => {
        if (!iso) return 'Never'
        return new Date(iso).toLocaleDateString('en-US', {
            year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        })
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
                <p className="text-slate-500">Manage your workspace configuration, team members, and API access.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                {/* Left Column */}
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

                    <div className="bg-red-50 p-6 rounded-xl border border-red-200 shadow-sm">
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

                {/* Right Column */}
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
                        <p className="text-slate-500 text-sm mb-4">
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

            {/* API Keys — Full Width */}
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <div className="flex items-center justify-between mb-6 border-b border-slate-100 pb-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-violet-50 text-violet-600 rounded-lg">
                            <Key size={24} />
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-slate-800">API Keys</h2>
                            <p className="text-sm text-slate-500 mt-0.5">
                                Use these keys to access this project via the{' '}
                                <a href="/api-docs" target="_blank" className="text-violet-600 hover:underline font-medium">
                                    REST API
                                </a>{' '}
                                — no login required.
                            </p>
                        </div>
                    </div>
                </div>

                {/* New key revealed banner */}
                {createdKey && (
                    <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                        <div className="flex items-start justify-between mb-2">
                            <div>
                                <p className="text-sm font-semibold text-amber-800">Key created — save it now!</p>
                                <p className="text-xs text-amber-600 mt-0.5">This is the only time the full key will be shown.</p>
                            </div>
                            <button onClick={() => setCreatedKey(null)} className="text-amber-400 hover:text-amber-600">
                                <X size={16} />
                            </button>
                        </div>
                        <div className="flex items-center gap-2 mt-3">
                            <code className="flex-1 font-mono text-sm bg-white border border-amber-200 rounded px-3 py-2 text-slate-800 break-all">
                                {showKeyValue ? createdKey.key : createdKey.key.replace(/./g, '•')}
                            </code>
                            <button
                                onClick={() => setShowKeyValue(v => !v)}
                                className="p-2 text-amber-600 hover:bg-amber-100 rounded"
                                title={showKeyValue ? 'Hide key' : 'Show key'}
                            >
                                {showKeyValue ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                            <button
                                onClick={handleCopyKey}
                                className="flex items-center gap-1.5 px-3 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium rounded transition-colors"
                            >
                                <Copy size={14} />
                                {copiedKey ? 'Copied!' : 'Copy'}
                            </button>
                        </div>
                    </div>
                )}

                {/* Existing keys list */}
                <div className="mb-6">
                    {isLoadingKeys ? (
                        <p className="text-sm text-slate-500">Loading keys...</p>
                    ) : apiKeys.length === 0 ? (
                        <p className="text-sm text-slate-400 text-center py-6">No API keys yet. Create one below.</p>
                    ) : (
                        <div className="space-y-2">
                            {apiKeys.map(k => (
                                <div key={k.id} className="flex items-center justify-between px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg">
                                    <div className="flex items-center gap-3">
                                        <Key size={15} className="text-slate-400 shrink-0" />
                                        <div>
                                            <span className="text-sm font-medium text-slate-800">{k.name}</span>
                                            <div className="flex items-center gap-3 mt-0.5">
                                                <code className="text-xs text-slate-400 font-mono">{k.key_prefix}••••••••••••••••</code>
                                                <span className="text-xs text-slate-400">
                                                    Created {formatDate(k.created_at)}
                                                </span>
                                                {k.last_used_at && (
                                                    <span className="text-xs text-slate-400">
                                                        Last used {formatDate(k.last_used_at)}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => handleDeleteApiKey(k.id)}
                                        className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                                        title="Revoke key"
                                    >
                                        <Trash2 size={15} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Create new key form */}
                <form onSubmit={handleCreateApiKey} className="flex items-center gap-3 border-t border-slate-100 pt-5">
                    <input
                        type="text"
                        value={newKeyName}
                        onChange={(e) => setNewKeyName(e.target.value)}
                        placeholder="Key name (e.g. Production, CI pipeline)"
                        className="flex-1 px-4 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition-colors"
                        required
                    />
                    <button
                        type="submit"
                        disabled={isCreatingKey || !newKeyName.trim()}
                        className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 whitespace-nowrap"
                    >
                        <Plus size={16} />
                        {isCreatingKey ? 'Creating...' : 'Create Key'}
                    </button>
                </form>
            </div>
        </div>
    )
}
