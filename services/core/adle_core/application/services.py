"""The service container: everything a request handler may depend on.

Built once at startup and attached to the FastAPI app. Handlers receive it via
``Depends(get_services)`` so that tests can construct an isolated instance.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx2 as httpx
from fastapi import Request

from adle_core.api.auth import LaunchToken
from adle_core.application.assessment import AssessmentService
from adle_core.application.courses import CourseService
from adle_core.application.curriculum import CurriculumService
from adle_core.application.generation import GenerationService
from adle_core.application.jobs import JobRunner
from adle_core.application.learner import LearnerService
from adle_core.application.learning import LearningService
from adle_core.application.lessons import LessonService
from adle_core.application.model_gateway import ModelGateway
from adle_core.application.retrieval import FtsRetriever, Retriever
from adle_core.application.sample_course import SampleCourseService
from adle_core.application.sources import SourceService
from adle_core.config import Settings
from adle_core.generation.credentials import CredentialVault
from adle_core.generation.provider import ChatClient
from adle_core.generation.quota import DEFAULT_LIMITS, QuotaLimits
from adle_core.infrastructure.asset_store import AssetStore
from adle_core.infrastructure.database import Database
from adle_core.infrastructure.migrate import MigrationOutcome, migrate
from adle_core.ingestion.extract import Extractor, extract_isolated


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
    assessment: AssessmentService
    learning: LearningService
    sample_course: SampleCourseService
    provider_client: ChatClient
    gateway: ModelGateway
    generation: GenerationService

    def close(self) -> None:
        """Stop background work and release the database. Safe to call more than once."""
        self.jobs.stop()
        self.provider_client.close()
        self.database.dispose()


def build_services(
    settings: Settings,
    launch_token: LaunchToken,
    *,
    extract: Extractor = extract_isolated,
    provider_transport: httpx.BaseTransport | None = None,
    quota_limits: QuotaLimits = DEFAULT_LIMITS,
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
    curriculum = CurriculumService(database, retriever)
    lessons = LessonService(database)
    learner = LearnerService(database)
    credentials = CredentialVault()
    provider_client = ChatClient(settings.provider, credentials, transport=provider_transport)
    gateway = ModelGateway(database, provider_client, limits=quota_limits)
    return Services(
        settings=settings,
        launch_token=launch_token,
        credentials=credentials,
        database=database,
        migration=migration,
        jobs=jobs,
        courses=courses,
        sources=SourceService(database, source_files, jobs, extract=extract),
        retriever=retriever,
        curriculum=curriculum,
        learner=learner,
        lessons=lessons,
        assessment=AssessmentService(database, lessons, learner),
        learning=LearningService(database, curriculum, learner, credentials),
        sample_course=SampleCourseService(database, courses, curriculum, lessons),
        provider_client=provider_client,
        gateway=gateway,
        generation=GenerationService(
            database, jobs, gateway, curriculum, lessons, learner, retriever
        ),
    )


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services
