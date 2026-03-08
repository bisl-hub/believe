import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import api from '../lib/axios'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import Pagination from '../components/Pagination'
import Modal from '../components/Modal'
import { useProject } from '../lib/ProjectContext'

export default function Analysis() {
  const [jobName, setJobName] = useState('')
  const [queryTerm, setQueryTerm] = useState('')
  const [sourceType, setSourceType] = useState('')
  const [hypothesis, setHypothesis] = useState('')
  const [maxArticles, setMaxArticles] = useState('100')
  const [samplingMode, setSamplingMode] = useState<'count' | 'percent'>('count')
  const [samplingPercent, setSamplingPercent] = useState('10')
  const [isAllArticles, setIsAllArticles] = useState(false)
  const { currentProject } = useProject()

  const [openaiApiKey, setOpenaiApiKey] = useState('')
  const [openaiModel, setOpenaiModel] = useState('')
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [llmConcurrencyLimit, setLlmConcurrencyLimit] = useState('1024')
  const [llmTemperature, setLlmTemperature] = useState('0.0')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()
  const page = parseInt(searchParams.get('page') || '1', 10)

  const setPage = (newPage: number) => {
    setSearchParams(prev => {
      prev.set('page', newPage.toString())
      return prev
    })
  }
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()

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

  useEffect(() => {
    if (location.state && location.state.cloneJobData) {
      const job = location.state.cloneJobData
      setJobName(job.name ? `Copy of ${job.name}` : '')
      setQueryTerm(job.query_term || '')
      setSourceType(job.source_type || 'pubtator3')
      setHypothesis(job.hypothesis || '')

      if (job.max_articles_percent !== null && job.max_articles_percent !== undefined) {
        setSamplingMode('percent')
        setSamplingPercent(job.max_articles_percent.toString())
        setIsAllArticles(false)
      } else if (job.max_articles === -1) {
        setIsAllArticles(true)
        setSamplingMode('count')
      } else {
        setSamplingMode('count')
        setMaxArticles(job.max_articles?.toString() || '100')
        setIsAllArticles(false)
      }

      setOpenaiApiKey(job.openai_api_key || '')
      setOpenaiModel(job.openai_model || '')
      setOpenaiBaseUrl(job.openai_base_url || '')
      setSystemPrompt(job.system_prompt || '')
      setLlmConcurrencyLimit(job.llm_concurrency_limit?.toString() || '1024')
      setLlmTemperature(job.llm_temperature?.toString() || '0.0')

      // Once we've cloned, clear the state so it doesn't persist on refresh
      window.history.replaceState({}, document.title)
      setIsModalOpen(true) // Open the modal automatically when cloning
    }
  }, [location.state])

  const { data: datasetConfigs } = useQuery(['datasetConfigs', currentProject?.id], async () => {
    if (!currentProject) return []
    const res = await api.get('/configs/datasets', { params: { project_id: currentProject.id } })
    return res.data
  }, { enabled: !!currentProject })

  const { data: analysisConfigs } = useQuery(['analysisConfigs', currentProject?.id], async () => {
    if (!currentProject) return []
    const res = await api.get('/configs/analysis', { params: { project_id: currentProject.id } })
    return res.data
  }, { enabled: !!currentProject })

  const { data: modelConfigs } = useQuery(['modelConfigs', currentProject?.id], async () => {
    if (!currentProject) return []
    const res = await api.get('/configs/model', { params: { project_id: currentProject.id } })
    return res.data
  }, { enabled: !!currentProject })

  const [selectedAnalysisConfig, setSelectedAnalysisConfig] = useState<number | ''>('')
  const [selectedModelConfig, setSelectedModelConfig] = useState<number | ''>('')

  // Automatically select the first config if none selected and configs are loaded
  useEffect(() => {
    if (!selectedAnalysisConfig && analysisConfigs && analysisConfigs.length > 0) {
      handleAnalysisConfigSelect(analysisConfigs[0].id)
    }
    if (!selectedModelConfig && modelConfigs && modelConfigs.length > 0) {
      handleModelConfigSelect(modelConfigs[0].id)
    }
  }, [analysisConfigs, modelConfigs, datasetConfigs]) // Added datasetConfigs to sync if it loads later

  const handleAnalysisConfigSelect = (id: number | '') => {
    setSelectedAnalysisConfig(id)
    if (id && analysisConfigs) {
      const config = analysisConfigs.find((c: any) => c.id === id)
      if (config) {
        setHypothesis(config.hypothesis)
        // Attempt to sync dataset details if available
        if (config.default_dataset_id && datasetConfigs) {
          const defaultDs = datasetConfigs.find((ds: any) => ds.id === config.default_dataset_id)
          if (defaultDs) {
            setQueryTerm(defaultDs.query || '')
            setSourceType(defaultDs.source_type || 'pubtator3')
          }
        }
      }
    }
  }

  const handleModelConfigSelect = (id: number | '') => {
    setSelectedModelConfig(id)
    if (id && modelConfigs) {
      const config = modelConfigs.find((c: any) => c.id === id)
      if (config) {
        setOpenaiApiKey(config.openai_api_key)
        setOpenaiModel(config.openai_model)
        setOpenaiBaseUrl(config.openai_base_url)
        setSystemPrompt(config.system_prompt)
        setLlmConcurrencyLimit(config.llm_concurrency_limit?.toString() || '1024')
        setLlmTemperature(config.llm_temperature?.toString() || '0.0')
      }
    }
  }

  const { mutate: submitJob, isLoading: isSubmitting } = useMutation(async () => {
    if (!currentProject) throw new Error("No active project")
    const payload = {
      project_id: currentProject.id,
      name: jobName,
      query_term: queryTerm,
      hypothesis: hypothesis,
      source_type: sourceType,
      max_articles: isAllArticles ? -1 : (samplingMode === 'count' ? parseInt(maxArticles) : -1),
      max_articles_percent: samplingMode === 'percent' ? parseFloat(samplingPercent) : null,
      openai_api_key: openaiApiKey,
      openai_model: openaiModel,
      openai_base_url: openaiBaseUrl,
      system_prompt: systemPrompt,
      llm_concurrency_limit: parseInt(llmConcurrencyLimit),
      llm_temperature: parseFloat(llmTemperature)
    }
    const res = await api.post('/jobs', payload)
    return res.data
  }, {
    onSuccess: () => {
      setJobName('')
      setIsModalOpen(false)
      queryClient.invalidateQueries('jobs')
    },
    onError: (error: any) => {
      alert('Failed to submit job: ' + (error.response?.data?.detail || error.message))
    }
  })



  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedAnalysisConfig || !selectedModelConfig) {
      alert('Please select both Analysis and Model configurations.')
      return
    }
    submitJob()
  }

  const { data: jobsData, isLoading, error } = useQuery(['jobs', page, currentProject?.id], async () => {
    if (!currentProject) return { items: [], total: 0, pages: 1 }
    const res = await api.get('/jobs', { params: { project_id: currentProject.id, page, limit: 10 } })
    return res.data
  }, {
    enabled: !!currentProject,
    refetchInterval: 5000,
    keepPreviousData: true,
    retry: false
  })

  const jobs = jobsData?.items || []
  const totalPages = jobsData?.pages || 1

  const combinedConfig = {
    analysis: analysisConfigs?.find((c: any) => c.id === selectedAnalysisConfig),
    model: modelConfigs?.find((c: any) => c.id === selectedModelConfig),
    runtime: {
      jobName,
      maxArticles: isAllArticles ? -1 : (samplingMode === 'count' ? parseInt(maxArticles) : -1),
      maxArticlesPercent: samplingMode === 'percent' ? parseFloat(samplingPercent) : null,
    }
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-400">Failed to load jobs. Please try refreshing the page.</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-900">Analysis</h1>
        <button
          onClick={() => setIsModalOpen(true)}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg transition-colors flex items-center gap-2 shadow-sm"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Create New Job
        </button>
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="New Analysis"
      >
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Analysis Config</label>
              <select
                value={selectedAnalysisConfig}
                onChange={(e) => handleAnalysisConfigSelect(Number(e.target.value))}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-4 py-2 text-slate-900 focus:ring-2 focus:ring-blue-500 outline-none"
              >
                {analysisConfigs?.map((c: any) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Model Config</label>
              <select
                value={selectedModelConfig}
                onChange={(e) => handleModelConfigSelect(Number(e.target.value))}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-4 py-2 text-slate-900 focus:ring-2 focus:ring-blue-500 outline-none"
              >
                {modelConfigs?.map((c: any) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {(selectedAnalysisConfig || selectedModelConfig) && (
              <details className="group bg-slate-50 rounded-lg border border-slate-200 overflow-hidden">
                <summary className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-slate-100 transition-colors list-none">
                  <span className="text-xs font-bold text-slate-600 uppercase tracking-widest">Configuration JSON</span>
                  <svg className="w-4 h-4 text-slate-400 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </summary>
                <div className="p-4 border-t border-slate-200 bg-slate-900">
                  <pre className="text-[11px] font-mono text-blue-300 overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(combinedConfig, null, 2)}
                  </pre>
                </div>
              </details>
            )}

            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-widest">Job Name (Optional)</label>
              <input
                type="text"
                value={jobName}
                onChange={(e) => setJobName(e.target.value)}
                className="w-full border border-slate-200 rounded-lg px-4 py-2 text-slate-900 focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="e.g. Test Run 01"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-widest">Max Articles</label>
              <div className="flex gap-2">
                <div className="flex rounded-lg border border-slate-200 p-1 bg-slate-50">
                  <button
                    type="button"
                    onClick={() => { setSamplingMode('count'); setIsAllArticles(false); }}
                    className={`px-3 py-1 rounded text-[10px] font-bold uppercase ${samplingMode === 'count' && !isAllArticles ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-400'}`}
                  >
                    Count
                  </button>
                  <button
                    type="button"
                    onClick={() => { setSamplingMode('percent'); setIsAllArticles(false); }}
                    className={`px-3 py-1 rounded text-[10px] font-bold uppercase ${samplingMode === 'percent' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-400'}`}
                  >
                    %
                  </button>
                </div>

                {samplingMode === 'count' ? (
                  <>
                    <input
                      type="number"
                      value={maxArticles}
                      onChange={(e) => setMaxArticles(e.target.value)}
                      disabled={isAllArticles}
                      className="flex-1 border border-slate-200 rounded-lg px-4 py-2 text-slate-900 disabled:opacity-50"
                    />
                    <button
                      type="button"
                      onClick={() => setIsAllArticles(!isAllArticles)}
                      className={`px-4 py-2 rounded-lg border font-bold text-xs uppercase ${isAllArticles ? 'bg-blue-600 text-white' : 'bg-white text-slate-400'}`}
                    >
                      ALL
                    </button>
                  </>
                ) : (
                  <div className="flex-1 relative">
                    <input
                      type="number"
                      value={samplingPercent}
                      onChange={(e) => setSamplingPercent(e.target.value)}
                      min="0" max="100" step="0.1"
                      className="w-full border border-slate-200 rounded-lg px-4 py-2 text-slate-900"
                    />
                    <span className="absolute right-4 top-2 text-slate-300">%</span>
                  </div>
                )}
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 text-white font-bold py-3 rounded-lg transition-colors uppercase tracking-widest text-sm"
            >
              {isSubmitting ? 'Starting...' : 'Start Analysis'}
            </button>
          </form>
        </div>
      </Modal>

      <div className="space-y-4">
        <h2 className="text-xl font-bold text-slate-900">Active Queue</h2>
        {isLoading ? (
          <div className="text-center py-12 text-slate-400">Loading tasks...</div>
        ) : jobs.length > 0 ? (
          <div className="grid gap-3">
            {jobs.map((job: any) => (
              <div
                key={job.id}
                onClick={() => navigate(`/${currentProject?.id}/jobs/${job.id}`)}
                className="bg-white p-6 rounded-xl border border-slate-200 hover:border-blue-400 cursor-pointer transition-all shadow-sm"
              >
                <div className="flex justify-between items-center">
                  <div className="space-y-2">
                    <div className="flex items-center gap-4 flex-wrap">
                      <span className="text-lg font-bold text-slate-900">{job.name?.replace('Force-Download: ', '')}</span>
                      {job.status === 'completed' ? (
                        <span className="px-3 py-1 rounded text-xs font-bold uppercase bg-green-100 text-green-700">
                          {job.status}
                        </span>
                      ) : job.status === 'running' ? (
                        <div className="flex items-center gap-3">
                          <span className="px-3 py-1 rounded text-xs font-bold uppercase bg-blue-100 text-blue-700 animate-pulse flex items-center gap-1.5">
                            <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            {job.status}
                          </span>
                          {job.progress_text && (
                            <span className="text-xs text-blue-600 bg-blue-50 px-3 py-1 rounded border border-blue-100 font-mono">
                              {formatProgress(job.progress_text)}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="px-3 py-1 rounded text-xs font-bold uppercase bg-slate-100 text-slate-500">
                          {job.status}
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-slate-500 truncate max-w-2xl">{job.hypothesis}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-20 bg-slate-50 rounded-xl border border-dashed border-slate-200 text-slate-400">No active tasks</div>
        )}

        <Pagination
          currentPage={page}
          totalPages={totalPages}
          onPageChange={(p) => setPage(p)}
          maxVisiblePages={20}
        />
      </div>
    </div>
  )
}
