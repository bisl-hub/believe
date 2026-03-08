import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from 'react-query'
import api from '../lib/axios'
import { useState, useEffect, useRef } from 'react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts'
import { useProject } from '../lib/ProjectContext'

const COLORS = {
  support: '#16a34a',    // green-600
  reject: '#dc2626',     // red-600
  neutral: '#2563eb',    // blue-600
  downloaded: '#9333ea', // purple-600
  error: '#94a3b8'       // slate-400
}

export default function JobDetail() {
  const { id } = useParams()
  const [activeTab, setActiveTab] = useState<'logs' | 'results'>('results')
  const [filter, setFilter] = useState<'all' | 'support' | 'reject' | 'neutral' | 'downloaded'>('all')
  const [page, setPage] = useState(1)
  const [visibleVerdicts, setVisibleVerdicts] = useState({ support: true, reject: true, neutral: true })
  const [sortBy, setSortBy] = useState('confidence')
  const [sortOrder, setSortOrder] = useState('desc')
  const [isDeleting, setIsDeleting] = useState(false)
  const itemsPerPage = 10
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const [autoScroll, setAutoScroll] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)


  const { data: job, error: jobError } = useQuery(['job', id], async () => {
    const res = await api.get(`/jobs/${id}`)
    return res.data
  })

  const { data: logs } = useQuery(['logs', id], async () => {
    const res = await api.get(`/jobs/${id}/logs`)
    return res.data.logs
  }, {
    refetchInterval: job?.status === 'running' ? 2000 : false,
    enabled: !!job
  })

  const { data: stats } = useQuery(['stats', id], async () => {
    const res = await api.get(`/jobs/${id}/stats`)
    return res.data
  }, {
    enabled: job?.status === 'completed'
  })

  useEffect(() => {
    if (autoScroll && scrollRef.current && activeTab === 'logs') {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, autoScroll, activeTab])

  const { data: resultsData } = useQuery(['results', id, page, filter, sortBy, sortOrder], async () => {
    const res = await api.get(`/jobs/${id}/results`, {
      params: { page, limit: itemsPerPage, filter, sort_by: sortBy, order: sortOrder }
    })
    return res.data
  }, {
    enabled: job?.status === 'completed',
    keepPreviousData: true
  })

  const results = resultsData?.items || []
  const totalPages = resultsData?.pages || 1

  const toggleVerdict = (verdict: 'support' | 'reject' | 'neutral') => {
    setVisibleVerdicts(prev => ({ ...prev, [verdict]: !prev[verdict] }))
  }

  // Prepare data for charts based on visibility
  const pieData = stats ? [
    { name: 'Support', value: stats.verdict_counts.support || 0, type: 'support' },
    { name: 'Reject', value: stats.verdict_counts.reject || 0, type: 'reject' },
    { name: 'Neutral', value: stats.verdict_counts.neutral || 0, type: 'neutral' }
  ].filter(d => visibleVerdicts[d.type as keyof typeof visibleVerdicts]) : []

  const barData = stats?.year_data?.map((d: any) => ({
    year: d.year,
    support: visibleVerdicts.support ? d.support : 0,
    reject: visibleVerdicts.reject ? d.reject : 0,
    neutral: visibleVerdicts.neutral ? d.neutral : 0,
    downloaded: d.downloaded || 0
  })) || []

  const handleDownloadCsv = () => {
    const token = localStorage.getItem('token')
    if (!token) {
      alert('Authentication error. Please log in again.')
      return
    }
    // Using direct URL navigation to trigger the browser's native download streamer
    // rather than forcing Axios to buffer the entire file into frontend RAM first.
    const url = `/api/jobs/${id}/download_csv?token=${token}`
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', '') // Let the browser use the filename from the backend's Content-Disposition header
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  const { mutate: deleteJob } = useMutation(async () => {
    if (!id) return
    const res = await api.delete(`/jobs/${id}`)
    return res.data
  }, {
    onSuccess: () => {
      navigate(`/${currentProject?.id}/history`)
    },
    onError: (err: any) => {
      setIsDeleting(false)
      alert('Failed to delete job: ' + (err.response?.data?.detail || err.message))
    }
  })

  const handleCloneJob = () => {
    navigate(`/${currentProject?.id}/analysis`, { state: { cloneJobData: job } })
  }

  if (jobError || (job && currentProject && job.project_id !== currentProject.id)) {
    return (
      <div className="text-center py-24">
        <div className="text-red-500 font-medium text-lg mb-2">Access Denied</div>
        <p className="text-slate-500 mb-6">This job either does not exist or belongs to a different workspace.</p>
        <button onClick={() => navigate(`/${currentProject?.id}/history`)} className="text-blue-600 hover:text-blue-800 font-medium">
          &larr; Return to Workspace
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">

      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-900">
          {job?.name?.replace('Force-Download: ', '') || job?.query_term}
        </h1>
        <div className="flex gap-3">
          <button
            onClick={handleCloneJob}
            className="px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded transition-colors flex items-center gap-2 shadow-sm"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M7 9a2 2 0 012-2h6a2 2 0 012 2v6a2 2 0 01-2 2H9a2 2 0 01-2-2V9z" />
              <path d="M5 3a2 2 0 00-2 2v6a2 2 0 002 2V5h8a2 2 0 00-2-2H5z" />
            </svg>
            Clone Job
          </button>
          {job?.status === 'completed' && (
            <button
              onClick={handleDownloadCsv}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition-colors flex items-center gap-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
              Download CSV
            </button>
          )}
          <span className={`px-3 py-1 rounded text-white flex items-center ${job?.status === 'completed' ? 'bg-green-600' :
            job?.status === 'failed' ? 'bg-red-600' :
              'bg-blue-600'
            }`}>
            {job?.status?.toUpperCase()}
          </span>

          <button
            disabled={isDeleting}
            onClick={async () => {
              if (confirm('Are you sure you want to delete this job? This action cannot be undone.')) {
                setIsDeleting(true)
                if (job?.status === 'running' || job?.status === 'queued') {
                  try {
                    await api.post(`/jobs/${id}/stop`);
                  } catch (e) {
                    console.error("Failed to stop job before deletion", e);
                  }
                }
                deleteJob()
              }
            }}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-400 disabled:cursor-not-allowed text-white rounded transition-colors flex items-center gap-2 font-medium"
          >
            {isDeleting ? (
              <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-4v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            )}
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>

      {/* Job Configuration Summary */}
      <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm text-sm">
        <h3 className="text-slate-500 font-medium mb-3 uppercase text-xs tracking-wider">Job Configuration</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <span className="block text-slate-500 text-xs">Query Term</span>
            <span className="text-slate-900">{job?.query_term}</span>
          </div>
          <div>
            <span className="block text-slate-500 text-xs">Hypothesis</span>
            <span className="text-slate-900 line-clamp-2" title={job?.hypothesis}>{job?.hypothesis}</span>
          </div>
          <div>
            <span className="block text-slate-500 text-xs">Max Articles</span>
            <span className="text-slate-900">
              {job?.max_articles_percent
                ? `${job.max_articles_percent}%`
                : (job?.max_articles === -1 ? 'All' : job?.max_articles)}
            </span>
          </div>
          <div>
            <span className="block text-slate-500 text-xs">Source Type</span>
            <span className="text-slate-900 capitalize px-2 py-0.5 bg-slate-100 rounded border border-slate-200">{job?.source_type || 'pubtator3'}</span>
          </div>
          {job?.job_type !== 'download' && (
            <>
              <div>
                <span className="block text-slate-500 text-xs">OpenAI Model</span>
                <span className="text-slate-900">{job?.openai_model || 'Default'}</span>
              </div>
              <div className="flex flex-col justify-end">
                <span className="text-slate-900 truncate" title={job?.openai_base_url}>{job?.openai_base_url || 'Default'}</span>
              </div>
              <div>
                <span className="block text-slate-500 text-xs">LLM Concurrency</span>
                <span className="text-slate-900">{job?.llm_concurrency_limit ?? 'Default'}</span>
              </div>
              <div>
                <span className="block text-slate-500 text-xs">LLM Temperature</span>
                <span className="text-slate-900">{job?.llm_temperature ?? 'Default'}</span>
              </div>
              <div className="md:col-span-2 lg:col-span-3">
                <details className="group">
                  <summary className="cursor-pointer text-slate-500 text-xs hover:text-slate-300 select-none flex items-center gap-1">
                    <span>System Prompt</span>
                    <svg className="w-3 h-3 transition-transform group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                  </summary>
                  <div className="mt-2 p-3 bg-slate-50 rounded border border-slate-200 text-slate-600 font-mono text-xs whitespace-pre-wrap">
                    {job?.system_prompt || 'Default System Prompt'}
                  </div>
                </details>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="flex gap-4 border-b border-slate-200">
        <button
          onClick={() => setActiveTab('results')}
          className={`px-4 py-2 font-medium border-b-2 transition-colors ${activeTab === 'results'
            ? 'border-blue-500 text-blue-600'
            : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
        >
          Results & Visualization
        </button>
        <button
          onClick={() => setActiveTab('logs')}
          className={`px-4 py-2 font-medium border-b-2 transition-colors ${activeTab === 'logs'
            ? 'border-blue-500 text-blue-600'
            : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
        >
          Live Logs
        </button>
      </div>

      {activeTab === 'logs' && (
        <div className="space-y-2">
          <div className="flex justify-end">
            <label className="flex items-center gap-2 text-sm text-slate-600 font-medium cursor-pointer hover:text-slate-900 transition-colors">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
              Auto-scroll
            </label>
          </div>
          <div ref={scrollRef} className="bg-slate-950 rounded-lg p-4 font-mono text-sm text-slate-300 h-[600px] overflow-auto whitespace-pre border border-slate-800 shadow-inner">
            {logs || 'Waiting for logs...'}
          </div>
        </div>
      )}

      {activeTab === 'results' && (
        <div className="space-y-6">
          {/* State 1: Job is Running/Queued/Pending */}
          {job?.status !== 'completed' && job?.status !== 'failed' && (
            <div className="bg-white p-12 rounded-xl border border-slate-200 shadow-sm text-center flex flex-col items-center justify-center min-h-[400px]">
              <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mb-6"></div>
              <h3 className="text-xl font-semibold text-slate-900 mb-2">Analysis in Progress</h3>
              <p className="text-slate-500 max-w-md mx-auto mb-6">
                Your hypothesis is currently being validated. This process involves searching literature, fetching abstracts, and running LLM evaluation.
              </p>
              <button
                onClick={() => setActiveTab('logs')}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition-colors"
              >
                View Live Logs
              </button>
            </div>
          )}

          {/* State Loading: Job Completed but Fetching Data */}
          {job?.status === 'completed' && (!stats || !resultsData) && (
            <div className="space-y-6 animate-pulse">
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm mb-6 h-48 flex flex-col gap-4">
                <div className="h-6 bg-slate-200 rounded w-48 mb-2"></div>
                <div className="h-10 bg-slate-200 rounded w-full"></div>
                <div className="h-10 bg-slate-200 rounded w-full"></div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm h-80 flex flex-col items-center justify-center">
                  <div className="w-48 h-48 bg-slate-200 rounded-full"></div>
                </div>
                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm h-80">
                  <div className="h-full w-full bg-slate-200 rounded-lg"></div>
                </div>
              </div>
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm h-96">
                <div className="h-full w-full bg-slate-200 rounded-lg"></div>
              </div>
            </div>
          )}

          {/* State 2: Job Completed but NO Data (Stats total is 0) */}
          {job?.status === 'completed' && stats && resultsData && Object.values(stats.verdict_counts || {}).reduce((a: any, b: any) => a + (b || 0), 0) === 0 && (
            <div className="bg-white p-12 rounded-xl border border-slate-200 shadow-sm text-center flex flex-col items-center justify-center min-h-[400px]">
              <svg className="w-16 h-16 text-slate-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <h3 className="text-xl font-semibold text-slate-900 mb-2">No Results Found</h3>
              <p className="text-slate-500 max-w-md mx-auto">
                The search query returned 0 results, or no articles matched the criteria. Please check your query terms and try again.
              </p>
            </div>
          )}

          {/* State 3: Job Completed AND Has Data */}
          {job?.status === 'completed' && stats && resultsData && (Object.values(stats.verdict_counts || {}).reduce((a: any, b: any) => a + (b || 0), 0) as number) > 0 && (
            <>
              {/* Statistical Summary Table */}
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm mb-6">
                <h3 className="text-lg font-semibold text-slate-900 mb-4">Statistical Summary</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left text-slate-600">
                    <thead className="text-xs text-slate-700 uppercase bg-slate-50">
                      <tr>
                        <th scope="col" className="px-6 py-3 rounded-l-lg">Metric</th>
                        <th scope="col" className="px-6 py-3 text-right">Support</th>
                        <th scope="col" className="px-6 py-3 text-right">Reject</th>
                        <th scope="col" className="px-6 py-3 text-right">Neut.</th>
                        {job?.job_type === 'download' && <th scope="col" className="px-6 py-3 text-right">Downloaded</th>}
                        <th scope="col" className="px-6 py-3 text-right">Error</th>
                        <th scope="col" className="px-6 py-3 text-right rounded-r-lg">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        const dbTotal = Object.values(stats.verdict_counts).reduce((acc: number, v: any) => acc + (v || 0), 0) as number;

                        // Determine true total (considering max_articles if set)
                        let targetTotal = dbTotal;
                        if (job?.max_articles && job.max_articles !== -1 && job.max_articles !== null && Number.isFinite(job.max_articles)) {
                          if (job.max_articles > dbTotal) {
                            targetTotal = job.max_articles;
                          }
                        }

                        const support = stats.verdict_counts.support || 0;
                        const reject = stats.verdict_counts.reject || 0;
                        const neutral = stats.verdict_counts.neutral || 0;
                        const downloaded = stats.verdict_counts.downloaded || 0;

                        // Error includes explicit DB errors (other verdicts) + missing items
                        const dbError = dbTotal - (support + reject + neutral + downloaded);
                        const missing = targetTotal - dbTotal;
                        const totalError = dbError + missing;

                        return (
                          <>
                            <tr className="bg-white border-b border-slate-200 hover:bg-slate-50 transition-colors">
                              <td className="px-6 py-4 font-medium text-slate-900">Count</td>
                              <td className="px-6 py-4 text-right text-green-600 font-medium">{support.toLocaleString()}</td>
                              <td className="px-6 py-4 text-right text-red-600 font-medium">{reject.toLocaleString()}</td>
                              <td className="px-6 py-4 text-right text-blue-600 font-medium">{neutral.toLocaleString()}</td>
                              {job?.job_type === 'download' && <td className="px-6 py-4 text-right text-purple-600 font-medium">{downloaded.toLocaleString()}</td>}
                              <td className="px-6 py-4 text-right text-slate-500 font-medium">
                                {totalError.toLocaleString()}
                                {missing > 0 && <span className="text-xs text-slate-500 ml-1">({missing} missing)</span>}
                              </td>
                              <td className="px-6 py-4 text-right text-slate-900 font-bold">{targetTotal.toLocaleString()}</td>
                            </tr>
                            <tr className="bg-white hover:bg-slate-50 transition-colors">
                              <td className="px-6 py-4 font-medium text-slate-900">Percentage</td>
                              <td className="px-6 py-4 text-right">{targetTotal ? `${(support / targetTotal * 100).toFixed(1)}%` : '0%'}</td>
                              <td className="px-6 py-4 text-right">{targetTotal ? `${(reject / targetTotal * 100).toFixed(1)}%` : '0%'}</td>
                              <td className="px-6 py-4 text-right">{targetTotal ? `${(neutral / targetTotal * 100).toFixed(1)}%` : '0%'}</td>
                              {job?.job_type === 'download' && <td className="px-6 py-4 text-right">{targetTotal ? `${(downloaded / targetTotal * 100).toFixed(1)}%` : '0%'}</td>}
                              <td className="px-6 py-4 text-right">{targetTotal ? `${(totalError / targetTotal * 100).toFixed(1)}%` : '0%'}</td>
                              <td className="px-6 py-4 text-right text-slate-900 font-bold">100%</td>
                            </tr>
                          </>
                        );
                      })()}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Visualization Section */}
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="text-lg font-semibold text-slate-900">Interactive Analysis</h3>
                  {job?.job_type !== 'download' && (
                    <div className="flex gap-2">
                      {(['support', 'reject', 'neutral'] as const).map(v => (
                        <button
                          key={v}
                          onClick={() => toggleVerdict(v)}
                          className={`px-3 py-1 rounded text-xs font-medium uppercase transition-colors ${visibleVerdicts[v]
                            ? v === 'support' ? 'bg-green-600 text-white' : v === 'reject' ? 'bg-red-600 text-white' : 'bg-blue-600 text-white'
                            : 'bg-slate-700 text-slate-400'
                            }`}
                        >
                          {v}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  {/* Verdict Distribution */}
                  {job?.job_type !== 'download' && (
                    <div className="h-72 flex flex-col items-center">
                      <h4 className="text-sm font-medium text-slate-500 mb-4 text-center">Verdict Distribution</h4>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart margin={{ top: 20, bottom: 20, left: 0, right: 0 }}>
                          <Pie
                            data={pieData}
                            cx="40%"
                            cy="50%"
                            innerRadius={40}
                            outerRadius={60}
                            paddingAngle={5}
                            dataKey="value"
                            label={({ percent }: { percent?: number }) => `${((percent || 0) * 100).toFixed(1)}%`}
                          >
                            {pieData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[entry.type as keyof typeof COLORS]} />
                            ))}
                          </Pie>
                          <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', color: '#0f172a' }} itemStyle={{ color: '#0f172a' }} />
                          <Legend layout="vertical" verticalAlign="middle" align="right" wrapperStyle={{ paddingLeft: '20px' }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Yearly Trends (Bar Chart) */}
                  <div className={`h-72 ${job?.job_type === 'download' ? 'lg:col-span-2' : ''}`}>
                    <h4 className="text-sm font-medium text-slate-500 mb-4 text-center">Yearly Volume</h4>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={barData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="year" stroke="#64748b" />
                        <YAxis stroke="#64748b" />
                        <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', color: '#0f172a' }} itemStyle={{ color: '#0f172a' }} />
                        <Legend verticalAlign="bottom" height={36} />
                        {job?.job_type !== 'download' && visibleVerdicts.neutral && <Bar dataKey="neutral" stackId="a" fill={COLORS.neutral} />}
                        {job?.job_type !== 'download' && visibleVerdicts.reject && <Bar dataKey="reject" stackId="a" fill={COLORS.reject} />}
                        {job?.job_type !== 'download' && visibleVerdicts.support && <Bar dataKey="support" stackId="a" fill={COLORS.support} />}
                        {job?.job_type === 'download' && <Bar dataKey="downloaded" stackId="a" fill={COLORS.downloaded} />}
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Yearly Trends (Line Chart) */}
                  {job?.job_type !== 'download' && (
                    <div className="h-72 lg:col-span-2">
                      <h4 className="text-sm font-medium text-slate-500 mb-4 text-center">Support vs Reject Trends</h4>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={barData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="year" stroke="#64748b" />
                          <YAxis stroke="#64748b" />
                          <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', color: '#0f172a' }} itemStyle={{ color: '#0f172a' }} />
                          <Legend verticalAlign="bottom" height={36} />
                          {visibleVerdicts.support && <Line type="monotone" dataKey="support" stroke={COLORS.support} strokeWidth={2} dot={{ r: 4 }} />}
                          {visibleVerdicts.reject && <Line type="monotone" dataKey="reject" stroke={COLORS.reject} strokeWidth={2} dot={{ r: 4 }} />}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              </div>

              {job?.job_type !== 'download' && (
                <>
                  {/* Filters */}
                  <div className="flex gap-2">
                    {(['all', 'support', 'reject', 'neutral'] as const).map((f) => (
                      <button
                        key={f}
                        onClick={() => { setFilter(f); setPage(1); }}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${filter === f
                          ? 'bg-blue-600 text-white'
                          : 'bg-white border border-slate-200 text-slate-500 hover:bg-slate-50 shadow-sm'
                          }`}
                      >
                        {f.charAt(0).toUpperCase() + f.slice(1)}
                      </button>
                    ))}
                  </div>

                  {/* Sort Dropdown */}
                  <div className="flex items-center gap-3">
                    <label htmlFor="sort-select" className="text-sm font-medium text-slate-500">
                      Sort by:
                    </label>
                    <select
                      id="sort-select"
                      value={`${sortBy}-${sortOrder}`}
                      onChange={(e) => {
                        const [newSortBy, newSortOrder] = e.target.value.split('-')
                        setSortBy(newSortBy)
                        setSortOrder(newSortOrder)
                        setPage(1)
                      }}
                      className="px-4 py-2 rounded-lg text-sm font-medium bg-white text-slate-900 border border-slate-200 shadow-sm hover:border-slate-300 focus:border-blue-500 focus:outline-none transition-colors cursor-pointer"
                    >
                      <option value="confidence-desc">Confidence (High → Low)</option>
                      <option value="confidence-asc">Confidence (Low → High)</option>
                      <option value="year-desc">Year (Newest First)</option>
                      <option value="year-asc">Year (Oldest First)</option>
                      <option value="verdict-asc">Verdict (Support First)</option>
                      <option value="pmid-asc">PMID (Ascending)</option>
                      <option value="pmid-desc">PMID (Descending)</option>
                    </select>
                  </div>

                  {/* Articles List */}
                  <div className="grid gap-4">
                    {results.map((item: any, idx: number) => (
                      <div key={idx} className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm hover:border-blue-500 transition-colors">
                        <div className="flex justify-between mb-2">
                          <span className={`font-bold px-2 py-0.5 rounded text-xs ${item.verdict === 'support' ? 'bg-green-100 text-green-700 border border-green-200' :
                            item.verdict === 'reject' ? 'bg-red-100 text-red-700 border border-red-200' :
                              'bg-blue-100 text-blue-700 border border-blue-200'
                            }`}>
                            {item.verdict.toUpperCase()} ({item.confidence})
                          </span>
                          <div className="flex gap-3 items-center">
                            {item.year && <span className="text-slate-500 text-sm">{item.year}</span>}
                            <a
                              href={`https://pubmed.ncbi.nlm.nih.gov/${item.pmid}/`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-600 hover:text-blue-500 text-sm hover:underline"
                            >
                              PMID: {item.pmid}
                            </a>
                          </div>
                        </div>
                        <h4 className="font-medium text-slate-900 mb-2 line-clamp-2">{item.title}</h4>
                        <p className="text-sm text-slate-600 mb-3">{item.rationale}</p>
                        <details className="text-xs text-slate-500 group">
                          <summary className="cursor-pointer hover:text-slate-800 select-none">Show Abstract</summary>
                          <p className="mt-2 p-3 bg-slate-50 rounded text-slate-600 leading-relaxed border border-slate-200">
                            {item.abstract || "No abstract available for this article."}
                          </p>
                        </details>
                      </div>
                    ))}

                    {results.length === 0 && (
                      <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg border border-slate-200 border-dashed">
                        No results found for this filter.
                      </div>
                    )}
                  </div>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex justify-center gap-2 mt-6">
                      <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="px-3 py-1 rounded bg-white border border-slate-200 text-slate-600 disabled:opacity-50 hover:bg-slate-50 transition-colors"
                      >
                        Previous
                      </button>
                      <span className="px-3 py-1 text-slate-500 flex items-center">
                        Page {page} of {totalPages}
                      </span>
                      <button
                        onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages}
                        className="px-3 py-1 rounded bg-white border border-slate-200 text-slate-600 disabled:opacity-50 hover:bg-slate-50 transition-colors"
                      >
                        Next
                      </button>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
