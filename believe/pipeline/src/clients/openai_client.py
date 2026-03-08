import os
import json
import re
import subprocess
import tempfile
from typing import List, Sequence, Dict

from ..models.data import Article, ArticleEvaluation
from ..utils.logging import log, ProgressLogger

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "bislaprom3#")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11433/v1")
LLM_CONCURRENCY_LIMIT = int(os.getenv("LLM_CONCURRENCY_LIMIT", "1024"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))

SUPPORTED_VERDICTS = ("support", "reject", "neutral")

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

def _parse_confidence(value: object) -> str:
    if value is None:
        return "Unknown"
    return str(value).strip()


def evaluate_articles_with_llm(hypothesis: str, articles: Sequence[Article]) -> List[ArticleEvaluation]:
    if not articles:
        return []

    # 1. Prepare input payload for Go Worker
    with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8') as fin:
        input_path = fin.name
        for article in articles:
            # Apply OpenAI Harmony Format specifically for gpt-oss-120b
            if OPENAI_MODEL == "openai/gpt-oss-120b" or "gpt-oss" in OPENAI_MODEL:
                messages = [
                    {
                        "role": "system",
                        "content": "You are ChatGPT, a large language model trained by OpenAI.\nKnowledge cutoff: 2024-06\nCurrent date: 2026-03-05\n\nReasoning: high\n\n# Valid channels: analysis, commentary, final. Channel must be included for every message."
                    },
                    {
                        "role": "developer",
                        "content": f"# Instructions\n\n{LLM_SYSTEM_PROMPT}"
                    },
                    {
                        "role": "user",
                        "content": _build_llm_user_prompt(hypothesis, article)
                    }
                ]
            else:
                messages = [
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": _build_llm_user_prompt(hypothesis, article)},
                ]
                
            request_params = {
                "model": OPENAI_MODEL,
                "messages": messages,
            }
            if LLM_TEMPERATURE > 0:
                request_params["temperature"] = LLM_TEMPERATURE
                
            job = {
                "pmid": article.pmid,
                "request_params": request_params
            }
            fin.write(json.dumps(job) + "\n")

    with tempfile.NamedTemporaryFile(delete=False) as fout:
        output_path = fout.name
        
    try:
        # 2. Run Go Binary
        binary_path = "/app/src/llm_worker/llm_worker"
        if not os.path.exists(binary_path):
            local_path = os.path.join(os.path.dirname(__file__), "..", "llm_worker", "llm_worker")
            if os.path.exists(local_path):
                binary_path = local_path
            else:
                log.warning("Go llm_worker binary not found! Proceeding without evaluation.")
                return []
                
        cmd = [binary_path, input_path, output_path]
        
        env = os.environ.copy()
        env["OPENAI_API_KEY"] = OPENAI_API_KEY
        env["OPENAI_BASE_URL"] = OPENAI_BASE_URL
        env["LLM_CONCURRENCY_LIMIT"] = str(LLM_CONCURRENCY_LIMIT)
        
        log.info(f"Delegating LLM evaluation of {len(articles)} articles to Go CLI Worker...")
        proc = subprocess.Popen(cmd, env=env, stderr=subprocess.PIPE, text=True)
        
        for line in proc.stderr:
            line = line.strip()
            if line:
                if "[GO]" in line or "Loaded" in line or "Error" in line:
                    log.info(line)
                elif "failed" in line.lower() or "error" in line.lower():
                    log.warning(line)
                    
        proc.wait()
        if proc.returncode != 0:
            log.error(f"Go llm_worker exited with code {proc.returncode}")
            
        # 3. Read Output & Parse
        results = []
        article_map = {a.pmid: a for a in articles}
        
        # In case the go worker crashed entirely and didn't create the file properly
        if not os.path.exists(output_path):
            log.error("Output file from Go worker is completely missing.")
            return []
            
        with open(output_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    out_job = json.loads(line)
                except json.JSONDecodeError:
                    log.warning("Received malformed JSON line from Go worker output.")
                    continue
                    
                pmid = out_job.get("pmid")
                content = out_job.get("response_content", "")
                err = out_job.get("error", "")
                
                article = article_map.get(pmid)
                if not article:
                    continue
                    
                if err:
                    log.error(f"Go worker failed for pmid {pmid}: {err}")
                    results.append(ArticleEvaluation(
                        pmid=pmid, title=article.title, abstract=article.abstract, year=article.year,
                        hypothesis=hypothesis, verdict="error", confidence="0.0", rationale=err
                    ))
                    continue
                    
                payload = _extract_json_object(content)
                verdict = _normalize_verdict(payload.get("verdict"))
                if verdict not in SUPPORTED_VERDICTS: verdict = "neutral"
                confidence = _parse_confidence(payload.get("confidence"))
                rationale = str(payload.get("rationale") or payload.get("evidence") or "").strip()
                
                results.append(ArticleEvaluation(
                    pmid=pmid, title=article.title, abstract=article.abstract, year=article.year,
                    hypothesis=hypothesis, verdict=verdict, confidence=confidence, rationale=rationale
                ))
        return results
        
    finally:
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)
