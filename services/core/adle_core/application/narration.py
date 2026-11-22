"""A lesson's narration in a natural voice, recorded on this computer (ADR-042).

When the natural voice is set up and chosen, each line a lesson says is recorded once, as a
clip with the time of each of its words, and kept beside the data. The lesson then plays the
clips and marks each word as it is said; a line without a clip is read as before.

A clip is named by the voice and the words it says, so that a lesson whose words or voice
change is recorded again and nothing is spoken in a voice that was not chosen. The clips of a
lesson go when the lesson goes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from adle_core.application.jobs import LANE_VOICE, JobContext, JobRunner, JobSnapshot
from adle_core.application.lessons import LessonService
from adle_core.errors import ConflictError, NotFoundError
from adle_core.infrastructure.ids import is_id
from adle_core.voice.catalog import DEFAULT_DESIGN, TIERS, Tier
from adle_core.voice.catalog import tier as find_tier
from adle_core.voice.hardware import Fit, Hardware, detect, fit
from adle_core.voice.install import VoiceInstaller, VoiceSetupError
from adle_core.voice.runtime import VoiceEngine, VoicePaths, VoiceUnavailableError

logger = logging.getLogger(__name__)

KIND_NARRATION = "narration_recording"
#: Setting a size of voice up: its programs, its models, a word said to check it.
KIND_VOICE_SETUP = "voice_setup"
_CLIP = re.compile(r"^[0-9a-f]{24}$")


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


@dataclass(frozen=True, slots=True)
class NarrationClip:
    #: The words it says, exactly as the lesson says them.
    text: str
    clip: str
    seconds: float
    words: list[dict[str, float | int]]


class NarrationService:
    def __init__(
        self,
        lessons: LessonService,
        jobs: JobRunner,
        paths: VoicePaths,
        hardware: Callable[[], Hardware] = detect,
        installer: Callable[[VoicePaths], VoiceInstaller] = VoiceInstaller,
    ) -> None:
        self._lessons = lessons
        self._jobs = jobs
        self._paths = paths
        self._installer = installer
        self._preferences = paths.root / "preferences.json"
        self._detect = hardware
        self._hardware: Hardware | None = None

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
        return VoiceStatus(
            ready=ready,
            tier=tier,
            enabled=tier is not None and chosen.get("enabled", True) is not False,
            speakers=speakers,
            borrowed=self._paths.borrowed,
        )

    def choose(
        self, *, enabled: bool | None = None, tier: str | None = None, speaker: str | None = None
    ) -> VoiceStatus:
        """Turn the natural voice on or off, choose a size of it, or a voice of a size."""
        chosen = self._chosen()
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
        return self.status()

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
        try:
            self._installer(self._paths).install(
                tier,
                report=lambda message, done, total: context.report(done, total, message),
                cancelled=lambda: context.cancelled,
            )
        except VoiceSetupError:
            # Stopped by the learner is a stop, not a failure.
            context.check_cancelled()
            raise
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
        if self._jobs.any_active([KIND_VOICE_SETUP, KIND_NARRATION]):
            raise ConflictError("The voice is busy. Wait for it to finish, then try again.")
        keep = [other for other in self._paths.ready_tiers() if other.id != tier.id]
        self._installer(self._paths).remove(tier, keep)
        self._forget_recordings(tier.id)
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
            # Designed from what the lesson says of its narrator, written with it; a lesson
            # that says nothing (the sample course's, or one written before) is read in
            # Adle's own.
            folder = self._folder(lesson_id)
            design = self._lessons.get_lesson(lesson_id).voice or DEFAULT_DESIGN
            reference = folder / f"voice-{_digest(design)}.wav"
            return tier, {"tier": tier.id, "design": design, "reference": str(reference)}
        return tier, {"tier": tier.id, "speaker": status.speakers[tier.id]}

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

    def record_ahead(self, lesson_id: str) -> None:
        """Record a lesson as soon as its words are stored, when a natural voice reads the
        lessons: the clips are made while the learner is elsewhere, and not while the
        lesson plays in the computer's voice waiting for them. A picture that arrives later
        changes nothing that is said. With no voice chosen, nothing is done."""
        try:
            if self.status().enabled:
                self.start(lesson_id)
        except (VoiceUnavailableError, NotFoundError, ConflictError, OSError) as error:
            logger.info("narration.not_recorded_ahead kind=%s", type(error).__name__)

    def start(self, lesson_id: str) -> JobSnapshot:
        """Record what a lesson says, in the background. Work already under way is returned."""
        self._voice(lesson_id)
        self._lessons.get_lesson(lesson_id)
        running = self._jobs.find_active(KIND_NARRATION, lesson_id)
        if running is not None:
            return running
        return self._jobs.submit(
            KIND_NARRATION,
            lambda context: self._record(lesson_id, context),
            subject_id=lesson_id,
            lane=LANE_VOICE,
        )

    def _record(self, lesson_id: str, context: JobContext) -> dict[str, Any]:
        tier, voice = self._voice(lesson_id)
        lines = self._lines(lesson_id)
        folder = self._folder(lesson_id)
        folder.mkdir(parents=True, exist_ok=True)
        engine = VoiceEngine(self._paths, tier.family)
        recorded = 0
        try:
            for number, text in enumerate(lines):
                context.check_cancelled()
                name = self._name(voice, text)
                clip, timing = folder / f"{name}.clip", folder / f"{name}.json"
                if clip.is_file() and timing.is_file():
                    continue
                context.report(number, len(lines), "Recording the narration")
                spoken = engine.speak(text, voice, clip, cancelled=lambda: context.cancelled)
                timing.write_text(
                    json.dumps({"seconds": spoken.seconds, "words": spoken.words, "tier": tier.id}),
                    encoding="utf-8",
                )
                recorded += 1
        finally:
            engine.close()
        context.report(len(lines), len(lines), "Done")
        return {
            "kind": "narration",
            "lesson_id": lesson_id,
            "lines": len(lines),
            "recorded": recorded,
        }

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
        """A lesson that has gone takes its clips with it."""
        try:
            folder = self._folder(lesson_id)
        except NotFoundError:
            return
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


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _sound_kind(data: bytes) -> str:
    if data.startswith(b"OggS"):
        return "audio/ogg"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    return "application/octet-stream"
