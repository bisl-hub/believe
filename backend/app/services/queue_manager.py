import threading
import time
import docker
from collections import Counter
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError, ObjectDeletedError
from ..db.session import SessionLocal
from ..models import job as job_model
from ..services.docker_service import docker_service

class QueueManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QueueManager, cls).__new__(cls)
            cls._instance.monitoring_thread = None
            cls._instance.stop_event = threading.Event()
        return cls._instance

    def start(self):
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.stop_event.clear()
            self.monitoring_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.monitoring_thread.start()
            print("QueueManager started.")

    def stop(self):
        self.stop_event.set()
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
            print("QueueManager stopped.")

    def _worker_loop(self):
        print("QueueManager worker loop running...")
        while not self.stop_event.is_set():
            try:
                self._process_queue()
            except Exception as e:
                print(f"Error in QueueManager loop: {e}")
            
            # Simple polling interval
            time.sleep(2)

    # Concurrency is budgeted PER model serving name (job.openai_model) rather
    # than globally, so a large backlog for one model can't block jobs for
    # another. No global ceiling — total running = per_model_limit x #models.
    PER_MODEL_LIMIT = 32

    @staticmethod
    def _queue_key(job: job_model.Job) -> str:
        # The model serving name is the queue key. Download-only jobs carry
        # "none" and thus share their own bucket.
        return job.openai_model or "none"

    def _process_queue(self):
        db: Session = SessionLocal()
        try:
            # 1. Check and monitor all currently RUNNING jobs
            running_jobs = db.query(job_model.Job).filter(job_model.Job.status == job_model.JobStatus.RUNNING).all()

            for running_job in running_jobs:
                # Isolate each job: a row deleted out from under us (e.g. the
                # dataset was deleted mid-run) must not abort the whole pass.
                try:
                    self._monitor_running_job(db, running_job)
                except (StaleDataError, ObjectDeletedError):
                    print(f"QueueManager: Job {running_job.id} row vanished during monitoring; skipping.")
                    db.rollback()
                except Exception as e:
                    print(f"QueueManager: Error monitoring Job {running_job.id}: {e}")
                    db.rollback()

            # 2. Count how many jobs are RUNNING per model serving name.
            running_now = db.query(job_model.Job).filter(job_model.Job.status == job_model.JobStatus.RUNNING).all()
            running_per_model = Counter(self._queue_key(j) for j in running_now)

            # 3. For each model that has QUEUED work, start up to its remaining
            #    per-model slots. Each model is an independent queue.
            queued_models = [
                m for (m,) in db.query(job_model.Job.openai_model)
                                .filter(job_model.Job.status == job_model.JobStatus.QUEUED)
                                .distinct()
                                .all()
            ]

            for model in queued_models:
                key = model or "none"
                slots = self.PER_MODEL_LIMIT - running_per_model[key]
                if slots <= 0:
                    continue

                next_jobs = db.query(job_model.Job)\
                    .filter(job_model.Job.status == job_model.JobStatus.QUEUED,
                            job_model.Job.openai_model == model)\
                    .order_by(job_model.Job.created_at.asc())\
                    .limit(slots)\
                    .all()

                for next_job in next_jobs:
                    try:
                        self._start_job(db, next_job)
                        running_per_model[key] += 1
                    except (StaleDataError, ObjectDeletedError):
                        print(f"QueueManager: Job {next_job.id} row vanished before start; skipping.")
                        db.rollback()
                    except Exception as e:
                        print(f"QueueManager: Error starting Job {next_job.id}: {e}")
                        db.rollback()

        finally:
            db.close()

    def _start_job(self, db: Session, job: job_model.Job):
        print(f"QueueManager: Starting Job {job.id}")
        try:
            # Update status to RUNNING immediately to block other jobs
            job.status = job_model.JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            db.commit()

            force_refresh = False
            if job.name and job.name.startswith("Force-Download:"):
                force_refresh = True

            container_id = docker_service.start_job(
                job.id, job.query_term, job.hypothesis, job.max_articles,
                job_type=job.job_type,
                source_type=job.source_type,
                openai_api_key=job.openai_api_key,
                openai_model=job.openai_model,
                openai_base_url=job.openai_base_url,
                system_prompt=job.system_prompt,
                max_articles_percent=job.max_articles_percent,
                llm_concurrency_limit=job.llm_concurrency_limit,
                llm_temperature=job.llm_temperature,
                force_refresh=force_refresh
            )
            
            job.container_id = container_id
            db.commit()
            print(f"QueueManager: Job {job.id} started (Container {container_id})")

        except Exception as e:
            print(f"QueueManager: Failed to start Job {job.id}: {e}")
            job.status = job_model.JobStatus.FAILED
            db.commit()

    def _monitor_running_job(self, db: Session, job: job_model.Job):
        # Check container status
        if not job.container_id:
            print(f"QueueManager: Job {job.id} is RUNNING but has no container_id. Marking FAILED.")
            job.status = job_model.JobStatus.FAILED
            db.commit()
            return

        client = docker_service.client
        try:
            container = client.containers.get(job.container_id)
            if container.status in ['exited', 'dead']:
                # Container finished
                exit_code = container.attrs['State']['ExitCode']
                print(f"QueueManager: Job {job.id} container finished with code {exit_code}")
                
                if exit_code == 0:
                    job.status = job_model.JobStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                else:
                    job.status = job_model.JobStatus.FAILED
                
                # Fetch Logs
                try:
                    logs = docker_service.get_logs(job.container_id)
                    if logs:
                        job.logs = logs
                except Exception as e:
                    print(f"Error fetching logs for Job {job.id}: {e}")

                db.commit()

                # Remove the container now that we have the logs and final status
                try:
                    container.remove()
                except Exception as e:
                    print(f"QueueManager: Failed to remove container for Job {job.id}: {e}")
            else:
                # Still running, do nothing (wait for next loop)
                pass

        except docker.errors.NotFound:
            print(f"QueueManager: Job {job.id} running but container {job.container_id} not found.")
            # Check if it was canceled?
            if job.status == job_model.JobStatus.STOPPED:
                 # Already handled state change, just ignore
                 pass
            else:
                 # Unexpected loss
                 job.status = job_model.JobStatus.FAILED
                 db.commit()

        except (StaleDataError, ObjectDeletedError):
            # The job row was deleted concurrently (e.g. dataset removed).
            # Let the caller roll back and move on.
            raise

        except Exception as e:
            print(f"QueueManager: Error monitoring Job {job.id}: {e}")
            # Don't fail immediately on transient docker errors
            pass

queue_manager = QueueManager()
