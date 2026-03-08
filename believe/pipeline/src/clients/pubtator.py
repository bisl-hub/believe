import httpx
import time
import threading
import logging
import json
import math
import random
import re
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Sequence, Union, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models.data import Article
from ..utils.logging import log, ProgressLogger

# Configuration
PUBTATOR_SEARCH_URL = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/search/"
PUBTATOR_PAGE_SIZE = 1000 
SEARCH_THREAD_COUNT = int(os.getenv("SEARCH_THREAD_COUNT", "4"))

PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_CHUNK_SIZE = 200 
FETCH_THREAD_COUNT = int(os.getenv("FETCH_THREAD_COUNT", "8"))

NCBI_MAX_REQUESTS_PER_SECOND = float(os.getenv("NCBI_MAX_REQUESTS_PER_SECOND", "3.0"))
HTTP_TIMEOUT_SEC = float(os.getenv("HTTP_TIMEOUT_SEC", "180.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "30"))
RETRY_BACKOFF_BASE_SEC = float(os.getenv("RETRY_BACKOFF_BASE_SEC", "2.0"))
NCBI_API_KEY = os.getenv("NCBI_API_KEY")

HEADERS = {
    "User-Agent": "HypothesisValidation/2.3 (+research@hypothesis-validation.example)",
}

class RateLimiter:
    def __init__(self, max_per_second: float) -> None:
        self._interval = 1.0 / max_per_second if max_per_second > 0 else 0.0
        self._last_time = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        if self._interval <= 0.0:
            return
        
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

class LiteratureClient:
    def __init__(self) -> None:
        timeout = httpx.Timeout(HTTP_TIMEOUT_SEC)
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
        # Inject API Key for NCBI/PubMed domains
        if NCBI_API_KEY and ("ncbi.nlm.nih.gov" in url or "pubtator3-api" in url):
            params["api_key"] = NCBI_API_KEY

        for attempt in range(1, MAX_RETRIES + 1):
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
                    
                return response

            except httpx.HTTPError as exc:
                if attempt == MAX_RETRIES:
                    log.warning(f"Request failed after {MAX_RETRIES} attempts: {exc}")
                    return None
                
                wait_time = min(60.0, RETRY_BACKOFF_BASE_SEC * (1.5 ** attempt))
                if isinstance(exc, httpx.HTTPStatusError):
                    status_code = exc.response.status_code
                    response_text = exc.response.text[:200]
                    log.error(f"     └─ [HTTP ERROR] Status: {status_code}, Response: {response_text}")
                    if status_code == 429:
                        header_wait = exc.response.headers.get("Retry-After")
                        if header_wait:
                            wait_time = float(header_wait)
                
                log.info(f"Request attempt {attempt}/{MAX_RETRIES} failed ({type(exc).__name__}). Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
        return None

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
        if max_articles < 0:
            max_articles = float('inf')
            
        log.info(f"Searching PMIDs via PubTator: '{query}' (Threads: {SEARCH_THREAD_COUNT})")
        log.info("Sending initial query to PubTator (this may take a moment)...")
        
        first_params = {"text": query, "page": 1, "size": PUBTATOR_PAGE_SIZE, "format": "json"}
        first_payload = None
        
        # [Retry] Initial search retry logic (MAX_RETRIES attempts)
        for attempt in range(1, MAX_RETRIES + 1):
            first_resp = self._request("GET", PUBTATOR_SEARCH_URL, params=first_params)
            
            if first_resp and first_resp.status_code == 200:
                try:
                    first_payload = first_resp.json()
                    # Basic validation logic could go here if needed
                    break # Success
                except json.JSONDecodeError:
                    log.warning(f"Search response JSON decode failed (Attempt {attempt}/{MAX_RETRIES}).")
            else:
                 log.warning(f"Search request failed or status not 200 (Attempt {attempt}/{MAX_RETRIES}).")
            
            if attempt < MAX_RETRIES:
                wait_time = min(60.0, RETRY_BACKOFF_BASE_SEC * (1.5 ** attempt))
                log.info(f"Retrying initial search in {wait_time:.1f}s...")
                time.sleep(wait_time)

        if not first_payload:
            log.warning(f"Search failed after {MAX_RETRIES} attempts. Returning empty list.")
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

        if required_pages <= 1:
             collected_pmids = collected_pmids[:total_hits]
        else:
            pages_to_fetch = list(range(2, required_pages + 1))
            
            # Use ProgressLogger instead of tqdm
            logger = ProgressLogger(total=required_pages, desc="[1/3] Searching Pages")
            logger.update(1) # Account for first page

            with ThreadPoolExecutor(max_workers=SEARCH_THREAD_COUNT) as executor:
                future_to_page = {
                    executor.submit(self._fetch_search_page, query, page): page 
                    for page in pages_to_fetch
                }
                
                for future in as_completed(future_to_page):
                    page_pmids = future.result()
                    if page_pmids:
                        collected_pmids.extend(page_pmids)
                    logger.update(1)

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
        
        target_count = max_articles
        if max_articles_percent is not None:
            calculated_count = int(len(final_pmids) * (max_articles_percent / 100.0))
            target_count = max(1, calculated_count) if len(final_pmids) > 0 else 0
            log.info(f"Sampling {max_articles_percent}% of {len(final_pmids)} hits => {target_count} articles.")

        return final_pmids

    def search_pmids_via_pubmed(self, query: str, max_articles: float = float('inf'), max_articles_percent: float = None) -> List[str]:
        if max_articles < 0:
            max_articles = float('inf')
            
        log.info(f"Searching PMIDs via PubMed (ESearch): '{query}'")
        
        import datetime
        
        # Determine total valid records first
        params_count = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": "0" 
        }
        resp = self._request("GET", PUBMED_ESEARCH_URL, params=params_count)
        if not resp or resp.status_code != 200:
            log.warning("PubMed ESearch initial count failed. Returning empty list.")
            return []
            
        try:
            total_count = int(resp.json().get("esearchresult", {}).get("count", "0"))
        except Exception as e:
            log.warning(f"Failed to parse count response: {e}")
            return []
            
        log.info(f"PubMed ESearch: Total available PMIDs: {total_count}")
        
        final_pmids_list = []
        seen_pmids = set()
        
        if total_count <= 9999: # Easy fast path for typical queries
            params = {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": "9999"
            }
            resp = self._request("GET", PUBMED_ESEARCH_URL, params=params)
            if resp and resp.status_code == 200:
                try:
                    for p in resp.json().get("esearchresult", {}).get("idlist", []):
                        sp = str(p)
                        if sp not in seen_pmids:
                            seen_pmids.add(sp)
                            final_pmids_list.append(sp)
                except Exception as e:
                    log.warning(f"Failed to parse ESearch response: {e}")
        else:
            log.info(f"Query exceeds 9999 limit. Employing E-utilities WebEnv history to retrieve all {total_count} PMIDs...")
            
            log.info(f"Falling back to Date-Chunking method to fetch {total_count} PMIDs because ESearch limits retstart <= 9998.")
            stack = [(datetime.date(1800, 1, 1), datetime.date(datetime.datetime.now().year + 1, 12, 31))]
            
            while stack:
                if len(final_pmids_list) >= max_articles:
                    break
                    
                start_date, end_date = stack.pop()
                start_str = start_date.strftime("%Y/%m/%d")
                end_str = end_date.strftime("%Y/%m/%d")
                
                params = {
                    "db": "pubmed",
                    "term": query,
                    "retmode": "json",
                    "retstart": "0",
                    "retmax": "9999",
                    "mindate": start_str,
                    "maxdate": end_str,
                    "datetype": "pdat"
                }
                
                resp = self._request("GET", PUBMED_ESEARCH_URL, params=params)
                if not resp or resp.status_code != 200:
                    log.warning(f"Failed to fetch date chunk {start_str}-{end_str}")
                    continue
                    
                try:
                    payload = resp.json().get("esearchresult", {})
                    count = int(payload.get("count", "0"))
                    id_list = payload.get("idlist", [])
                except Exception as e:
                    log.warning(f"Failed to parse chunk {start_str}-{end_str}: {e}")
                    continue
                    
                if count > 8000 and (end_date - start_date).days > 0:
                    mid_date = start_date + datetime.timedelta(days=(end_date - start_date).days // 2)
                    # Push right half then left half to process left (older) first
                    stack.append((mid_date + datetime.timedelta(days=1), end_date))
                    stack.append((start_date, mid_date))
                else:
                    if count > 9999:
                        log.warning(f"Limit reached for interval {start_str}-{end_str} ({count} results). Truncating.")
                    new_adds = 0
                    for p in id_list:
                        sp = str(p)
                        if len(final_pmids_list) >= max_articles:
                            break
                        if sp not in seen_pmids:
                            seen_pmids.add(sp)
                            final_pmids_list.append(sp)
                            new_adds += 1
                    log.info(f"Fetched {count} PMIDs for {start_str} to {end_str}. Unique added: {new_adds}. Total: {len(final_pmids_list)}/{total_count}")

        final_pmids = final_pmids_list
        log.info(f"PubMed ESearch: Collected {len(final_pmids)} unique PMIDs.")
        
        target_count = max_articles
        if max_articles_percent is not None:
            calculated_count = int(len(final_pmids) * (max_articles_percent / 100.0))
            target_count = max(1, calculated_count) if len(final_pmids) > 0 else 0
            log.info(f"Sampling {max_articles_percent}% of {len(final_pmids)} hits => {target_count} articles.")

        if target_count != float('inf') and len(final_pmids) > target_count:
            log.info(f"Sampling {target_count} articles from {len(final_pmids)} hits.")
            final_pmids = random.sample(final_pmids, int(target_count))
            
        return final_pmids

    def _fetch_pubmed_chunk(self, chunk: List[str]) -> List[Article]:
        data_payload = {
            "db": "pubmed",
            "retmode": "xml",
            "id": ",".join(chunk)
        }
        response = self._request("POST", PUBMED_EFETCH_URL, params={}, data=data_payload)
        if response and response.status_code == 200:
            return self._parse_pubmed_xml(response.content, expected_count=len(chunk))
        elif response:
            log.warning(f"     └─ [NCBI API Warning] eFetch HTTP {response.status_code}: {response.text[:100]}")
        else:
            log.warning(f"     └─ [NCBI API Error] eFetch request totally failed for chunk of {len(chunk)} PMIDs.")
        return []

    def fetch_abstracts_via_pubmed(self, pmids: Sequence[str]) -> List[Article]:
        articles: List[Article] = []
        if not pmids:
            return articles

        chunks = list(_chunked(list(pmids), PUBMED_FETCH_CHUNK_SIZE))
        log.info(f"Fetching abstracts for {len(pmids)} PMIDs in {len(chunks)} chunks (Threads: {FETCH_THREAD_COUNT})")

        # Use ProgressLogger instead of tqdm
        logger = ProgressLogger(total=len(chunks), desc="[2/3] Fetching Abstracts")

        with ThreadPoolExecutor(max_workers=FETCH_THREAD_COUNT) as executor:
            future_to_chunk = {
                executor.submit(self._fetch_pubmed_chunk, chunk): chunk 
                for chunk in chunks
            }
            
            for future in as_completed(future_to_chunk):
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
    def _parse_pubmed_xml(xml_content: bytes, expected_count: int = None) -> List[Article]:
        articles = []
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            log.warning("     └─ [NCBI XML Parse Error] Root XML was malformed.")
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
                
                year = ""
                journal_issue = article_elem.find("Journal/JournalIssue")
                if journal_issue is not None:
                    pub_date = journal_issue.find("PubDate")
                    if pub_date is not None:
                        year_elem = pub_date.find("Year")
                        if year_elem is not None:
                            year = year_elem.text
                        else:
                            medline_date = pub_date.find("MedlineDate")
                            if medline_date is not None and medline_date.text:
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
            log.warning(f"     └─ [NCBI Data Quality] Dropped {dropped_count} articles from chunk due to missing titles or abstracts.")
            
        if expected_count is not None:
            total_processed = len(articles) + dropped_count
            if total_processed < expected_count:
                 missing_from_xml = expected_count - total_processed
                 log.warning(f"     └─ [NCBI Missing Entity] Requested {expected_count} PMIDs but only found {total_processed} items in XML. The remaining {missing_from_xml} PMIDs likely do not exist in the PubMed DB or are unsupported document types.")

        return articles
