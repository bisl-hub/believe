import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import { useNavigate } from 'react-router-dom'
import api from '../lib/axios'
import Modal from '../components/Modal'
import { useProject } from '../lib/ProjectContext'

export default function Datasets() {
    const queryClient = useQueryClient()
    const navigate = useNavigate()
    const { currentProject } = useProject()

    const formatProgress = (text: string) => {
        if (!text) return '';
        let clean = text.replace(/^[\d-]+\s[\d:,]+\s(?:INFO|WARN|ERROR|DEBUG)\s/, '').trim();

        const regex = /^(?:\[(.*?)\]\s+)?(.*?)(?::\s*|\s+)\d+\/\d+\s*\(([\d.]+)%\)(?:\s*-\s*([\d.]+)\s*it\/s)?/;
        const match = clean.match(regex);

        if (match) {
            const prefix = match[1] ? `[${match[1]}] ` : '';
            const name = match[2].trim();
            const percent = Math.floor(parseFloat(match[3]));
            const speed = match[4] ? ` (${parseFloat(match[4]).toFixed(1)} it/s)` : '';
            return `${prefix}${name}: ${percent}%${speed}`;
        }
        return clean;
    }

    const [editingDsId, setEditingDsId] = useState<number | null>(null)
    const [dsName, setDsName] = useState('')
    const [dsSourceType, setDsSourceType] = useState('pubtator3')
    const [dsQuery, setDsQuery] = useState('')

    const [isModalOpen, setIsModalOpen] = useState(false)

    const handleEdit = (c: any) => {
        setEditingDsId(c.id)
        setDsName(c.name)
        setDsSourceType(c.source_type)
        setDsQuery(c.query)
        setIsModalOpen(true)
    }

    const handleCancelEdit = () => {
        setEditingDsId(null)
        setDsName('')
        setDsSourceType('pubtator3')
        setDsQuery('')
        setIsModalOpen(false)
    }

    const { data: datasetConfigs, isLoading: dsLoading } = useQuery(['datasetConfigs', currentProject?.id], async () => {
        if (!currentProject) return []
        const res = await api.get('/configs/datasets', { params: { project_id: currentProject.id } })
        return res.data
    }, {
        enabled: !!currentProject,
        refetchInterval: 3000
    })

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return
        const reader = new FileReader()
        reader.onload = (evt) => {
            const text = evt.target?.result as string
            const pmids = text.split('\n').map(l => l.trim()).filter(l => l)
            setDsQuery(pmids.join(','))
        }
        reader.readAsText(file)
    }

    const { mutate: createDs } = useMutation(async () => {
        if (!currentProject) throw new Error("No project selected")
        return await api.post('/configs/datasets', {
            project_id: currentProject.id,
            name: dsName,
            source_type: dsSourceType,
            query: dsQuery
        })
    }, {
        onSuccess: () => {
            setDsName('')
            setDsQuery('')
            setIsModalOpen(false)
            queryClient.invalidateQueries('datasetConfigs')
        }
    })

    const { mutate: updateDs } = useMutation(async (id: number) => {
        if (!currentProject) throw new Error("No project selected")
        return await api.put(`/configs/datasets/${id}`, {
            project_id: currentProject.id,
            name: dsName,
            source_type: dsSourceType,
            query: dsQuery
        })
    }, {
        onSuccess: () => {
            handleCancelEdit()
            queryClient.invalidateQueries('datasetConfigs')
        }
    })

    const { mutate: deleteDs } = useMutation(async (id: number) => {
        return await api.delete(`/configs/datasets/${id}`)
    }, {
        onSuccess: () => queryClient.invalidateQueries('datasetConfigs')
    })



    return (
        <div className="space-y-8">
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold text-slate-900">Datasets (Data Sources)</h1>
                <button
                    onClick={() => {
                        handleCancelEdit() // Clear any existing form state
                        setIsModalOpen(true)
                    }}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg transition-colors flex items-center gap-2 shadow-sm"
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Create Dataset
                </button>
            </div>

            <Modal
                isOpen={isModalOpen}
                onClose={handleCancelEdit}
                title={editingDsId ? 'Edit Dataset Config' : 'Create Dataset Config'}
            >
                <form onSubmit={(e) => { e.preventDefault(); editingDsId ? updateDs(editingDsId) : createDs() }} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Dataset Name</label>
                        <input type="text" placeholder="E.g. Glioblastoma PMIDs" value={dsName} onChange={e => setDsName(e.target.value)} required className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2" />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Source Type</label>
                            <select value={dsSourceType} onChange={e => { setDsSourceType(e.target.value); setDsQuery(''); }} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2">
                                <option value="txt_file">Local TXT File (PMIDs)</option>
                                <option value="pubtator3">PubTator3 Query</option>
                                <option value="pubmed">PubMed Server Query</option>
                            </select>
                        </div>

                        {dsSourceType === 'txt_file' ? (
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Upload PMIDs (.txt, one per line)</label>
                                <input type="file" accept=".txt" onChange={handleFileUpload} required className="w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
                            </div>
                        ) : (
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Search Query</label>
                                <input type="text" placeholder={dsSourceType === 'pubtator3' ? "e.g. glioblastoma AND temozolomide" : "e.g. Nature[Journal]"} value={dsQuery} onChange={e => setDsQuery(e.target.value)} required className="w-full bg-slate-50 border border-slate-300 rounded-lg px-4 py-2" />
                            </div>
                        )}
                    </div>
                    {dsSourceType === 'txt_file' && dsQuery && (
                        <p className="text-sm text-slate-500">Selected {dsQuery.split(',').length} PMIDs.</p>
                    )}
                    <div className="flex justify-between items-center mt-6 pt-4 border-t border-slate-100">
                        <div className="flex space-x-3">
                            <button type="submit" className="bg-blue-600 text-white px-5 py-2 rounded-lg hover:bg-blue-700 font-medium transition-colors">
                                {editingDsId ? 'Update Dataset' : 'Save Dataset'}
                            </button>
                            {editingDsId && (
                                <button type="button" onClick={handleCancelEdit} className="bg-slate-100 text-slate-700 px-5 py-2 rounded-lg border border-slate-300 hover:bg-slate-200 font-medium transition-colors">
                                    Cancel
                                </button>
                            )}
                        </div>
                        {editingDsId && (
                            <button
                                type="button"
                                onClick={() => {
                                    if (confirm('Are you sure you want to delete this dataset config?')) {
                                        deleteDs(editingDsId);
                                        handleCancelEdit();
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
                <h3 className="text-xl font-bold text-slate-900 mb-6">Saved Datasets</h3>
                {dsLoading ? (
                    <div className="grid gap-4 animate-pulse">
                        {[1, 2, 3].map((i) => (
                            <div key={i} className="p-4 border border-slate-200 rounded-lg flex justify-between items-center min-w-0">
                                <div className="space-y-3 w-full">
                                    <div className="h-5 bg-slate-200 rounded w-1/3"></div>
                                    <div className="flex gap-2">
                                        <div className="h-6 bg-slate-200 rounded w-20"></div>
                                        <div className="h-6 bg-slate-200 rounded w-24"></div>
                                    </div>
                                    <div className="h-4 bg-slate-200 rounded w-2/3"></div>
                                </div>
                                <div className="flex gap-2 pl-4">
                                    <div className="h-8 bg-slate-200 rounded w-16"></div>
                                    <div className="h-8 bg-slate-200 rounded w-16"></div>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="grid gap-4">
                        {datasetConfigs?.map((c: any) => (
                            <div
                                key={c.id}
                                onClick={() => c.download_job_id ? navigate(`/${currentProject?.id}/jobs/${c.download_job_id}`) : null}
                                className={`bg-white p-6 rounded-xl border border-slate-200 flex justify-between items-center min-w-0 shadow-sm transition-all ${c.download_job_id ? 'cursor-pointer hover:border-blue-400' : ''}`}
                            >
                                <div className="overflow-hidden min-w-0 flex-1">
                                    <h4 className="font-semibold truncate" title={c.name}>{c.name}</h4>
                                    <div className="flex items-center space-x-2 mb-1">
                                        <span className="px-3 py-1 rounded text-xs font-bold uppercase bg-slate-100 text-slate-500">{c.source_type}</span>

                                        {c.is_downloaded || c.download_job_status === 'completed' ? (
                                            <span className="px-3 py-1 rounded text-xs font-bold uppercase bg-green-100 text-green-700">
                                                DOWNLOADED
                                            </span>
                                        ) : c.download_job_status === 'running' ? (
                                            <div className="flex flex-col items-start gap-1">
                                                <div className="flex items-center space-x-2">
                                                    <span className="px-3 py-1 rounded text-xs font-bold uppercase bg-blue-100 text-blue-700 animate-pulse flex items-center gap-1.5">
                                                        <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                                        </svg>
                                                        DOWNLOADING...
                                                    </span>
                                                </div>
                                                {c.progress_text && (
                                                    <span className="text-xs text-blue-600 bg-blue-50 px-3 py-1 rounded border border-blue-100 font-mono">
                                                        {formatProgress(c.progress_text)}
                                                    </span>
                                                )}
                                            </div>
                                        ) : c.download_job_status === 'failed' ? (
                                            <span className="px-3 py-1 rounded text-xs font-bold uppercase bg-red-100 text-red-700">
                                                FAILED
                                            </span>
                                        ) : (
                                            <div className="flex items-center space-x-2">
                                                <span className="px-3 py-1 rounded text-xs font-bold uppercase bg-slate-100 text-slate-500 animate-pulse">
                                                    QUEUED
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                    <p className="text-sm text-slate-500 truncate" title={c.query}>Query/Data: {c.query}</p>
                                </div>
                                <div className="space-x-2 pl-4 flex-shrink-0 flex items-center">
                                    <button onClick={(e) => { e.stopPropagation(); handleEdit(c); }} className="text-sm px-4 py-2 bg-slate-50 text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-100 hover:text-blue-600 font-medium z-10 relative transition-colors flex items-center gap-1.5 shadow-sm whitespace-nowrap">
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                                        Edit
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </section>
        </div>
    )
}
