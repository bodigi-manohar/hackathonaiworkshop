from fastapi import APIRouter

from backend.dependencies import RunStoreDep
from backend.schemas.explain import ExplainContext

router = APIRouter(tags=["explain"])


@router.get("/explain-context", response_model=ExplainContext)
def get_explain_context(
    run_id: str | None = None,
    store: RunStoreDep = None,  # type: ignore[assignment]
) -> dict:
    """The pre-computed explanation context for a run (the only input the chat LLM sees)."""
    bundle = store.resolve(run_id)
    return store.load_json(bundle.path, "explain_context.json", bundle.run_id)