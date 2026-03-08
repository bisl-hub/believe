#!/usr/bin/env python3
"""
Batch processor for hypothesis validation.

Reads hypothesis and query pairs from batch_process/ directory
and runs hypothesis_validation.py sequentially for each pair,
saving results in batch_process/results/.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import os
from pathlib import Path
from typing import List, Tuple

from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


def read_lines(file_path: Path) -> List[str]:
    """Read lines from a file, stripping whitespace."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def load_hypothesis_query_pairs(batch_dir: Path) -> List[Tuple[str, str, int]]:
    """
    Load hypothesis and query pairs from batch_process directory.
    
    Returns:
        List of (hypothesis, query, line_number) tuples
    """
    hypothesis_file = batch_dir / "hypothesis.txt"
    query_file = batch_dir / "query.txt"
    
    log.info(f"Loading hypothesis from: {hypothesis_file}")
    log.info(f"Loading queries from: {query_file}")
    
    hypotheses = read_lines(hypothesis_file)
    queries = read_lines(query_file)
    
    # Match pairs by line number
    pairs = []
    max_len = max(len(hypotheses), len(queries))
    
    for i in range(max_len):
        hypothesis = hypotheses[i] if i < len(hypotheses) else ""
        query = queries[i] if i < len(queries) else ""
        
        if hypothesis and query:
            pairs.append((hypothesis, query, i + 1))
        else:
            log.warning(f"Line {i + 1}: Missing {'hypothesis' if not hypothesis else 'query'}")
    
    log.info(f"Loaded {len(pairs)} valid hypothesis-query pairs")
    return pairs


def run_hypothesis_validation(
    hypothesis: str,
    query: str,
    output_dir: Path,
    script_path: Path
) -> bool:
    """
    Run hypothesis_validation.py for a single hypothesis-query pair.
    
    Args:
        hypothesis: The hypothesis to validate
        query: The query term for PubTator search
        output_dir: Directory to save results
        script_path: Path to hypothesis_validation.py
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Build command
        cmd = [
            sys.executable,
            str(script_path),
            "--query", query,
            "--hypothesis", hypothesis,
            "--output-dir", str(output_dir),
        ]
        
        log.info(f"Running: {' '.join(cmd[:3])}...")
        log.info(f"  Query: {query[:80]}...")
        log.info(f"  Hypothesis: {hypothesis[:80]}...")
        log.info("")  # Add blank line before subprocess output
        
        # Run the subprocess without capturing output
        # This allows internal progress bars to be displayed in real-time
        result = subprocess.run(
            cmd,
            check=False
        )
        
        log.info("")  # Add blank line after subprocess output
        if result.returncode == 0:
            log.info("✓ Completed successfully")
            return True
        else:
            log.error(f"✗ Failed with return code {result.returncode}")
            return False
            
    except Exception as e:
        log.error(f"✗ Exception occurred: {e}")
        return False


def main():
    """Main batch processing function."""
    # Setup paths
    root_dir = Path(__file__).parent.resolve()
    batch_dir = root_dir / "batch_process"
    results_base_dir = batch_dir / "results"
    script_path = root_dir / "hypothesis_validation.py"
    
    log.info("=" * 70)
    log.info("Starting Batch Hypothesis Validation")
    log.info("=" * 70)
    log.info(f"Root directory: {root_dir}")
    log.info(f"Batch directory: {batch_dir}")
    log.info(f"Results directory: {results_base_dir}")
    log.info(f"Script path: {script_path}")
    
    # Validate paths
    if not batch_dir.exists():
        log.error(f"Batch directory not found: {batch_dir}")
        sys.exit(1)
    
    if not script_path.exists():
        log.error(f"Script not found: {script_path}")
        sys.exit(1)
    
    # Create results directory
    results_base_dir.mkdir(parents=True, exist_ok=True)
    
    # Load hypothesis-query pairs
    try:
        pairs = load_hypothesis_query_pairs(batch_dir)
    except Exception as e:
        log.error(f"Failed to load hypothesis-query pairs: {e}")
        sys.exit(1)
    
    if not pairs:
        log.error("No valid hypothesis-query pairs found")
        sys.exit(1)
    
    # Process each pair sequentially
    total = len(pairs)
    successful = 0
    failed = 0
    
    log.info("")
    log.info("=" * 70)
    log.info(f"Processing {total} hypothesis-query pairs")
    log.info("=" * 70)
    log.info("")
    
    # Use tqdm progress bar for overall batch progress
    with tqdm(total=total, desc="Batch Progress", unit="pair", ncols=100, position=0) as pbar:
        for idx, (hypothesis, query, line_num) in enumerate(pairs, start=1):
            pbar.set_description(f"Batch Progress (Pair {line_num})")
            
            log.info(f"[{idx}/{total}] Processing pair from line {line_num}")
            log.info("-" * 70)
            
            # Create output directory for this pair
            output_dir = results_base_dir / f"pair_{line_num:03d}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save the hypothesis and query to the output directory for reference
            (output_dir / "hypothesis.txt").write_text(hypothesis, encoding='utf-8')
            (output_dir / "query.txt").write_text(query, encoding='utf-8')
            
            # Run validation
            success = run_hypothesis_validation(
                hypothesis=hypothesis,
                query=query,
                output_dir=output_dir,
                script_path=script_path
            )
            
            if success:
                successful += 1
                log.info(f"✓ Results saved to: {output_dir}")
            else:
                failed += 1
                log.error(f"✗ Processing failed for pair {line_num}")
            
            pbar.update(1)
            log.info("")

    
    # Summary
    log.info("")
    log.info("=" * 70)
    log.info("Batch Processing Complete")
    log.info("=" * 70)
    log.info(f"Total pairs: {total}")
    log.info(f"Successful: {successful}")
    log.info(f"Failed: {failed}")
    log.info(f"Results directory: {results_base_dir}")
    log.info("=" * 70)
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
