"""A lesson's narration in a natural voice, recorded on this computer (ADR-042, ADR-051).

When the natural voice is set up and chosen, each line a lesson says is recorded once, as a
clip with the time of each of its words, and kept beside the data. The lesson then plays the
clips and marks each word as it is said.

A lesson is made with its voice (ADR-051). Its models are loaded as soon as a lesson is
asked for, while its first words are written; it is recorded part by part as its parts are
written, by one recording that follows it until it is whole, on one engine that stays
loaded; and it can be started once its first part can be heard. Loading a model takes far
longer than saying a line with it, so nothing is loaded twice for one lesson.

A clip is named by the voice and the words it says, so that a lesson whose words or voice
change is recorded again and nothing is spoken in a voice that was not chosen. Every voice's
clips are kept: a voice chosen again plays what it recorded (ADR-057). The clips of a lesson
go when the lesson goes, and a voice's when the voice is removed.

When the voice changes, the lessons the learner opened last and has not finished are
recorded in the new one at once, before they are opened; a recording under way goes on in
the voice chosen now, from its next line (ADR-057).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adle_core.application.jobs import (
    LANE_VOICE,
    JobCancelledError,
    JobContext,
    JobRunner,
    JobSnapshot,
)
from adle_core.application.lessons import LessonService
from adle_core.errors import AdleError, ConflictError, NotFoundError, ValidationFailedError
from adle_core.infrastructure.ids import is_id
from adle_core.lessons.ir import is_plain_text
from adle_core.voice.catalog import (
    DEFAULT_DESIGN,
    MAX_DESIGN_CHARACTERS,
    REFERENCE_TEXT,
    RETIRED,
    SAMPLE_TEXT,
    TIERS,
    Family,
    Tier,
)
from adle_core.voice.catalog import tier as find_tier
from adle_core.voice.hardware import Fit, Hardware, detect, fit
from adle_core.voice.install import VoiceInstaller, VoiceSetupError
from adle_core.voice.runtime import (
    VoiceEngine,
    VoiceEngineError,
    VoicePaths,
    VoiceUnavailableError,
)
from adle_core.voice.timing import (
    LESSON_SPEECH,
    VoiceTiming,
    kept,
    kept_ahead,
    mean,
    read_timing,
    speech_of,
)
from adle_core.voice.timing import ready_after as timed_ready_after

logger = logging.getLogger(__name__)

KIND_NARRATION = "narration_recording"
#: Setting a size of voice up: its programs, its models, a word said to check it.
KIND_VOICE_SETUP = "voice_setup"
#: Loading a voice's models while a lesson's first words are written (ADR-051).
KIND_VOICE_WARMUP = "voice_warmup"
#: A short sample of a voice, for the learner to hear before choosing it (ADR-057).
KIND_VOICE_SAMPLE = "voice_sample"
#: How many of the lessons the learner opened last, and has not finished, are recorded in a
#: new voice as soon as it is chosen, the latest first (ADR-057).
RECORD_AHEAD_LESSONS = 2
_CLIP = re.compile(r"^[0-9a-f]{24}$")

#: How long the voice's engine stays loaded after its last line, for the next lesson.
ENGINE_IDLE_SECONDS = 180.0
#: How long a recording waits for the next part of a lesson that is still being written.
FOLLOW_QUIET_SECONDS = 600.0
#: How long after a lesson is asked for it can usually be heard, until this computer has
#: timed its voice: measured on the development machine (PERFORMANCE.md, 2026-11-23; the
#: Expressive voice's again on 2026-11-24, now designed saying a passage first, ADR-057).
READY_GUESS_SECONDS: dict[str, float] = {"kokoro": 30.0, "expressive": 65.0}
#: The lines an engine says while it is still loading what it speaks with, which are not
#: counted in how fast it is: the Expressive voice designs a lesson's voice with one model
#: and speaks with another, loaded at its second line.
_LOADING_LINES = {"expressive": 2}
#: A warm-up this old is not what a recording that begins now was asked with.
_WARMUP_COUNTS_FOR = 600.0


@dataclass(frozen=True, slots=True)
class VoiceStatus:
    #: The sizes of voice that are here, whole.
    ready: list[str]
    #: The one lessons are read in, when there is one: the one chosen, or else the richest.
    tier: str | None
    enabled: bool
    #: The voice chosen for each size that has voices to choose from.
    speakers: dict[str, str]
    #: A voice a developer pointed Adle at: used as it is, never removed.
    borrowed: bool
    #: Who reads the lessons in the Expressive voice, as the learner described them (ADR-057).
    design: str = DEFAULT_DESIGN


@dataclass(frozen=True, slots=True)
class VoiceRecording:
    """A lesson being recorded in the voice chosen now."""

    lesson_id: str
    title: str
    done: int
    total: int


@dataclass(frozen=True, slots=True)
class NarrationClip:
    #: The words it says, exactly as the lesson says them.
    text: str
    clip: str
    seconds: float
    words: list[dict[str, float | int]]


class _Engines:
    """The engine of the voice in use, kept loaded between recordings for a while (ADR-051):
    loading a model takes far longer than saying a line with it. One engine at a time, used
    by one recording at a time (the voice lane runs one job at a time); closed when it has
    been idle for a while, when a voice is set up or removed, and when the core stops."""

    def __init__(
        self,
        paths: VoicePaths,
        make: Callable[[VoicePaths, Family], VoiceEngine],
        idle_seconds: float = ENGINE_IDLE_SECONDS,
    ) -> None:
        self._paths = paths
        self._make = make
        self._idle = idle_seconds
        self._lock = threading.Lock()
        self._engine: VoiceEngine | None = None
        self._family: Family | None = None
        self._timer: threading.Timer | None = None
        self._busy = 0
        #: The lines said by the engine there is now, since it was made.
        self.lines = 0

    def take(self, family: Family) -> VoiceEngine:
        stale: VoiceEngine | None = None
        with self._lock:
            self._stop_timer()
            if self._engine is not None and self._family != family:
                stale, self._engine = self._engine, None
            if self._engine is None:
                self._engine, self._family = self._make(self._paths, family), family
                self.lines = 0
            self._busy += 1
            engine = self._engine
        if stale is not None:
            stale.close()
        return engine

    def give_back(self) -> None:
        with self._lock:
            self._busy = max(0, self._busy - 1)
            if self._busy == 0 and self._engine is not None:
                self._timer = threading.Timer(self._idle, self._close_idle)
                self._timer.daemon = True
                self._timer.start()

    def _close_idle(self) -> None:
        with self._lock:
            if self._busy:
                return
            engine, self._engine, self._family = self._engine, None, None
        if engine is not None:
            engine.close()

    def close(self) -> None:
        with self._lock:
            self._stop_timer()
            engine, self._engine, self._family = self._engine, None, None
        if engine is not None:
            engine.close()

    def _stop_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None


class NarrationService:
    def __init__(
        self,
        lessons: LessonService,
        jobs: JobRunner,
        paths: VoicePaths,
        hardware: Callable[[], Hardware] = detect,
        installer: Callable[[VoicePaths], VoiceInstaller] = VoiceInstaller,
        engine: Callable[[VoicePaths, Family], VoiceEngine] = VoiceEngine,
        idle_seconds: float = ENGINE_IDLE_SECONDS,
    ) -> None:
        self._lessons = lessons
        self._jobs = jobs
        self._paths = paths
        self._installer = installer
        self._preferences = paths.root / "preferences.json"
        self._timing = paths.root / "timing.json"
        self._detect = hardware
        self._hardware: Hardware | None = None
        self._engines = _Engines(paths, engine, idle_seconds)
        #: Woken when a lesson that is being recorded has another part to record.
        self._more: dict[str, threading.Event] = {}
        #: Lessons with a recording asked for and not yet ended, queued or under way.
        self._recording: set[str] = set()
        self._more_lock = threading.Lock()
        #: When the last warm-up began: a lesson was asked for then (``ready_after``).
        self._warmed_at: float | None = None
        #: Lessons recorded ahead of their being opened, in a voice just chosen (ADR-057):
        #: they step aside for what the learner opens or waits for.
        self._ahead: set[str] = set()
        #: Told the id of a lesson when another of its parts can be heard.
        self.on_voiced: Callable[[str], None] | None = None
        self._retire()

    def _retire(self) -> None:
        """A voice no longer offered (ADR-057) is taken off this computer, with what it
        recorded, as the core starts: what a voice still offered here needs is kept."""
        if self._paths.borrowed:
            return
        for retired in RETIRED:
            if not any((self._paths.models / repo.folder).exists() for repo in retired.repos):
                continue
            try:
                self._installer(self._paths).remove(retired, self._paths.ready_tiers())
                self._forget_recordings(retired.id)
            except (OSError, VoiceSetupError) as error:
                logger.info("narration.not_retired kind=%s", type(error).__name__)
            else:
                logger.info("narration.retired tier=%s", retired.id)

    def hardware(self) -> Hardware:
        """What this computer has, found once: it does not change while Adle runs."""
        if self._hardware is None:
            self._hardware = self._detect()
        return self._hardware

    def fits(self) -> dict[str, Fit]:
        """Which sizes of voice run on this computer, and why not where one does not."""
        found = self.hardware()
        return {tier.id: fit(tier, found) for tier in TIERS}

    def recommended(self) -> str | None:
        """The richest size of voice this computer runs, which is the one to offer first."""
        fitting = [tier.id for tier in TIERS if fit(tier, self.hardware()).fits]
        return fitting[-1] if fitting else None

    # -- what is set up, and what was chosen -------------------------------------------------

    def _chosen(self) -> dict[str, Any]:
        try:
            raw = json.loads(self._preferences.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def status(self) -> VoiceStatus:
        ready: list[str] = [tier.id for tier in self._paths.ready_tiers()]
        chosen = self._chosen()
        wanted = chosen.get("tier")
        # The sizes are listed from the lightest to the richest: the richest one here reads
        # the lessons, unless the learner chose another.
        tier = wanted if wanted in ready else (ready[-1] if ready else None)
        stored = chosen.get("speakers")
        picked = stored if isinstance(stored, dict) else {}
        speakers: dict[str, str] = {}
        for each in TIERS:
            if each.default_speaker is None:
                continue
            value = picked.get(each.id)
            known = {speaker.id for speaker in each.speakers}
            speakers[each.id] = value if value in known else each.default_speaker
        design = chosen.get("design")
        return VoiceStatus(
            ready=ready,
            tier=tier,
            enabled=tier is not None and chosen.get("enabled", True) is not False,
            speakers=speakers,
            borrowed=self._paths.borrowed,
            design=design if isinstance(design, str) and design.strip() else DEFAULT_DESIGN,
        )

    def choose(
        self,
        *,
        enabled: bool | None = None,
        tier: str | None = None,
        speaker: str | None = None,
        design: str | None = None,
    ) -> VoiceStatus:
        """Turn the natural voice on or off, choose a size of it, a voice of a size, or say
        who reads in the Expressive voice (an empty description is Adle's own again). A
        voice that changes is recorded at once in what the learner is likely to open next."""
        before = self._identity()
        chosen = self._chosen()
        if design is not None:
            described = _described(design)
            if described:
                chosen["design"] = described
            else:
                chosen.pop("design", None)
        if enabled is not None:
            chosen["enabled"] = enabled
        if tier is not None:
            if find_tier(tier) is None:
                raise NotFoundError("There is no such voice.")
            chosen["tier"] = tier
        if speaker is not None:
            which = find_tier(tier) if tier is not None else find_tier(self.status().tier or "")
            if which is None or speaker not in {item.id for item in which.speakers}:
                raise NotFoundError("There is no such voice.")
            stored = chosen.get("speakers")
            speakers = dict(stored) if isinstance(stored, dict) else {}
            speakers[which.id] = speaker
            chosen["speakers"] = speakers
        self._paths.root.mkdir(parents=True, exist_ok=True)
        self._preferences.write_text(json.dumps(chosen), encoding="utf-8")
        if self._identity() != before:
            self._record_recent()
        return self.status()

    def _identity(self) -> tuple[Any, ...]:
        """What makes the voice lessons are read in sound as it does: a change to any of it
        is a new voice."""
        status = self.status()
        if not status.enabled or status.tier is None:
            return (False,)
        design = status.design if status.tier == "expressive" else None
        return (True, status.tier, status.speakers.get(status.tier), design)

    def _record_recent(self) -> None:
        """The lessons the learner opened last and has not finished, recorded now in the
        voice chosen, before they are opened (ADR-057). Nothing with no voice chosen."""
        try:
            if not self.status().enabled:
                return
            for lesson_id in self._lessons.unfinished(RECORD_AHEAD_LESSONS):
                self.start(lesson_id, ahead=True)
        except (AdleError, OSError) as error:
            logger.info("narration.not_recorded_ahead kind=%s", type(error).__name__)

    def _step_aside(self, keep: str | None = None) -> None:
        """Lessons recorded ahead of time stop for what the learner is waiting for: the voice
        works on one thing at a time. A lesson's clips so far are kept."""
        with self._more_lock:
            ahead = [lesson_id for lesson_id in self._ahead if lesson_id != keep]
            self._ahead.difference_update(ahead)
        for lesson_id in ahead:
            running = self._jobs.find_active(KIND_NARRATION, lesson_id)
            if running is not None:
                self._jobs.cancel(running.id)

    # -- setting a voice up, and taking it away ---------------------------------------------

    def setting_up(self) -> JobSnapshot | None:
        """The setup under way, if there is one: there is only ever one at a time."""
        running = self._jobs.list_all_active([KIND_VOICE_SETUP])
        return running[0] if running else None

    def install(self, tier_id: str) -> JobSnapshot:
        """Set a size of voice up, in the background, at the learner's word."""
        tier = find_tier(tier_id)
        if tier is None:
            raise NotFoundError("There is no such voice.")
        if self._paths.borrowed:
            raise ConflictError("The voice here was set up by hand, and is used as it is.")
        fits = fit(tier, self.hardware())
        if not fits.fits:
            raise ConflictError(fits.why)
        running = self.setting_up()
        if running is not None:
            if running.subject_id == tier.id:
                return running
            raise ConflictError("Another voice is being set up. Wait for it, or stop it.")
        return self._jobs.submit(
            KIND_VOICE_SETUP,
            lambda context: self._install(tier, context),
            subject_id=tier.id,
            lane=LANE_VOICE,
        )

    def _install(self, tier: Tier, context: JobContext) -> dict[str, Any]:
        # An engine kept loaded runs from the programs about to be replaced.
        self._engines.close()
        try:
            timed = self._installer(self._paths).install(
                tier,
                report=lambda message, done, total: context.report(done, total, message),
                cancelled=lambda: context.cancelled,
            )
        except VoiceSetupError:
            # Stopped by the learner is a stop, not a failure.
            context.check_cancelled()
            raise
        # How fast it is here, said at setup as much as a lesson's first part (ADR-052).
        if timed is not None:
            before = self._timing_of(tier.id)
            self._keep_timing(tier.id, VoiceTiming(ready=before.ready, **timed))
        # The size just set up is the one that reads the lessons from now on.
        self.choose(tier=tier.id, enabled=True)
        context.report(1, 1, "Done")
        return {"kind": "voice_setup", "tier": tier.id}

    def remove(self, tier_id: str) -> VoiceStatus:
        """Take a size of voice off this computer, with what it recorded and what no other
        size here needs."""
        tier = find_tier(tier_id)
        if tier is None:
            raise NotFoundError("There is no such voice.")
        if self._paths.borrowed:
            raise ConflictError("The voice here was set up by hand, and is used as it is.")
        if self._jobs.any_active([KIND_VOICE_SETUP, KIND_NARRATION, KIND_VOICE_WARMUP]):
            raise ConflictError("The voice is busy. Wait for it to finish, then try again.")
        self._engines.close()
        keep = [other for other in self._paths.ready_tiers() if other.id != tier.id]
        self._installer(self._paths).remove(tier, keep)
        self._forget_recordings(tier.id)
        shutil.rmtree(self._samples(tier.id), ignore_errors=True)
        return self.status()

    def _forget_recordings(self, tier_id: str) -> None:
        if not self._paths.clips.is_dir():
            return
        for timing in self._paths.clips.glob("*/*.json"):
            try:
                said = json.loads(timing.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                said = None
            if isinstance(said, dict) and said.get("tier") not in (None, tier_id):
                continue
            timing.with_suffix(".clip").unlink(missing_ok=True)
            timing.unlink(missing_ok=True)

    # -- recording ---------------------------------------------------------------------------

    def _voice(self, lesson_id: str) -> tuple[Tier, dict[str, Any]]:
        """The voice lessons are read in now, and how the engine is asked for it."""
        status = self.status()
        tier = find_tier(status.tier or "")
        if not status.enabled or tier is None:
            raise VoiceUnavailableError()
        if tier.id == "expressive":
            # The learner's voice, delivered as the lesson says it is delivered, written with
            # it (ADR-057). A lesson that says nothing (the sample course's) is delivered
            # as the voice is.
            folder = self._folder(lesson_id)
            delivery = self._lessons.get_lesson(lesson_id).voice
            design = f"{status.design} Its delivery here: {delivery}" if delivery else status.design
            return tier, self._designed(design, folder)
        return tier, {"tier": tier.id, "speaker": status.speakers[tier.id]}

    @staticmethod
    def _designed(design: str, folder: Path) -> dict[str, Any]:
        """The Expressive voice of a description: designed once, saying a passage made for
        it, kept in ``folder``, and every line spoken as a copy of it."""
        reference = folder / f"voice-{_digest(design + chr(10) + REFERENCE_TEXT)}.wav"
        return {
            "tier": "expressive",
            "design": design,
            "reference": str(reference),
            "reference_text": REFERENCE_TEXT,
        }

    def _folder(self, lesson_id: str) -> Any:
        if not is_id(lesson_id, "les"):
            raise NotFoundError("Lesson not found.")
        return self._paths.clips / lesson_id

    @staticmethod
    def _name(voice: dict[str, Any], text: str) -> str:
        # The reference recording is the lesson's own; the voice is what it was made from.
        identity = {key: value for key, value in voice.items() if key != "reference"}
        return _digest(json.dumps(identity, sort_keys=True) + "\n" + text)

    def _lines(self, lesson_id: str) -> list[str]:
        lesson = self._lessons.get_lesson(lesson_id)
        lines: list[str] = []
        for segment in lesson.segments:
            for beat in getattr(segment, "narration", None) or []:
                if beat.text not in lines:
                    lines.append(beat.text)
        return lines

    def warm(self) -> None:
        """A lesson was just asked for: load the voice's models now, while its first words
        are written, so that its first part can be recorded as soon as it is stored. With
        no voice chosen, or one already at work, nothing is done."""
        try:
            status = self.status()
            tier = find_tier(status.tier or "")
            if not status.enabled or tier is None:
                return
            self._warmed_at = time.monotonic()
            if self._jobs.any_active([KIND_VOICE_SETUP, KIND_NARRATION, KIND_VOICE_WARMUP]):
                return
            voice: dict[str, Any] = {"tier": tier.id}
            if tier.id in status.speakers:
                voice["speaker"] = status.speakers[tier.id]
            self._jobs.submit(
                KIND_VOICE_WARMUP,
                lambda context: self._warm(tier, voice),
                subject_id=tier.id,
                lane=LANE_VOICE,
            )
        except (AdleError, OSError) as error:
            logger.info("narration.not_warmed kind=%s", type(error).__name__)

    def _warm(self, tier: Tier, voice: dict[str, Any]) -> dict[str, Any]:
        engine = self._engines.take(tier.family)
        try:
            engine.request({"op": "load", "voice": voice})
        finally:
            self._engines.give_back()
        return {"kind": "voice_warmup", "tier": tier.id}

    def record_ahead(self, lesson_id: str) -> None:
        """Record a lesson as soon as its first words are stored, when a natural voice reads
        the lessons, and each part after as it is stored (ADR-051). A picture that arrives
        later changes nothing that is said. With no voice chosen, nothing is done."""
        try:
            if self.status().enabled:
                self.start(lesson_id)
        except (VoiceUnavailableError, NotFoundError, ConflictError, OSError) as error:
            logger.info("narration.not_recorded_ahead kind=%s", type(error).__name__)

    def start(self, lesson_id: str, *, ahead: bool = False) -> JobSnapshot:
        """Record what a lesson says, in the background. A recording under way is returned,
        and told that there may be more to record. ``ahead``: recorded before the learner
        opens it, in a voice just chosen; otherwise lessons recorded ahead step aside."""
        self._voice(lesson_id)
        self._lessons.get_lesson(lesson_id)
        if not ahead:
            self._step_aside(keep=lesson_id)
        with self._more_lock:
            if ahead:
                self._ahead.add(lesson_id)
            else:
                self._ahead.discard(lesson_id)
            running = self._jobs.find_active(KIND_NARRATION, lesson_id)
            if running is not None:
                self._more.setdefault(lesson_id, threading.Event()).set()
                return running
            self._more[lesson_id] = threading.Event()
            self._recording.add(lesson_id)
            return self._jobs.submit(
                KIND_NARRATION,
                lambda context: self._record(lesson_id, context),
                subject_id=lesson_id,
                lane=LANE_VOICE,
            )

    def _record(self, lesson_id: str, context: JobContext) -> dict[str, Any]:
        """Record every line the lesson has, in the order it says them; while it is still
        being written, wait for its next part and record that too. One engine, loaded once,
        for the whole of it."""
        # The voice is read after what makes it the voice, so that a change between the two
        # is seen at the first line (ADR-057).
        identity = self._identity()
        try:
            tier, voice = self._voice(lesson_id)
        except VoiceUnavailableError:
            identity = (False,)
        folder = self._folder(lesson_id)
        with self._more_lock:
            more = self._more.setdefault(lesson_id, threading.Event())
        if not identity[0]:
            # The natural voice was turned off before this began: nothing is recorded.
            with self._more_lock:
                if self._more.get(lesson_id) is more:
                    del self._more[lesson_id]
                self._recording.discard(lesson_id)
                self._ahead.discard(lesson_id)
            self._tell_voiced(lesson_id)
            return {"kind": "narration", "lesson_id": lesson_id, "lines": 0, "recorded": 0}
        folder.mkdir(parents=True, exist_ok=True)
        engine = self._engines.take(tier.family)
        family = tier.family
        turned_off = False
        recorded = 0
        lines: list[str] = []
        quiet_since = time.monotonic()
        try:
            heard = self.voiced_parts(lesson_id)
            ready = not self.voice_pending(lesson_id)
            while True:
                context.check_cancelled()
                more.clear()
                lines = self._lines(lesson_id)
                said = 0
                for text in lines:
                    chosen = self._identity()
                    if chosen != identity:
                        # Another voice was chosen: what is left is said in it (ADR-057).
                        if not chosen[0]:
                            turned_off = True
                            break
                        identity = chosen
                        tier, voice = self._voice(lesson_id)
                        if tier.family != family:
                            self._engines.give_back()
                            engine = self._engines.take(tier.family)
                            family = tier.family
                    name = self._name(voice, text)
                    clip, timing = folder / f"{name}.clip", folder / f"{name}.json"
                    if clip.is_file() and timing.is_file():
                        continue
                    context.check_cancelled()
                    done = self._recorded_count(folder, voice, lines)
                    context.report(done, len(lines), "Recording the voice")
                    began = time.monotonic()
                    spoken = engine.speak(text, voice, clip, cancelled=lambda: context.cancelled)
                    took = time.monotonic() - began
                    timing.write_text(
                        json.dumps(
                            {"seconds": spoken.seconds, "words": spoken.words, "tier": tier.id}
                        ),
                        encoding="utf-8",
                    )
                    recorded += 1
                    said += 1
                    self._engines.lines += 1
                    if self._engines.lines > _LOADING_LINES.get(tier.id, 1):
                        # How fast it is here, once loaded, line by line (ADR-052).
                        self._timed_line(tier.id, took, spoken.seconds)
                    now = self.voiced_parts(lesson_id)
                    became_ready = not ready and not self.voice_pending(lesson_id)
                    if became_ready:
                        ready = True
                        self._timed_ready(tier.id)
                    if now != heard or became_ready:
                        heard = now
                        self._tell_voiced(lesson_id)
                if turned_off:
                    break
                if said:
                    # Parts may have come while these were said: the lesson is read again.
                    quiet_since = time.monotonic()
                    continue
                if not self._lessons.is_writing(lesson_id):
                    break
                if time.monotonic() - quiet_since > FOLLOW_QUIET_SECONDS:
                    break
                more.wait(timeout=1.0)
        except NotFoundError:
            # The lesson was removed while it was recorded: there is nothing left to record.
            raise JobCancelledError(None) from None
        except (VoiceEngineError, OSError):
            # Stopped in the middle of a line (the lesson removed, its folder gone with it)
            # is a stop, not a failure: the engine is ended to stop the line, and whichever
            # of the two is noticed first, it ends the same way.
            if context.cancelled or not self._lessons.exists(lesson_id):
                raise JobCancelledError(None) from None
            raise
        finally:
            self._engines.give_back()
            with self._more_lock:
                if self._more.get(lesson_id) is more:
                    del self._more[lesson_id]
                self._recording.discard(lesson_id)
                self._ahead.discard(lesson_id)
            # Ended, however it ended: whoever waits for the lesson's voice is told, so that
            # a voice that failed holds nothing back.
            self._tell_voiced(lesson_id)
        context.report(len(lines), len(lines), "Done")
        return {
            "kind": "narration",
            "lesson_id": lesson_id,
            "lines": len(lines),
            "recorded": recorded,
        }

    def _recorded_count(self, folder: Path, voice: dict[str, Any], lines: list[str]) -> int:
        return sum(1 for text in lines if self._has_clip(folder, voice, text))

    def _has_clip(self, folder: Path, voice: dict[str, Any], text: str) -> bool:
        name = self._name(voice, text)
        return (folder / f"{name}.clip").is_file() and (folder / f"{name}.json").is_file()

    def _tell_voiced(self, lesson_id: str) -> None:
        if self.on_voiced is None:
            return
        try:
            self.on_voiced(lesson_id)
        except Exception as error:
            # A listener's failure must not stop the voice.
            logger.info("narration.voiced_not_told kind=%s", type(error).__name__)

    # -- how far a lesson can be heard ----------------------------------------------------------

    def voiced_parts(self, lesson_id: str) -> int:
        """How many of a lesson's parts, from its first, can be heard in the voice chosen
        now: every line of each recorded. A part that says nothing needs no voice."""
        try:
            _, voice = self._voice(lesson_id)
        except VoiceUnavailableError:
            return 0
        folder = self._folder(lesson_id)
        count = 0
        for segment in self._lessons.get_lesson(lesson_id).segments:
            said = [beat.text for beat in getattr(segment, "narration", None) or []]
            if not all(self._has_clip(folder, voice, text) for text in said):
                break
            count += 1
        return count

    def voice_pending(self, lesson_id: str) -> bool:
        """Whether a lesson's first part is still being recorded in the voice chosen, and so
        cannot be heard yet (ADR-051). False when no voice is chosen, and when no recording
        is under way for it: a voice that failed holds nothing back."""
        try:
            if not self.status().enabled:
                return False
            with self._more_lock:
                if lesson_id not in self._recording:
                    return False
            lesson = self._lessons.get_lesson(lesson_id)
            spoken = [
                index
                for index, segment in enumerate(lesson.segments)
                if getattr(segment, "narration", None)
            ]
            if not spoken:
                return False
            if self.voiced_parts(lesson_id) <= spoken[0]:
                return True
            # A voice slower than speech on this computer needs a head start (ADR-052).
            tier, voice = self._voice(lesson_id)
            heard, lesson_speech = self._speech(lesson_id, voice)
            return not kept_ahead(self._timing_of(tier.id).rate, heard, lesson_speech)
        except (AdleError, OSError):
            return False

    def _speech(self, lesson_id: str, voice: dict[str, Any]) -> tuple[float, float]:
        """How much of a lesson can be heard from its start, and how long it all is: in
        seconds, each line recorded as long as its clip, any other as long as its words.
        A lesson still being written is taken to be at least as long as one usually is."""
        folder = self._folder(lesson_id)
        heard = 0.0
        total = 0.0
        unbroken = True
        for text in self._lines(lesson_id):
            seconds: float | None = None
            if self._has_clip(folder, voice, text):
                try:
                    said = json.loads(
                        (folder / f"{self._name(voice, text)}.json").read_text(encoding="utf-8")
                    )
                    seconds = float(said.get("seconds", 0)) if isinstance(said, dict) else None
                except (OSError, ValueError, TypeError):
                    seconds = None
            if seconds is None or seconds <= 0:
                unbroken = False
                seconds = speech_of(text)
            elif unbroken:
                heard += seconds
            total += seconds
        if self._lessons.is_writing(lesson_id):
            total = max(total, LESSON_SPEECH)
        return heard, total

    def ready_after(self) -> float | None:
        """About how long after a lesson is asked for its first part can be heard, in the
        voice chosen now: as timed on this computer, or as usual. None with no voice."""
        status = self.status()
        if not status.enabled or status.tier is None:
            return None
        return timed_ready_after(
            self._timing_of(status.tier), READY_GUESS_SECONDS.get(status.tier, 45.0)
        )

    def timing(self, tier_id: str) -> VoiceTiming:
        """What has been measured of a voice on this computer (ADR-052)."""
        return self._timing_of(tier_id)

    def _timing_of(self, tier_id: str) -> VoiceTiming:
        return read_timing(self._timings().get(tier_id))

    def _keep_timing(self, tier_id: str, timing: VoiceTiming) -> None:
        timings = self._timings()
        timings[tier_id] = kept(timing)
        try:
            self._paths.root.mkdir(parents=True, exist_ok=True)
            self._timing.write_text(json.dumps(timings), encoding="utf-8")
        except OSError as error:
            logger.info("narration.timing_not_kept kind=%s", type(error).__name__)

    def _timed_line(self, tier_id: str, took: float, seconds: float) -> None:
        """A line said by a loaded engine: how much work a second of its speech took."""
        if seconds <= 0.2 or took <= 0:
            return
        before = self._timing_of(tier_id)
        rate = mean(before.rate, took / seconds)
        self._keep_timing(tier_id, VoiceTiming(before.ready, before.start, rate))

    def _timings(self) -> dict[str, Any]:
        try:
            found = json.loads(self._timing.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return found if isinstance(found, dict) else {}

    def _timed_ready(self, tier_id: str) -> None:
        """A lesson is ready in its voice: how long that took from when it was asked for is
        kept, as a running mean, to say how long a lesson usually takes here."""
        began, self._warmed_at = self._warmed_at, None
        if began is None:
            return
        took = time.monotonic() - began
        if took > _WARMUP_COUNTS_FOR:
            return
        before = self._timing_of(tier_id)
        self._keep_timing(tier_id, VoiceTiming(mean(before.ready, took), before.start, before.rate))

    def close(self) -> None:
        """The core is stopping: the engine goes with it."""
        self._engines.close()

    def recordings(self) -> list[VoiceRecording]:
        """The lessons being recorded now, and how far each has come."""
        found: list[VoiceRecording] = []
        for job in self._jobs.list_all_active([KIND_NARRATION]):
            if job.subject_id is None:
                continue
            try:
                title = self._lessons.get_lesson(job.subject_id).title
            except NotFoundError:
                continue
            found.append(
                VoiceRecording(job.subject_id, title, job.progress_done, job.progress_total)
            )
        return found

    # -- a sample of a voice ---------------------------------------------------------------------

    def sample(
        self, tier_id: str, *, speaker: str | None = None, design: str | None = None
    ) -> JobSnapshot:
        """A few words in a voice set up here, for the learner to hear before choosing it: a
        speaker of the Natural voice, or the Expressive voice of a description (ADR-057).
        Made once and kept; lessons recorded ahead of time step aside for it."""
        tier = find_tier(tier_id)
        if tier is None or tier.id not in self.status().ready:
            raise NotFoundError("That voice is not set up here.")
        voice = self._sample_voice(tier, speaker, design)
        name = self._name(voice, SAMPLE_TEXT)
        running = self._jobs.find_active(KIND_VOICE_SAMPLE, name)
        if running is not None:
            return running
        self._step_aside()
        return self._jobs.submit(
            KIND_VOICE_SAMPLE,
            lambda context: self._sample(tier, voice, name, context),
            subject_id=name,
            lane=LANE_VOICE,
        )

    def _sample_voice(self, tier: Tier, speaker: str | None, design: str | None) -> dict[str, Any]:
        if tier.id == "expressive":
            described = _described(design) if design is not None else ""
            folder = self._samples(tier.id)
            return self._designed(described or self.status().design, folder)
        chosen = speaker or self.status().speakers.get(tier.id) or tier.default_speaker
        if chosen not in {item.id for item in tier.speakers}:
            raise NotFoundError("There is no such voice.")
        return {"tier": tier.id, "speaker": chosen}

    def _samples(self, tier_id: str) -> Path:
        return self._paths.root / "samples" / tier_id

    def _sample(
        self, tier: Tier, voice: dict[str, Any], name: str, context: JobContext
    ) -> dict[str, Any]:
        folder = self._samples(tier.id)
        folder.mkdir(parents=True, exist_ok=True)
        clip = folder / f"{name}.clip"
        if not clip.is_file():
            context.report(0, 1, "Making a sample")
            engine = self._engines.take(tier.family)
            try:
                engine.speak(SAMPLE_TEXT, voice, clip, cancelled=lambda: context.cancelled)
            finally:
                self._engines.give_back()
        # What stepped aside for it carries on.
        self._record_recent()
        context.report(1, 1, "Done")
        return {"kind": "voice_sample", "sample": name}

    def sample_clip(self, name: str) -> tuple[bytes, str]:
        """A sample made before, and the kind of sound it is."""
        if not _CLIP.match(name):
            raise NotFoundError("Sample not found.")
        for tier in TIERS:
            path = self._samples(tier.id) / f"{name}.clip"
            if path.is_file():
                data = path.read_bytes()
                return data, _sound_kind(data)
        raise NotFoundError("Sample not found.")

    # -- what has been recorded ------------------------------------------------------------

    def clips(self, lesson_id: str) -> list[NarrationClip]:
        """The lesson's lines that have been recorded in the voice chosen now."""
        try:
            _, voice = self._voice(lesson_id)
        except VoiceUnavailableError:
            return []
        folder = self._folder(lesson_id)
        found: list[NarrationClip] = []
        for text in self._lines(lesson_id):
            name = self._name(voice, text)
            try:
                timing = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not (folder / f"{name}.clip").is_file() or not isinstance(timing, dict):
                continue
            found.append(
                NarrationClip(
                    text=text,
                    clip=name,
                    seconds=float(timing.get("seconds", 0)),
                    words=list(timing.get("words", [])),
                )
            )
        return found

    def clip(self, lesson_id: str, name: str) -> tuple[bytes, str]:
        """A recorded clip, and the kind of sound it is."""
        if not _CLIP.match(name):
            raise NotFoundError("Clip not found.")
        path = self._folder(lesson_id) / f"{name}.clip"
        try:
            data = path.read_bytes()
        except OSError as error:
            raise NotFoundError("Clip not found.") from error
        return data, _sound_kind(data)

    def forget(self, lesson_id: str) -> None:
        """A lesson that has gone takes its clips with it, and its recording stops."""
        try:
            folder = self._folder(lesson_id)
        except NotFoundError:
            return
        running = self._jobs.find_active(KIND_NARRATION, lesson_id)
        if running is not None:
            self._jobs.cancel(running.id)
        shutil.rmtree(folder, ignore_errors=True)

    def tidy(self) -> None:
        """Clips of lessons that are no longer there, from before a removal, go."""
        if not self._paths.clips.is_dir():
            return
        for folder in self._paths.clips.iterdir():
            if folder.is_dir() and not (
                is_id(folder.name, "les") and self._lessons.exists(folder.name)
            ):
                shutil.rmtree(folder, ignore_errors=True)

    def ensure_not_recording(self, lesson_id: str) -> None:
        if self._jobs.find_active(KIND_NARRATION, lesson_id) is not None:
            raise ConflictError("The narration of this lesson is being recorded.")


def _described(text: str) -> str:
    """A learner's description of a voice, as one plain line: empty for Adle's own."""
    described = " ".join(text.split())
    if len(described) > MAX_DESIGN_CHARACTERS:
        raise ValidationFailedError(
            f"Describe the voice in {MAX_DESIGN_CHARACTERS} characters or fewer."
        )
    if described and not is_plain_text(described):
        raise ValidationFailedError("Describe the voice in plain words.")
    return described


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _sound_kind(data: bytes) -> str:
    if data.startswith(b"OggS"):
        return "audio/ogg"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    return "application/octet-stream"
