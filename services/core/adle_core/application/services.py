"""The service container: everything a request handler may depend on.

Built once at startup and attached to the FastAPI app. Handlers receive it via
``Depends(get_services)`` so that tests can construct an isolated instance.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from adle_core.api.auth import LaunchToken
from adle_core.application.courses import CourseService
from adle_core.application.curriculum import CurriculumService
from adle_core.application.jobs import JobRunner
from adle_core.application.learner import LearnerService
from adle_core.application.retrieval import FtsRetriever, Retriever
from adle_core.application.sources import SourceService
from adle_core.config import Settings
from adle_core.generation.credentials import CredentialVault
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

    def close(self) -> None:
        """Stop background work and release the database. Safe to call more than once."""
        self.jobs.stop()
        self.database.dispose()


def build_services(
    settings: Settings,
    launch_token: LaunchToken,
    *,
    extract: Extractor = extract_isolated,
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
    return Services(
        settings=settings,
        launch_token=launch_token,
        credentials=CredentialVault(),
        database=database,
        migration=migration,
        jobs=jobs,
        courses=CourseService(database, source_files),
        sources=SourceService(database, source_files, jobs, extract=extract),
        retriever=retriever,
        curriculum=CurriculumService(database, retriever),
        learner=LearnerService(database),
    )


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services
