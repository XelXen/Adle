"""Background jobs the interface can watch and cancel.

Long work (importing documents, and later generating lessons) must not block
a request or the interface. A job is a row in the database plus a function
run on a single worker thread:

* one job runs at a time, so heavy work is naturally bounded;
* progress and outcome are persisted, so the interface can poll for them;
* cancellation is cooperative: the work checks ``context.cancelled``;
* a job that was still pending when the app closed is marked as interrupted
  on the next start, never silently lost or left "running" forever.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from adle_core.errors import AdleError, NotFoundError
from adle_core.infrastructure.database import Database
from adle_core.infrastructure.ids import new_id
from adle_core.infrastructure.orm import Job

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "running")


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    id: str
    kind: str
    course_id: str | None
    subject_id: str | None
    status: str
    progress_done: int
    progress_total: int
    progress_message: str
    result: Any | None
    error_code: str | None
    error_message: str | None

    @property
    def finished(self) -> bool:
        return self.status not in ACTIVE_STATUSES


def _snapshot(job: Job) -> JobSnapshot:
    progress = job.progress or {}
    error = job.error or {}
    return JobSnapshot(
        id=job.id,
        kind=job.kind,
        course_id=job.course_id,
        subject_id=job.subject_id,
        status=job.status,
        progress_done=int(progress.get("done", 0)),
        progress_total=int(progress.get("total", 0)),
        progress_message=str(progress.get("message", "")),
        result=job.result,
        error_code=error.get("code"),
        error_message=error.get("message"),
    )


class JobCancelledError(Exception):
    """Raised inside a job's work function to stop early after a cancel request.

    ``result`` carries whatever was completed before stopping, so partial work
    (for example the files already imported) is still reported.
    """

    def __init__(self, result: Any | None = None) -> None:
        super().__init__("cancelled")
        self.result = result


class JobContext:
    """What a job's work function may use to report progress and notice cancellation."""

    def __init__(self, runner: JobRunner, job_id: str, cancel_event: threading.Event) -> None:
        self._runner = runner
        self.job_id = job_id
        self._cancel_event = cancel_event

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def check_cancelled(self, partial_result: Any | None = None) -> None:
        if self.cancelled:
            raise JobCancelledError(partial_result)

    def report(self, done: int, total: int, message: str = "") -> None:
        self._runner._update(
            self.job_id, progress={"done": done, "total": total, "message": message}
        )


Work = Callable[[JobContext], Any]


class JobRunner:
    """Runs submitted work one job at a time on a background thread."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self._queue: queue.Queue[tuple[str, Work] | None] = queue.Queue()
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Mark work abandoned by a previous run as interrupted, then start the worker."""
        with self._database.session() as session:
            for job in session.query(Job).filter(Job.status.in_(ACTIVE_STATUSES)):
                job.status = "failed"
                job.error = {
                    "code": "interrupted",
                    "message": "Adle was closed before this finished. You can start it again.",
                }
        self._thread = threading.Thread(target=self._work_loop, name="adle-jobs", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Ask running work to stop and wait briefly for the worker to finish."""
        with self._lock:
            for cancel_event in self._cancel_events.values():
                cancel_event.set()
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout)

    def submit(
        self,
        kind: str,
        work: Work,
        *,
        course_id: str | None = None,
        subject_id: str | None = None,
    ) -> JobSnapshot:
        job_id = new_id("job")
        with self._database.session() as session:
            job = Job(
                id=job_id,
                kind=kind,
                course_id=course_id,
                subject_id=subject_id,
                status="queued",
                progress={},
            )
            session.add(job)
            session.flush()
            snapshot = _snapshot(job)
        with self._lock:
            self._cancel_events[job_id] = threading.Event()
        self._queue.put((job_id, work))
        return snapshot

    def find_active(self, kind: str, subject_id: str) -> JobSnapshot | None:
        """The job of this kind already working on this subject, if there is one."""
        with self._database.session() as session:
            job = session.scalars(
                select(Job)
                .where(
                    Job.kind == kind,
                    Job.subject_id == subject_id,
                    Job.status.in_(ACTIVE_STATUSES),
                )
                .order_by(Job.created_at.desc())
            ).first()
            return _snapshot(job) if job is not None else None

    def latest(self, kind: str, subject_id: str) -> JobSnapshot | None:
        """The most recent job of this kind about this subject, whatever became of it."""
        with self._database.session() as session:
            job = session.scalars(
                select(Job)
                .where(Job.kind == kind, Job.subject_id == subject_id)
                .order_by(Job.created_at.desc(), Job.id.desc())
            ).first()
            return _snapshot(job) if job is not None else None

    def list_active(self, course_id: str) -> list[JobSnapshot]:
        """Jobs of a course that are waiting or running, oldest first."""
        with self._database.session() as session:
            jobs = session.scalars(
                select(Job)
                .where(Job.course_id == course_id, Job.status.in_(ACTIVE_STATUSES))
                .order_by(Job.created_at, Job.id)
            )
            return [_snapshot(job) for job in jobs]

    def set_result(self, job_id: str, result: Any) -> None:
        """Replace a finished job's result (for example to note that it has been used)."""
        self._update(job_id, result=result)

    def get(self, job_id: str) -> JobSnapshot:
        with self._database.session() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise NotFoundError("That task no longer exists.")
            return _snapshot(job)

    def cancel(self, job_id: str) -> JobSnapshot:
        """Request cancellation.

        A queued job is cancelled at once; a running one at its next cancellation check.
        """
        with self._lock:
            cancel_event = self._cancel_events.get(job_id)
        if cancel_event is not None:
            cancel_event.set()
        with self._database.session() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise NotFoundError("That task no longer exists.")
            if job.status == "queued":
                job.status = "cancelled"
            session.flush()
            return _snapshot(job)

    def wait(self, job_id: str, timeout: float = 30.0) -> JobSnapshot:
        """Block until the job finishes. For tests and command-line tools."""
        deadline = threading.Event()
        waited = 0.0
        while waited < timeout:
            snapshot = self.get(job_id)
            if snapshot.finished:
                return snapshot
            deadline.wait(0.02)
            waited += 0.02
        raise TimeoutError(f"Job {job_id} did not finish within {timeout} seconds.")

    # -- internals ---------------------------------------------------------

    def _update(self, job_id: str, **fields: Any) -> None:
        with self._database.session() as session:
            job = session.get(Job, job_id)
            if job is None:
                return  # The course (and its jobs) was deleted while the job ran.
            for name, value in fields.items():
                setattr(job, name, value)

    def _work_loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            job_id, work = item
            with self._lock:
                cancel_event = self._cancel_events.get(job_id, threading.Event())
            try:
                self._run_one(job_id, work, cancel_event)
            finally:
                with self._lock:
                    self._cancel_events.pop(job_id, None)

    def _run_one(self, job_id: str, work: Work, cancel_event: threading.Event) -> None:
        if cancel_event.is_set():
            self._update(job_id, status="cancelled")
            return
        self._update(job_id, status="running")
        try:
            result = work(JobContext(self, job_id, cancel_event))
        except JobCancelledError as cancelled:
            self._update(job_id, status="cancelled", result=cancelled.result)
        except AdleError as error:
            self._update(
                job_id, status="failed", error={"code": error.code, "message": error.message}
            )
        except Exception:
            # Log where it failed, not what it was processing.
            logger.exception("Job %s failed unexpectedly", job_id)
            self._update(
                job_id,
                status="failed",
                error={
                    "code": "internal_error",
                    "message": "Something went wrong. Nothing was lost; please try again.",
                },
            )
        else:
            # Work that ran to completion succeeded, even if a cancel arrived too late to matter.
            self._update(job_id, status="succeeded", result=result)
