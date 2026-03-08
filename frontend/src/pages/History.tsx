import { useState } from 'react'
import { useQuery } from 'react-query'
import api from '../lib/axios'
import { useNavigate } from 'react-router-dom'
import { useProject } from '../lib/ProjectContext'

export default function History() {
  const [page, setPage] = useState(1)
  const { currentProject } = useProject()
  const navigate = useNavigate()

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

  const { data: jobsData, isLoading } = useQuery(['jobs-history', page, currentProject?.id], async () => {
    if (!currentProject) return { items: [], total: 0, pages: 1 }
    const res = await api.get('/jobs', { params: { project_id: currentProject.id, page, limit: 20 } })
    return res.data
  }, {
    enabled: !!currentProject,
    keepPreviousData: true
  })

  const jobs = jobsData?.items || []
  const totalPages = jobsData?.pages || 1

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6 text-slate-900">Job History</h2>

      {isLoading && !jobs.length ? (
        <div className="text-center py-12 text-slate-400">Loading history...</div>
      ) : (
        <>
          <div className="grid gap-3">
            {jobs.map((job: any) => (
              <div
                key={job.id}
                onClick={() => navigate(`/${currentProject?.id}/jobs/${job.id}`)}
                className="bg-white p-6 rounded-xl border border-slate-200 hover:border-blue-400 cursor-pointer transition-all shadow-sm flex flex-col sm:flex-row justify-between sm:items-center gap-4"
              >
                <div className="space-y-2 flex-grow min-w-0">
                  <div className="flex items-center gap-4 flex-wrap">
                    <span className="text-lg font-bold text-slate-900">
                      {job.name?.replace('Force-Download: ', '') || job.query_term}
                    </span>
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
                          <span className="text-xs text-blue-600 bg-blue-50 px-3 py-1 rounded border border-blue-100 font-mono hidden sm:inline-block">
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
                  <div className="text-sm text-slate-500 truncate max-w-2xl">
                    {job.hypothesis || job.query_term}
                  </div>
                </div>
                <div className="text-sm text-slate-400 font-medium whitespace-nowrap flex-shrink-0">
                  {new Date(job.created_at).toLocaleDateString()}
                </div>
              </div>
            ))}
            {jobs.length === 0 && (
              <div className="text-center py-20 bg-slate-50 rounded-xl border border-dashed border-slate-200 text-slate-400">
                No job history found.
              </div>
            )}
          </div>

          {/* Pagination Controls */}
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
    </div>
  )
}
