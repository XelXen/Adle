"""A film of a whole course, made at the learner's word (ADR-065).

The learner asks for it once, is told that it takes a long time and that they need not
wait, and it is made in a lane of its own:

1. Each concept of the course, in the order it is learned, becomes a chapter. A model is
   asked for the chapter as one complete ManimGX file (``prompts.film_chapter_request``),
   with how the course's subject is taught (ADR-061). The file is checked by the rules
   (``film.policy``) and, if it passes, run by the engine alone with the film's voice and
   without making a video (``inspect``): every moment of it is looked at, and whatever stops
   it, lies over other words or under a line, or goes past the edge is found, by the line
   of the file. What was found is told to the model, and the file sent back to be mended,
   up to ``MAX_MENDS`` times. The version that ran with the least wrong is kept; a chapter
   whose every version was refused or stopped is told in words by Adle instead. Where a
   model that sees pictures can be asked, a chapter's storyboard (the screen at the end of
   each animation) is looked over once, and what it sees is told to the writer in the same
   way (ADR-066).
2. As each chapter is kept, its lines are recorded in the natural voice, in the voice lane,
   while the next chapter is written. Without a natural voice the film is quiet, and its
   words are shown as it plays.
3. The chapters are put together, after an opening Adle writes (``film.script``), looked at
   whole with their recordings, and made into a video at 1920 by 1080, with subtitles.

The requests are bounded: a chapter is asked for once, mended at most ``MAX_MENDS``
times, and looked over at most once, and the learner is told that number before anything
is sent. Nothing made is lost: a film stopped, failed, or left when Adle closed is
unfinished, and continuing it begins at the first chapter not yet kept. Removing it, or
its course, stops the work and takes its files away.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import secrets
import shutil
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from adle_core.application.courses import get_course_or_404
from adle_core.application.curriculum import ConceptRecord, CurriculumService
from adle_core.application.generation import KIND_FILM, GenerationService, subject_of
from adle_core.application.jobs import (
    LANE_FILM,
    JobCancelledError,
    JobContext,
    JobRunner,
    JobSnapshot,
    WorkContext,
    side_by_side,
)
from adle_core.application.model_gateway import ModelGateway, QuotaExhaustedError
from adle_core.application.narration import KIND_FILM_NARRATION, NarrationService
from adle_core.application.retrieval import Passage as StoredPassage
from adle_core.errors import AdleError, ConflictError, NotFoundError, ValidationFailedError
from adle_core.film import script, storyboard
from adle_core.film.catalog import INSTALLED_BYTES, SOURCES, build_for
from adle_core.film.install import FilmInstaller
from adle_core.film.policy import (
    check_chapter_source,
    with_engine_names,
    with_spans_fitted,
    with_timing_passed_on,
)
from adle_core.film.report import Report, chapter_starts, findings
from adle_core.film.runtime import (
    INSPECT_SECONDS,
    FilmEngine,
    FilmEngineError,
    FilmEngineStoppedError,
    FilmEngineTimeoutError,
    FilmPaths,
    seconds_for,
)
from adle_core.generation import prompts
from adle_core.generation.provider import ChatResult, RequestCancelledError
from adle_core.infrastructure.database import Database, utc_now
from adle_core.infrastructure.ids import is_id, new_id
from adle_core.infrastructure.orm import Course, Film
from adle_core.ingestion.types import heading_leaf
from adle_core.logs import where

logger = logging.getLogger(__name__)

#: Setting the film maker up (``KIND_FILM``, making a film, is generation's: it is long work).
KIND_FILM_SETUP = "film_setup"

#: A chapter's state: still to be written, being written now, written by a model and
#: checked, or told in words by Adle because no version of a model's would run. A chapter
#: being written when the work stopped is waiting again.
WAITING, WRITING, WRITTEN, IN_WORDS = "waiting", "writing", "written", "in_words"
#: The most chapters written at once, where the provider that writes them takes several
#: requests at once (ADR-068): each is minutes of a model's work, and they do not depend on
#: each other's words.
CHAPTERS_AT_ONCE = 3
#: The opening is Adle's, and is always the first chapter.
OPENING_TITLE = "Introduction"
#: How much of a video one request for it carries.
PART_BYTES = 1024 * 1024
#: A video of more than this is not offered to the page a part at a time.
MAX_VIDEO_BYTES = 4 * 1024 * 1024 * 1024
#: Files handed to the desktop shell to be saved where the learner chooses.
HANDED_OVER = re.compile(r"^film-[0-9a-f]{20}\.(?:mp4|srt)$")
_NOT_IN_A_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
#: Where the engine keeps what a voice said, beside the scene it said it for.
ENGINE_SPEECH = "voice"
#: A chapter told this much more often than it should be short is sent back for it.
_SHORT = 3
#: How long a whole film is taken to be, a line, before it has been looked at whole.
_SECONDS_A_LINE = 6.0


@dataclass(frozen=True, slots=True)
class FilmEngineStatus:
    """Whether the film maker is on this computer, and what setting it up takes."""

    ready: bool
    #: It runs on this kind of computer.
    fits: bool
    #: Set up by a developer elsewhere: used as it is, never removed.
    borrowed: bool
    setting_up: JobSnapshot | None
    download_bytes: int
    installed_bytes: int
    sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FilmChapter:
    title: str
    state: str
    #: ``model`` or ``adle``, once it is made.
    by: str
    #: How many problems of layout the engine still found in it.
    problems: int
    #: When it begins in the video, once the film is made.
    start: float | None


@dataclass(frozen=True, slots=True)
class FilmRecord:
    id: str
    course_id: str
    status: str
    title: str
    chapters: list[FilmChapter]
    #: The voice it is read in, as a learner names it; none for a quiet film.
    voice: str | None
    seconds: float | None
    size: int | None
    notes: list[str]
    written_by: dict[str, Any]
    reason: str | None
    created_at: datetime | None
    finished_at: datetime | None
    #: The work under way on it, if there is any.
    making: JobSnapshot | None


@dataclass(frozen=True, slots=True)
class FilmPlan:
    """What a film of a course would be, before it is begun or continued."""

    chapters: list[str]
    #: The most requests it may send: each chapter once, up to ``MAX_MENDS`` more, and one
    #: to look over its pictures when they are looked over.
    requests_at_most: int
    #: The voice it would be read in, as a learner names it; none for a quiet film.
    voice: str | None
    #: Why it cannot be made now, in a sentence; none when it can.
    blocked: str | None
    #: Whether each chapter's pictures are looked over by a model that sees them (ADR-066).
    checks_pictures: bool = False


@dataclass(frozen=True, slots=True)
class VideoPart:
    data: bytes
    part: int
    parts: int
    size: int


@dataclass(frozen=True, slots=True)
class SavedFilm:
    """A film written into the folder of files handed over, for the shell to move."""

    file_name: str
    #: Its subtitles, beside it, when it has any.
    captions_name: str | None
    #: What to call it, from the course's title.
    suggested_name: str


@dataclass
class _Chapter:
    concept_id: str | None
    title: str
    state: str = WAITING
    by: str = ""
    problems: int = 0
    lines: list[str] | None = None

    def stored(self) -> dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "title": self.title,
            "state": self.state,
            "by": self.by,
            "problems": self.problems,
            "lines": list(self.lines or []),
        }

    @classmethod
    def read(cls, raw: object) -> _Chapter | None:
        if not isinstance(raw, dict) or not isinstance(raw.get("title"), str):
            return None
        state = raw.get("state")
        lines = raw.get("lines")
        return cls(
            concept_id=raw.get("concept_id") if isinstance(raw.get("concept_id"), str) else None,
            title=raw["title"],
            state=state if state in (WAITING, WRITING, WRITTEN, IN_WORDS) else WAITING,
            by=str(raw.get("by") or ""),
            problems=int(raw.get("problems") or 0),
            lines=[line for line in lines if isinstance(line, str)]
            if isinstance(lines, list)
            else None,
        )


@dataclass
class _Best:
    """The version of a chapter that ran with the least wrong with it, so far."""

    score: int
    source: str
    lines: list[str]
    problems: int


def file_name_for(title: str) -> str:
    """A course's name as a film's file name."""
    plain = " ".join(_NOT_IN_A_NAME.sub(" ", title).split()).strip(". ")
    return f"{plain[:80].strip() or 'Course'}.mp4"


def _where(passage: StoredPassage) -> str:
    if passage.page_number is not None:
        return f"page {passage.page_number}"
    return heading_leaf(passage.section_title or "") or "the document"


class FilmService:
    def __init__(
        self,
        database: Database,
        jobs: JobRunner,
        gateway: ModelGateway,
        curriculum: CurriculumService,
        generation: GenerationService,
        narration: NarrationService,
        paths: FilmPaths,
        *,
        handover_dir: Path,
        installer: Callable[[FilmPaths], FilmInstaller] = FilmInstaller,
        engine: Callable[[FilmPaths], FilmEngine] = FilmEngine,
        inspect_seconds: float = INSPECT_SECONDS,
    ) -> None:
        self._database = database
        self._jobs = jobs
        self._gateway = gateway
        self._curriculum = curriculum
        self._generation = generation
        self._narration = narration
        self._paths = paths
        self._handover = handover_dir
        self._installer = installer
        self._engine = engine(paths)
        #: The longest a chapter may take to be looked at alone.
        self._inspect_seconds = inspect_seconds
        # The engine is run for one chapter at a time, even while several are written: the
        # takes share the film's folder, and what a run writes there is named by its scene.
        self._engine_turn = threading.Lock()
        #: Looking for work under way and starting it are one step (as in generation).
        self._starting = threading.Lock()

    # -- the film maker ----------------------------------------------------------------

    def engine_status(self) -> FilmEngineStatus:
        build = build_for()
        return FilmEngineStatus(
            ready=self._paths.ready(),
            fits=self._paths.fits(),
            borrowed=self._paths.borrowed,
            setting_up=self._jobs.find_active(KIND_FILM_SETUP, "film-engine"),
            download_bytes=build.download_bytes if build is not None else 0,
            installed_bytes=INSTALLED_BYTES,
            sources=SOURCES,
        )

    def install(self) -> JobSnapshot:
        """Set the film maker up: it is downloaded, at the learner's word."""
        if self._paths.borrowed:
            raise ConflictError("The film maker here was set up by hand, and is used as it is.")
        if not self._paths.fits():
            raise ConflictError("The film maker doesn’t run on this kind of computer.")
        with self._starting:
            running = self._jobs.find_active(KIND_FILM_SETUP, "film-engine")
            if running is not None:
                return running
            installer = self._installer(self._paths)

            def work(context: JobContext) -> dict[str, Any]:
                installer.install(
                    lambda message, done, total: context.report(done, total, message),
                    lambda: context.cancelled,
                )
                context.check_cancelled()
                return {"kind": "film_setup", "ready": self._paths.ready()}

            return self._jobs.submit(
                KIND_FILM_SETUP, work, subject_id="film-engine", lane=LANE_FILM
            )

    def remove_engine(self) -> None:
        """Take the film maker off this computer. Films already made are kept."""
        if self._jobs.any_active((KIND_FILM, KIND_FILM_SETUP)):
            raise ConflictError("The film maker is in use. Stop what it is doing first.")
        self._installer(self._paths).remove()

    # -- a course's film ---------------------------------------------------------------

    def _concepts(self, course_id: str) -> tuple[list[ConceptRecord], str | None]:
        """A course's concepts in the order they are learned, or why there is no order."""
        curriculum = self._curriculum.get(course_id)
        if not curriculum.concepts:
            return [], "Add concepts to the course first: a film has a chapter for each."
        if not curriculum.learning_order:
            return [], "Two concepts need each other. Put them in an order first."
        by_id = {concept.id: concept for concept in curriculum.concepts}
        ordered = [by_id[concept_id] for concept_id in curriculum.learning_order]
        if len(ordered) > script.MAX_CHAPTERS:
            return ordered, (
                f"A film has at most {script.MAX_CHAPTERS} chapters, and this course has "
                f"{len(ordered)} concepts."
            )
        return ordered, None

    def plan(self, course_id: str) -> FilmPlan:
        with self._database.read() as session:
            get_course_or_404(session, course_id)
        concepts, blocked = self._concepts(course_id)
        voice = self._narration.film_voice()
        if blocked is None and not self._paths.ready():
            blocked = "Set up the film maker first."
        if blocked is None and not self._gateway.has_key:
            blocked = "Add an AI provider’s key first: the chapters are written by the AI."
        looks = self._looks()
        return FilmPlan(
            chapters=[concept.title for concept in concepts],
            requests_at_most=len(concepts) * (1 + script.MAX_MENDS + (1 if looks else 0)),
            voice=self._narration.voice_name(voice) if voice is not None else None,
            blocked=blocked,
            checks_pictures=looks,
        )

    def _looks(self) -> bool:
        """Whether a chapter's pictures can be looked over now (ADR-066): a model that sees
        pictures can be asked, by the learner's choice, with a key. Without one, nothing is
        looked over and nothing is sent in its place."""
        try:
            self._gateway.ready_for("storyboard")
        except AdleError:
            return False
        return True

    def making(self) -> list[JobSnapshot]:
        """Films being made, or the film maker being set up, in any course, oldest first."""
        return self._jobs.list_all_active((KIND_FILM, KIND_FILM_SETUP))

    def film_of(self, course_id: str) -> FilmRecord | None:
        with self._database.read() as session:
            get_course_or_404(session, course_id)
            film = session.scalars(select(Film).where(Film.course_id == course_id)).first()
            if film is None:
                return None
            return self._record(film)

    def _record(self, film: Film) -> FilmRecord:
        marks = {
            index: float(mark["start"])
            for index, mark in enumerate(film.marks or [])
            if isinstance(mark, dict) and isinstance(mark.get("start"), int | float)
        }
        chapters = [chapter for chapter in map(_Chapter.read, film.chapters or []) if chapter]
        making = self._jobs.find_active(KIND_FILM, film.course_id)
        if making is None:
            # Being written when the work stopped: waiting to be written again.
            for chapter in chapters:
                if chapter.state == WRITING:
                    chapter.state = WAITING
        voice = film.voice
        return FilmRecord(
            id=film.id,
            course_id=film.course_id,
            status=film.status,
            title=film.title,
            chapters=[
                FilmChapter(
                    title=chapter.title,
                    state=chapter.state,
                    by=chapter.by,
                    problems=chapter.problems,
                    # The opening is the first mark: each chapter's is the one after it.
                    start=marks.get(index + 1),
                )
                for index, chapter in enumerate(chapters)
            ],
            voice=self._narration.voice_name(voice) if isinstance(voice, dict) else None,
            seconds=film.seconds,
            size=film.size,
            notes=[note for note in film.notes or [] if isinstance(note, str)],
            written_by=dict(film.written_by or {}),
            reason=film.reason,
            created_at=film.created_at,
            finished_at=film.finished_at,
            making=making,
        )

    def make(self, course_id: str) -> JobSnapshot:
        """Begin a course's film, or continue one left unfinished."""
        with self._starting:
            running = self._jobs.find_active(KIND_FILM, course_id)
            if running is not None:
                return running
            plan = self.plan(course_id)
            if plan.blocked is not None:
                raise ConflictError(plan.blocked)
            self._gateway.ready_for("film")
            film_id = self._begin(course_id)
            return self._jobs.submit(
                KIND_FILM,
                lambda context: self._make(film_id, context),
                course_id=course_id,
                subject_id=course_id,
                lane=LANE_FILM,
            )

    def _begin(self, course_id: str) -> str:
        with self._database.session() as session:
            course: Course = get_course_or_404(session, course_id)
            film = session.scalars(select(Film).where(Film.course_id == course_id)).first()
            if film is not None and film.status == "ready":
                raise ConflictError("This course has a film. Remove it to make a new one.")
            if film is None:
                film = Film(
                    id=new_id("flm"),
                    course_id=course_id,
                    status="making",
                    title=course.title,
                    chapters=[],
                    marks=[],
                    notes=[],
                    written_by={},
                )
                session.add(film)
            film.status = "making"
            film.reason = None
            session.flush()
            return film.id

    def remove(self, course_id: str) -> None:
        """Remove a course's film: its work stops, and its files go."""
        with self._database.session() as session:
            get_course_or_404(session, course_id)
            film = session.scalars(select(Film).where(Film.course_id == course_id)).first()
            if film is None:
                raise NotFoundError("This course has no film.")
            film_id = film.id
            session.delete(film)
        self._stop(course_id, film_id)
        self._forget(film_id)

    def stop_for_course(self, course_id: str) -> None:
        """A course is about to be removed: its film stops, and its files go once it has."""
        with self._database.read() as session:
            film_id = session.scalars(select(Film.id).where(Film.course_id == course_id)).first()
        if film_id is not None:
            self._stop(course_id, film_id)
            self._forget(film_id)

    def _stop(self, course_id: str, film_id: str) -> None:
        running = self._jobs.find_active(KIND_FILM, course_id)
        if running is not None:
            with contextlib.suppress(NotFoundError):
                self._jobs.cancel(running.id)
        self._stop_recordings(film_id)

    def _stop_recordings(self, film_id: str) -> None:
        while True:
            recording = self._jobs.find_active(KIND_FILM_NARRATION, film_id)
            if recording is None:
                return
            with contextlib.suppress(NotFoundError):
                self._jobs.cancel(recording.id)
            # A recording that is running stops at its next line; a queued one at once.
            if not self._jobs.get(recording.id).finished:
                return

    def _forget(self, film_id: str) -> None:
        shutil.rmtree(self._paths.work / film_id, ignore_errors=True)
        shutil.rmtree(self._paths.films / film_id, ignore_errors=True)

    def settle(self) -> None:
        """As the core starts: a film that was being made when Adle closed is unfinished,
        and a film whose video is gone is no longer offered; folders of films that are no
        longer there go."""
        with self._database.session() as session:
            for film in session.scalars(select(Film)):
                if film.status == "making":
                    film.status = "unfinished"
                    film.reason = "Adle was closed before the film was made. Continue it."
                elif film.status == "ready" and not self._video(film.id).is_file():
                    session.delete(film)
            kept = set(session.scalars(select(Film.id)))
        for folder in (self._paths.work, self._paths.films):
            if not folder.is_dir():
                continue
            for entry in folder.iterdir():
                if entry.is_dir() and not (is_id(entry.name, "flm") and entry.name in kept):
                    shutil.rmtree(entry, ignore_errors=True)

    # -- watching and saving it ----------------------------------------------------------

    def _video(self, film_id: str) -> Path:
        return self._paths.films / film_id / "film.mp4"

    def _ready(self, film_id: str) -> Film:
        if not is_id(film_id, "flm"):
            raise NotFoundError("Film not found.")
        with self._database.read() as session:
            film = session.get(Film, film_id)
            if film is None or film.status != "ready":
                raise NotFoundError("Film not found.")
            session.expunge(film)
            return film

    def video_part(self, film_id: str, part: int) -> VideoPart:
        """One part of a film's video, for the page to put together and play."""
        self._ready(film_id)
        video = self._video(film_id)
        try:
            size = video.stat().st_size
            if size > MAX_VIDEO_BYTES:
                raise NotFoundError("Film not found.")
            parts = max(1, -(-size // PART_BYTES))
            if not 0 <= part < parts:
                raise NotFoundError("There is no such part of the film.")
            with video.open("rb") as handle:
                handle.seek(part * PART_BYTES)
                data = handle.read(PART_BYTES)
        except OSError as error:
            raise NotFoundError("Film not found.") from error
        return VideoPart(data=data, part=part, parts=parts, size=size)

    def captions(self, film_id: str) -> list[tuple[float, float, str]]:
        """What the film says, as when each line is shown."""
        self._ready(film_id)
        try:
            text = (self._paths.films / film_id / "film.srt").read_text(encoding="utf-8")
        except OSError:
            return []
        return script.captions(text)

    def save(self, film_id: str) -> SavedFilm:
        """Write a film, and its subtitles, into the folder of files handed over."""
        film = self._ready(film_id)
        self._handover.mkdir(parents=True, exist_ok=True)
        stem = f"film-{secrets.token_hex(10)}"
        video = self._handover / f"{stem}.mp4"
        try:
            shutil.copyfile(self._video(film_id), video)
        except OSError as error:
            video.unlink(missing_ok=True)
            raise NotFoundError("Film not found.") from error
        captions: str | None = None
        with contextlib.suppress(OSError):
            shutil.copyfile(
                self._paths.films / film_id / "film.srt", self._handover / f"{stem}.srt"
            )
            captions = f"{stem}.srt"
        return SavedFilm(
            file_name=video.name,
            captions_name=captions,
            suggested_name=file_name_for(film.title),
        )

    # -- making it --------------------------------------------------------------------------

    def _make(self, film_id: str, context: JobContext) -> dict[str, Any]:
        try:
            return self._made(film_id, context)
        except (JobCancelledError, FilmEngineStoppedError):
            self._leave(film_id, "Stopped. What was made is kept: continue when you like.")
            self._stop_recordings(film_id)
            raise JobCancelledError(None) from None
        except QuotaExhaustedError as error:
            self._leave(film_id, f"{error.message} What was made is kept: continue then.")
            self._stop_recordings(film_id)
            raise
        except AdleError as error:
            self._leave(film_id, f"{error.message} What was made is kept.")
            self._stop_recordings(film_id)
            raise
        except Exception as error:
            logger.error("film.failed %s", where(error))
            self._leave(film_id, "Something went wrong. What was made is kept: try again.")
            self._stop_recordings(film_id)
            raise
        finally:
            if not self._exists(film_id):
                # Removed while it was made: nothing of it is left behind.
                self._forget(film_id)

    def _exists(self, film_id: str) -> bool:
        with self._database.read() as session:
            return session.get(Film, film_id) is not None

    def _leave(self, film_id: str, reason: str) -> None:
        with self._database.session() as session:
            film = session.get(Film, film_id)
            if film is not None and film.status == "making":
                film.status = "unfinished"
                film.reason = reason

    def _save_chapters(self, film_id: str, chapters: Sequence[_Chapter], **fields: Any) -> None:
        with self._database.session() as session:
            film = session.get(Film, film_id)
            if film is None:
                raise JobCancelledError(None)
            film.chapters = [chapter.stored() for chapter in chapters]
            for name, value in fields.items():
                setattr(film, name, value)

    def _made(self, film_id: str, context: JobContext) -> dict[str, Any]:
        with self._database.read() as session:
            film = session.get(Film, film_id)
            if film is None:
                raise JobCancelledError(None)
            course = get_course_or_404(session, film.course_id)
            course_id, course_title = course.id, course.title
            subject = subject_of(course)
            stored = [chapter for chapter in map(_Chapter.read, film.chapters or []) if chapter]
            voice = film.voice
            earlier_authors = dict(film.written_by or {})
        concepts, blocked = self._concepts(course_id)
        if blocked is not None:
            raise ValidationFailedError(blocked)
        work = self._paths.work / film_id
        kept = work / "kept"
        clips = work / "clips"
        kept.mkdir(parents=True, exist_ok=True)

        # The voice it was begun in, while it can still be recorded; else the one chosen now.
        if voice is not None and not self._narration.film_voice_ready(voice):
            voice = None
        if voice is None:
            voice = self._narration.film_voice()
        previous = {chapter.concept_id: chapter for chapter in stored}
        chapters = []
        for concept in concepts:
            before = previous.get(concept.id)
            if (
                before is not None
                and before.state != WAITING
                and (kept / f"{concept.id}.py").is_file()
            ):
                chapters.append(before)
            else:
                chapters.append(_Chapter(concept_id=concept.id, title=concept.title))
        titles = [concept.title for concept in concepts]
        self._save_chapters(film_id, chapters, voice=voice, title=course_title)

        # The engine's home readied, as a driver update can leave it as if it were new.
        context.report(0, len(chapters) + 2, "Getting the film maker ready")
        self._engine.prime(lambda: context.cancelled)
        (work / f"{script.VOICE_MODULE}.py").write_text(script.voice_source(), encoding="utf-8")
        (work / script.VOICE_INDEX).unlink(missing_ok=True)
        opening = script.plain_chapter(
            course_title,
            script.opening_points(titles),
            opening=f"This film goes through {course_title}, in {_count(len(titles), 'chapter')}.",
        )
        recordings: list[str] = []

        def record(lines: Sequence[str]) -> None:
            if voice is None or not lines:
                return
            try:
                job = self._narration.record_film(
                    film_id, clips, voice, [script.spoken_key(line) for line in lines]
                )
            except AdleError as error:
                logger.info("film.not_recorded kind=%s", type(error).__name__)
                return
            recordings.append(job.id)

        record(opening.lines)
        total = len(chapters) + 2
        results: list[ChatResult] = []
        looks = self._looks()
        for chapter in chapters:
            if chapter.state != WAITING:
                record(chapter.lines or [])
        waiting = [index for index, chapter in enumerate(chapters) if chapter.state == WAITING]
        guard = threading.Lock()
        written_so_far = [len(chapters) - len(waiting)]

        def write(index: int, shared: WorkContext) -> None:
            """One chapter written, checked, and kept; recorded as soon as it is."""
            chapter, concept = chapters[index], concepts[index]
            with guard:
                chapter.state = WRITING
                self._save_chapters(film_id, chapters)
            written: list[ChatResult] = []
            made = self._chapter(
                prompts.FilmChapterBrief(
                    course_title=course_title,
                    subject=subject,
                    chapters=titles,
                    index=index,
                    concept=prompts.ConceptBrief(
                        title=concept.title,
                        summary=concept.summary,
                        objectives=[objective.statement for objective in concept.objectives],
                        prerequisites=[item.title for item in concept.prerequisites],
                    ),
                    passages=self._passages(concept.id),
                ),
                work,
                index,
                shared,
                written,
                total,
                looks=looks,
                done=lambda: written_so_far[0],
            )
            if made is None:
                plain = script.plain_chapter(
                    concept.title,
                    [objective.statement for objective in concept.objectives]
                    or [concept.summary or concept.title],
                )
                state, by, problems, lines = IN_WORDS, "adle", 0, list(plain.lines)
                source = plain.source
            else:
                state, by, problems, lines = WRITTEN, "model", made.problems, made.lines
                source = made.source
            (kept / f"{concept.id}.py").write_text(source, encoding="utf-8")
            with guard:
                results.extend(written)
                chapter.state, chapter.by, chapter.problems = state, by, problems
                chapter.lines = lines
                written_so_far[0] += 1
                self._save_chapters(
                    film_id, chapters, written_by=self._authors(earlier_authors, results)
                )
                record(chapter.lines)

        side_by_side(waiting, write, context, min(CHAPTERS_AT_ONCE, self._gateway.at_once("film")))

        def voiced() -> int:
            """Wait for every line to be recorded, and write down where each one is."""
            context.report(len(chapters), total, "Recording the voice", {"stage": "voicing"})
            self._await(recordings, context, len(chapters), total)
            said = [opening.lines, *[chapter.lines or [] for chapter in chapters]]
            return self._index(work, clips, voice, said)

        missing = voiced()

        def replaced(chapter: _Chapter) -> None:
            nonlocal missing
            self._save_chapters(film_id, chapters)
            record(chapter.lines or [])
            missing = voiced()

        context.report(len(chapters) + 1, total, "Putting the film together", {"stage": "drawing"})
        report = self._whole(work, kept, opening.source, chapters, concepts, context, replaced)
        marks = chapter_starts(
            report, [f"{script.chapter_module(index)}.py" for index in range(len(chapters) + 1)]
        )
        context.report(len(chapters) + 1, total, "Making the video", {"stage": "drawing"})
        out = work / "out.mp4"
        out.unlink(missing_ok=True)
        rendered = self._engine.render(
            work,
            f"{script.FILM_MODULE}.py",
            script.FILM_SCENE,
            out,
            lambda: context.cancelled,
            seconds=seconds_for(report.seconds),
        )
        if rendered.failure is not None or not out.is_file():
            raise FilmEngineError("The film maker couldn’t make the video. Try again.")
        finished = self._paths.films / film_id
        finished.mkdir(parents=True, exist_ok=True)
        shutil.move(str(out), str(finished / "film.mp4"))
        captions = work / "out.srt"
        if captions.is_file():
            shutil.move(str(captions), str(finished / "film.srt"))
        size = (finished / "film.mp4").stat().st_size
        names = [OPENING_TITLE, *titles]
        with self._database.session() as session:
            film = session.get(Film, film_id)
            if film is None:
                raise JobCancelledError(None)
            film.status = "ready"
            film.reason = None
            film.seconds = rendered.seconds or report.seconds
            film.size = size
            film.marks = [
                {
                    "title": names[index],
                    "start": round(marks.get(f"{script.chapter_module(index)}.py", 0.0), 3),
                }
                for index in range(len(names))
            ]
            film.chapters = [chapter.stored() for chapter in chapters]
            film.notes = self._notes(
                chapters, voice, missing, self._authors(earlier_authors, results)
            )
            film.written_by = self._authors(earlier_authors, results)
            film.finished_at = utc_now()
        shutil.rmtree(work, ignore_errors=True)
        context.report(total, total, "Done")
        return {"kind": "film", "film_id": film_id, "chapters": len(chapters)}

    def _passages(self, concept_id: str) -> list[prompts.Passage]:
        stored = self._curriculum.related_passages(concept_id, limit=prompts.MAX_FILM_PASSAGES)
        return [
            prompts.Passage(
                source_name=passage.source_name, locator=_where(passage), text=passage.text
            )
            for passage in stored
        ]

    def _authors(self, earlier: dict[str, Any], results: Sequence[ChatResult]) -> dict[str, Any]:
        """Who wrote the film's chapters: those who wrote them before it was continued, and
        those who wrote them since."""
        now = self._generation.written_by(results) if results else {}
        if not earlier:
            return now
        if not now:
            return earlier
        authors = [*earlier.get("authors", []), *now.get("authors", [])]
        unique = list({json.dumps(item, sort_keys=True): item for item in authors}.values())
        notes = " ".join(note for note in (earlier.get("note"), now.get("note")) if note)
        return {**now, "authors": unique, "note": notes}

    def _ask(
        self, request: Any, context: WorkContext, done: int, total: int, doing: str
    ) -> ChatResult:
        """One request from inside the film's job, its wait said as it goes."""

        def say(message: str, stage: str | None = None) -> None:
            context.report(done, total, message, {"stage": stage} if stage else None)

        say(doing, "waiting")
        try:
            return self._gateway.complete(
                request,
                cancelled=lambda: context.cancelled,
                on_wait=lambda seconds: say(
                    f"Waiting about {max(1, round(seconds))} seconds to stay under the rate limit",
                    "waiting",
                ),
                on_fallback=lambda away, following, _why: say(
                    f"{away} isn’t available right now. Asking {following} instead", "waiting"
                ),
                on_stage=lambda model, reached: say(
                    f"{doing}: {model} is {'thinking' if reached == 'thinking' else 'writing'}",
                    reached,
                ),
                on_busy=lambda provider: say(
                    f"Waiting for {provider} to finish another request", "waiting"
                ),
            )
        except RequestCancelledError as error:
            raise JobCancelledError(None) from error

    def _chapter(
        self,
        brief: prompts.FilmChapterBrief,
        work: Path,
        index: int,
        context: WorkContext,
        results: list[ChatResult],
        total: int,
        *,
        looks: bool = False,
        done: Callable[[], int] | None = None,
    ) -> _Best | None:
        """A chapter written by a model, checked, run, and mended until nothing is wrong
        with it, or ``MAX_MENDS`` times: the version that ran with the least wrong, or
        nothing when no version ran.

        With ``looks``, its pictures are looked over once (ADR-066): the first version that
        runs clean while a mend is left, or else the version before the last mend if it ran,
        so that what is seen can still be acted on. What is seen is told to the writer with
        what the engine found, and a version written after the look is kept over one looked
        at unless the engine finds more wrong with it."""
        position = index + 1  # the opening is the film's first chapter
        # How many chapters are written, for the job's progress: several may be under way.
        so_far: Callable[[], int] = done if done is not None else (lambda: index)
        module = script.chapter_module(position)
        take = script.take_module(position)
        number, count = index + 1, len(brief.chapters)
        previous: str | None = None
        problems: list[str] = []
        best: _Best | None = None
        # Whether the one look has been had; whether the problems told next include what it
        # saw; and whether the version being judged was written after it.
        looked = telling_pictures = after_look = False
        for attempt in range(1 + script.MAX_MENDS):
            context.check_cancelled()
            doing = (
                f"Writing chapter {number} of {count}"
                if attempt == 0
                else f"Mending chapter {number} of {count}"
            )
            result = self._ask(
                prompts.film_chapter_request(
                    brief, previous=previous, problems=problems, looked_over=telling_pictures
                ),
                context,
                so_far(),
                total,
                doing,
            )
            results.append(result)
            after_look = after_look or telling_pictures
            telling_pictures = False
            # Slips mended, not sent back: an engine name used bare (`WHITE` for `m.WHITE`)
            # or numpy not imported, a line given a run time of its own, and a line with
            # more bracketed spans than animations.
            source = with_spans_fitted(
                with_timing_passed_on(with_engine_names(script.written_file(result.text)))
            )
            checked = check_chapter_source(source)
            previous = source
            if not checked.ok:
                problems = [
                    f"line {violation.line}: {violation.message}"
                    if violation.line
                    else violation.message
                    for violation in checked.violations[:10]
                ]
                logger.info("film.chapter_refused attempt=%s", attempt)
                continue
            with self._engine_turn:
                (work / f"{module}.py").write_text(source, encoding="utf-8")
                (work / f"{take}.py").write_text(script.take_source(position), encoding="utf-8")
                context.report(
                    so_far(), total, f"Checking chapter {number} of {count}", {"stage": "drawing"}
                )
                report = self._looked_at(work, take, context)
                # Read while it is this chapter's: the next run draws over it.
                sheets = (
                    storyboard.sheets(work, script.TAKE_SCENE)
                    if looks and not looked and report is not None
                    else []
                )
            if report is None:
                problems = [
                    "It ran for longer than five minutes without ending: something in it "
                    "never stops, or takes far too long."
                ]
                continue
            found = findings(report, f"{module}.py")
            lines = list(checked.lines)
            short = len(lines) < script.MIN_LINES
            if short:
                found.append(
                    f"The chapter says {len(lines)} lines. A chapter says 16 to 28: teach "
                    "every objective, each with an example."
                )
            logger.info(
                "film.chapter_checked attempt=%s ran=%s problems=%s",
                attempt,
                report.ran,
                len(report.problems),
            )
            if report.ran:
                score = len(report.problems) + (_SHORT if short else 0)
                if best is None or score < best.score or (after_look and score <= best.score):
                    best = _Best(score, source, lines, len(report.problems))
                last_chance = attempt == script.MAX_MENDS - 1
                if (
                    looks
                    and not looked
                    and attempt < script.MAX_MENDS
                    and (score == 0 or last_chance)
                ):
                    looked = True
                    seen = self._look_over(
                        brief.concept.title,
                        sheets,
                        module,
                        source,
                        report,
                        context,
                        results,
                        so_far(),
                        total,
                        f"Checking the pictures of chapter {number} of {count}",
                    )
                    if seen:
                        problems = _together(found, seen)
                        telling_pictures = True
                        continue
                if score == 0:
                    break
            problems = found or [_stopped(report)]
        return best

    def _look_over(
        self,
        title: str,
        sheets: Sequence[bytes],
        module: str,
        source: str,
        report: Report,
        context: WorkContext,
        results: list[ChatResult],
        done: int,
        total: int,
        doing: str,
    ) -> list[str]:
        """What a model that sees pictures sees wrong in the storyboard the engine drew of a
        chapter (ADR-066), a sentence each for its writer. Nothing waits on it: with no
        sheets, or a look that is refused or fails, nothing is seen."""
        if not sheets:
            return []
        chapter = f"{module}.py"
        told = storyboard.told(report, source, chapter)
        request = prompts.storyboard_request(
            prompts.StoryboardBrief(
                chapter_title=title,
                told=[(item.index, item.said) for item in told],
                sheets=sheets,
            )
        )
        try:
            result = self._ask(request, context, done, total, doing)
        except JobCancelledError:
            raise
        except AdleError as error:
            logger.info("film.chapter_not_looked_over %s", where(error))
            return []
        results.append(result)
        seen = storyboard.seen(result.text, report, chapter)
        logger.info("film.chapter_looked_over sheets=%s seen=%s", len(sheets), len(seen))
        return seen

    def _looked_at(self, work: Path, take: str, context: WorkContext) -> Report | None:
        """A chapter run alone by the engine, or nothing when it ran out of time twice. The
        first run on a computer can spend its time compiling the graphics driver's shaders,
        which the next finds kept (``FilmPaths.home``): a chapter is not blamed for that."""
        for _ in range(2):
            context.check_cancelled()
            try:
                return self._engine.inspect(
                    work,
                    f"{take}.py",
                    script.TAKE_SCENE,
                    lambda: context.cancelled,
                    seconds=self._inspect_seconds,
                )
            except FilmEngineTimeoutError:
                logger.info("film.chapter_out_of_time")
        return None

    def _await(self, recordings: Sequence[str], context: JobContext, done: int, total: int) -> None:
        """Wait for the film's lines to be recorded."""
        waiting = list(recordings)
        while waiting:
            context.check_cancelled()
            still = []
            for job_id in waiting:
                try:
                    if not self._jobs.get(job_id).finished:
                        still.append(job_id)
                except NotFoundError:
                    continue
            waiting = still
            if waiting:
                context.report(done, total, "Recording the voice", {"stage": "voicing"})
                time.sleep(0.25)

    def _index(
        self,
        work: Path,
        clips: Path,
        voice: dict[str, Any] | None,
        said: Sequence[Sequence[str]],
    ) -> int:
        """Write down, for the film's voice, the clip of each line and when each of its
        words is said; and how many lines have none."""
        if voice is None:
            return 0
        index: dict[str, Any] = {}
        missing = 0
        for lines in said:
            for line in lines:
                key = script.spoken_key(line)
                if key in index:
                    continue
                found = self._narration.film_line(clips, voice, key)
                if found is None:
                    missing += 1
                    continue
                clip, seconds, words = found
                index[key] = {
                    "clip": f"clips/{clip}",
                    "words": [list(word) for word in script.engine_words(key, words, seconds)],
                }
        (work / script.VOICE_INDEX).write_text(json.dumps(index), encoding="utf-8")
        return missing

    def _whole(
        self,
        work: Path,
        kept: Path,
        opening: str,
        chapters: list[_Chapter],
        concepts: Sequence[ConceptRecord],
        context: JobContext,
        replaced: Callable[[_Chapter], None],
    ) -> Report:
        """The film put together and looked at whole. A chapter that ran alone and stops
        here is told in words instead (``replaced`` records what it says), and the film is
        looked at again."""
        for _ in range(len(chapters) + 1):
            context.check_cancelled()
            for stale in [*work.glob("chapter_*.py"), *work.glob("take_*.py")]:
                stale.unlink(missing_ok=True)
            # The engine keeps what a voice said beside the scene, named by the words and by
            # the voice's code, which does not change when a line's recording arrives: what
            # was said while a chapter was looked at alone, before it was recorded, would
            # be said again in the film. It is said afresh, from the recordings.
            shutil.rmtree(work / ENGINE_SPEECH, ignore_errors=True)
            (work / f"{script.chapter_module(0)}.py").write_text(opening, encoding="utf-8")
            for index, concept in enumerate(concepts):
                source = (kept / f"{concept.id}.py").read_text(encoding="utf-8")
                (work / f"{script.chapter_module(index + 1)}.py").write_text(
                    source, encoding="utf-8"
                )
            (work / f"{script.FILM_MODULE}.py").write_text(
                script.film_source([OPENING_TITLE, *[chapter.title for chapter in chapters]]),
                encoding="utf-8",
            )
            lines = sum(len(chapter.lines or []) for chapter in chapters)
            report = self._engine.inspect(
                work,
                f"{script.FILM_MODULE}.py",
                script.FILM_SCENE,
                lambda: context.cancelled,
                seconds=seconds_for(lines * _SECONDS_A_LINE),
            )
            if report.ran:
                return report
            failure = report.failure
            failed = re.fullmatch(r"chapter_(\d\d)\.py", failure.file or "") if failure else None
            position = int(failed.group(1)) - 1 if failed else 0
            if position < 1 or position > len(chapters):
                raise FilmEngineError("The film couldn’t be put together. Try again.")
            chapter, concept = chapters[position - 1], concepts[position - 1]
            plain = script.plain_chapter(
                concept.title,
                [objective.statement for objective in concept.objectives]
                or [concept.summary or concept.title],
            )
            (kept / f"{concept.id}.py").write_text(plain.source, encoding="utf-8")
            chapter.state, chapter.by, chapter.problems = IN_WORDS, "adle", 0
            chapter.lines = list(plain.lines)
            logger.info("film.chapter_in_words_when_joined position=%s", position)
            replaced(chapter)
        raise FilmEngineError("The film couldn’t be put together. Try again.")

    def _notes(
        self,
        chapters: Sequence[_Chapter],
        voice: dict[str, Any] | None,
        missing: int,
        authors: dict[str, Any],
    ) -> list[str]:
        notes: list[str] = []
        in_words = sum(1 for chapter in chapters if chapter.state == IN_WORDS)
        if in_words:
            notes.append(
                f"{_count(in_words, 'chapter')} {'is' if in_words == 1 else 'are'} told in "
                "words: no version the AI wrote would run."
            )
        untidy = sum(1 for chapter in chapters if chapter.state == WRITTEN and chapter.problems)
        if untidy:
            notes.append(
                f"In {_count(untidy, 'chapter')}, some words may lie over others for a moment."
            )
        if voice is None:
            notes.append(
                "It has no voice: no natural voice reads lessons here. Its words show as it plays."
            )
        elif missing:
            verb = "is" if missing == 1 else "are"
            notes.append(f"{_count(missing, 'line')} could not be recorded, and {verb} quiet.")
        if authors.get("note"):
            notes.append(str(authors["note"]))
        return notes


def _count(number: int, noun: str) -> str:
    """A number of things as it is said: "one chapter", "3 chapters"."""
    return f"one {noun}" if number == 1 else f"{number} {noun}s"


def _together(found: Sequence[str], seen: Sequence[str]) -> list[str]:
    """What the engine found and what was seen in the pictures, told in one mend: the
    engine's first, as what it finds is sure, but never so much of it that what was seen is
    crowded out of what a mend is told."""
    room = prompts.MAX_PROBLEMS_IN_RETRY
    told_seen = min(len(seen), max(room - len(found), room // 2))
    return [*found[: room - told_seen], *seen[:told_seen]]


def _stopped(report: Report) -> str:
    if report.failure is not None:
        return f"The scene stopped. {report.failure.text}"
    return "The scene stopped without saying why. Write it more simply."
