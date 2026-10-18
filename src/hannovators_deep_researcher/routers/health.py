"""Which ports are real or fake, and whether their keys are configured. Never key values."""

from dataclasses import asdict

from fastapi import APIRouter

from hannovators_deep_researcher.routers.dependencies import Container

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/providers")
async def provider_health(container: Container) -> dict[str, object]:
    return {
        "provider_mode": container.settings.provider_mode,
        "ports": {port: asdict(status) for port, status in container.providers.items()},
    }
