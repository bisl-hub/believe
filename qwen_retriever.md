# Hypothesis Embeddings

PubMed 2800만+ 논문 대상 시맨틱 검색. 여러 임베딩 모델을 등록하고, GPU 서버 API로 임베딩을 생성한 뒤, FAISS IVFPQ 인덱스로 밀리초 단위 검색을 제공합니다.

## 아키텍처

```
MongoDB ──► collect.py ──────────► articles.db (공용, 메타데이터만)
                                         │
                              embed.py (GPU API 병렬 요청)
                                         │
                                 embeddings.db (모델별)
                                         │
                              train_index.py (FAISS IVFPQ 학습)
                                         │
                              build_index.py (벡터 삽입)
                                         │
                          articles_final.index (FAISS, 메모리 로드)
                                         │
                                  FastAPI /search
```

**논문 수집은 전체 모델이 공유하는 1회 작업**이며, 서버 기동 시 `articles.db`가 비어있으면 자동 시작됩니다.  
**임베딩은 모델별로 독립적**으로 실행되며, 원격 GPU 서버 API에 병렬 요청을 보냅니다.

```
data/
  articles.db                          # 공용 (제목·초록·날짜)
  models/
    Qwen__Qwen3-Embedding-0.6B/
      embeddings.db                    # 모델별 임베딩
      trained.index                    # FAISS 학습된 구조
      articles_final.index             # 검색용 완성 인덱스
```

## 시작하기

```bash
docker compose up --build -d
```

- Web UI: **http://localhost:8001**
- API 문서: **http://localhost:8001/docs**

### 처음 실행 시 흐름

1. 서버 기동 → `articles.db` 비어있으면 MongoDB 수집 자동 시작
2. 수집 완료 후 Web UI에서 모델 추가 → 임베딩 파이프라인 자동 시작
3. `ready` 상태가 되면 검색 가능

## 환경 변수 (`docker-compose.yml`)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MONGO_URI` | `mongodb://pubmed-mongo:27017` | MongoDB 연결 |
| `DB_NAME` | `pubmed` | MongoDB 데이터베이스 |
| `COLLECTION_NAME` | `articles` | MongoDB 컬렉션 |
| `REMOTE_API_BASE` | `http://.../v1/embeddings` | GPU 임베딩 API 주소 |
| `API_KEY` | — | GPU API 인증 키 |
| `EMBED_CONCURRENCY` | `64` | 동시 API 요청 수 |
| `DEFAULT_MODEL_ID` | *(첫 번째 ready 모델)* | 검색 기본 모델 |

## Web UI

- **파이프라인 관리 탭**: 수집 상태 카드 + 모델 목록 + 실시간 로그 패널
- **검색 탭**: 시맨틱 검색 + 날짜 필터

## 파이프라인 단계

| 단계 | 설명 |
|------|------|
| `collecting` | MongoDB → articles.db (공용, 1회) |
| `loading_model` | GPU API 연결 확인 및 차원(dim) 파악 |
| `waiting_collect` | 수집이 진행 중일 때 대기 |
| `embedding` | GPU API로 병렬 임베딩 생성 → embeddings.db |
| `training` | FAISS IVFPQ 인덱스 구조 학습 |
| `building` | 학습된 인덱스에 전체 벡터 삽입 |
| `ready` | 검색 가능, FAISS 인덱스 메모리 로드 완료 |

파이프라인은 체크포인트 기반으로 중단 후 재개 가능합니다.

## API 사용법

베이스 URL: `http://localhost:8001`  
전체 인터랙티브 문서: **http://localhost:8001/docs**

---

### 검색 (`/search`)

```
GET /search
```

**파라미터**

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `q` | string | 필수 | 자연어 검색어 |
| `n` | int | 10 | 결과 수 (1–200) |
| `model_id` | string | 첫 번째 ready | 사용할 모델 ID |
| `include_content` | bool | true | 제목·초록 포함 여부 |
| `start_date` | string | — | 출판일 시작 (YYYYMMDD) |
| `end_date` | string | — | 출판일 종료 (YYYYMMDD) |

**응답** — 배열 (score 내림차순)

```json
[
  {
    "id": "35052848",
    "score": 0.7747,
    "title": "Diagnostic Blood Biomarkers in Alzheimer's Disease.",
    "abstract": "Potential biomarkers for Alzheimer's disease..."
  }
]
```

- `id`: PubMed PMID
- `score`: 코사인 유사도 (0–1, 높을수록 관련성 높음)
- `title` / `abstract`: `include_content=false`면 null

**날짜 필터 원리**: FAISS ID = `pub_date_int * 10^8 + PMID` 형태로 인코딩. `IDSelectorRange`로 C++ 레이어에서 처리하므로 포스트필터 없이 성능 손실 없음.

**예시**

```bash
# 기본 검색
curl "http://localhost:8001/search?q=CRISPR+gene+editing+cancer&n=5"

# 2020년 이후 COVID 백신 논문
curl "http://localhost:8001/search?q=COVID+mRNA+vaccine+efficacy&n=20&start_date=20200101"

# 특정 기간, 제목만 (초록 제외)
curl "http://localhost:8001/search?q=Alzheimer+amyloid&n=10&start_date=20180101&end_date=20221231&include_content=false"
```

**Python 예시**

```python
import requests

BASE = "http://localhost:8001"

results = requests.get(f"{BASE}/search", params={
    "q": "CRISPR cancer immunotherapy",
    "n": 10,
    "start_date": "20200101",
    "end_date": "20241231",
}).json()

for r in results:
    print(f"[{r['score']:.3f}] PMID {r['id']}: {r['title']}")
```

---

### 수집 상태 (`/api/collect`)

논문 메타데이터를 MongoDB에서 가져오는 공용 작업입니다. 서버 기동 시 자동 시작됩니다.

```bash
# 수집 진행 상태 확인
curl http://localhost:8001/api/collect/status
```

```json
{
  "running": false,
  "stage": "done",
  "progress": 100.0,
  "current": 28346137,
  "total": 28346137,
  "speed": 0.0,
  "eta_seconds": null,
  "error": null,
  "articles_count": 28346137
}
```

- `stage`: `collecting` | `done` | `not_started` | `idle` | `error`
- `speed`: 초당 처리 건수
- `eta_seconds`: 남은 예상 시간 (초)

```bash
# 수동으로 재수집 시작 (articles.db 초기화 후 사용)
curl -X POST http://localhost:8001/api/collect/start

# 수집 중단
curl -X POST http://localhost:8001/api/collect/stop

# 수집 로그 확인 (최근 200줄)
curl "http://localhost:8001/api/collect/logs?n=200"
```

---

### 모델 관리 (`/api/models`)

각 모델은 독립적으로 임베딩·인덱스를 가집니다.

#### 모델 목록 조회

```bash
curl http://localhost:8001/api/models
```

```json
[
  {
    "id": "Qwen__Qwen3-Embedding-0.6B",
    "hf_repo": "Qwen/Qwen3-Embedding-0.6B",
    "display_name": "Qwen/Qwen3-Embedding-0.6B",
    "dimension": 1024,
    "status": "ready",
    "articles_count": 28346137,
    "error_message": null,
    "created_at": "2026-05-19T15:12:50+00:00",
    "updated_at": "2026-05-20T11:30:42+00:00"
  }
]
```

- `id`: 모델 식별자 (`hf_repo`의 `/` → `__`)
- `status`: `idle` | `loading_model` | `waiting_collect` | `embedding` | `training` | `building` | `ready` | `error`
- `articles_count`: 임베딩 완료된 논문 수

#### 모델 추가

```bash
curl -X POST http://localhost:8001/api/models \
  -H "Content-Type: application/json" \
  -d '{
    "hf_repo": "BAAI/bge-m3",
    "display_name": "BGE-M3",
    "auto_start": true
  }'
```

- `auto_start: true` (기본값): 추가 즉시 파이프라인 시작
- 추가 후 반환되는 `id`를 이후 API 호출에 사용

#### 모델 삭제

```bash
# embeddings.db, trained.index, articles_final.index 모두 삭제
# articles.db(공용)는 유지됨
curl -X DELETE http://localhost:8001/api/models/Qwen__Qwen3-Embedding-0.6B
```

---

### 파이프라인 제어 (`/api/models/{id}/pipeline`)

#### 상태 조회

```bash
curl http://localhost:8001/api/models/Qwen__Qwen3-Embedding-0.6B/pipeline/status
```

```json
{
  "model_id": "Qwen__Qwen3-Embedding-0.6B",
  "status": "embedding",
  "stage": "embedding",
  "running": true,
  "progress": 45.2,
  "speed": 1850.0,
  "eta_seconds": 8640,
  "current": 12800000,
  "total": 28346137,
  "error": null
}
```

#### 시작 / 중단 / 재개

```bash
# 파이프라인 시작 (또는 재개 — 체크포인트부터 이어서)
curl -X POST http://localhost:8001/api/models/Qwen__Qwen3-Embedding-0.6B/pipeline/start

# 파이프라인 중단 (현재 배치 완료 후 정지, 재개 가능)
curl -X POST http://localhost:8001/api/models/Qwen__Qwen3-Embedding-0.6B/pipeline/stop
```

#### 로그 조회

```bash
# 최근 100줄
curl "http://localhost:8001/api/models/Qwen__Qwen3-Embedding-0.6B/pipeline/logs?n=100"
```

```json
{
  "model_id": "Qwen__Qwen3-Embedding-0.6B",
  "lines": [
    "16:40:46 INFO Embed 5,120/28,346,137 (0.0%)  954 art/s  ETA 8h15m",
    "16:40:52 INFO Embed 10,240/28,346,137 (0.0%)  885 art/s  ETA 8h53m"
  ]
}
```

#### FAISS 인덱스 핫스왑

```bash
# 인덱스 파일이 갱신됐을 때 재시작 없이 메모리 교체
curl -X POST http://localhost:8001/api/models/Qwen__Qwen3-Embedding-0.6B/reload
```

---

### 헬스체크

```bash
curl http://localhost:8001/health
```

```json
{
  "status": "ok",
  "ready_models": ["Qwen__Qwen3-Embedding-0.6B"],
  "shared_articles": 28346137
}
```

---

### Python 통합 예시

```python
import requests

BASE = "http://localhost:8001"

def search(query, n=10, start_date=None, end_date=None, model_id=None):
    params = {"q": query, "n": n}
    if start_date: params["start_date"] = start_date
    if end_date:   params["end_date"]   = end_date
    if model_id:   params["model_id"]   = model_id
    return requests.get(f"{BASE}/search", params=params).json()

def get_pipeline_status(model_id):
    return requests.get(f"{BASE}/api/models/{model_id}/pipeline/status").json()

# 검색 예시
results = search("mRNA vaccine immunogenicity", n=20, start_date="20210101")
for r in results:
    url = f"https://pubmed.ncbi.nlm.nih.gov/{r['id']}/"
    print(f"[{r['score']:.3f}] {r['title']}\n  {url}\n")

# 파이프라인 모니터링
import time
status = get_pipeline_status("Qwen__Qwen3-Embedding-0.6B")
while status["running"]:
    print(f"{status['progress']:.1f}%  {status['speed']:.0f} art/s  ETA {status['eta_seconds']}s")
    time.sleep(10)
    status = get_pipeline_status("Qwen__Qwen3-Embedding-0.6B")
print("Done!")
```
