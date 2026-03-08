import docker
import os
import logging
from pathlib import Path

log = logging.getLogger("docker_manager")

class DockerManager:
    def __init__(self):
        self.client = docker.from_env()
        self.image_name = "hypothesis-validator:latest"
        self.output_base_dir = Path("/app/outputs") # Inside the web container
        # Ensure this matches the volume mount in docker-compose

    def start_job(self, job_id: int, query: str, hypothesis: str, max_articles: float = float('inf'), 
                  openai_api_key: str = None, openai_model: str = None, openai_base_url: str = None, system_prompt: str = None,
                  max_articles_percent: float = None, llm_concurrency_limit: int = None, llm_temperature: float = None):
        try:
            cmd = [
                "--query", query,
                "--hypothesis", hypothesis,
                "--job-id", str(job_id),
                "--db-url", os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/dbname")
            ]
            if max_articles != float('inf'):
                cmd.extend(["--max-articles", str(max_articles)])
            
            if max_articles_percent is not None:
                cmd.extend(["--max-articles-percent", str(max_articles_percent)])

            # Fix localhost URLs from web UI to work inside containers
            if openai_base_url:
                openai_base_url = openai_base_url.replace("localhost", "host.docker.internal")
                openai_base_url = openai_base_url.replace("127.0.0.1", "host.docker.internal")

            # Use custom settings if provided, otherwise fall back to environment defaults
            container = self.client.containers.run(
                self.image_name,
                command=cmd,
                detach=True,
                environment={
                    "OPENAI_API_KEY": openai_api_key or os.getenv("OPENAI_API_KEY"),
                    "OPENAI_MODEL": openai_model or os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b"),
                    "OPENAI_BASE_URL": openai_base_url or os.getenv("OPENAI_BASE_URL", "http://host.docker.internal:11433/v1"),
                    "LLM_SYSTEM_PROMPT": system_prompt or os.getenv("LLM_SYSTEM_PROMPT"),
                    "DATABASE_URL": os.getenv("DATABASE_URL"),
                    "LLM_CONCURRENCY_LIMIT": str(llm_concurrency_limit) if llm_concurrency_limit is not None else os.getenv("LLM_CONCURRENCY_LIMIT", "1024"),
                    "OPENAI_MAX_RETRIES": os.getenv("OPENAI_MAX_RETRIES", "0"),
                    "LLM_TEMPERATURE": str(llm_temperature) if llm_temperature is not None else os.getenv("LLM_TEMPERATURE", "0.0"),
                    "NCBI_MAX_REQUESTS_PER_SECOND": os.getenv("NCBI_MAX_REQUESTS_PER_SECOND", "3.0"),
                    "HTTP_TIMEOUT_SEC": os.getenv("HTTP_TIMEOUT_SEC", "60.0"),
                    "MAX_RETRIES": os.getenv("MAX_RETRIES", "10"),
                    "RETRY_BACKOFF_BASE_SEC": os.getenv("RETRY_BACKOFF_BASE_SEC", "1.5"),
                    "SEARCH_THREAD_COUNT": os.getenv("SEARCH_THREAD_COUNT", "8"),
                    "FETCH_THREAD_COUNT": os.getenv("FETCH_THREAD_COUNT", "16"),
                },
                extra_hosts={"host.docker.internal": "host-gateway"},
                labels={"job_id": str(job_id)},
                network="hypothesis-validation_default"
            )
            return container.id
        except Exception as e:
            log.error(f"Failed to start container for job {job_id}: {e}")
            raise e

    def stop_job(self, container_id: str):
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=5)
            container.remove()
        except docker.errors.NotFound:
            pass
        except Exception as e:
            log.error(f"Failed to stop container {container_id}: {e}")

    def get_logs(self, container_id: str):
        try:
            import re
            container = self.client.containers.get(container_id)
            # Get logs as bytes, decode to string
            logs = container.logs(stdout=True, stderr=True)
            if not logs:
                return ""
            
            log_text = logs.decode('utf-8', errors='replace')
            
            # Remove ANSI escape codes (colors, cursor movements, etc.)
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            log_text = ansi_escape.sub('', log_text)
            
            # Process carriage returns to simulate terminal overwriting
            lines = log_text.split('\n')
            processed_lines = []
            
            for line in lines:
                # If line contains carriage return, take everything after the last \r
                if '\r' in line:
                    # Take content after the last carriage return
                    processed_lines.append(line.split('\r')[-1])
                else:
                    processed_lines.append(line)
            
            return '\n'.join(processed_lines)
        except Exception as e:
            print(f"Error getting logs for {container_id}: {e}")
            return None

docker_manager = DockerManager()
