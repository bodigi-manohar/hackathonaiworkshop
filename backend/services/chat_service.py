"""Chat service: answers strictly from explain_context.json (FR-7xx)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.config import Settings
from backend.core.exceptions import NotFoundError
from backend.llm.client import LLMClient
from backend.llm.explain import answer_question
from backend.models import ChatLog
from backend.schemas.chat import ChatOut
from backend.services.run_store import RunStore

logger = logging.getLogger("gridsight.chat")


class ChatService:
    def __init__(self, settings: Settings, store: RunStore, db: Session):
        self.settings = settings
        self.store = store
        self.db = db

    def ask(self, question: str, run_id: str | None = None) -> ChatOut:
        bundle = self.store.resolve(run_id)
        context = self.store.load_json(bundle.path, "explain_context.json", bundle.run_id)
        alerts = self.store.load_json(bundle.path, "alerts.json", bundle.run_id, default=[])
        plan = self.store.load_json(bundle.path, "plan.json", bundle.run_id, default={})

        client = LLMClient(self.settings)
        answer, used_llm = answer_question(client, question, context, alerts, plan)
        logger.info("chat run=%s used_llm=%s question=%r", bundle.run_id, used_llm, question[:80])

        self.db.add(
            ChatLog(
                timestamp=datetime.now(tz=timezone.utc),
                run_id=bundle.run_id,
                question=question,
                answer=answer,
                used_llm=used_llm,
            )
        )
        self.db.commit()
        return ChatOut(answer=answer, used_llm=used_llm, run_id=bundle.run_id)


def load_context_or_404(store: RunStore, run_id: str | None) -> tuple:  # noqa: ARG001 (kept for API clarity)
    raise NotFoundError("explain_context.json not available for the requested run")
