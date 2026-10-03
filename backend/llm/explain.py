"""Context-only answering: LLM with a deterministic template fallback (FR-704)."""
from __future__ import annotations

from backend.llm.client import LLMClient, LLMUnavailableError
from backend.llm.prompts import SYSTEM_PROMPT, user_prompt


def _fmt_context(context: dict, alerts: list, plan: dict) -> dict:
    return {
        "context": context,
        "alerts": alerts,
        "plan": {
            "saving": plan.get("saving"),
            "cost_before": plan.get("cost_before"),
            "cost_after": plan.get("cost_after"),
            "peak_before_kw": plan.get("peak_before_kw"),
            "peak_after_kw": plan.get("peak_after_kw"),
        },
    }


def template_fallback(question: str, context: dict, alerts: list, plan: dict) -> str:
    """Deterministic answer built only from the same context the LLM would see."""
    q = question.lower()
    peak = context.get("peak", {})
    accuracy = context.get("accuracy_last_7_days", {})
    plan_summary = context.get("plan_summary", {})

    if "peak" in q or "high" in q or "why" in q:
        drivers = ", ".join(context.get("drivers", [])) or "no drivers listed"
        return (
            f"The evening peak is expected at {peak.get('time')} with P50 {peak.get('p50_kw')} kW "
            f"(P90 {peak.get('p90_kw')} kW). Pre-computed drivers: {drivers}. "
            f"{context.get('band_width_note') or ''}".strip()
        )
    if "risk" in q:
        alert_lines = "; ".join(context.get("alerts_summary", [])) or "no alerts in the context"
        return (
            f"Biggest risk tomorrow per the context: {alert_lines}. "
            f"Peak P50 is {peak.get('p50_kw')} kW at {peak.get('time')}. "
            f"Uncertainty note: {context.get('band_width_note') or 'none listed'}."
        )
    if "batter" in q or "sav" in q or "cost" in q or "bill" in q:
        return (
            f"The advisory battery plan saves {plan_summary.get('saving')} vs. doing nothing, "
            f"reducing the peak by {plan_summary.get('peak_reduction_kw')} kW. "
            f"Cost before {plan.get('cost_before')} vs. after {plan.get('cost_after')}. "
            "Values use illustrative tariff and battery assumptions; this is advisory only."
        )
    if "accura" in q or "well" in q or "yesterday" in q:
        return (
            f"Last 7 days accuracy from the context: MAE {accuracy.get('mae_kw')} kW, "
            f"skill vs. seasonal naive {accuracy.get('skill_vs_naive')}."
        )
    return (
        f"Run {context.get('run_id')}: next 24 h totals {context.get('total_kwh_next_24h')} kWh. "
        f"Peak P50 {peak.get('p50_kw')} kW at {peak.get('time')}. "
        f"Alerts: {'; '.join(context.get('alerts_summary', [])) or 'none'}. "
        f"Advisory plan saving {plan_summary.get('saving')}. "
        "All numbers come from pre-computed results; advisory only."
    )


def answer_question(
    client: LLMClient,
    question: str,
    context: dict,
    alerts: list,
    plan: dict,
) -> tuple[str, bool]:
    """Return (answer, used_llm). Falls back to the template when the LLM is unavailable."""
    payload = _fmt_context(context, alerts, plan)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt(payload, question)},
    ]
    try:
        return client.chat(messages), True
    except LLMUnavailableError:
        return template_fallback(question, context, alerts, plan), False
