import { useState } from 'react'
import { Copy, ChevronDown, ChevronRight, Terminal, Zap, Database, Settings, FlaskConical, BookOpen, Key, Code2, Play } from 'lucide-react'

const BASE_URL = `${window.location.origin}/api/v1`
const BASE_ORIGIN = window.location.origin

// ─── Primitives ───────────────────────────────────────────────────────────────

function useClipboard(ms = 1800) {
    const [copied, setCopied] = useState<string | null>(null)
    const copy = (text: string, id: string) => {
        navigator.clipboard.writeText(text)
        setCopied(id)
        setTimeout(() => setCopied(null), ms)
    }
    return { copied, copy }
}

type Lang = 'python' | 'bash' | 'json' | 'text'

function CodeBlock({ code, id, lang = 'python' }: { code: string; id: string; lang?: Lang }) {
    const { copied, copy } = useClipboard()
    const langLabel: Record<Lang, string> = { python: 'Python', bash: 'Shell', json: 'JSON', text: 'Text' }
    const langColor: Record<Lang, string> = {
        python: 'text-blue-400', bash: 'text-emerald-400', json: 'text-amber-400', text: 'text-slate-400'
    }
    return (
        <div className="relative group rounded-xl overflow-hidden border border-slate-700">
            <div className="flex items-center justify-between bg-slate-800 px-4 py-2 border-b border-slate-700">
                <span className={`text-xs font-semibold font-mono ${langColor[lang]}`}>{langLabel[lang]}</span>
                <button
                    onClick={() => copy(code, id)}
                    className="flex items-center gap-1.5 px-2 py-1 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded text-xs transition-colors"
                >
                    <Copy size={11} />
                    {copied === id ? 'Copied!' : 'Copy'}
                </button>
            </div>
            <pre className="bg-slate-900 text-slate-100 p-4 text-xs overflow-x-auto leading-relaxed font-mono whitespace-pre">
                {code}
            </pre>
        </div>
    )
}

function Badge({ method }: { method: string }) {
    const colors: Record<string, string> = {
        GET: 'bg-emerald-100 text-emerald-700 border-emerald-200',
        POST: 'bg-blue-100 text-blue-700 border-blue-200',
        PUT: 'bg-amber-100 text-amber-700 border-amber-200',
        DELETE: 'bg-red-100 text-red-700 border-red-200',
    }
    return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-mono font-bold border ${colors[method] ?? 'bg-slate-100 text-slate-600 border-slate-200'}`}>
            {method}
        </span>
    )
}

interface Param { name: string; type: string; required?: boolean; description: string; default?: string }
interface EndpointDef {
    method: string; path: string; summary: string
    description?: string
    params?: Param[]
    body?: string
    response?: string
    python?: string
    curl?: string
}

function Endpoint({ ep }: { ep: EndpointDef }) {
    const [open, setOpen] = useState(false)
    const [tab, setTab] = useState<'python' | 'curl'>('python')
    return (
        <div className="border border-slate-200 rounded-xl overflow-hidden">
            <button
                onClick={() => setOpen(o => !o)}
                className="w-full flex items-center gap-3 px-5 py-3.5 bg-white hover:bg-slate-50 transition-colors text-left"
            >
                <Badge method={ep.method} />
                <code className="text-sm font-mono text-slate-800 flex-1">{ep.path}</code>
                <span className="text-sm text-slate-400 hidden md:block truncate max-w-xs">{ep.summary}</span>
                {open ? <ChevronDown size={16} className="text-slate-400 shrink-0" /> : <ChevronRight size={16} className="text-slate-400 shrink-0" />}
            </button>

            {open && (
                <div className="border-t border-slate-200 bg-slate-50 p-5 space-y-5">
                    {ep.description && (
                        <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">{ep.description}</p>
                    )}

                    {ep.params && ep.params.length > 0 && (
                        <div>
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Parameters</h4>
                            <div className="bg-white border border-slate-200 rounded-lg divide-y divide-slate-100">
                                {ep.params.map(p => (
                                    <div key={p.name} className="flex items-start gap-4 px-4 py-2.5 text-sm">
                                        <code className="font-mono text-xs bg-slate-100 border border-slate-200 px-2 py-0.5 rounded text-violet-700 shrink-0 mt-0.5">{p.name}</code>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-0.5">
                                                <span className="text-xs text-slate-400">{p.type}</span>
                                                {p.required && <span className="text-xs text-red-500 font-medium">required</span>}
                                                {p.default && <span className="text-xs text-slate-400">default: <code className="font-mono">{p.default}</code></span>}
                                            </div>
                                            <span className="text-xs text-slate-600">{p.description}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {ep.body && (
                        <div>
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Request Body</h4>
                            <CodeBlock code={ep.body} id={`body-${ep.method}-${ep.path}`} lang="json" />
                        </div>
                    )}

                    {ep.response && (
                        <div>
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Response</h4>
                            <CodeBlock code={ep.response} id={`res-${ep.method}-${ep.path}`} lang="json" />
                        </div>
                    )}

                    {(ep.python || ep.curl) && (
                        <div>
                            <div className="flex items-center gap-2 mb-2">
                                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest">Example</h4>
                                <div className="flex border border-slate-200 rounded-lg overflow-hidden text-xs">
                                    {ep.python && (
                                        <button onClick={() => setTab('python')} className={`px-3 py-1 font-medium transition-colors ${tab === 'python' ? 'bg-violet-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}>Python</button>
                                    )}
                                    {ep.curl && (
                                        <button onClick={() => setTab('curl')} className={`px-3 py-1 font-medium transition-colors ${tab === 'curl' ? 'bg-violet-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}>curl</button>
                                    )}
                                </div>
                            </div>
                            {tab === 'python' && ep.python && <CodeBlock code={ep.python} id={`py-${ep.method}-${ep.path}`} lang="python" />}
                            {tab === 'curl' && ep.curl && <CodeBlock code={ep.curl} id={`curl-${ep.method}-${ep.path}`} lang="bash" />}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

// ─── Endpoint catalogue ───────────────────────────────────────────────────────

const PY_SETUP = `import requests

BASE_URL = "${BASE_URL}"
API_KEY  = "blv_your_key_here"          # Project Settings → API Keys
HEADERS  = {"X-Api-Key": API_KEY}

# qwen_retriever query format (JSON string)
QUERY = '{"q": "dopamine neurotransmission schizophrenia nucleus accumbens", "n": 1000}'
# Optional date filtering:
# QUERY = '{"q": "...", "n": 500, "start_date": "2015-01-01", "end_date": "2024-12-31"}'`

const SECTIONS: { id: string; title: string; icon: React.ReactNode; description: string; endpoints: EndpointDef[] }[] = [
    {
        id: 'project',
        title: 'Project',
        icon: <BookOpen size={18} />,
        description: 'Retrieve information about the project linked to your API key.',
        endpoints: [
            {
                method: 'GET', path: '/api/v1/project', summary: 'Get project info',
                description: 'Returns name, description, and creation date of the project this API key belongs to.',
                response: JSON.stringify({ id: 13, name: 'api test project', description: 'api test project', created_at: '2026-04-28T06:37:20Z' }, null, 2),
                python: `${PY_SETUP}

resp = requests.get(f"{BASE_URL}/project", headers=HEADERS)
project = resp.json()
print(project["name"])   # → "api test project"`,
                curl: `curl -H "X-Api-Key: blv_your_key_here" \\
  ${BASE_URL}/project`,
            },
        ],
    },
    {
        id: 'datasets',
        title: 'Datasets',
        icon: <Database size={18} />,
        description: 'Manage dataset configurations. qwen_retriever uses natural-language semantic search — pass the query as a JSON string with "q" and "n" fields.',
        endpoints: [
            {
                method: 'GET', path: '/api/v1/datasets', summary: 'List dataset configs',
                description: 'Returns all saved dataset configs with their current download status.',
                response: JSON.stringify([
                    { id: 88, name: 'DA & SZ — Qwen Semantic (n=1000)', source_type: 'qwen_retriever',
                      query: '{"q": "dopamine neurotransmission schizophrenia nucleus accumbens caudate", "n": 1000}',
                      is_downloaded: true, download_job_id: 445, download_job_status: 'completed', progress_text: null }
                ], null, 2),
                python: `${PY_SETUP}

datasets = requests.get(f"{BASE_URL}/datasets", headers=HEADERS).json()
for d in datasets:
    status = "✓ ready" if d["is_downloaded"] else f"⏳ {d['download_job_status']}"
    print(f"[{d['id']}] {d['name']}  {status}")`,
                curl: `curl -H "X-Api-Key: blv_your_key_here" ${BASE_URL}/datasets`,
            },
            {
                method: 'POST', path: '/api/v1/datasets', summary: 'Create dataset config',
                description: `Save a new dataset config. A DOWNLOAD job is queued automatically to pre-cache all matching PMIDs and abstracts.

── qwen_retriever (권장) ─────────────────────────────────────────────
  자연어로 의미 기반 검색. query는 아래 형식의 JSON 문자열로 전달:

  기본형:
    {"q": "natural language query", "n": 1000}

  날짜 필터 포함:
    {"q": "natural language query", "n": 500,
     "start_date": "2015-01-01", "end_date": "2024-12-31"}

  q  — 자연어 검색어 (의미 기반, 키워드 그대로 쓰면 됨)
  n  — 가져올 논문 수 (서버 내 임베딩 DB에서 유사도 순 상위 n개)

── 다른 source_type ─────────────────────────────────────────────────
  pubtator3   — @CHEMICAL_Dopamine AND @DISEASE_Schizophrenia
  pubmed      — dopamine schizophrenia[MeSH Terms]
  txt_file    — "12345678,23456789,34567890"  (PMID 목록 직접 입력)`,
                body: JSON.stringify({
                    name: 'DA & SZ — Qwen Semantic (n=1000)',
                    source_type: 'qwen_retriever',
                    query: '{"q": "dopamine neurotransmission schizophrenia nucleus accumbens caudate", "n": 1000}',
                }, null, 2),
                response: JSON.stringify({
                    id: 88, name: 'DA & SZ — Qwen Semantic (n=1000)', source_type: 'qwen_retriever',
                    query: '{"q": "dopamine neurotransmission schizophrenia nucleus accumbens caudate", "n": 1000}',
                    is_downloaded: false, download_job_id: 445, download_job_status: 'queued',
                    created_at: '2026-04-28T06:43:47Z',
                }, null, 2),
                python: `${PY_SETUP}
import json

# query는 JSON 문자열로 전달 (dict가 아님에 주의)
qwen_query = json.dumps({
    "q": "dopamine neurotransmission schizophrenia nucleus accumbens caudate",
    "n": 1000,
    # "start_date": "2010-01-01",  # 선택: 날짜 범위 필터
    # "end_date":   "2024-12-31",
})

dataset = requests.post(f"{BASE_URL}/datasets", headers=HEADERS, json={
    "name":        "DA & SZ — Qwen Semantic (n=1000)",
    "source_type": "qwen_retriever",
    "query":       qwen_query,
}).json()

print(f"Dataset {dataset['id']} created")
print(f"Download job {dataset['download_job_id']} is {dataset['download_job_status']}")`,
                curl: String.raw`curl -X POST ${BASE_URL}/datasets \
  -H "X-Api-Key: blv_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DA & SZ — Qwen Semantic (n=1000)",
    "source_type": "qwen_retriever",
    "query": "{\"q\": \"dopamine neurotransmission schizophrenia nucleus accumbens caudate\", \"n\": 1000}"
  }'`,
            },
            {
                method: 'POST', path: '/api/v1/datasets/{config_id}/pre-download', summary: 'Trigger pre-download',
                description: '다운로드 전용 job을 큐에 올립니다. 데이터셋 생성 시 자동으로 큐에 올라가지만, 강제 재다운로드가 필요할 때 사용합니다.',
                params: [{ name: 'config_id', type: 'integer', required: true, description: 'Dataset config ID' }],
                response: JSON.stringify({ message: 'Pre-download job queued', job_id: 445 }, null, 2),
                python: `${PY_SETUP}
import time

DATASET_ID = 88

# 재다운로드 트리거
r = requests.post(f"{BASE_URL}/datasets/{DATASET_ID}/pre-download", headers=HEADERS).json()
dl_job_id = r["job_id"]
print(f"Download job {dl_job_id} queued")

# 완료될 때까지 대기
while True:
    job = requests.get(f"{BASE_URL}/jobs/{dl_job_id}", headers=HEADERS).json()
    print(f"  [{job['status']}]  {job.get('progress_text') or ''}")
    if job["status"] in ("completed", "failed", "stopped"):
        break
    time.sleep(10)`,
                curl: `curl -X POST ${BASE_URL}/datasets/88/pre-download \\
  -H "X-Api-Key: blv_your_key_here"`,
            },
            {
                method: 'PUT', path: '/api/v1/datasets/{config_id}', summary: 'Update dataset config',
                params: [{ name: 'config_id', type: 'integer', required: true, description: 'Dataset config ID to update' }],
                body: JSON.stringify({
                    name: 'DA & SZ — Qwen (2015–2024, n=500)',
                    source_type: 'qwen_retriever',
                    query: '{"q": "dopamine neurotransmission schizophrenia", "n": 500, "start_date": "2015-01-01", "end_date": "2024-12-31"}',
                }, null, 2),
                python: `${PY_SETUP}
import json

requests.put(f"{BASE_URL}/datasets/88", headers=HEADERS, json={
    "name":        "DA & SZ — Qwen (2015–2024, n=500)",
    "source_type": "qwen_retriever",
    "query":       json.dumps({
        "q": "dopamine neurotransmission schizophrenia",
        "n": 500,
        "start_date": "2015-01-01",
        "end_date":   "2024-12-31",
    }),
})`,
                curl: String.raw`curl -X PUT ${BASE_URL}/datasets/88 \
  -H "X-Api-Key: blv_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DA & SZ — Qwen (2015–2024, n=500)",
    "source_type": "qwen_retriever",
    "query": "{\"q\": \"dopamine neurotransmission schizophrenia\", \"n\": 500, \"start_date\": \"2015-01-01\", \"end_date\": \"2024-12-31\"}"
  }'`,
            },
            {
                method: 'DELETE', path: '/api/v1/datasets/{config_id}', summary: 'Delete dataset config',
                description: 'Removes the config, stops any running download jobs, and clears the query cache so a new dataset will re-fetch from scratch.',
                params: [{ name: 'config_id', type: 'integer', required: true, description: 'Dataset config ID to delete' }],
                response: JSON.stringify({ message: 'Deleted' }, null, 2),
                python: `${PY_SETUP}

requests.delete(f"{BASE_URL}/datasets/88", headers=HEADERS)`,
                curl: `curl -X DELETE ${BASE_URL}/datasets/88 \\
  -H "X-Api-Key: blv_your_key_here"`,
            },
        ],
    },
    {
        id: 'model-configs',
        title: 'Model Configs',
        icon: <Settings size={18} />,
        description: 'Save reusable LLM configurations (endpoint, model name, temperature, concurrency). Reference them in jobs with model_config_id.',
        endpoints: [
            {
                method: 'GET', path: '/api/v1/model-configs', summary: 'List model configs',
                response: JSON.stringify([
                    { id: 16, name: 'oss-120b-4096-concurrency', openai_model: 'openai/gpt-oss-120b',
                      openai_base_url: 'http://143.248.74.105:11434/v1', llm_temperature: 0.0, llm_concurrency_limit: 4096 }
                ], null, 2),
                python: `${PY_SETUP}

configs = requests.get(f"{BASE_URL}/model-configs", headers=HEADERS).json()
for c in configs:
    print(f"[{c['id']}] {c['name']}  concurrency={c['llm_concurrency_limit']}")`,
                curl: `curl -H "X-Api-Key: blv_your_key_here" ${BASE_URL}/model-configs`,
            },
            {
                method: 'POST', path: '/api/v1/model-configs', summary: 'Create model config',
                description: `Save a reusable LLM configuration.

llm_concurrency_limit: 동시에 LLM에 보내는 논문 수.
  로컬 모델은 64–512 권장. 서버 스펙에 따라 조절.
llm_temperature: 0.0 권장 (판정 일관성).
system_prompt: null이면 내장 바이오의학 리뷰어 프롬프트 사용.`,
                body: JSON.stringify({
                    name: 'oss-120b-4096-concurrency',
                    openai_api_key: 'your-api-key',
                    openai_model: 'openai/gpt-oss-120b',
                    openai_base_url: 'http://143.248.74.105:11434/v1',
                    system_prompt: null,
                    llm_concurrency_limit: 4096,
                    llm_temperature: 0.0,
                }, null, 2),
                response: JSON.stringify({ id: 16, name: 'oss-120b-4096-concurrency', owner_id: 4, created_at: '2026-04-28T06:38:14Z' }, null, 2),
                python: `${PY_SETUP}

cfg = requests.post(f"{BASE_URL}/model-configs", headers=HEADERS, json={
    "name":                  "oss-120b-4096-concurrency",
    "openai_api_key":        "your-api-key",
    "openai_model":          "openai/gpt-oss-120b",
    "openai_base_url":       "http://143.248.74.105:11434/v1",
    "llm_concurrency_limit": 4096,
    "llm_temperature":       0.0,
    "system_prompt":         None,   # None → 내장 바이오의학 프롬프트 사용
}).json()

MODEL_CONFIG_ID = cfg["id"]
print(f"Model config {MODEL_CONFIG_ID} saved")`,
                curl: `curl -X POST ${BASE_URL}/model-configs \\
  -H "X-Api-Key: blv_your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"oss-120b","openai_model":"openai/gpt-oss-120b","openai_base_url":"http://143.248.74.105:11434/v1","llm_concurrency_limit":4096,"llm_temperature":0.0}'`,
            },
            {
                method: 'PUT', path: '/api/v1/model-configs/{config_id}', summary: 'Update model config',
                params: [{ name: 'config_id', type: 'integer', required: true, description: 'Model config ID to update' }],
                python: `${PY_SETUP}

requests.put(f"{BASE_URL}/model-configs/16", headers=HEADERS, json={
    "name":                  "oss-120b-4096-concurrency",
    "openai_model":          "openai/gpt-oss-120b",
    "openai_base_url":       "http://143.248.74.105:11434/v1",
    "llm_concurrency_limit": 2048,   # 조정
    "llm_temperature":       0.0,
})`,
                curl: `curl -X PUT ${BASE_URL}/model-configs/16 \\
  -H "X-Api-Key: blv_your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"oss-120b","openai_model":"openai/gpt-oss-120b","openai_base_url":"http://143.248.74.105:11434/v1","llm_concurrency_limit":2048}'`,
            },
            {
                method: 'DELETE', path: '/api/v1/model-configs/{config_id}', summary: 'Delete model config',
                params: [{ name: 'config_id', type: 'integer', required: true, description: 'Model config ID to delete' }],
                python: `${PY_SETUP}

requests.delete(f"{BASE_URL}/model-configs/16", headers=HEADERS)`,
                curl: `curl -X DELETE ${BASE_URL}/model-configs/16 -H "X-Api-Key: blv_your_key_here"`,
            },
        ],
    },
    {
        id: 'analysis-configs',
        title: 'Analysis Configs',
        icon: <FlaskConical size={18} />,
        description: 'Store hypothesis text + default dataset pairings for quick, repeatable analysis launches.',
        endpoints: [
            {
                method: 'GET', path: '/api/v1/analysis-configs', summary: 'List analysis configs',
                response: JSON.stringify([
                    { id: 1, name: 'DA hypothesis v1',
                      hypothesis: 'Dopaminergic neurotransmission starting from the nucleus accumbens to the caudate nucleus is elevated in schizophrenia patients.',
                      default_dataset_id: 88 }
                ], null, 2),
                python: `${PY_SETUP}

configs = requests.get(f"{BASE_URL}/analysis-configs", headers=HEADERS).json()
for c in configs:
    print(f"[{c['id']}] {c['name']}")
    print(f"    {c['hypothesis'][:80]}...")`,
                curl: `curl -H "X-Api-Key: blv_your_key_here" ${BASE_URL}/analysis-configs`,
            },
            {
                method: 'POST', path: '/api/v1/analysis-configs', summary: 'Create analysis config',
                description: 'default_dataset_id로 dataset을 연결해두면 job 생성 시 query 반복 없이 불러와 사용 가능.',
                body: JSON.stringify({
                    name: 'DA hypothesis v1',
                    hypothesis: 'Dopaminergic neurotransmission starting from the nucleus accumbens to the caudate nucleus is elevated in patients with schizophrenia.',
                    default_dataset_id: 88,
                }, null, 2),
                python: `${PY_SETUP}

ac = requests.post(f"{BASE_URL}/analysis-configs", headers=HEADERS, json={
    "name":               "DA hypothesis v1",
    "hypothesis":         "Dopaminergic neurotransmission starting from the nucleus "
                          "accumbens to the caudate nucleus is elevated in "
                          "patients with schizophrenia.",
    "default_dataset_id": 88,   # qwen_retriever 데이터셋과 연결
}).json()
print(f"Analysis config {ac['id']} saved")`,
                curl: `curl -X POST ${BASE_URL}/analysis-configs \\
  -H "X-Api-Key: blv_your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"DA v1","hypothesis":"Dopaminergic neurotransmission is elevated in schizophrenia.","default_dataset_id":88}'`,
            },
            {
                method: 'PUT', path: '/api/v1/analysis-configs/{config_id}', summary: 'Update analysis config',
                params: [{ name: 'config_id', type: 'integer', required: true, description: 'Analysis config ID' }],
                python: `${PY_SETUP}

requests.put(f"{BASE_URL}/analysis-configs/1", headers=HEADERS, json={
    "name":               "DA hypothesis v2",
    "hypothesis":         "수정된 가설 텍스트.",
    "default_dataset_id": 88,
})`,
                curl: `curl -X PUT ${BASE_URL}/analysis-configs/1 \\
  -H "X-Api-Key: blv_your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"DA v2","hypothesis":"Updated hypothesis.","default_dataset_id":88}'`,
            },
            {
                method: 'DELETE', path: '/api/v1/analysis-configs/{config_id}', summary: 'Delete analysis config',
                params: [{ name: 'config_id', type: 'integer', required: true, description: 'Analysis config ID' }],
                python: `${PY_SETUP}

requests.delete(f"{BASE_URL}/analysis-configs/1", headers=HEADERS)`,
                curl: `curl -X DELETE ${BASE_URL}/analysis-configs/1 -H "X-Api-Key: blv_your_key_here"`,
            },
        ],
    },
    {
        id: 'jobs',
        title: 'Jobs',
        icon: <Zap size={18} />,
        description: 'Create and monitor hypothesis-validation analysis jobs. Each job searches PubMed via qwen_retriever, downloads abstracts, and evaluates them with an LLM.',
        endpoints: [
            {
                method: 'POST', path: '/api/v1/jobs', summary: 'Create analysis job',
                description: `hypothesis-validation job을 큐에 올립니다. QueueManager가 자동으로 픽업합니다.

query_term (qwen_retriever):
  JSON 문자열 형식으로 전달합니다.
  {"q": "natural language query", "n": 1000}
  {"q": "...", "n": 500, "start_date": "2015-01-01", "end_date": "2024-12-31"}

max_articles:
  -1  → query에서 n개 전부 사용
  N   → n개 중 무작위 N개만 분석 (빠른 테스트용)

model_config_id:
  저장된 ModelConfig를 상속합니다.
  body에 명시한 openai_* 필드가 config 값을 덮어씁니다.

source_type:
  qwen_retriever  — 자연어 의미 기반 검색 (권장)
  pubtator3       — @CHEMICAL_X AND @DISEASE_Y 형식
  pubmed          — PubMed/MeSH 키워드 쿼리
  txt_file        — PMID 목록 직접 입력`,
                body: JSON.stringify({
                    name: 'DA Hypothesis — Qwen 1000',
                    query_term: '{"q": "dopamine neurotransmission schizophrenia nucleus accumbens caudate", "n": 1000}',
                    hypothesis: 'Dopaminergic neurotransmission starting from the nucleus accumbens to the caudate nucleus is elevated in patients with schizophrenia.',
                    source_type: 'qwen_retriever',
                    max_articles: 1000,
                    model_config_id: 16,
                }, null, 2),
                response: JSON.stringify({ id: 446, status: 'queued', name: 'DA Hypothesis — Qwen 1000', created_at: '2026-04-28T06:44:17Z' }, null, 2),
                python: `${PY_SETUP}
import json

job = requests.post(f"{BASE_URL}/jobs", headers=HEADERS, json={
    "name":         "DA Hypothesis — Qwen 1000",
    "query_term":   json.dumps({
        "q": "dopamine neurotransmission schizophrenia nucleus accumbens caudate",
        "n": 1000,
        # "start_date": "2010-01-01",   # 선택
        # "end_date":   "2024-12-31",
    }),
    "hypothesis":   "Dopaminergic neurotransmission starting from the nucleus "
                    "accumbens to the caudate nucleus is elevated in "
                    "patients with schizophrenia.",
    "source_type":  "qwen_retriever",
    "max_articles": 1000,

    # 저장된 model config 사용 (권장)
    "model_config_id": 16,

    # 또는 직접 지정:
    # "openai_api_key":        "your-key",
    # "openai_model":          "openai/gpt-oss-120b",
    # "openai_base_url":       "http://143.248.74.105:11434/v1",
    # "llm_concurrency_limit": 4096,
    # "llm_temperature":       0.0,
}).json()

JOB_ID = job["id"]
print(f"Job {JOB_ID} queued (status: {job['status']})")`,
                curl: String.raw`curl -X POST ${BASE_URL}/jobs \
  -H "X-Api-Key: blv_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DA Hypothesis — Qwen 1000",
    "query_term": "{\"q\": \"dopamine neurotransmission schizophrenia nucleus accumbens caudate\", \"n\": 1000}",
    "hypothesis": "Dopaminergic neurotransmission is elevated in schizophrenia patients.",
    "source_type": "qwen_retriever",
    "max_articles": 1000,
    "model_config_id": 16
  }'`,
            },
            {
                method: 'GET', path: '/api/v1/jobs', summary: 'List jobs (paginated)',
                params: [
                    { name: 'page', type: 'integer', description: 'Page number', default: '1' },
                    { name: 'limit', type: 'integer', description: 'Items per page (max 100)', default: '20' },
                    { name: 'status', type: 'string', description: 'Filter: queued | running | completed | failed | stopped' },
                ],
                response: JSON.stringify({ items: [{ id: 42, status: 'completed', name: 'DA Run 1', progress_text: null }], total: 1, page: 1, limit: 20, pages: 1 }, null, 2),
                python: `${PY_SETUP}

# List all completed jobs
resp = requests.get(f"{BASE_URL}/jobs", headers=HEADERS,
                    params={"status": "completed", "page": 1, "limit": 50}).json()
print(f"{resp['total']} completed jobs")
for j in resp["items"]:
    print(f"  [{j['id']}] {j['name']}")`,
                curl: `curl -H "X-Api-Key: blv_your_key_here" \\
  "${BASE_URL}/jobs?status=completed&page=1&limit=20"`,
            },
            {
                method: 'GET', path: '/api/v1/jobs/{job_id}', summary: 'Get job status',
                params: [{ name: 'job_id', type: 'integer', required: true, description: 'Job ID' }],
                response: JSON.stringify({
                    id: 42, status: 'running', name: 'DA Run 1',
                    progress_text: '[3/3] Evaluating articles... 243/500',
                    started_at: '2025-01-10T09:31:00Z', finished_at: null,
                }, null, 2),
                python: `${PY_SETUP}
import time

JOB_ID = 42

while True:
    job = requests.get(f"{BASE_URL}/jobs/{JOB_ID}", headers=HEADERS).json()
    status = job["status"]
    progress = job.get("progress_text") or ""
    print(f"  [{status}]  {progress}")

    if status == "completed":
        print("Done!")
        break
    elif status in ("failed", "stopped"):
        print("Job did not finish successfully")
        break

    time.sleep(10)`,
                curl: `curl -H "X-Api-Key: blv_your_key_here" ${BASE_URL}/jobs/42`,
            },
            {
                method: 'POST', path: '/api/v1/jobs/{job_id}/stop', summary: 'Stop a running job',
                params: [{ name: 'job_id', type: 'integer', required: true, description: 'Job ID' }],
                response: JSON.stringify({ message: 'Job stopped' }, null, 2),
                python: `${PY_SETUP}

requests.post(f"{BASE_URL}/jobs/42/stop", headers=HEADERS)`,
                curl: `curl -X POST ${BASE_URL}/jobs/42/stop -H "X-Api-Key: blv_your_key_here"`,
            },
            {
                method: 'GET', path: '/api/v1/jobs/{job_id}/logs', summary: 'Get job logs',
                description: 'Returns the raw pipeline log output — useful for debugging failed jobs or checking progress details.',
                params: [{ name: 'job_id', type: 'integer', required: true, description: 'Job ID' }],
                response: JSON.stringify({ logs: '[1/3] Searching Pages: 100%|██████| 12/12\n[2/3] Fetching Abstracts: 100%|██████| 6/6\n[3/3] Evaluating: 500/500 done' }, null, 2),
                python: `${PY_SETUP}

logs = requests.get(f"{BASE_URL}/jobs/42/logs", headers=HEADERS).json()
print(logs["logs"])`,
                curl: `curl -H "X-Api-Key: blv_your_key_here" ${BASE_URL}/jobs/42/logs`,
            },
            {
                method: 'GET', path: '/api/v1/jobs/{job_id}/results', summary: 'Get results (paginated JSON)',
                description: 'Article-level evaluation results. Each item has verdict, confidence, and rationale.',
                params: [
                    { name: 'job_id', type: 'integer', required: true, description: 'Job ID' },
                    { name: 'page', type: 'integer', description: 'Page number', default: '1' },
                    { name: 'limit', type: 'integer', description: 'Items per page (max 200)', default: '20' },
                    { name: 'filter', type: 'string', description: 'all | support | reject | neutral', default: 'all' },
                    { name: 'sort_by', type: 'string', description: 'confidence | year | verdict | pmid | title', default: 'confidence' },
                    { name: 'order', type: 'string', description: 'asc | desc', default: 'desc' },
                ],
                response: JSON.stringify({
                    items: [{
                        pmid: '12345678', title: 'Dopamine D2 upregulation in schizophrenia caudate', year: '2021',
                        verdict: 'support', confidence: 'HIGH',
                        rationale: 'The abstract explicitly reports elevated D2 receptor binding in the caudate nucleus, directly supporting the hypothesis.',
                        abstract: '...',
                    }],
                    total: 500, page: 1, limit: 20, pages: 25,
                }, null, 2),
                python: `${PY_SETUP}

JOB_ID = 42

# Fetch all supporting articles (iterate pages)
all_support = []
page = 1
while True:
    resp = requests.get(f"{BASE_URL}/jobs/{JOB_ID}/results", headers=HEADERS,
                        params={"filter": "support", "sort_by": "confidence",
                                "order": "desc", "page": page, "limit": 100}).json()
    all_support.extend(resp["items"])
    if page >= resp["pages"]:
        break
    page += 1

print(f"Found {len(all_support)} supporting articles")
for r in all_support[:5]:
    print(f"  [{r['confidence']}] {r['title'][:60]}")
    print(f"    → {r['rationale'][:100]}...")`,
                curl: `curl -H "X-Api-Key: blv_your_key_here" \\
  "${BASE_URL}/jobs/42/results?filter=support&sort_by=confidence&order=desc&limit=50"`,
            },
            {
                method: 'GET', path: '/api/v1/jobs/{job_id}/stats', summary: 'Get verdict statistics',
                description: 'Aggregated verdict counts + year-by-year breakdown. Great for building charts without loading all results.',
                params: [{ name: 'job_id', type: 'integer', required: true, description: 'Job ID' }],
                response: JSON.stringify({
                    verdict_counts: { support: 180, reject: 95, neutral: 225 },
                    year_data: [
                        { year: '2019', support: 18, reject: 10, neutral: 25 },
                        { year: '2020', support: 22, reject: 14, neutral: 30 },
                        { year: '2021', support: 31, reject: 18, neutral: 42 },
                    ],
                }, null, 2),
                python: `${PY_SETUP}

stats = requests.get(f"{BASE_URL}/jobs/42/stats", headers=HEADERS).json()
counts = stats["verdict_counts"]
total  = sum(counts.values())

print(f"Support : {counts.get('support', 0):4d}  ({counts.get('support',0)/total*100:.1f}%)")
print(f"Reject  : {counts.get('reject',  0):4d}  ({counts.get('reject', 0)/total*100:.1f}%)")
print(f"Neutral : {counts.get('neutral', 0):4d}  ({counts.get('neutral',0)/total*100:.1f}%)")`,
                curl: `curl -H "X-Api-Key: blv_your_key_here" ${BASE_URL}/jobs/42/stats`,
            },
            {
                method: 'GET', path: '/api/v1/jobs/{job_id}/csv', summary: 'Download results as CSV',
                description: 'Streams all results as a CSV file. Columns: pmid, title, year, abstract, verdict, confidence, rationale.',
                params: [{ name: 'job_id', type: 'integer', required: true, description: 'Job ID' }],
                python: `${PY_SETUP}

resp = requests.get(f"{BASE_URL}/jobs/42/csv", headers=HEADERS)
with open("results.csv", "wb") as f:
    f.write(resp.content)
print("Saved results.csv")

# Or read directly into pandas:
import io, pandas as pd
df = pd.read_csv(io.BytesIO(resp.content))
print(df["verdict"].value_counts())`,
                curl: `curl -H "X-Api-Key: blv_your_key_here" \\
  -o results.csv \\
  ${BASE_URL}/jobs/42/csv`,
            },
            {
                method: 'GET', path: '/api/v1/jobs/{job_id}/image', summary: 'Download summary chart (PNG)',
                description: 'Returns the verdict distribution bar chart generated after job completion.',
                params: [{ name: 'job_id', type: 'integer', required: true, description: 'Job ID' }],
                python: `${PY_SETUP}

resp = requests.get(f"{BASE_URL}/jobs/42/image", headers=HEADERS)
with open("summary.png", "wb") as f:
    f.write(resp.content)
print("Saved summary.png")`,
                curl: `curl -H "X-Api-Key: blv_your_key_here" \\
  -o summary.png \\
  ${BASE_URL}/jobs/42/image`,
            },
        ],
    },
]

// ─── Complete workflow examples ───────────────────────────────────────────────

const EXAMPLE_QUICKSTART = `"""
Quickstart — run a hypothesis validation job from scratch using Qwen Retriever.
pip install requests
"""
import json, time
import requests

BASE_URL        = "${BASE_URL}"
API_KEY         = "blv_your_key_here"
HEADERS         = {"X-Api-Key": API_KEY}
MODEL_CONFIG_ID = 16   # use an existing model config (see GET /model-configs)

# qwen_retriever query: semantic vector search, fetch top-N articles
QUERY = json.dumps({"q": "dopamine schizophrenia nucleus accumbens caudate", "n": 1000})

# ── Step 1: Create a job ──────────────────────────────────────────────────────
job = requests.post(f"{BASE_URL}/jobs", headers=HEADERS, json={
    "name":             "Dopamine & Schizophrenia — Qwen Run 1",
    "query_term":       QUERY,
    "hypothesis":       "Dopaminergic neurotransmission starting from the nucleus "
                        "accumbens to the caudate nucleus is elevated in schizophrenia.",
    "source_type":      "qwen_retriever",
    "max_articles":     300,
    "model_config_id":  MODEL_CONFIG_ID,
}).json()

JOB_ID = job["id"]
print(f"✓ Job {JOB_ID} queued")

# ── Step 2: Poll until done ───────────────────────────────────────────────────
while True:
    info = requests.get(f"{BASE_URL}/jobs/{JOB_ID}", headers=HEADERS).json()
    status   = info["status"]
    progress = info.get("progress_text") or ""
    print(f"  [{status}]  {progress}")

    if status == "completed":
        break
    elif status in ("failed", "stopped"):
        raise RuntimeError(f"Job ended with status: {status}")
    time.sleep(10)

# ── Step 3: Print summary statistics ─────────────────────────────────────────
stats  = requests.get(f"{BASE_URL}/jobs/{JOB_ID}/stats", headers=HEADERS).json()
counts = stats["verdict_counts"]
total  = sum(counts.values())

print("\\n── Results ──────────────────────────")
print(f"  Support : {counts.get('support',0):4d}  ({counts.get('support',0)/total*100:.1f}%)")
print(f"  Reject  : {counts.get('reject', 0):4d}  ({counts.get('reject', 0)/total*100:.1f}%)")
print(f"  Neutral : {counts.get('neutral',0):4d}  ({counts.get('neutral',0)/total*100:.1f}%)")

# ── Step 4: Save CSV ──────────────────────────────────────────────────────────
csv_bytes = requests.get(f"{BASE_URL}/jobs/{JOB_ID}/csv", headers=HEADERS).content
with open("results.csv", "wb") as f:
    f.write(csv_bytes)
print(f"\\n✓ results.csv saved ({len(csv_bytes)//1024} KB)")`

const EXAMPLE_BATCH = `"""
Batch runner — run the same hypothesis over multiple semantic queries
and compare support rates across them (qwen_retriever).
pip install requests
"""
import json, time
import requests

BASE_URL        = "${BASE_URL}"
HEADERS         = {"X-Api-Key": "blv_your_key_here"}
MODEL_CONFIG_ID = 16   # existing model config ID

HYPOTHESIS = (
    "Dopaminergic neurotransmission starting from the nucleus accumbens "
    "to the caudate nucleus is elevated in schizophrenia patients."
)

# Each query uses semantic search via Qwen Retriever
QUERIES = {
    "Dopamine & Schizophrenia":  {"q": "dopamine schizophrenia neurotransmission", "n": 500},
    "D2 Receptor":               {"q": "D2 receptor dopamine schizophrenia DRD2",  "n": 500},
    "Striatum & Caudate":        {"q": "dopamine striatum caudate nucleus schizophrenia", "n": 500},
}

# Submit all jobs
job_ids = {}
for name, q in QUERIES.items():
    job = requests.post(f"{BASE_URL}/jobs", headers=HEADERS, json={
        "name":             name,
        "query_term":       json.dumps(q),
        "hypothesis":       HYPOTHESIS,
        "source_type":      "qwen_retriever",
        "max_articles":     200,
        "model_config_id":  MODEL_CONFIG_ID,
    }).json()
    job_ids[name] = job["id"]
    print(f"  Queued [{job['id']}] {name}")

# Wait for all to finish
pending = set(job_ids.values())
while pending:
    for jid in list(pending):
        info = requests.get(f"{BASE_URL}/jobs/{jid}", headers=HEADERS).json()
        if info["status"] in ("completed", "failed", "stopped"):
            print(f"  Job {jid} → {info['status']}")
            pending.discard(jid)
    if pending:
        time.sleep(15)

# Compare support rates
print("\\n── Comparison ───────────────────────────────────")
for name, jid in job_ids.items():
    stats  = requests.get(f"{BASE_URL}/jobs/{jid}/stats", headers=HEADERS).json()
    counts = stats["verdict_counts"]
    total  = sum(counts.values()) or 1
    pct    = counts.get("support", 0) / total * 100
    print(f"  {name:<35}  {pct:5.1f}% support  (n={total})")`

const EXAMPLE_PANDAS = `"""
Pandas analysis — load results and do exploratory data analysis.
pip install requests pandas matplotlib
"""
import io, requests
import pandas as pd
import matplotlib.pyplot as plt

BASE_URL = "${BASE_URL}"
HEADERS  = {"X-Api-Key": "blv_your_key_here"}
JOB_ID   = 42

# Load results into DataFrame
csv_bytes = requests.get(f"{BASE_URL}/jobs/{JOB_ID}/csv", headers=HEADERS).content
df = pd.read_csv(io.BytesIO(csv_bytes))

print(df.shape)                          # (N, 7)
print(df["verdict"].value_counts())      # support / reject / neutral counts

# ── High-confidence supporting articles ───────────────────────────────────────
top = (df[(df["verdict"] == "support") & (df["confidence"] == "HIGH")]
       .sort_values("year", ascending=False)
       [["pmid", "year", "title", "rationale"]])
print(top.head(10).to_string(index=False))

# ── Year trend plot ───────────────────────────────────────────────────────────
stats    = requests.get(f"{BASE_URL}/jobs/{JOB_ID}/stats", headers=HEADERS).json()
year_df  = pd.DataFrame(stats["year_data"]).set_index("year")

year_df[["support", "reject", "neutral"]].plot(
    kind="bar", stacked=True,
    color={"support": "#2ca02c", "reject": "#d62728", "neutral": "#1f77b4"},
    figsize=(12, 5), title="Verdict distribution by year",
)
plt.tight_layout()
plt.savefig("trend.png", dpi=150)
print("Saved trend.png")`

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ApiDocs() {
    const [activeSections, setActiveSections] = useState<Set<string>>(new Set(['jobs']))
    const [activeExample, setActiveExample] = useState<'quickstart' | 'batch' | 'pandas'>('quickstart')

    const toggleSection = (id: string) => {
        setActiveSections(prev => {
            const next = new Set(prev)
            next.has(id) ? next.delete(id) : next.add(id)
            return next
        })
    }

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Header */}
            <div className="bg-white border-b border-slate-200 sticky top-0 z-10">
                <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-violet-600 rounded-lg text-white">
                            <Terminal size={20} />
                        </div>
                        <div>
                            <h1 className="text-xl font-bold text-slate-900 leading-tight">Believe API Reference</h1>
                            <p className="text-xs text-slate-500">
                                Base URL: <code className="font-mono text-violet-700">{BASE_URL}</code>
                            </p>
                        </div>
                    </div>
                    <a
                        href={`${BASE_ORIGIN}/${window.location.pathname.split('/')[1]}/settings`}
                        className="text-xs text-violet-600 hover:underline font-medium hidden md:block"
                    >
                        Generate API Key →
                    </a>
                </div>
            </div>

            <div className="max-w-5xl mx-auto px-6 py-8 space-y-8">

                {/* Auth */}
                <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Key size={18} className="text-violet-600" />
                        <h2 className="text-base font-bold text-slate-800">Authentication</h2>
                    </div>
                    <p className="text-sm text-slate-600 mb-5 leading-relaxed">
                        Every request must include a project-scoped API key in the <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono text-xs text-violet-700">X-Api-Key</code> header.
                        Keys are created in <strong>Project Settings → API Keys</strong>. A key grants full access to its project — treat it like a password.
                    </p>

                    <div className="grid md:grid-cols-2 gap-4">
                        <div>
                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">Setup (copy this)</p>
                            <CodeBlock code={PY_SETUP} id="auth-setup" lang="python" />
                        </div>
                        <div className="space-y-3">
                            <div>
                                <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">Key format</p>
                                <CodeBlock code="blv_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2  (52 chars)" id="key-fmt" lang="text" />
                            </div>
                            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 leading-relaxed">
                                <strong>One-time reveal:</strong> the full key is shown only once at creation. Store it as an environment variable or CI/CD secret.
                            </div>
                        </div>
                    </div>

                    <div className="mt-5">
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">HTTP status codes</p>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                            {[['200', 'Success'], ['401', 'Invalid/missing API key'], ['403', 'Permission denied'], ['404', 'Resource not found'], ['422', 'Validation error'], ['500', 'Server error']].map(([code, msg]) => (
                                <div key={code} className="flex items-center gap-2 text-xs bg-slate-50 border border-slate-200 rounded px-3 py-2">
                                    <code className="font-mono font-bold text-slate-700">{code}</code>
                                    <span className="text-slate-500">{msg}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* Complete examples */}
                <section className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                    <div className="flex items-center gap-2 px-6 py-5 border-b border-slate-200">
                        <Play size={18} className="text-violet-600" />
                        <h2 className="text-base font-bold text-slate-800">Complete Python Examples</h2>
                    </div>

                    <div className="flex border-b border-slate-200">
                        {([
                            ['quickstart', 'Quickstart', 'Run a job end-to-end'],
                            ['batch', 'Batch runner', 'Compare multiple queries'],
                            ['pandas', 'Pandas analysis', 'EDA + charts'],
                        ] as const).map(([key, label, sub]) => (
                            <button
                                key={key}
                                onClick={() => setActiveExample(key)}
                                className={`px-5 py-3 text-left transition-colors border-b-2 ${activeExample === key ? 'border-violet-600 bg-violet-50 text-violet-700' : 'border-transparent text-slate-500 hover:bg-slate-50'}`}
                            >
                                <div className="text-sm font-semibold">{label}</div>
                                <div className="text-xs text-slate-400 mt-0.5">{sub}</div>
                            </button>
                        ))}
                    </div>

                    <div className="p-6">
                        {activeExample === 'quickstart' && (
                            <>
                                <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                                    Full end-to-end workflow: create a job, poll until completion, print verdict counts, and save the CSV. A good starting point for any automation.
                                </p>
                                <CodeBlock code={EXAMPLE_QUICKSTART} id="ex-quickstart" lang="python" />
                            </>
                        )}
                        {activeExample === 'batch' && (
                            <>
                                <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                                    Submit multiple jobs simultaneously for different query terms and compare support rates side-by-side after all jobs finish.
                                </p>
                                <CodeBlock code={EXAMPLE_BATCH} id="ex-batch" lang="python" />
                            </>
                        )}
                        {activeExample === 'pandas' && (
                            <>
                                <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                                    Load results into a Pandas DataFrame for exploratory analysis. Requires <code className="bg-slate-100 px-1 rounded font-mono text-xs">pip install requests pandas matplotlib</code>.
                                </p>
                                <CodeBlock code={EXAMPLE_PANDAS} id="ex-pandas" lang="python" />
                            </>
                        )}
                    </div>
                </section>

                {/* Endpoint reference */}
                <div>
                    <div className="flex items-center gap-2 mb-4">
                        <Code2 size={18} className="text-slate-600" />
                        <h2 className="text-base font-bold text-slate-800">Endpoint Reference</h2>
                        <span className="text-xs text-slate-400 ml-1">click an endpoint to expand</span>
                    </div>

                    <div className="space-y-4">
                        {SECTIONS.map(sec => (
                            <div key={sec.id} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                                <button
                                    onClick={() => toggleSection(sec.id)}
                                    className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50 transition-colors text-left"
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="p-1.5 bg-violet-50 text-violet-600 rounded-lg">{sec.icon}</div>
                                        <div>
                                            <div className="text-sm font-bold text-slate-800">{sec.title}</div>
                                            <div className="text-xs text-slate-500 mt-0.5">{sec.description}</div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        <span className="text-xs text-slate-400 hidden md:block">{sec.endpoints.length} endpoints</span>
                                        {activeSections.has(sec.id)
                                            ? <ChevronDown size={16} className="text-slate-400" />
                                            : <ChevronRight size={16} className="text-slate-400" />
                                        }
                                    </div>
                                </button>

                                {activeSections.has(sec.id) && (
                                    <div className="border-t border-slate-200 p-4 space-y-2">
                                        {sec.endpoints.map(ep => (
                                            <Endpoint key={`${ep.method}-${ep.path}`} ep={ep} />
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                <footer className="text-center text-xs text-slate-400 pb-6">
                    Believe API — keys never expire unless manually revoked · project-scoped access only
                </footer>
            </div>
        </div>
    )
}
