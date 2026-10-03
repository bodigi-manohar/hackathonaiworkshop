from fastapi import APIRouter

from backend.config import get_settings
from backend.dependencies import DbSession, RunStoreDep
from backend.schemas.chat import ChatIn, ChatOut
from backend.services.chat_service import ChatService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatOut)
def post_chat(
    body: ChatIn,
    store: RunStoreDep = None,  # type: ignore[assignment]
    db: DbSession = None,  # type: ignore[assignment]
) -> ChatOut:
    return ChatService(get_settings(), store, db).ask(body.question, body.run_id)
