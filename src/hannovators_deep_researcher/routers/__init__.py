"""Transport layer and application routes. Every router module is registered here once."""

from fastapi import FastAPI

from hannovators_deep_researcher.routers import (
    chat,
    deep_research,
    events,
    graph,
    health,
    seeds,
    sources,
    trajectory,
    workspaces,
)

API_PREFIX = "/api"


def include_routers(app: FastAPI) -> None:
    for module in (
        workspaces,
        seeds,
        sources,
        events,
        graph,
        health,
        trajectory,
        chat,
        deep_research,
    ):
        app.include_router(module.router, prefix=API_PREFIX)
