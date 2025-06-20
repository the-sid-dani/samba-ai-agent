from fastapi import APIRouter

from sambaai.server.openai_assistants_api.asssistants_api import (
    router as assistants_router,
)
from sambaai.server.openai_assistants_api.messages_api import router as messages_router
from sambaai.server.openai_assistants_api.runs_api import router as runs_router
from sambaai.server.openai_assistants_api.threads_api import router as threads_router


def get_full_openai_assistants_api_router() -> APIRouter:
    router = APIRouter(prefix="/openai-assistants")

    router.include_router(assistants_router)
    router.include_router(runs_router)
    router.include_router(threads_router)
    router.include_router(messages_router)

    return router
