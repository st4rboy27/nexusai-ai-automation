"""Orchestrates the request pipeline and records per-agent timing."""
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4
from typing import Any
from app.agents import classify_agent, analyze_agent, response_agent, route_agent
from app.database import insert_request
from app.schemas import RequestIn

def process_request(payload: RequestIn | dict[str, Any], source: str = "api", force_local: bool = False) -> dict[str, Any]:
    if isinstance(payload, dict):
        data = payload
    else:
        data = payload.model_dump()
    started = perf_counter()
    protocol = f"NX-{uuid4().hex[:8].upper()}"
    trace: list[dict[str, Any]] = []

    def record(agent: str, fn, *args):
        t0 = perf_counter()
        # force_local is useful for deterministic seed data and tests; agents fall back naturally without a key.
        if force_local:
            from app.config import settings
            original = settings.anthropic_api_key
            settings.anthropic_api_key = ""
            try:
                output, used_llm = fn(*args)
            finally:
                settings.anthropic_api_key = original
        else:
            output, used_llm = fn(*args)
        duration = max(0.001, round((perf_counter() - t0) * 1000, 3))
        trace.append({"agent": agent, "output": output if isinstance(output, dict) else {"reply": output}, "used_llm": used_llm, "duration_ms": duration})
        return output, used_llm

    classified, llm1 = record("classificador", classify_agent, data["subject"], data["message"])
    analysis, llm2 = record("analista", analyze_agent, data["subject"], data["message"], classified["category"])
    reply, llm3 = record("respondente", response_agent, data["name"], data["subject"], data["message"], analysis["summary"], protocol)
    routed, llm4 = record("roteador", route_agent, classified["category"], classified["urgency"])

    priority_map = {"critica": 1, "alta": 2, "media": 3, "baixa": 4}
    priority = priority_map[classified["urgency"]]
    processing_ms = max(0.001, round((perf_counter() - started) * 1000, 3))
    output = {
        "protocol": protocol,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "name": data["name"], "email": data["email"], "subject": data["subject"], "message": data["message"],
        "category": classified["category"], "urgency": classified["urgency"], "priority": priority,
        "sentiment": classified["sentiment"], "confidence": float(classified["confidence"]),
        "summary": analysis["summary"], "analysis": analysis, "reply": reply,
        "department": routed["department"], "sla_hours": routed["sla_hours"], "status": routed["status"],
        "used_llm": any((llm1, llm2, llm3, llm4)), "processing_ms": processing_ms, "trace": trace,
    }
    return insert_request(output)
