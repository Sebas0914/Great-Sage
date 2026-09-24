"""Background work queue for Great Sage.

The conversational model and the worker model are deliberately separate.
A worker job runs on its own daemon thread, so the WebSocket/event loop and
the fast conversational agent remain responsive while a long task is being
processed.

The worker currently delegates the actual generation/file building to
great_sage.core.heavy. It is intentionally a single-worker queue: this
machine has 7.8 GB RAM and a 4 GB GPU, so running several large local models
at once would create avoidable memory pressure.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from great_sage.core import heavy

log = logging.getLogger(__name__)


@dataclass
class WorkerJob:
    id: str
    request: str
    kind: str
    status: str = "queued"
    progress: str = ""


class WorkerManager:
    """Run one long job at a time and publish small progress events."""

    def __init__(self):
        self._lock = threading.RLock()
        self._active: Optional[WorkerJob] = None
        self._jobs: Dict[str, WorkerJob] = {}

    @property
    def active(self) -> Optional[WorkerJob]:
        with self._lock:
            return self._active

    def submit(
        self,
        request: str,
        kind: str,
        on_event: Optional[Callable[[dict], None]] = None,
        on_done: Optional[Callable[[WorkerJob, object, Optional[Exception]], None]] = None,
        provider=None,
        provider_label: str = "Ollama / Local",
    ) -> Optional[WorkerJob]:
        request = (request or "").strip()
        if not request:
            return None

        with self._lock:
            if self._active is not None:
                return None
            job = WorkerJob(
                id=uuid.uuid4().hex[:10],
                request=request,
                kind=kind or "general",
            )
            self._jobs[job.id] = job
            self._active = job

        def emit(**payload):
            payload.setdefault("job_id", job.id)
            payload.setdefault("kind", job.kind)
            if on_event is not None:
                try:
                    on_event(payload)
                except Exception:
                    log.exception("Worker event callback failed")

        def run():
            result = None
            error = None
            with self._lock:
                job.status = "running"
            emit(status="started", message="Iniciando trabajo...")

            def progress(message: str):
                with self._lock:
                    job.progress = str(message)
                emit(status="progress", message=str(message))

            try:
                emit(status="progress",
                     message="Agente seleccionado: %s" % provider_label)
                try:
                    result = heavy.run_job(
                        job.request,
                        job.kind,
                        provider=provider,
                        progress=progress,
                    )
                except Exception as online_exc:
                    # API providers are preferred for specialist work, but
                    # losing the network must never lose the job. Retry once
                    # with the local worker model.
                    if provider is not None and not str(provider_label).startswith("Ollama / Local"):
                        log.warning(
                            "Specialized provider failed for job %s; "
                            "falling back to local worker: %s",
                            job.id, online_exc,
                        )
                        emit(
                            status="progress",
                            message="API no disponible. Cambiando al agente local...",
                        )
                        result = heavy.run_job(
                            job.request,
                            job.kind,
                            provider=heavy.build_provider(),
                            progress=progress,
                        )
                    else:
                        raise
                with self._lock:
                    job.status = "finished"
                emit(
                    status="finished",
                    message="Trabajo terminado.",
                    title=getattr(result, "title", ""),
                    path=str(getattr(result, "path", "") or ""),
                    text=getattr(result, "text", "") or "",
                    model=getattr(result, "model", ""),
                )
            except Exception as exc:
                error = exc
                with self._lock:
                    job.status = "failed"
                log.exception("Worker job %s failed", job.id)
                emit(status="failed", message=str(exc))
            finally:
                with self._lock:
                    if self._active is job:
                        self._active = None
                if on_done is not None:
                    try:
                        on_done(job, result, error)
                    except Exception:
                        log.exception("Worker completion callback failed")

        threading.Thread(
            target=run,
            name="great-sage-worker",
            daemon=True,
        ).start()
        return job
