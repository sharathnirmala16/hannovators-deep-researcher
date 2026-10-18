"""Composition root: settings -> adapters -> services -> FastAPI app, and the `hdr-api` command."""

import argparse
import importlib
import logging
import sys
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import URL

from hannovators_deep_researcher.adapters.fake.chat import FakeChatModel
from hannovators_deep_researcher.adapters.fake.decisions import FakeDecisionModel
from hannovators_deep_researcher.adapters.fake.embeddings import FakeEmbedder
from hannovators_deep_researcher.adapters.fake.literature import (
    FakeLiteratureSearch,
    fake_http_transport,
)
from hannovators_deep_researcher.adapters.fake.web import FakeWebSearch
from hannovators_deep_researcher.adapters.websearch import build_providers
from hannovators_deep_researcher.configuration.settings import ProviderMode, Settings, get_settings
from hannovators_deep_researcher.infrastructure.database import create_database_engine
from hannovators_deep_researcher.infrastructure.http import create_http_client
from hannovators_deep_researcher.models.ports import (
    ChatModel,
    DecisionModel,
    Embedder,
    LiteratureSearch,
    WebSearch,
)
from hannovators_deep_researcher.persistence.repositories import (
    Repositories,
    create_session_factory,
)
from hannovators_deep_researcher.routers import include_routers
from hannovators_deep_researcher.routers.dependencies import ApiContainer, PortStatus
from hannovators_deep_researcher.routers.errors import install_error_handlers
from hannovators_deep_researcher.services.documents.files import WORKSPACES_DIR, data_root
from hannovators_deep_researcher.services.events import DatabaseEventSink
from hannovators_deep_researcher.services.pipeline.context import PipelineServices
from hannovators_deep_researcher.services.pipeline.orchestrator import Orchestrator
from hannovators_deep_researcher.services.websearch_router import create_web_search_router
from hannovators_deep_researcher.services.workspace_state import WorkspaceStateService

logger = logging.getLogger(__name__)

PACKAGE = "hannovators_deep_researcher"
DEV_ORIGIN_REGEX = r"^http://(127\.0\.0\.1|localhost)(:\d+)?$"


@dataclass(frozen=True, slots=True)
class ProviderPorts:
    chat: ChatModel
    embedder: Embedder
    decisions: DecisionModel
    web: WebSearch
    literature: LiteratureSearch
    status: dict[str, PortStatus]


def _key_status(secret: object | None) -> str:
    return "configured" if secret is not None else "missing"


def _real_or_fake[T](
    port: str,
    provider: str,
    *,
    module: str,
    factory: str,
    args: Sequence[object],
    key: str,
    fake: Callable[[], T],
    status: dict[str, PortStatus],
) -> T:
    """Build the real adapter `<module>.<factory>(*args)`, else the fake with a warning."""

    if key == "missing":
        note = f"{provider} key missing"
    else:
        try:
            build = getattr(importlib.import_module(f"{PACKAGE}.{module}"), factory)
        except (ImportError, AttributeError):
            note = f"{module}.{factory} is not available yet"
        else:
            status[port] = PortStatus("real", provider, key)
            return cast(T, build(*args))
    logger.warning("Port %s uses the fake adapter: %s", port, note)
    status[port] = PortStatus("fake", provider, key, note)
    return fake()


def _real_web(settings: Settings, status: dict[str, PortStatus]) -> WebSearch:
    key = _key_status(settings.tavily_api_key)
    try:
        web: WebSearch = create_web_search_router(settings, build_providers(settings))
    except Exception as error:
        logger.warning("Port web uses the fake adapter: %s", error)
        status["web"] = PortStatus("fake", "tavily", key, str(error))
        return FakeWebSearch()
    status["web"] = PortStatus("real", "tavily", key)
    return web


def build_ports(settings: Settings, http: httpx.AsyncClient) -> ProviderPorts:
    """Wire every port. Fake mode uses `adapters/fake`; real mode falls back per port."""

    status: dict[str, PortStatus] = {}

    def fake_embedder() -> Embedder:
        return FakeEmbedder(settings.embedding_dimensions)

    if settings.provider_mode is ProviderMode.FAKE:
        for port in ("chat", "embedder", "decisions", "web", "literature"):
            status[port] = PortStatus("fake", "fake", "not_required")
        return ProviderPorts(
            chat=FakeChatModel(),
            embedder=fake_embedder(),
            decisions=FakeDecisionModel(),
            web=FakeWebSearch(),
            literature=FakeLiteratureSearch(),
            status=status,
        )

    args: tuple[Any, ...] = (settings, http)
    nebius_key = _key_status(settings.nebius_api_key)
    chat: ChatModel = _real_or_fake(
        "chat",
        "nebius",
        module="adapters.nebius",
        factory="build_chat_model",
        args=args,
        key=nebius_key,
        fake=FakeChatModel,
        status=status,
    )
    embedder: Embedder = _real_or_fake(
        "embedder",
        "nebius",
        module="adapters.nebius",
        factory="build_embedder",
        args=args,
        key=nebius_key,
        fake=fake_embedder,
        status=status,
    )
    decisions: DecisionModel = _real_or_fake(
        "decisions",
        "jev",
        module="adapters.jev",
        factory="build_decision_model",
        args=args,
        key=_key_status(settings.jev_api_key),
        fake=FakeDecisionModel,
        status=status,
    )
    literature: LiteratureSearch = _real_or_fake(
        "literature",
        "pubmed",
        module="adapters.pubmed",
        factory="build_literature_search",
        args=args,
        key="not_required",
        fake=FakeLiteratureSearch,
        status=status,
    )
    return ProviderPorts(
        chat=chat,
        embedder=embedder,
        decisions=decisions,
        web=_real_web(settings, status),
        literature=literature,
        status=status,
    )


def build_container(settings: Settings, *, database_url: str | URL | None = None) -> ApiContainer:
    fake_mode = settings.provider_mode is ProviderMode.FAKE
    http = (
        httpx.AsyncClient(transport=fake_http_transport(), follow_redirects=True)
        if fake_mode
        else create_http_client()
    )
    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    repositories = Repositories(session_factory)
    ports = build_ports(settings, http)
    services = PipelineServices(
        app_settings=settings,
        session_factory=session_factory,
        repositories=repositories,
        chat=ports.chat,
        embedder=ports.embedder,
        decisions=ports.decisions,
        web=ports.web,
        literature=ports.literature,
        events=DatabaseEventSink(repositories),
    )
    return ApiContainer(
        settings=settings,
        engine=engine,
        http=http,
        services=services,
        orchestrator=Orchestrator(services),
        state=WorkspaceStateService(repositories),
        providers=ports.status,
    )


def create_app(
    settings: Settings | None = None,
    *,
    database_url: str | URL | None = None,
    files_dir: Path | None = None,
) -> FastAPI:
    """Build the app. `database_url` and `files_dir` default to the project `data/` folder."""

    container = build_container(settings or get_settings(), database_url=database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await container.aclose()

    app = FastAPI(title="Hannovators Deep Researcher", lifespan=lifespan)
    app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=DEV_ORIGIN_REGEX,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    include_routers(app)
    workspaces_dir = files_dir or data_root() / WORKSPACES_DIR
    workspaces_dir.mkdir(parents=True, exist_ok=True)
    # Stored paths start with `workspaces/`, so `/files/<relative path>` serves them.
    app.mount(f"/files/{WORKSPACES_DIR}", StaticFiles(directory=workspaces_dir), name="files")
    return app


def run(argv: Sequence[str] | None = None) -> None:
    """`hdr-api`: serve on API_HOST/API_PORT from settings; `--host`/`--port` override them."""

    parser = argparse.ArgumentParser(prog="hdr-api", description=run.__doc__)
    parser.add_argument("--host", help="override API_HOST")
    parser.add_argument("--port", type=int, help="override API_PORT")
    options = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    try:
        port = options.port or settings.require_api_port()
    except RuntimeError as error:
        sys.exit(f"hdr-api: {error}")
    uvicorn.run(create_app(settings), host=options.host or settings.api_host, port=port)
