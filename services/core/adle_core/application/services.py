"""The service container: everything a request handler may depend on.

Built once at startup and attached to the FastAPI app. Handlers receive it via
``Depends(get_services)`` so that tests can construct an isolated instance.
"""

from __future__ import annotations

import contextlib
import secrets
from dataclasses import dataclass
from pathlib import Path

import httpx2 as httpx
from fastapi import Request

from adle_core import __version__
from adle_core.api.auth import LaunchToken
from adle_core.application.asks import AskService
from adle_core.application.assessment import AssessmentService
from adle_core.application.course_sharing import CourseFileService
from adle_core.application.courses import CourseService
from adle_core.application.curriculum import CurriculumService
from adle_core.application.generation import GenerationService
from adle_core.application.jobs import JobRunner
from adle_core.application.learner import LearnerService
from adle_core.application.learning import LearningService
from adle_core.application.lessons import LessonService
from adle_core.application.model_gateway import ModelGateway
from adle_core.application.narration import NarrationService
from adle_core.application.retrieval import FtsRetriever, Retriever
from adle_core.application.sample_course import SampleCourseService
from adle_core.application.sources import PageDrawer, SourceService
from adle_core.config import Settings
from adle_core.generation.credentials import CredentialVault
from adle_core.generation.provider import ChatClient
from adle_core.generation.quota import QuotaLimits
from adle_core.infrastructure.asset_store import AssetStore
from adle_core.infrastructure.database import Database
from adle_core.infrastructure.migrate import MigrationOutcome, migrate
from adle_core.ingestion.extract import Extractor, extract_isolated, render_isolated
from adle_core.ingestion.types import Limits
from adle_core.lessons.player import ItemMask
from adle_core.voice.runtime import VoicePaths


@dataclass(slots=True)
class Services:
    settings: Settings
    launch_token: LaunchToken
    credentials: CredentialVault
    database: Database
    migration: MigrationOutcome
    jobs: JobRunner
    courses: CourseService
    sources: SourceService
    retriever: Retriever
    curriculum: CurriculumService
    learner: LearnerService
    lessons: LessonService
    asks: AskService
    #: Names the items of an ordering question so that their ids, which are its answer,
    #: are never shown.
    item_mask: ItemMask
    assessment: AssessmentService
    learning: LearningService
    sample_course: SampleCourseService
    provider_clients: tuple[ChatClient, ...]
    gateway: ModelGateway
    generation: GenerationService
    #: A lesson's narration in a natural voice, when one is set up (ADR-042).
    narration: NarrationService
    #: A course saved as a file, and brought in from one (ADR-063).
    course_files: CourseFileService

    def close(self) -> None:
        """Stop background work and release the database. Safe to call more than once."""
        self.jobs.stop()
        self.narration.close()
        for client in self.provider_clients:
            client.close()
        self.database.dispose()


def _installation_secret(path: Path) -> bytes:
    """Thirty-two random bytes that stay the same for this installation.

    Kept beside the database so that a lesson left open keeps working when the service
    starts again. It protects nothing worth more than the answer to a question, so a
    folder that cannot be written to is not an error: the secret then lasts for this run.
    """
    try:
        found = path.read_bytes()
        if len(found) >= 32:
            return found
    except OSError:
        pass
    made = secrets.token_bytes(32)
    with contextlib.suppress(OSError):
        path.write_bytes(made)
    return made


def build_services(
    settings: Settings,
    launch_token: LaunchToken,
    *,
    extract: Extractor = extract_isolated,
    draw_page: PageDrawer = render_isolated,
    provider_transport: httpx.BaseTransport | None = None,
    quota_limits: QuotaLimits | None = None,
) -> Services:
    """Open (and if needed migrate) the database, then assemble the services.

    Raises ``MigrationError`` if the database cannot be brought to the current
    schema; in that case nothing has been changed without a backup.
    """
    settings.ensure_directories()
    database = Database(settings.db_path)
    try:
        migration = migrate(database, settings.backups_dir)
    except BaseException:
        database.dispose()
        raise

    jobs = JobRunner(database)
    jobs.start()
    source_files = AssetStore(settings.sources_dir)
    retriever = FtsRetriever(database)
    courses = CourseService(database, source_files)
    # A course made before courses had subjects is placed by its name (ADR-061).
    courses.settle_subjects()
    curriculum = CurriculumService(database, retriever)
    lessons = LessonService(database)
    # Nothing is being drawn while the core starts: a lesson still waiting for a picture
    # was left by a run that ended, and that picture is not coming (ADR-031).
    lessons.settle_unfinished()
    asks = AskService(database)
    learner = LearnerService(database)
    narration = NarrationService(lessons, jobs, VoicePaths.under(settings.data_dir))
    # Clips of lessons removed while the core was not looking go now.
    narration.tidy()
    item_mask = ItemMask(_installation_secret(settings.item_key_path))
    # One vault, and one client for each provider. A client asks the vault for its own
    # provider's key and for no other, and only ever talks to its own address. The
    # learner's choice starts as "automatic": whichever providers they give a key to.
    # The desktop shell hands over a choice they made earlier, if there is one.
    credentials = CredentialVault(settings.providers.default.provider_id)
    provider_clients = tuple(
        ChatClient(config, credentials, transport=provider_transport)
        for config in settings.providers.providers
    )
    # Each provider is held to its own limits, unless a test lifts them.
    gateway = ModelGateway(database, provider_clients, limits=quota_limits)
    # A lesson in a natural voice is made with its voice (ADR-051): its models load as the
    # lesson is asked for, each part is recorded as it is stored, and the lesson is ready
    # once its first part can be heard.
    generation = GenerationService(
        database,
        jobs,
        gateway,
        curriculum,
        lessons,
        learner,
        retriever,
        asks,
        on_stored=narration.record_ahead,
        on_begun=narration.warm,
        voice_pending=narration.voice_pending,
        voice_wait=narration.ready_after,
    )
    narration.on_voiced = generation.voiced
    sources = SourceService(
        database, source_files, jobs, extract=extract, gateway=gateway, draw_page=draw_page
    )
    course_files = CourseFileService(
        database,
        courses,
        curriculum,
        sources,
        lessons,
        learner,
        asks,
        handover_dir=settings.handover_dir,
        made_by=f"Adle {__version__}",
        max_file_bytes=Limits().max_file_bytes,
    )
    # A file written for the learner and never collected is not kept.
    course_files.clear_handed_over()
    return Services(
        settings=settings,
        launch_token=launch_token,
        credentials=credentials,
        database=database,
        migration=migration,
        jobs=jobs,
        courses=courses,
        sources=sources,
        retriever=retriever,
        curriculum=curriculum,
        learner=learner,
        lessons=lessons,
        asks=asks,
        item_mask=item_mask,
        assessment=AssessmentService(database, lessons, learner, item_mask),
        learning=LearningService(database, curriculum, learner, credentials, item_mask),
        sample_course=SampleCourseService(database, courses, curriculum, lessons),
        provider_clients=provider_clients,
        gateway=gateway,
        generation=generation,
        narration=narration,
        course_files=course_files,
    )


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services
