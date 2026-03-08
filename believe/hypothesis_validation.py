from __future__ import annotations

import csv
import json
import logging
import math
import re
import time
import xml.etree.ElementTree as ET
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import threading
import signal
from dataclasses import dataclass
import time

# [Graceful Shutdown]
SHUTDOWN_EVENT = threading.Event()

def signal_handler(signum, frame):
    log.info(f"Received signal {signum}. Initiating graceful shutdown...")
    SHUTDOWN_EVENT.set()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

class ProgressLogger:
    def __init__(self, total, desc="Processing", interval_sec=5.0):
        self.total = total
        self.desc = desc
        self.interval_sec = interval_sec
        self.current = 0
        self.start_time = time.time()
        self.last_log_time = time.time()
        self._log_progress(0)

    def update(self, n=1):
        self.current += n
        now = time.time()
        if now - self.last_log_time >= self.interval_sec or self.current >= self.total:
            self._log_progress(now)
            self.last_log_time = now

    def _log_progress(self, now):
        elapsed = now - self.start_time
        pct = (self.current / self.total) * 100 if self.total > 0 else 0
        rate = self.current / elapsed if elapsed > 0 else 0
        log.info(f"{self.desc}: {self.current}/{self.total} ({pct:.1f}%) - {rate:.2f} it/s")
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import httpx
import matplotlib
from openai import OpenAI
import httpx
import matplotlib
from openai import OpenAI
# from tqdm import tqdm # Removed for web logging optimization 

# ---
import argparse
import sys

# ... (Imports remain the same, but I will ensure they are all there)

# ---
# Configuration
# ---

# [Matplotlib 설정]
MPL_CACHE_DIRECTORY = Path(os.getenv("MPL_CACHE_DIR", ".mpl-cache"))
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIRECTORY))
MPL_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# [OpenAI 설정]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "bislaprom3#")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "0"))
LLM_CONCURRENCY_LIMIT = int(os.getenv("LLM_CONCURRENCY_LIMIT", "1024"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# [PubTator3 API 설정 (검색용)]
PUBTATOR_SEARCH_URL = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/search/"
PUBTATOR_PAGE_SIZE = 1000 
SEARCH_THREAD_COUNT = int(os.getenv("SEARCH_THREAD_COUNT", "8"))

# [PubMed E-utilities 설정 (본문 수집용)]
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_FETCH_CHUNK_SIZE = 200 
FETCH_THREAD_COUNT = int(os.getenv("FETCH_THREAD_COUNT", "16"))

# API 요청 제한
NCBI_MAX_REQUESTS_PER_SECOND = float(os.getenv("NCBI_MAX_REQUESTS_PER_SECOND", "3.0"))
HTTP_TIMEOUT_SEC = float(os.getenv("HTTP_TIMEOUT_SEC", "60.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))
RETRY_BACKOFF_BASE_SEC = float(os.getenv("RETRY_BACKOFF_BASE_SEC", "1.5"))

HEADERS = {
    "User-Agent": "HypothesisValidation/2.3 (+research@hypothesis-validation.example)",
}

# 결과 저장 경로 (Will be set in main)
OUTPUT_DIRECTORY = Path("outputs")
OUTPUT_CSV_PATH = OUTPUT_DIRECTORY / "pubtator_hypothesis_results.csv"
OUTPUT_FIGURE_PATH = OUTPUT_DIRECTORY / "pubtator_hypothesis_summary.png"
CSV_ENCODING = "utf-8"
CSV_NEWLINE = ""

# 기본값
DEFAULT_QUERY_TERM = "@CHEMICAL_Dopamine AND @DISEASE_Schizophrenia"
DEFAULT_HYPOTHESIS = "The dopaminergic neurotransmission starting from the nucleus accumbens to the caudate nucleus is elevated in the patients with schizophrenia."

SUPPORTED_VERDICTS: Tuple[str, ...] = ("support", "reject", "neutral")

FIGURE_TITLE = "Hypothesis Support Across PubMed Abstracts"
FIGURE_BAR_COLORS = {
    "support": "#2ca02c",
    "reject": "#d62728",
    "neutral": "#1f77b4",
}


# ---
# Logging
# ---

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

log = logging.getLogger("pubmed_hypothesis")


# ---
# Data structures
# ---

@dataclass(frozen=True)
class Article:
    pmid: str
    title: str
    abstract: str
    year: str

@dataclass(frozen=True)
class ArticleEvaluation:
    pmid: str
    title: str
    abstract: str
    year: str
    hypothesis: str
    verdict: str
    confidence: str
    rationale: str

# ... (helpers omitted) ...



# ... (LLM helpers omitted) ...

def evaluate_articles_with_llm(hypothesis: str, articles: List[Article]) -> List[ArticleEvaluation]:
    log.info(f"Evaluating {len(articles)} articles against hypothesis...")
    evaluations = []
    
    with ThreadPoolExecutor(max_workers=LLM_THREAD_COUNT) as executor:
        future_to_article = {
            executor.submit(_evaluate_single_article, hypothesis, article): article
            for article in articles
        }
        
        logger = ProgressLogger(total=len(articles), desc="[3/3] LLM Evaluation")
        for future in as_completed(future_to_article):
                article = future_to_article[future]
                try:
                    result = future.result()
                    if result:
                        evaluations.append(ArticleEvaluation(
                            pmid=article.pmid,
                            title=article.title,
                            abstract=article.abstract,
                            year=article.year,
                            hypothesis=hypothesis,
                            verdict=result.get("verdict", "neutral"),
                            confidence=result.get("confidence", "0.0"),
                            rationale=result.get("rationale", "")
                        ))
                except Exception as e:
                    log.warning(f"LLM evaluation failed for PMID {article.pmid}: {e}")
                logger.update(1)
                
    return evaluations

def write_results_csv(evaluations: Sequence[ArticleEvaluation]) -> None:
    _ensure_output_directory()
    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pmid", "title", "year", "verdict", "confidence", "rationale", "hypothesis", "abstract"])
        writer.writeheader()
        for item in evaluations:
            writer.writerow({
                "pmid": item.pmid, "title": item.title, "year": item.year,
                "verdict": item.verdict, "confidence": item.confidence, "rationale": item.rationale,
                "hypothesis": item.hypothesis, "abstract": item.abstract,
            })
    log.info(f"Saved CSV results to {OUTPUT_CSV_PATH}")

# ... (write_summary_figure omitted) ...

# ---
# Database Integration
# ---
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, ForeignKey, LargeBinary
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

class JobResult(Base):
    __tablename__ = "job_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, index=True)
    pmid = Column(String)
    title = Column(String)
    abstract = Column(Text)
    verdict = Column(String)
    confidence = Column(String)
    rationale = Column(Text)
    year = Column(String)

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    query_term = Column(String, index=True)
    hypothesis = Column(Text)
    status = Column(String, default="pending")
    result_csv = Column(LargeBinary, nullable=True)
    summary_image = Column(LargeBinary, nullable=True)

def write_results_db(evaluations: List[ArticleEvaluation], job_id: int, db_url: str, counts: Dict[str, int]) -> None:
    log.info(f"Writing {len(evaluations)} results and files to database for Job {job_id}...")
    
    import io
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 1. Save individual results
        for eval_item in evaluations:
            result = JobResult(
                job_id=job_id,
                pmid=eval_item.pmid,
                title=eval_item.title,
                abstract=eval_item.abstract,
                verdict=eval_item.verdict,
                confidence=eval_item.confidence,
                rationale=eval_item.rationale,
                year=eval_item.year
            )
            db.add(result)
        
        # 2. Generate CSV in memory
        csv_buffer = io.BytesIO()
        csv_text = io.StringIO()
        fieldnames = ["pmid", "title", "verdict", "confidence", "rationale", "hypothesis", "abstract", "year"]
        writer = csv.DictWriter(csv_text, fieldnames=fieldnames)
        writer.writeheader()
        for item in evaluations:
            writer.writerow({
                "pmid": item.pmid, 
                "title": item.title, 
                "verdict": item.verdict,
                "confidence": item.confidence, 
                "rationale": item.rationale,
                "hypothesis": item.hypothesis, 
                "abstract": item.abstract, 
                "year": item.year
            })
        csv_buffer.write(csv_text.getvalue().encode('utf-8'))
        csv_bytes = csv_buffer.getvalue()
        
        # 3. Generate summary figure in memory
        categories = list(SUPPORTED_VERDICTS)
        values = [counts.get(category, 0) for category in categories]
        colors = [FIGURE_BAR_COLORS.get(category, "#7f7f7f") for category in categories]
        plt.figure(figsize=(8, 5))
        bars = plt.bar(categories, values, color=colors)
        plt.title(FIGURE_TITLE)
        plt.ylabel("Number of abstracts")
        ymax = max(values) if values else 1
        plt.ylim(0, math.ceil((ymax or 1) * 1.2))
        for bar, value in zip(bars, values):
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05, str(value), ha="center", va="bottom")
        plt.tight_layout()
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=200)
        plt.close()
        img_bytes = img_buffer.getvalue()
        
        # 4. Update Job record with generated files
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.result_csv = csv_bytes
            job.summary_image = img_bytes
        
        db.commit()
        log.info("Database write successful (with files).")
    except Exception as e:
        log.error(f"Database write failed: {e}")
        db.rollback()
        raise e
    finally:
        db.close()


# ---
# Helpers
# ---

class RateLimiter:
    def __init__(self, max_per_second: float) -> None:
        self._interval = 1.0 / max_per_second if max_per_second > 0 else 0.0
        self._last_time = 0.0
        self._lock = threading.Lock()  # [추가] 스레드 안전을 위한 Lock

    def wait(self) -> None:
        if self._interval <= 0.0:
            return
        
        # Lock을 사용하여 여러 스레드가 동시에 _last_time을 읽고 쓰는 것을 방지
        with self._lock:
            now = time.monotonic()
            since_last = now - self._last_time
            delay = self._interval - since_last
            if delay > 0:
                time.sleep(delay)
            self._last_time = time.monotonic()

def _chunked(sequence: Sequence[str], size: int) -> Iterable[List[str]]:
    if size <= 0:
        size = 1
    for start in range(0, len(sequence), size):
        yield list(sequence[start:start + size])


# ---
# Literature Client (Hybrid: PubTator Search + PubMed Fetch)
# ---

class LiteratureClient:
    def __init__(self) -> None:
        timeout = httpx.Timeout(HTTP_TIMEOUT_SEC)
        # 커넥션 풀 크기를 스레드 수에 맞춰 넉넉하게 조정
        limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)
        self._client = httpx.Client(timeout=timeout, limits=limits, headers=HEADERS)
        self._limiter = RateLimiter(NCBI_MAX_REQUESTS_PER_SECOND)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LiteratureClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _request(self, method: str, url: str, params: Dict[str, Union[str, int]], data: Dict = None) -> httpx.Response:
        backoff = 0.0
        for attempt in range(1, MAX_RETRIES + 1):
            if SHUTDOWN_EVENT.is_set():
                log.info("Shutdown detected. Cancelling request.")
                return None

            # RateLimiter는 내부적으로 Lock을 사용하여 스레드 안전함
            self._limiter.wait()
            try:
                if method.upper() == "POST":
                    response = self._client.post(url, data=data, params=params)
                else:
                    response = self._client.get(url, params=params)
                
                if response.status_code == 429:
                    raise httpx.HTTPStatusError("Rate Limit", request=response.request, response=response)
                
                if response.status_code >= 500:
                    response.raise_for_status()

                if attempt > 1:
                    log.info(f"Request succeeded after {attempt} attempts: {url}")
                    
                return response

            except httpx.HTTPError as exc:
                if attempt == MAX_RETRIES:
                    log.warning(f"Request failed after {MAX_RETRIES} attempts: {exc}")
                    return None
                
                wait_time = RETRY_BACKOFF_BASE_SEC ** attempt
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                    header_wait = exc.response.headers.get("Retry-After")
                    if header_wait:
                        wait_time = float(header_wait)
                
                log.warning(f"Request failed (Attempt {attempt}/{MAX_RETRIES}). Retrying in {wait_time:.1f}s... Error: {exc}")
                time.sleep(wait_time)
                backoff = wait_time
        return None

    # [추가] 단일 페이지 검색을 위한 헬퍼 메서드
    def _fetch_search_page(self, query: str, page: int) -> List[str]:
        params = {"text": query, "page": page, "size": PUBTATOR_PAGE_SIZE, "format": "json"}
        resp = self._request("GET", PUBTATOR_SEARCH_URL, params=params)
        if not resp:
            return []
        try:
            return self._extract_pmids_from_json(resp.json())
        except Exception:
            return []

    def search_pmids_via_pubtator(self, query: str, max_articles: float = float('inf'), max_articles_percent: float = None) -> List[str]:
        """
        PubTator API를 통해 관련 문서 PMID 검색
        - max_articles: 최대 가져올 문서 수 (inf면 전체)
        - max_articles_percent: 전체 검색 결과 중 가져올 비율 (0~100)
        """
        if max_articles < 0:
            max_articles = float('inf')
            
        log.info(f"Searching PMIDs via PubTator: '{query}' (Threads: {SEARCH_THREAD_COUNT})")
        
        # 1. 첫 페이지는 동기적으로 가져와서 전체 개수 파악
        first_params = {"text": query, "page": 1, "size": PUBTATOR_PAGE_SIZE, "format": "json"}
        first_payload = None
        
        # [Retry] 초기 검색 실패 시 3회 재시도
        for attempt in range(1, 4):
            first_resp = self._request("GET", PUBTATOR_SEARCH_URL, params=first_params)
            
            if first_resp and first_resp.status_code == 200:
                try:
                    first_payload = first_resp.json()
                    # Check if payload is valid (has results or count)
                    if not first_payload.get("results") and not first_payload.get("documents") and first_payload.get("count") is None:
                         # Valid JSON but empty logical content? Treat as potential failure if expected
                         # But sometimes valid result is 0 hits. 
                         # However, user log showed "Search failed" which comes from the `else` block below usually or `_request` fail.
                         pass 
                    break # Success
                except json.JSONDecodeError:
                    log.warning(f"Search response JSON decode failed (Attempt {attempt}/3).")
            else:
                 log.warning(f"Search request failed or status not 200 (Attempt {attempt}/3).")
            
            if attempt < 3:
                time.sleep(2.0)

        if not first_payload:
            log.warning("Search failed after 3 attempts. Returning empty list.")
            return []

        collected_pmids = self._extract_pmids_from_json(first_payload)
        
        total_hits = first_payload.get("count")
        if total_hits is None: 
            total_hits = 999999
        else:
            total_hits = int(total_hits)

        target_count = total_hits
        required_pages = math.ceil(target_count / PUBTATOR_PAGE_SIZE)

        if max_articles_percent is not None:
            log.info(f"Found {total_hits:,} hits. Fetching ALL PMIDs to sample top {max_articles_percent}% randomly.")
        else:
            log.info(f"Found {total_hits:,} hits. Fetching ALL PMIDs to sample top {max_articles} randomly.")

        # 페이지가 1개뿐이라면 여기서 종료
        if required_pages <= 1:
             collected_pmids = collected_pmids[:total_hits]
        else:
            # 2. 나머지 페이지 병렬 검색 (2페이지부터 required_pages까지)
            pages_to_fetch = list(range(2, required_pages + 1))
            
            with ThreadPoolExecutor(max_workers=SEARCH_THREAD_COUNT) as executor:
                # Future 객체 생성
                future_to_page = {
                    executor.submit(self._fetch_search_page, query, page): page 
                    for page in pages_to_fetch
                }
                
                # [Progress Bar] 페이지 단위 검색
                logger = ProgressLogger(total=required_pages, desc="[1/3] Searching Pages")
                logger.update(1) # Account for the first page already fetched
                
                for future in as_completed(future_to_page):
                        if SHUTDOWN_EVENT.is_set():
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                        page_pmids = future.result()
                        if page_pmids:
                            collected_pmids.extend(page_pmids)
                        logger.update(1)

        # 중복 제거
        seen = set()
        final_pmids = []
        duplicates_count = 0
        
        for pmid in collected_pmids:
            if pmid not in seen:
                seen.add(pmid)
                final_pmids.append(pmid)
            else:
                duplicates_count += 1
        
        log.info(f"PubTator Search: Collected {len(collected_pmids)} PMIDs. Removed {duplicates_count} duplicates. Unique count: {len(final_pmids)}.")
        
        # Calculate target count if percentage is used
        target_count = max_articles
        if max_articles_percent is not None:
            calculated_count = int(len(final_pmids) * (max_articles_percent / 100.0))
            # Ensure at least 1 if there are results
            target_count = max(1, calculated_count) if len(final_pmids) > 0 else 0
            log.info(f"Sampling {max_articles_percent}% of {len(final_pmids)} hits => {target_count} articles.")

        # Random Sampling
        if target_count != float('inf') and len(final_pmids) > target_count:
            log.info(f"Sampling {target_count} articles from {len(final_pmids)} unique hits.")
            final_pmids = random.sample(final_pmids, int(target_count))
        
        return final_pmids

    # [추가] 단일 청크 다운로드를 위한 헬퍼 메서드
    def _fetch_pubmed_chunk(self, chunk: List[str]) -> List[Article]:
        data_payload = {
            "db": "pubmed",
            "retmode": "xml",
            "id": ",".join(chunk)
        }
        response = self._request("POST", PUBMED_EFETCH_URL, params={}, data=data_payload)
        if response and response.status_code == 200:
            return self._parse_pubmed_xml(response.content)
        return []

    def fetch_abstracts_via_pubmed(self, pmids: Sequence[str]) -> List[Article]:
        articles: List[Article] = []
        if not pmids:
            return articles

        chunks = list(_chunked(list(pmids), PUBMED_FETCH_CHUNK_SIZE))
        log.info(f"Fetching abstracts for {len(pmids)} PMIDs in {len(chunks)} chunks (Threads: {FETCH_THREAD_COUNT})")

        # [Progress Bar] 청크 단위 병렬 다운로드
        with ThreadPoolExecutor(max_workers=FETCH_THREAD_COUNT) as executor:
            future_to_chunk = {
                executor.submit(self._fetch_pubmed_chunk, chunk): chunk 
                for chunk in chunks
            }
            
            logger = ProgressLogger(total=len(chunks), desc="[2/3] Fetching Abstracts")
            for future in as_completed(future_to_chunk):
                    if SHUTDOWN_EVENT.is_set():
                         executor.shutdown(wait=False, cancel_futures=True)
                         break
                    try:
                        chunk_articles = future.result()
                        articles.extend(chunk_articles)
                    except Exception as e:
                        log.warning(f"Failed to fetch a chunk: {e}")
                    logger.update(1)
        
        return articles

    @staticmethod
    def _extract_pmids_from_json(payload: dict) -> List[str]:
        pmids = []
        results = payload.get("results") or payload.get("documents") or []
        for item in results:
            if isinstance(item, dict):
                val = item.get("pmid") or item.get("_id")
                if val: pmids.append(str(val))
        return pmids

    @staticmethod
    def _parse_pubmed_xml(xml_content: bytes) -> List[Article]:
        articles = []
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return []

        dropped_count = 0
        for pubmed_article in root.findall(".//PubmedArticle"):
            try:
                medline_citation = pubmed_article.find("MedlineCitation")
                if medline_citation is None: 
                    dropped_count += 1
                    continue
                
                pmid_elem = medline_citation.find("PMID")
                pmid = pmid_elem.text if pmid_elem is not None else ""
                
                article_elem = medline_citation.find("Article")
                if article_elem is None: 
                    dropped_count += 1
                    continue
                
                title_elem = article_elem.find("ArticleTitle")
                title = "".join(title_elem.itertext()) if title_elem is not None else ""
                
                # Extract Year
                year = ""
                journal_issue = article_elem.find("Journal/JournalIssue")
                if journal_issue is not None:
                    pub_date = journal_issue.find("PubDate")
                    if pub_date is not None:
                        year_elem = pub_date.find("Year")
                        if year_elem is not None:
                            year = year_elem.text
                        else:
                            # Try MedlineDate if Year is missing
                            medline_date = pub_date.find("MedlineDate")
                            if medline_date is not None and medline_date.text:
                                # Extract first 4 digits
                                match = re.search(r"\d{4}", medline_date.text)
                                if match:
                                    year = match.group(0)
                
                abstract_elem = article_elem.find("Abstract")
                abstract_text = ""
                if abstract_elem is not None:
                    texts = []
                    for txt_elem in abstract_elem.findall("AbstractText"):
                        label = txt_elem.get("Label")
                        txt = "".join(txt_elem.itertext())
                        if label:
                            texts.append(f"{label}: {txt}")
                        else:
                            texts.append(txt)
                    abstract_text = " ".join(texts)
                
                if pmid and (title or abstract_text):
                    articles.append(Article(pmid=pmid, title=title, abstract=abstract_text, year=year))
                else:
                    dropped_count += 1
            except Exception:
                dropped_count += 1
                continue
        
        if dropped_count > 0:
            log.info(f"Dropped {dropped_count} articles from chunk due to missing content or parsing errors.")
        return articles


# ---
# LLM helpers
# ---

LLM_SYSTEM_PROMPT = os.getenv("LLM_SYSTEM_PROMPT", """You are a biomedical literature reviewer. Classify whether the given ABSTRACT supports, contradicts, or is neutral toward the HYPOTHESIS. Base your reasoning strictly on the ABSTRACT. 

EVALUATION CATEGORIES:
- SUPPORT: The abstract provides evidence that the hypothesis is correct
- REJECT: The abstract explicitly demonstrates the opposite direction  
- NEUTRAL: The abstract shows no significant difference, unclear results, or does not address any phenomenon related to the hypothesis

CRITICAL CLARIFICATION:
- No significant difference or no difference shown → NEUTRAL (null finding, not refutation)
- Abstract doesn't mention the phenomenon → NEUTRAL (no evidence to evaluate)
- Only classify as REJECT when an explicit opposite directional effect is shown

CONFIDENCE LEVELS:
- HIGH: Clear evidence directly addresses the hypothesis with explicit directional findings
- MEDIUM: Relevant findings present but with some ambiguity or indirect relevance
- LOW: Minimal evidence, borderline relevance, or high interpretive uncertainty

GUIDANCE FOR CONFIDENCE:
HIGH confidence applies when: The abstract explicitly reports directional effects with clear statistical significance or explicit null findings
MEDIUM confidence applies when: Findings of the abstract partially address the hypothesis with some ambiguity in interpretation
LOW confidence applies when: Abstract is tangentially related or confidence in the classification is uncertain

OUTPUT FORMAT (JSON):
{
  "verdict": "[ 'SUPPORT' | 'REJECT' | 'NEUTRAL' ]",
  "confidence": "[ 'HIGH' | 'MEDIUM' | 'LOW' ]",
  "rationale": "[ justification referencing the abstract, about 2-3 sentences ]"
}""")

def _build_llm_user_prompt(hypothesis: str, article: Article) -> str:
    title = article.title or "(no title available)"
    return (
        f"HYPOTHESIS:\n{hypothesis}\n\n"
        f"TITLE:\n{title}\n\n"
        f"ABSTRACT:\n{article.abstract}\n\n"
        "Answer using JSON."
    )

def _extract_json_object(text: str) -> Dict[str, object]:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text or ""):
        try:
            payload, _ = decoder.raw_decode(text[match.start():])
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue
    return {}

def _normalize_verdict(value: object) -> str:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if "support" in lowered: return "support"
        if "reject" in lowered or "contradict" in lowered or "refute" in lowered: return "reject"
        if "neutral" in lowered or "uncertain" in lowered: return "neutral"
    return "neutral"

def _normalize_confidence(value: object) -> str:
    if value is None:
        return "0.0"
    return str(value).strip()

_global_client: Optional[OpenAI] = None
_global_http_client: Optional[httpx.Client] = None
_client_lock = threading.Lock()

import random

def _get_global_openai_client() -> OpenAI:
    global _global_client, _global_http_client
    with _client_lock:
        if _global_client is None:
            # Configure connection pooling to match concurrency limit
            limits = httpx.Limits(
                max_connections=LLM_CONCURRENCY_LIMIT, 
                max_keepalive_connections=LLM_CONCURRENCY_LIMIT
            )
            timeout = httpx.Timeout(None) # Let OpenAI client handle timeouts or set specific if needed
            
            _global_http_client = httpx.Client(limits=limits, timeout=timeout)
            
            _global_client = OpenAI(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
                max_retries=max(5, OPENAI_MAX_RETRIES), # Increase default retries to 5
                http_client=_global_http_client,
            )
    return _global_client

# [Throttle] Limit concurrent LLM requests to prevent "Connection refused" on local server
_llm_semaphore = threading.Semaphore(LLM_CONCURRENCY_LIMIT)

def _evaluate_single_article(article: Article, hypothesis: str) -> ArticleEvaluation:
    # [Jitter] Add random delay to spread out connection attempts (Thundering Herd Mitigation)
    time.sleep(random.uniform(0, 2.0))
    
    client = _get_global_openai_client()
    last_error = None
    
    # Retry loop for transient errors
    for attempt in range(3):
        try:
            # Build request parameters
            request_params = {
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": _build_llm_user_prompt(hypothesis, article)},
                ],
                "timeout": None,
            }
            
            if LLM_TEMPERATURE > 0:
                request_params["temperature"] = LLM_TEMPERATURE
            
            if SHUTDOWN_EVENT.is_set(): return None

            # [Throttle] Acquire semaphore before making the API call
            with _llm_semaphore:
                response = client.chat.completions.create(**request_params)
                
            content = (response.choices[0].message.content or "").strip()
            payload = _extract_json_object(content)
            verdict = _normalize_verdict(payload.get("verdict"))
            if verdict not in SUPPORTED_VERDICTS: verdict = "neutral"
            confidence = _normalize_confidence(payload.get("confidence"))
            rationale = str(payload.get("rationale") or payload.get("evidence") or "").strip()
            
            return ArticleEvaluation(
                pmid=article.pmid, title=article.title, abstract=article.abstract, year=article.year,
                hypothesis=hypothesis, verdict=verdict, confidence=confidence, rationale=rationale,
            )
            
        except Exception as e:
            last_error = e
            # Wait briefly before retrying
            time.sleep(1.0 * (attempt + 1))
    
    # If all retries fail, return an error evaluation instead of None
    log.error(f"LLM evaluation failed for PMID {article.pmid} after 3 attempts: {last_error}")
    return ArticleEvaluation(
        pmid=article.pmid, title=article.title, abstract=article.abstract, year=article.year,
        hypothesis=hypothesis, verdict="error", confidence="0.0", 
        rationale=f"LLM evaluation failed: {last_error}"
    )

def evaluate_articles_with_llm(hypothesis: str, articles: Sequence[Article]) -> List[ArticleEvaluation]:
    if not articles: return []
    max_workers = max(1, LLM_CONCURRENCY_LIMIT)
    evaluations: List[Optional[ArticleEvaluation]] = []
    error_count = 0
    first_error = None
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_article = {
            executor.submit(_evaluate_single_article, article, hypothesis): article
            for article in articles
        }
        
        for future in tqdm(as_completed(future_to_article), total=len(articles), desc="[3/3] LLM Evaluation", unit="doc", ncols=100, mininterval=3.0):
            if SHUTDOWN_EVENT.is_set():
                executor.shutdown(wait=False, cancel_futures=True)
                break
            try:
                result = future.result()
                if result: 
                    evaluations.append(result)
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                if first_error is None:
                    first_error = e
                    log.error(f"First LLM evaluation error: {type(e).__name__}: {e}")
    
    if error_count > 0:
        log.warning(f"LLM evaluation failed for {error_count}/{len(articles)} articles")
        if first_error:
            log.error(f"Sample error: {first_error}")
    
    return evaluations


# ---
# Output helpers
# ---

def _ensure_output_directory() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

def write_results_csv(evaluations: Sequence[ArticleEvaluation]) -> None:
    _ensure_output_directory()
    fieldnames = ["pmid", "title", "verdict", "confidence", "rationale", "hypothesis", "abstract", "year"]
    with OUTPUT_CSV_PATH.open("w", encoding=CSV_ENCODING, newline=CSV_NEWLINE) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in evaluations:
            writer.writerow({
                "pmid": item.pmid, "title": item.title, "verdict": item.verdict,
                "confidence": item.confidence, "rationale": item.rationale,
                "hypothesis": item.hypothesis, "abstract": item.abstract, "year": item.year
            })
    log.info(f"Saved CSV results to {OUTPUT_CSV_PATH}")

def write_summary_figure(counts: Dict[str, int]) -> None:
    _ensure_output_directory()
    categories = list(SUPPORTED_VERDICTS)
    values = [counts.get(category, 0) for category in categories]
    colors = [FIGURE_BAR_COLORS.get(category, "#7f7f7f") for category in categories]
    plt.figure(figsize=(8, 5))
    bars = plt.bar(categories, values, color=colors)
    plt.title(FIGURE_TITLE)
    plt.ylabel("Number of abstracts")
    ymax = max(values) if values else 1
    plt.ylim(0, math.ceil((ymax or 1) * 1.2))
    for bar, value in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05, str(value), ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(OUTPUT_FIGURE_PATH, dpi=200)
    plt.close()
    log.info(f"Saved summary figure to {OUTPUT_FIGURE_PATH}")

def summarize_verdicts(evaluations: Sequence[ArticleEvaluation]) -> Dict[str, int]:
    counts: Dict[str, int] = {verdict: 0 for verdict in SUPPORTED_VERDICTS}
    for item in evaluations:
        counts[item.verdict] = counts.get(item.verdict, 0) + 1
    return counts



# ---
# Pipeline orchestration
# ---

import resource
import traceback

def run_pipeline(query: str, hypothesis: str, max_articles: float = float('inf'), max_articles_percent: float = None, pmids: List[str] = None):
    log.info("=== Pipeline Started ===")
    
    # [Diagnostics] Check system limits
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    log.info(f"System Open File Limit: Soft={soft}, Hard={hard}")
    
    # [Diagnostics] Log LLM Configuration
    log.info(f"LLM Config: URL={OPENAI_BASE_URL}, Model={OPENAI_MODEL}")
    log.info(f"LLM Config: API Key={'*' * 10 if OPENAI_API_KEY else 'None'}")
    
    # [Diagnostics] Check Host Resolution
    try:
        import socket
        from urllib.parse import urlparse
        hostname = urlparse(OPENAI_BASE_URL).hostname
        if hostname:
            resolved_ip = socket.gethostbyname(hostname)
            log.info(f"Resolved {hostname} to {resolved_ip}")
        else:
            log.info(f"Could not parse hostname from {OPENAI_BASE_URL}")
    except Exception as e:
        log.error(f"Failed to resolve host: {e}")

    # [Diagnostics] Check LLM Connectivity
    log.info("Checking LLM connectivity...")
    try:
        client = _get_global_openai_client()
        client.models.list()
        log.info("LLM Connectivity Check: SUCCESS")
    except Exception as e:
        log.error(f"LLM Connectivity Check: FAILED - {e}")
        # We continue anyway to see if it's intermittent, or return? 
        # Let's continue but warn heavily.
    
    log.info(f"Query: {query}")
    
    with LiteratureClient() as client:
        if pmids:
            log.info(f"Using {len(pmids)} manually provided PMIDs.")
        else:
            # 1. Search IDs (PubTator)
            pmids = client.search_pmids_via_pubtator(query, max_articles=max_articles, max_articles_percent=max_articles_percent)
        
        if not pmids:
            log.warning("No PMIDs returned for query.")
            return
            
        # 2. Fetch Content (PubMed)
        articles = client.fetch_abstracts_via_pubmed(pmids)

    if not articles:
        log.warning("No articles found to evaluate.")
        return
    
    # 3. LLM Evaluation
    evaluations = evaluate_articles_with_llm(hypothesis, articles)
    
    if not evaluations:
        log.warning("Hypothesis evaluation produced no results.")
        return
        
    counts = summarize_verdicts(evaluations)
    log.info(f"Results: Support({counts['support']}) / Reject({counts['reject']}) / Neutral({counts['neutral']})")
    
    # Write results to files (CSV and figure)
    try:
        write_results_csv(evaluations)
        write_summary_figure(counts)
    except Exception as e:
        log.error(f"Failed to write results to files: {e}")
    
    # Write to DB (files generated in-memory and stored in DB)
    if JOB_ID and DB_URL:
        try:
            write_results_db(evaluations, JOB_ID, DB_URL, counts)
        except Exception as e:
            log.error(f"Failed to write results to DB: {e}")
    else:
        log.info("No DB configured, skipping database write.")
            
    log.info(f"=== Pipeline Finished ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="PubTator/PubMed Hypothesis Validator")
    parser.add_argument("--query", type=str, default=DEFAULT_QUERY_TERM, help="Query term for PubTator")
    parser.add_argument("--hypothesis", type=str, default=DEFAULT_HYPOTHESIS, help="Hypothesis to validate")
    parser.add_argument("--max-articles", type=float, default=float('inf'), help="Max articles to analyze")
    parser.add_argument("--max-articles-percent", type=float, default=None, help="Max articles percent to analyze (0-100)")
    parser.add_argument("--output-dir", type=str, default="outputs", help="Output directory")
    parser.add_argument("--job-id", type=int, default=None, help="Job ID for DB logging")
    parser.add_argument("--db-url", type=str, default=None, help="Database URL")
    parser.add_argument("--pmids", type=str, default=None, help="Comma-separated list of PMIDs to process (skips PubTator search)")
    
    args = parser.parse_args()
    
    global OUTPUT_DIRECTORY, OUTPUT_CSV_PATH, OUTPUT_FIGURE_PATH, JOB_ID, DB_URL
    OUTPUT_DIRECTORY = Path(args.output_dir)
    OUTPUT_CSV_PATH = OUTPUT_DIRECTORY / "pubtator_hypothesis_results.csv"
    OUTPUT_FIGURE_PATH = OUTPUT_DIRECTORY / "pubtator_hypothesis_summary.png"
    JOB_ID = args.job_id
    DB_URL = args.db_url
    
    pmids_list = None
    if args.pmids:
        pmids_list = [p.strip() for p in args.pmids.split(",") if p.strip()]

    run_pipeline(args.query, args.hypothesis, args.max_articles, max_articles_percent=args.max_articles_percent, pmids=pmids_list)

if __name__ == "__main__":
    main()