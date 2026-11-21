"""The background job runner: progress, failure, cancellation, and interruption."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from adle_core.application.jobs import LANE_QUICK, JobContext, JobRunner
from adle_core.errors import AdleError, NotFoundError
from adle_core.infrastructure.database import Database
from adle_core.infrastructure.migrate import migrate
from adle_core.infrastructure.orm import Job


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "adle.db")
    migrate(database, tmp_path / "backups")
    yield database
    database.dispose()


@pytest.fixture
def runner(database: Database) -> Iterator[JobRunner]:
    runner = JobRunner(database)
    runner.start()
    yield runner
    runner.stop()


def test_a_job_reports_progress_and_its_result(runner: JobRunner) -> None:
    seen: list[tuple[int, int, str]] = []
    release = threading.Event()

    def work(context: JobContext) -> dict[str, int]:
        context.report(1, 3, "first file")
        snapshot = runner.get(context.job_id)
        seen.append((snapshot.progress_done, snapshot.progress_total, snapshot.progress_message))
        release.wait(5)
        return {"imported": 3}

    submitted = runner.submit("import_sources", work)
    assert submitted.status == "queued"
    assert not submitted.finished
    release.set()
    finished = runner.wait(submitted.id)

    assert finished.status == "succeeded"
    assert finished.finished
    assert finished.result == {"imported": 3}
    assert finished.error_code is None
    assert seen == [(1, 3, "first file")]


def test_an_expected_failure_keeps_its_code_and_message(runner: JobRunner) -> None:
    def work(_: JobContext) -> None:
        raise AdleError("The provider is out of quota for today.", code="quota_exhausted")

    finished = runner.wait(runner.submit("generate_lesson", work).id)
    assert finished.status == "failed"
    assert finished.error_code == "quota_exhausted"
    assert finished.error_message == "The provider is out of quota for today."


def test_an_unexpected_failure_never_exposes_internals(
    runner: JobRunner, caplog: pytest.LogCaptureFixture
) -> None:
    def work(_: JobContext) -> None:
        raise RuntimeError("secret detail: /home/learner/private-notes.pdf")

    finished = runner.wait(runner.submit("import_sources", work).id)
    assert finished.status == "failed"
    assert finished.error_code == "internal_error"
    assert "private-notes" not in (finished.error_message or "")
    assert "Please try again" in (finished.error_message or "")
    # It is still diagnosable from the log.
    assert any("failed unexpectedly" in record.message for record in caplog.records)
    # By what kind of error it was and where it happened, never by what it said.
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "RuntimeError" in logged
    assert "test_jobs.py" in logged
    assert "private-notes" not in logged
    assert "private-notes" not in caplog.text


def test_a_job_whose_record_cannot_be_written_does_not_stop_the_ones_behind_it(
    runner: JobRunner, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The lane has one thread. If it ended, everything after would wait for ever."""
    real_update = runner._update
    failed_once = threading.Event()

    def update(job_id: str, **fields: object) -> None:
        # The write that says the first job succeeded fails, as when the disk is full.
        if fields.get("status") == "succeeded" and not failed_once.is_set():
            failed_once.set()
            raise OSError("database or disk is full: /home/learner/adle.db")
        real_update(job_id, **fields)

    monkeypatch.setattr(runner, "_update", update)
    first = runner.submit("import_sources", lambda _: {"imported": 1})
    second = runner.submit("import_sources", lambda _: {"imported": 2})

    # The one behind it runs, and the first is not left saying it is still running.
    assert runner.wait(second.id).result == {"imported": 2}
    assert runner.wait(first.id).status == "failed"
    assert runner.wait(first.id).error_code == "internal_error"
    assert "could not be recorded (OSError)" in caplog.text
    assert "adle.db" not in caplog.text


def test_what_is_logged_about_an_error_is_its_kind_and_place_never_its_text() -> None:
    from adle_core.logs import where

    def inner() -> None:
        raise ValueError("the learner typed: my password is hunter2")

    try:
        try:
            inner()
        except ValueError as error:
            raise RuntimeError("while importing C:/Users/someone/notes.pdf") from error
    except RuntimeError as error:
        said = where(error)
    assert "RuntimeError" in said
    assert "ValueError" in said
    assert "test_jobs.py" in said
    assert "in inner" in said
    assert "hunter2" not in said
    assert "notes.pdf" not in said


def test_jobs_run_one_at_a_time_in_submission_order(runner: JobRunner) -> None:
    order: list[str] = []
    running = threading.Semaphore(1)

    def make(name: str):  # type: ignore[no-untyped-def]
        def work(_: JobContext) -> str:
            assert running.acquire(blocking=False), "two jobs ran at once"
            order.append(name)
            running.release()
            return name

        return work

    ids = [runner.submit("test", make(name)).id for name in ("a", "b", "c")]
    assert [runner.wait(job_id).result for job_id in ids] == ["a", "b", "c"]
    assert order == ["a", "b", "c"]


def test_cancelling_a_running_job_keeps_its_partial_result(runner: JobRunner) -> None:
    started = threading.Event()
    proceed = threading.Event()

    def work(context: JobContext) -> dict[str, list[str]]:
        done = ["first.pdf"]
        started.set()
        proceed.wait(5)
        context.check_cancelled({"files": done})
        return {"files": [*done, "second.pdf"]}

    job = runner.submit("import_sources", work)
    assert started.wait(5)
    assert runner.cancel(job.id).status == "running"  # takes effect at the next check
    proceed.set()
    finished = runner.wait(job.id)
    assert finished.status == "cancelled"
    assert finished.result == {"files": ["first.pdf"]}


def test_cancelling_a_queued_job_means_it_never_runs(runner: JobRunner) -> None:
    blocker_started = threading.Event()
    release = threading.Event()
    ran: list[str] = []

    def blocker(_: JobContext) -> None:
        blocker_started.set()
        release.wait(5)

    def queued(_: JobContext) -> None:
        ran.append("queued job ran")

    first = runner.submit("test", blocker)
    assert blocker_started.wait(5)
    second = runner.submit("test", queued)
    assert runner.cancel(second.id).status == "cancelled"
    release.set()
    runner.wait(first.id)
    assert runner.wait(second.id).status == "cancelled"
    assert ran == []


def test_work_that_finishes_despite_a_late_cancel_still_succeeded(runner: JobRunner) -> None:
    started = threading.Event()
    proceed = threading.Event()

    def work(_: JobContext) -> str:
        started.set()
        proceed.wait(5)
        return "all done"

    job = runner.submit("test", work)
    assert started.wait(5)
    runner.cancel(job.id)
    proceed.set()
    finished = runner.wait(job.id)
    assert (finished.status, finished.result) == ("succeeded", "all done")


def test_jobs_left_over_from_a_previous_run_are_marked_interrupted(database: Database) -> None:
    with database.session() as session:
        session.add(Job(id="job_00000000000000000001", kind="import_sources", status="running"))
        session.add(Job(id="job_00000000000000000002", kind="import_sources", status="queued"))
        session.add(Job(id="job_00000000000000000003", kind="import_sources", status="succeeded"))

    runner = JobRunner(database)
    runner.start()
    try:
        for job_id in ("job_00000000000000000001", "job_00000000000000000002"):
            snapshot = runner.get(job_id)
            assert snapshot.status == "failed"
            assert snapshot.error_code == "interrupted"
            assert "closed before this finished" in (snapshot.error_message or "")
        assert runner.get("job_00000000000000000003").status == "succeeded"
    finally:
        runner.stop()


def test_unknown_jobs_are_not_found(runner: JobRunner) -> None:
    with pytest.raises(NotFoundError):
        runner.get("job_missing")
    with pytest.raises(NotFoundError):
        runner.cancel("job_missing")


def test_stopping_the_runner_asks_running_work_to_stop(database: Database) -> None:
    runner = JobRunner(database)
    runner.start()
    started = threading.Event()
    observed: list[bool] = []

    def work(context: JobContext) -> None:
        started.set()
        for _ in range(500):
            if context.cancelled:
                observed.append(True)
                return
            threading.Event().wait(0.01)

    runner.submit("test", work)
    assert started.wait(5)
    runner.stop()
    assert observed == [True]


def test_short_work_does_not_wait_behind_long_work(runner: JobRunner) -> None:
    """Two lanes: a question asked during a lesson must not queue behind a lesson being written."""
    started, release = threading.Event(), threading.Event()

    def long_work(_: JobContext) -> str:
        started.set()
        release.wait(20)
        return "long"

    long_job = runner.submit("lesson_generation", long_work)
    queued_behind = runner.submit("lesson_generation", lambda _: "second")
    try:
        assert started.wait(20)
        quick = runner.wait(runner.submit("lesson_ask", lambda _: "short", lane=LANE_QUICK).id)
        assert (quick.status, quick.result) == ("succeeded", "short")
        # Long work is still one job at a time.
        assert runner.get(long_job.id).status == "running"
        assert runner.get(queued_behind.id).status == "queued"
        # Two jobs asked for in the same instant have no order between them.
        assert {job.id for job in runner.list_all_active(["lesson_generation"])} == {
            long_job.id,
            queued_behind.id,
        }
        assert runner.list_all_active(["lesson_ask"]) == []
    finally:
        release.set()
    assert runner.wait(queued_behind.id).result == "second"


def test_a_job_says_when_it_was_asked_for(runner: JobRunner) -> None:
    finished = runner.wait(runner.submit("import_sources", lambda _: None).id)
    assert finished.created_at is not None
