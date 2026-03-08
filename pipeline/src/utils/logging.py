import logging
import time

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

log = logging.getLogger("pubmed_hypothesis")

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

