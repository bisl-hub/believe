import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import api from '../lib/axios'
import Modal from '../components/Modal'
import { useProject } from '../lib/ProjectContext'

export default function Configs() {
    const { currentProject } = useProject()
    const { tab } = useParams<{ tab: string }>()
    const navigate = useNavigate()
    const activeTab = tab === 'model' ? 'model' : 'analysis'
    const queryClient = useQueryClient()

    // --- Analysis Config State ---
    const [editingAcId, setEditingAcId] = useState<number | null>(null)
    const [acName, setAcName] = useState('')
    const [acHypothesis, setAcHypothesis] = useState('')
    const [acDefaultDatasetId, setAcDefaultDatasetId] = useState<number | ''>('')
    const [isAnalysisModalOpen, setIsAnalysisModalOpen] = useState(false)

    const handleEditAc = (c: any) => {
        setEditingAcId(c.id)
        setAcName(c.name)
        setAcHypothesis(c.hypothesis)
        setAcDefaultDatasetId(c.default_dataset_id || '')
        setIsAnalysisModalOpen(true)
    }

    const handleCancelEditAc = () => {
        setEditingAcId(null)
        setAcName('')
        setAcHypothesis('')
        setAcDefaultDatasetId('')
        setIsAnalysisModalOpen(false)
    }

    // --- Model Config State ---
    const [editingMcId, setEditingMcId] = useState<number | null>(null)
    const [mcName, setMcName] = useState('')
    const [mcKey, setMcKey] = useState('')
    const [mcModel, setMcModel] = useState('gpt-4o')
    const [mcBaseUrl, setMcBaseUrl] = useState('https://api.openai.com/v1')
    const [mcPrompt, setMcPrompt] = useState('You are a biomedical literature reviewer.')
    const [mcConcurrency, setMcConcurrency] = useState('1024')
    const [mcTemp, setMcTemp] = useState('0.0')
    const [isModelModalOpen, setIsModelModalOpen] = useState(false)

    const handleEditMc = (c: any) => {
        setEditingMcId(c.id)
        setMcName(c.name)
        setMcKey(c.openai_api_key || '')
        setMcModel(c.openai_model || '')
        setMcBaseUrl(c.openai_base_url || '')
        setMcPrompt(c.system_prompt || '')
        setMcConcurrency(c.llm_concurrency_limit?.toString() || '1024')
        setMcTemp(c.llm_temperature?.toString() || '0.0')
        setIsModelModalOpen(true)
    }

    const handleCancelEditMc = () => {
        setEditingMcId(null)
        setMcName('')
        setMcKey('')
        setMcModel('gpt-4o')
        setMcBaseUrl('https://api.openai.com/v1')
        setMcPrompt('You are a biomedical literature reviewer.')
        setMcConcurrency('1024')
        setMcTemp('0.0')
        setIsModelModalOpen(false)
    }


    const { data: datasetConfigs } = useQuery(['datasetConfigs', currentProject?.id], async () => {
        if (!currentProject) return []
        const res = await api.get('/configs/datasets', { params: { project_id: currentProject.id } })
        return res.data
    }, { enabled: !!currentProject })

    const { data: analysisConfigs, isLoading: acLoading } = useQuery(['analysisConfigs', currentProject?.id], async () => {
        if (!currentProject) return []
        const res = await api.get('/configs/analysis', { params: { project_id: currentProject.id } })
        return res.data
    }, { enabled: !!currentProject })

    const { data: modelConfigs, isLoading: mcLoading } = useQuery(['modelConfigs', currentProject?.id], async () => {
        if (!currentProject) return []
        const res = await api.get('/configs/model', { params: { project_id: currentProject.id } })
        return res.data
    }, { enabled: !!currentProject })

    // --- Mutations ---
    const { mutate: createAc } = useMutation(async () => {
        if (!currentProject) throw new Error("No project selected")
        return await api.post('/configs/analysis', {
            project_id: currentProject.id,
            name: acName,
            hypothesis: acHypothesis,
            default_dataset_id: acDefaultDatasetId === '' ? null : acDefaultDatasetId
        })
    }, {
        onSuccess: () => {
            handleCancelEditAc()
            queryClient.invalidateQueries('analysisConfigs')
        }
    })

    const { mutate: updateAc } = useMutation(async (id: number) => {
        if (!currentProject) throw new Error("No project selected")
        return await api.put(`/configs/analysis/${id}`, {
            project_id: currentProject.id,
            name: acName,
            hypothesis: acHypothesis,
            default_dataset_id: acDefaultDatasetId === '' ? null : acDefaultDatasetId
        })
    }, {
        onSuccess: () => {
            handleCancelEditAc()
            queryClient.invalidateQueries('analysisConfigs')
        }
    })

    const { mutate: deleteAc } = useMutation(async (id: number) => {
        return await api.delete(`/configs/analysis/${id}`)
    }, {
        onSuccess: () => queryClient.invalidateQueries('analysisConfigs')
    })

    const { mutate: createMc } = useMutation(async () => {
        if (!currentProject) throw new Error("No project selected")
        return await api.post('/configs/model', {
            project_id: currentProject.id,
            name: mcName,
            openai_api_key: mcKey,
            openai_model: mcModel,
            openai_base_url: mcBaseUrl,
            system_prompt: mcPrompt,
            llm_concurrency_limit: parseInt(mcConcurrency),
            llm_temperature: parseFloat(mcTemp)
        })
    }, {
        onSuccess: () => {
            handleCancelEditMc()
            queryClient.invalidateQueries('modelConfigs')
        }
    })

    const { mutate: updateMc } = useMutation(async (id: number) => {
        if (!currentProject) throw new Error("No project selected")
        return await api.put(`/configs/model/${id}`, {
            project_id: currentProject.id,
            name: mcName,
            openai_api_key: mcKey,
            openai_model: mcModel,
            openai_base_url: mcBaseUrl,
            system_prompt: mcPrompt,
            llm_concurrency_limit: parseInt(mcConcurrency),
            llm_temperature: parseFloat(mcTemp)
        })
    }, {
        onSuccess: () => {
            handleCancelEditMc()
            queryClient.invalidateQueries('modelConfigs')
        }
    })

    const { mutate: deleteMc } = useMutation(async (id: number) => {
        return await api.delete(`/configs/model/${id}`)
    }, {
        onSuccess: () => queryClient.invalidateQueries('modelConfigs')
    })

    return (
        <div className="space-y-8">
            <h1 className="text-2xl font-bold text-slate-900">Configuration Management</h1>

            <div className="flex justify-between items-center mb-6">
                <div className="flex border-b border-slate-200 gap-2">
                    <button
                        onClick={() => navigate(`/${currentProject?.id}/configs/analysis`)}
                        className={`py-3 px-6 font-medium ${activeTab === 'analysis' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-slate-500'}`}
                    >
                        Analysis Configs
                    </button>
                    <button
                        onClick={() => navigate(`/${currentProject?.id}/configs/model`)}
                        className={`py-3 px-6 font-medium ${activeTab === 'model' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-slate-500'}`}
                    >
                        Model Configs
                    </button>
                </div>

                {activeTab === 'analysis' ? (
                    <button
                        onClick={() => {
                            handleCancelEditAc()
                            setIsAnalysisModalOpen(true)
                        }}
                        className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg transition-colors flex items-center gap-2 shadow-sm"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        Create Analysis Config
                    </button>
                ) : (
                    <button
                        onClick={() => {
                            handleCancelEditMc()
                            setIsModelModalOpen(true)
                        }}
                        className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg transition-colors flex items-center gap-2 shadow-sm"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        Create Model Config
                    </button>
                )}
            </div>

            {activeTab === 'analysis' && (
                <div className="space-y-6">
                    <Modal
                        isOpen={isAnalysisModalOpen}
                        onClose={handleCancelEditAc}
                        title={editingAcId ? 'Edit Analysis Config' : 'Create Analysis Config'}
                    >
                        <form onSubmit={(e) => { e.preventDefault(); editingAcId ? updateAc(editingAcId) : createAc() }} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Config Name</label>
                                <input type="text" placeholder="E.g. Schizophrenia-Dopamine Research" value={acName} onChange={e => setAcName(e.target.value)} required className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Hypothesis</label>
                                <input type="text" placeholder="e.g. The drug X inhibits tumor growth..." value={acHypothesis} onChange={e => setAcHypothesis(e.target.value)} required className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Dataset (Required)</label>
                                <select value={acDefaultDatasetId} onChange={e => setAcDefaultDatasetId(e.target.value ? Number(e.target.value) : '')} required className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2">
                                    <option value="" disabled>Select a downloaded dataset</option>
                                    {datasetConfigs?.filter((ds: any) => ds.is_downloaded || ds.download_job_status === 'completed').length === 0 && (
                                        <option value="" disabled>No datasets fully downloaded yet</option>
                                    )}
                                    {datasetConfigs?.filter((ds: any) => ds.is_downloaded || ds.download_job_status === 'completed').map((ds: any) => (
                                        <option key={ds.id} value={ds.id}>{ds.name} ({ds.source_type})</option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex justify-between items-center mt-6 pt-4 border-t border-slate-100">
                                <div className="flex space-x-3">
                                    <button type="submit" className="bg-blue-600 text-white px-5 py-2 rounded-lg hover:bg-blue-700 font-medium transition-colors">
                                        {editingAcId ? 'Update Config' : 'Save Config'}
                                    </button>
                                    {editingAcId && (
                                        <button type="button" onClick={handleCancelEditAc} className="bg-slate-100 text-slate-700 px-5 py-2 rounded-lg border border-slate-300 hover:bg-slate-200 font-medium transition-colors">
                                            Cancel
                                        </button>
                                    )}
                                </div>
                                {editingAcId && (
                                    <button
                                        type="button"
                                        onClick={() => {
                                            if (confirm('Are you sure you want to delete this analysis config?')) {
                                                deleteAc(editingAcId);
                                                handleCancelEditAc();
                                            }
                                        }}
                                        className="bg-red-50 text-red-600 px-5 py-2 rounded-lg border border-red-200 hover:bg-red-100 font-medium transition-colors flex items-center gap-2"
                                    >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-4v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                        Delete
                                    </button>
                                )}
                            </div>
                        </form>
                    </Modal>

                    <section className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
                        <h3 className="text-lg font-semibold mt-8">Saved Analysis Configs</h3>
                        {acLoading ? <p>Loading...</p> : (
                            <div className="grid gap-4">
                                {analysisConfigs?.map((c: any) => (
                                    <div key={c.id} className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex justify-between items-center transition-all hover:border-slate-300">
                                        <div>
                                            <h4 className="font-semibold">{c.name}</h4>
                                            <p className="text-sm text-slate-600">Hypothesis: {c.hypothesis}</p>
                                            {c.default_dataset_id && (
                                                <p className="text-xs text-blue-600 mt-1">
                                                    Default Dataset: {datasetConfigs?.find((ds: any) => ds.id === c.default_dataset_id)?.name || 'Unknown'}
                                                </p>
                                            )}
                                        </div>
                                        <button onClick={() => handleEditAc(c)} className="text-sm px-4 py-2 bg-slate-50 text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-100 hover:text-blue-600 font-medium transition-colors flex items-center gap-1.5 shadow-sm whitespace-nowrap">
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                                            Edit
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </section>
                </div>
            )}

            {activeTab === 'model' && (
                <div className="space-y-6">
                    <Modal
                        isOpen={isModelModalOpen}
                        onClose={handleCancelEditMc}
                        title={editingMcId ? 'Edit Model Config' : 'Create Model Config'}
                    >
                        <form onSubmit={(e) => { e.preventDefault(); editingMcId ? updateMc(editingMcId) : createMc() }} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Config Name</label>
                                <input type="text" placeholder="E.g. vLLM 120B Fast" value={mcName} onChange={e => setMcName(e.target.value)} required className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2" />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">OpenAI API Key</label>
                                    <input type="text" placeholder="sk-..." value={mcKey} onChange={e => setMcKey(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">OpenAI Model</label>
                                    <input type="text" placeholder="openai/gpt-oss-120b" value={mcModel} onChange={e => setMcModel(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">OpenAI Base URL</label>
                                    <input type="text" placeholder="http://localhost:11433/v1" value={mcBaseUrl} onChange={e => setMcBaseUrl(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Concurrency Limit</label>
                                    <input type="number" placeholder="1024" value={mcConcurrency} onChange={e => setMcConcurrency(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Temperature</label>
                                    <input type="number" step="0.1" placeholder="0.0" value={mcTemp} onChange={e => setMcTemp(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2" />
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">System Prompt</label>
                                <textarea placeholder="You are a biomedical literature reviewer..." value={mcPrompt} onChange={e => setMcPrompt(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2 h-24" />
                            </div>
                            <div className="flex justify-between items-center mt-6 pt-4 border-t border-slate-100">
                                <div className="flex space-x-3">
                                    <button type="submit" className="bg-blue-600 text-white px-5 py-2 rounded-lg hover:bg-blue-700 font-medium transition-colors">
                                        {editingMcId ? 'Update Config' : 'Save Config'}
                                    </button>
                                    {editingMcId && (
                                        <button type="button" onClick={handleCancelEditMc} className="bg-slate-100 text-slate-700 px-5 py-2 rounded-lg border border-slate-300 hover:bg-slate-200 font-medium transition-colors">
                                            Cancel
                                        </button>
                                    )}
                                </div>
                                {editingMcId && (
                                    <button
                                        type="button"
                                        onClick={() => {
                                            if (confirm('Are you sure you want to delete this model config?')) {
                                                deleteMc(editingMcId);
                                                handleCancelEditMc();
                                            }
                                        }}
                                        className="bg-red-50 text-red-600 px-5 py-2 rounded-lg border border-red-200 hover:bg-red-100 font-medium transition-colors flex items-center gap-2"
                                    >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-4v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                        Delete
                                    </button>
                                )}
                            </div>
                        </form>
                    </Modal>

                    <section className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
                        <h3 className="text-lg font-semibold mt-8">Saved Model Configs</h3>
                        {mcLoading ? <p>Loading...</p> : (
                            <div className="grid gap-4 mt-4">
                                {modelConfigs?.map((c: any) => (
                                    <div key={c.id} className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex justify-between items-center transition-all hover:border-slate-300">
                                        <div>
                                            <h4 className="font-semibold">{c.name}</h4>
                                            <p className="text-sm text-slate-600">Model: {c.openai_model}</p>
                                            <p className="text-sm text-slate-600 line-clamp-1">{c.system_prompt}</p>
                                        </div>
                                        <button onClick={() => handleEditMc(c)} className="text-sm px-4 py-2 bg-slate-50 text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-100 hover:text-blue-600 font-medium transition-colors flex items-center gap-1.5 shadow-sm whitespace-nowrap">
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                                            Edit
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </section>
                </div>
            )}
        </div>
    )
}
