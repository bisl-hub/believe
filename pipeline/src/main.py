import argparse
import os
import resource
import socket
import csv
import io
import math
import matplotlib
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Dict, Sequence
from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert

from src.utils.logging import log, setup_logging
from src.models.data import ArticleEvaluation, JobResult, Job, Base, QueryCache, ArticleCache, Article
from src.clients.pubtator import LiteratureClient
from src.clients.openai_client import evaluate_articles_with_llm, OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_API_KEY

# Matplotlib setup
MPL_CACHE_DIRECTORY = Path(os.getenv("MPL_CACHE_DIR", ".mpl-cache"))
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIRECTORY))
MPL_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
matplotlib.use("Agg")

# Constants
DEFAULT_QUERY_TERM = "@CHEMICAL_Dopamine AND @DISEASE_Schizophrenia"
DEFAULT_HYPOTHESIS = "The dopaminergic neurotransmission starting from the nucleus accumbens to the caudate nucleus is elevated in the patients with schizophrenia."
SUPPORTED_VERDICTS = ("support", "reject", "neutral")
FIGURE_TITLE = "Hypothesis Support Across PubMed Abstracts"
FIGURE_BAR_COLORS = {
    "support": "#2ca02c",
    "reject": "#d62728",
    "neutral": "#1f77b4",
}

OUTPUT_DIRECTORY = Path("outputs")
OUTPUT_CSV_PATH = OUTPUT_DIRECTORY / "pubtator_hypothesis_results.csv"
OUTPUT_FIGURE_PATH = OUTPUT_DIRECTORY / "pubtator_hypothesis_summary.png"
CSV_ENCODING = "utf-8"
CSV_NEWLINE = ""
JOB_ID = None
DB_URL = None

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

def write_results_db(evaluations: List[ArticleEvaluation], job_id: int, db_url: str, counts: Dict[str, int]) -> None:
    log.info(f"Writing {len(evaluations)} results to database for Job {job_id}...")
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Convert to raw dictionaries for massive speedup in bulk insert
        records = [
            {
                "job_id": job_id,
                "pmid": eval_item.pmid,
                "title": eval_item.title,
                "abstract": eval_item.abstract,
                "verdict": eval_item.verdict,
                "confidence": eval_item.confidence,
                "rationale": eval_item.rationale,
                "year": eval_item.year
            }
            for eval_item in evaluations
        ]
        
        chunk_size = 10000
        for i in range(0, len(records), chunk_size):
            chunk = records[i:i + chunk_size]
            db.bulk_insert_mappings(JobResult, chunk)
            
        db.commit()
        log.info("Database write successful.")
    except Exception as e:
        log.error(f"Database write failed: {e}")
        db.rollback()
        raise e
    finally:
        db.close()

def run_pipeline(query: str, hypothesis: str, source_type: str = "pubtator3", max_articles: float = float('inf'), max_articles_percent: float = None, pmids: List[str] = None, download_only: bool = False, force_refresh: bool = False):
    log.info("=" * 60)
    log.info("            [ BISL PIPELINE WORKER INITIATED ]")
    log.info("=" * 60)
    
    # --- 1. MODE & SOURCE ---
    log.info("\n=== [1] MODE & SOURCE ===")
    if download_only:
        log.info(f" ╰─ Mode: [ DOWNLOAD ONLY ] (LLM Evaluation Skipped)")
    else:
        log.info(f" ╰─ Mode: [ EVALUATION ] (Fetch + LLM Evaluation)")
    
    if source_type == 'txt_file':
        log.info(f" ╰─ Source: [ TXT FILE ] (Direct PMID List)")
    elif source_type == 'pubtator3':
        log.info(f" ╰─ Source: [ PUBTATOR3 ] (Entity Search API)")
    elif source_type == 'pubmed':
        log.info(f" ╰─ Source: [ PUBMED ] (Standard E-Utilities)")
    else:
        log.info(f" ╰─ Source: [ {source_type.upper()} ]")
        
    log.info(f" ╰─ Query: {query}")

    # --- 2. SYSTEM & LLM CONFIG ---
    log.info("\n=== [2] SYSTEM & CONFIG ===")
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    log.info(f" ╰─ File Limits (Soft/Hard): {soft} / {hard}")
    
    if max_articles != float('inf') and max_articles > 0:
        log.info(f" ╰─ Target Quantity: Maximum {int(max_articles)} articles")
    elif max_articles_percent:
        log.info(f" ╰─ Target Quantity: Top {max_articles_percent}% of search results")
    else:
        log.info(f" ╰─ Target Quantity: Unlimited (All Matches)")
        
    if not download_only:
        log.info(f" ╰─ LLM Model Parameter: {OPENAI_MODEL}")
        log.info(f" ╰─ LLM Endpoint URL: {OPENAI_BASE_URL}")
        log.info(f" ╰─ LLM API Key: {'[PROVIDED: **********]' if OPENAI_API_KEY else '[NOT PROVIDED]'}")
        
        try:
            hostname = urlparse(OPENAI_BASE_URL).hostname
            if hostname:
                resolved_ip = socket.gethostbyname(hostname)
                log.info(f"     └─ Network Resolution: {hostname} -> {resolved_ip}")
        except Exception as e:
            pass

        log.info(" ╰─ LLM Connectivity Check: (Delegated to Go Worker)")
    else:
        log.info(" ╰─ LLM Config: IGNORED (Running in Download-Only Mode)")

    # --- 3. DATA ACQUISITION & CACHE ---
    log.info("\n=== [3] DATA ACQUISITION & CACHE ===")
    articles = []
    
    # If source_type is txt_file and no explicit PMIDs passed via CLI, parsing query string as PMIDs
    if source_type == "txt_file" and not pmids:
        pmids = [p.strip() for p in query.split(",") if p.strip()]
        log.info(f" ╰─ Local Parsing: Extracted {len(pmids)} PMIDs directly from TXT input content.")
    
    if DB_URL:
        engine = create_engine(DB_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            import json
            if not pmids and not force_refresh:
                cached_query = db.query(QueryCache).filter(QueryCache.query_term == query).first()
                if cached_query and cached_query.pmids:
                    pmids = json.loads(cached_query.pmids)
                    log.info(f" ╰─ DB Cache Hit (Query Level): Successfully recovered {len(pmids)} PMIDs mapped to this exact query.")
                    if max_articles != float('inf') and max_articles > 0:
                        pmids = pmids[:int(max_articles)]
                        log.info(f"     └─ Limiting Target: Reduced to Top {int(max_articles)} PMIDs to satisfy user constraints.")
            
            if pmids:
                cached_articles = db.query(ArticleCache).filter(ArticleCache.pmid.in_(pmids)).all()
                cached_pmids = {a.pmid for a in cached_articles}
                
                for a in cached_articles:
                    articles.append(Article(pmid=a.pmid, title=a.title, abstract=a.abstract, year=a.year))
                
                missing_pmids = [p for p in pmids if p not in cached_pmids]
                pmids = missing_pmids
                if cached_articles:
                    log.info(f" ╰─ DB Cache Hit (Abstract Level): Recovered {len(cached_articles)} full abstracts locally.")
                if missing_pmids:
                    log.info(f" ╰─ Cache Miss: {len(missing_pmids)} PMIDs are missing their abstracts locally.")
                else:
                    log.info(f" ╰─ 100% Cache Match: All requested abstracts found in local DB. Network payload minimized.")
        except Exception as e:
            log.warning(f" ╰─ DB Cache Error: Unexpected issue checking cache -> {e}")
        finally:
            db.close()
            
    if not articles and not pmids:
        log.info(f" ╰─ Network Execution (Query): Consulting {source_type.upper()} API...")
        with LiteratureClient() as client:
            if source_type == "pubmed":
                pmids = client.search_pmids_via_pubmed(query, max_articles=max_articles, max_articles_percent=max_articles_percent)
            elif source_type == "qwen_retriever":
                pmids = client.search_pmids_via_qwen_retriever(query, max_articles=max_articles)
            else:
                pmids = client.search_pmids_via_pubtator(query, max_articles=max_articles, max_articles_percent=max_articles_percent)
        log.info(f"     └─ Search Complete: Discovered {len(pmids) if pmids else 0} new PMIDs to process.")
            
        # Cache the query results
        if pmids and DB_URL:
            import json
            engine = create_engine(DB_URL)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            db = SessionLocal()
            try:
                existing_cache = db.query(QueryCache).filter(QueryCache.query_term == query).first()
                if not existing_cache:
                    db.add(QueryCache(query_term=query, pmids=json.dumps(pmids)))
                else:
                    existing_cache.pmids = json.dumps(pmids)
                db.commit()
                log.info(f"     └─ Query Cache Sync: Saved {len(pmids)} PMIDs to DB for future jobs.")
            except Exception as e:
                db.rollback()
                log.warning(f"     └─ Query Cache Sync Error: {e}")
            finally:
                db.close()
            
    if pmids:
        log.info(f" ╰─ Network Execution (Abstracts): Downloading {len(pmids)} missing abstracts from NCBI servers...")
        with LiteratureClient() as client:
            new_articles = client.fetch_abstracts_via_pubmed(pmids)
            if new_articles:
                articles.extend(new_articles)
                log.info(f"     └─ Download Complete: {len(new_articles)} new abstracts saved to memory.")
                
                # Cache the fresh articles
                if DB_URL:
                    engine = create_engine(DB_URL)
                    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
                    db = SessionLocal()
                    try:
                        records = [
                            {"pmid": a.pmid, "title": a.title, "abstract": a.abstract, "year": a.year}
                            for a in new_articles
                        ]
                        
                        chunk_size = 10000
                        for i in range(0, len(records), chunk_size):
                            chunk = records[i:i + chunk_size]
                            
                            stmt = insert(ArticleCache).values(chunk)
                            stmt = stmt.on_conflict_do_nothing(index_elements=['pmid'])
                            
                            db.execute(stmt)
                            
                        db.commit()
                        log.info(f"     └─ Cache Sync: Saved up to {len(new_articles)} new articles to DB via Bulk Insert.")
                    except Exception as e:
                        db.rollback()
                        log.warning(f"     └─ Cache Sync Bulk Error: {e}")
                    finally:
                        db.close()

    log.info(f"\n[!] DATA ACQUISITION FINAL SCORE: Returning a total of {len(articles)} abstracts for next phase.")
    log.info("=" * 60)

    if not articles:
        log.warning("No articles found to evaluate.")
        return
    
    if download_only:
        log.info(f"Skipping LLM Evaluation due to --download-only. Mapping {len(articles)} articles as 'downloaded'.")
        evaluations = [
            ArticleEvaluation(
                pmid=a.pmid,
                title=a.title,
                abstract=a.abstract,
                year=a.year,
                verdict="downloaded",
                confidence="High",
                rationale="Article successfully downloaded and cached.",
                hypothesis=hypothesis
            ) for a in articles
        ]
    else:
        evaluations = evaluate_articles_with_llm(hypothesis, articles)
        
        if not evaluations:
            log.warning("Hypothesis evaluation produced no results.")
            return
        
    if download_only:
        counts = {"downloaded": len(evaluations)}
        log.info(f"Results: Downloaded({counts['downloaded']})")
    else:
        counts = summarize_verdicts(evaluations)
        log.info(f"Results: Support({counts['support']}) / Reject({counts['reject']}) / Neutral({counts['neutral']})")
    
    try:
        write_results_csv(evaluations)
        if not download_only:
            write_summary_figure(counts)
    except Exception as e:
        log.error(f"Failed to write results to files: {e}")
    
    if JOB_ID and DB_URL:
        try:
            write_results_db(evaluations, JOB_ID, DB_URL, counts)
        except Exception as e:
            log.error(f"Failed to write results to DB: {e}")
    else:
        log.info("No DB configured, skipping database write.")
            
    log.info(f"=== Pipeline Finished ===")

def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="PubTator/PubMed Hypothesis Validator")
    parser.add_argument("--source-type", type=str, default="pubtator3", help="Source type: pubtator3, pubmed, txt_file")
    parser.add_argument("--query", type=str, default=DEFAULT_QUERY_TERM, help="Query term for PubTator")
    parser.add_argument("--hypothesis", type=str, default=DEFAULT_HYPOTHESIS, help="Hypothesis to validate")
    parser.add_argument("--max-articles", type=float, default=float('inf'), help="Max articles to analyze")
    parser.add_argument("--max-articles-percent", type=float, default=None, help="Max articles percent to analyze (0-100)")
    parser.add_argument("--output-dir", type=str, default="outputs", help="Output directory")
    parser.add_argument("--job-id", type=int, default=None, help="Job ID for DB logging")
    parser.add_argument("--db-url", type=str, default=None, help="Database URL")
    parser.add_argument("--pmids", type=str, default=None, help="Comma-separated list of PMIDs to process (skips PubTator search)")
    parser.add_argument("--download-only", action="store_true", help="Skip LLM evaluation and only download/cache articles")
    parser.add_argument("--force-refresh", action="store_true", help="Bypass cache and force refresh PMIDs from network")
    
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

    run_pipeline(args.query, args.hypothesis, source_type=args.source_type, max_articles=args.max_articles, max_articles_percent=args.max_articles_percent, pmids=pmids_list, download_only=args.download_only, force_refresh=args.force_refresh)

if __name__ == "__main__":
    main()
