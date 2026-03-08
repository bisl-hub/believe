#!/usr/bin/env python3
"""
Batch processor for manual PMID hypothesis validation.

Reads hypothesis and PMID list pairs from manual_pmid/ directory
and runs hypothesis_validation.py sequentially for each pair,
saving results in manual_pmid/results/.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import re
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


def parse_pmids(pmid_line: str) -> str:
    """
    Parse a line of PMIDs in format '123', '456' or similar.
    Returns a comma-separated string of PMIDs: "123,456"
    """
    # Find all sequences of digits
    pmids = re.findall(r'\d+', pmid_line)
    return ",".join(pmids)


def load_hypothesis_pmid_pairs(manual_dir: Path) -> List[Tuple[str, str, int]]:
    """
    Load hypothesis and PMID pairs from manual_pmid directory.
    
    Returns:
        List of (hypothesis, pmids_string, line_number) tuples
    """
    hypothesis_file = manual_dir / "hypothesis.txt"
    pmid_file = manual_dir / "manual_PMIDs.txt"
    
    log.info(f"Loading hypothesis from: {hypothesis_file}")
    log.info(f"Loading PMIDs from: {pmid_file}")
    
    hypotheses = read_lines(hypothesis_file)
    pmid_lines = read_lines(pmid_file)
    
    # Match pairs by line number
    pairs = []
    max_len = max(len(hypotheses), len(pmid_lines))
    
    for i in range(max_len):
        hypothesis = hypotheses[i] if i < len(hypotheses) else ""
        pmid_line = pmid_lines[i] if i < len(pmid_lines) else ""
        
        if hypothesis and pmid_line:
            pmids = parse_pmids(pmid_line)
            if pmids:
                pairs.append((hypothesis, pmids, i + 1))
            else:
                log.warning(f"Line {i + 1}: No valid PMIDs found in line")
        else:
            log.warning(f"Line {i + 1}: Missing {'hypothesis' if not hypothesis else 'PMIDs'}")
    
    log.info(f"Loaded {len(pairs)} valid hypothesis-PMID pairs")
    return pairs


def run_hypothesis_validation(
    hypothesis: str,
    pmids: str,
    output_dir: Path,
    script_path: Path
) -> bool:
    """
    Run hypothesis_validation.py for a single hypothesis-PMID pair.
    
    Args:
        hypothesis: The hypothesis to validate
        pmids: Comma-separated string of PMIDs
        output_dir: Directory to save results
        script_path: Path to hypothesis_validation.py
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Build command
        # We provide a dummy query because the script might use it for logging or filenames,
        # but the actual search is skipped due to --pmids.
        cmd = [
            sys.executable,
            str(script_path),
            "--query", "MANUAL_PMID_BATCH", 
            "--hypothesis", hypothesis,
            "--pmids", pmids,
            "--output-dir", str(output_dir),
        ]
        
        log.info(f"Running validation for pair...")
        log.info(f"  Hypothesis: {hypothesis[:80]}...")
        log.info(f"  PMIDs: {pmids[:50]}... ({len(pmids.split(','))} total)")
        log.info("")
        
        # Run the subprocess
        result = subprocess.run(
            cmd,
            check=False
        )
        
        log.info("")
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
    manual_dir = root_dir / "manual_pmid"
    results_base_dir = manual_dir / "results"
    script_path = root_dir / "hypothesis_validation.py"
    
    log.info("=" * 70)
    log.info("Starting Manual PMID Hypothesis Validation")
    log.info("=" * 70)
    log.info(f"Root directory: {root_dir}")
    log.info(f"Manual directory: {manual_dir}")
    log.info(f"Results directory: {results_base_dir}")
    log.info(f"Script path: {script_path}")
    
    # Validate paths
    if not manual_dir.exists():
        log.error(f"Manual directory not found: {manual_dir}")
        sys.exit(1)
    
    if not script_path.exists():
        log.error(f"Script not found: {script_path}")
        sys.exit(1)
    
    # Create results directory
    results_base_dir.mkdir(parents=True, exist_ok=True)
    
    # Load hypothesis-PMID pairs
    try:
        pairs = load_hypothesis_pmid_pairs(manual_dir)
    except Exception as e:
        log.error(f"Failed to load pairs: {e}")
        sys.exit(1)
    
    if not pairs:
        log.error("No valid pairs found")
        sys.exit(1)
    
    # Process each pair sequentially
    total = len(pairs)
    successful = 0
    failed = 0
    
    log.info("")
    log.info("=" * 70)
    log.info(f"Processing {total} pairs")
    log.info("=" * 70)
    log.info("")
    
    with tqdm(total=total, desc="Batch Progress", unit="pair", ncols=100, position=0) as pbar:
        for idx, (hypothesis, pmids, line_num) in enumerate(pairs, start=1):
            pbar.set_description(f"Batch Progress (Pair {line_num})")
            
            log.info(f"[{idx}/{total}] Processing pair from line {line_num}")
            log.info("-" * 70)
            
            # Create output directory for this pair
            output_dir = results_base_dir / f"pair_{line_num:03d}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save the hypothesis and PMIDs to the output directory for reference
            (output_dir / "hypothesis.txt").write_text(hypothesis, encoding='utf-8')
            (output_dir / "pmids.txt").write_text(pmids, encoding='utf-8')
            
            # Run validation
            success = run_hypothesis_validation(
                hypothesis=hypothesis,
                pmids=pmids,
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
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
