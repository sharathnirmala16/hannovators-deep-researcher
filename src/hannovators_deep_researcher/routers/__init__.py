"""Transport layer and application routes."""

from fastapi import FastAPI

from hannovators_deep_researcher.routers import events, graph, health, seeds, workspaces

API_PREFIX = "/api"


def include_routers(app: FastAPI) -> None:
    for module in (workspaces, seeds, events, graph, health):
        app.include_router(module.router, prefix=API_PREFIX)
