"""FastAPI entry point for NexusAI."""
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
try:
    from anthropic import Anthropic
except ImportError:  # permite executar o modo local antes de instalar o SDK
    Anthropic = None  # type: ignore[assignment,misc]
from app.config import settings, PROJECT_ROOT
from app.database import connection, get_request, list_requests, all_requests
from app.schemas import RequestIn, RequestOut
from app.service import process_request

app = FastAPI(title="NexusAI", version="1.0.0", description="Triagem e atendimento inteligente de solicitações com quatro agentes de IA.")
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/health")
def health(check_llm: bool = Query(False, description="Faz uma chamada mínima à Anthropic quando true")):
    configured = bool(settings.anthropic_api_key)
    result = {"status": "ok", "llm_enabled": configured, "model": settings.anthropic_model}
    if not check_llm:
        return result
    if not configured:
        result.update({"llm_reachable": False, "llm_error": "ANTHROPIC_API_KEY não configurada no ambiente ou arquivo .env."})
        return result
    try:
        if Anthropic is None:
            raise RuntimeError("SDK anthropic não instalado. Execute: pip install -r requirements.txt")
        client = Anthropic(api_key=settings.anthropic_api_key, timeout=settings.llm_timeout_seconds, max_retries=0)
        client.messages.create(model=settings.anthropic_model, max_tokens=8, temperature=0,
                               messages=[{"role": "user", "content": "Responda apenas: OK"}])
        result.update({"llm_reachable": True, "llm_error": None})
    except Exception as exc:
        result.update({"llm_reachable": False, "llm_error": f"{type(exc).__name__}: {str(exc)[:300]}"})
    return result

@app.post("/api/requests", response_model=RequestOut, status_code=201)
def create_request(payload: RequestIn, source: str = Query("api", pattern="^(api|form)$")):
    return process_request(payload, source=source)

@app.get("/api/requests", response_model=list[RequestOut])
def get_requests(category: str | None = None, urgency: str | None = None,
                 department: str | None = None, limit: int = Query(50, ge=1, le=200),
                 offset: int = Query(0, ge=0)):
    return list_requests(category=category, urgency=urgency, department=department, limit=limit, offset=offset)

@app.get("/api/requests/{ticket_id}", response_model=RequestOut)
def get_request_by_id(ticket_id: int):
    item = get_request(ticket_id)
    if not item:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    return item

@app.get("/api/reports/summary")
def report_summary():
    rows = all_requests()
    now = datetime.now(timezone.utc)
    recent = []
    for row in rows:
        try:
            created = datetime.fromisoformat(row["created_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created >= now - timedelta(hours=24):
                recent.append(row)
        except (TypeError, ValueError):
            pass
    def count_by(key):
        result = {}
        for row in rows:
            result[row[key]] = result.get(row[key], 0) + 1
        return result
    dept_groups: dict[str, list[dict]] = {}
    daily: dict[str, int] = {}
    for row in rows:
        dept_groups.setdefault(row["department"], []).append(row)
        day = str(row["created_at"])[:10]
        daily[day] = daily.get(day, 0) + 1
    dept_load = [{"department": dep, "avg_priority": round(sum(x["priority"] for x in group) / len(group), 2), "n": len(group)} for dep, group in sorted(dept_groups.items())]
    durations = [float(r["processing_ms"]) for r in rows]
    confidence = [float(r["confidence"]) for r in rows]
    return {
        "total": len(rows), "last_24h": len(recent),
        "priority_1_count": sum(1 for r in rows if r["priority"] == 1),
        "avg_processing_ms": round(sum(durations) / len(durations), 3) if durations else 0.0,
        "avg_confidence": round(sum(confidence) / len(confidence), 3) if confidence else 0.0,
        "llm_share": round(sum(1 for r in rows if r["used_llm"]) / len(rows), 3) if rows else 0.0,
        "by_category": count_by("category"), "by_urgency": count_by("urgency"),
        "by_priority": {str(k): v for k, v in sorted(count_by("priority").items())},
        "by_sentiment": count_by("sentiment"), "by_department": count_by("department"),
        "department_load": dept_load,
        "daily_volume": [{"day": d, "n": daily[d]} for d in sorted(daily)],
    }

@app.get("/api/reports/export.csv")
def export_csv():
    rows = all_requests()
    buffer = io.StringIO(newline="")
    fields = ["id", "protocol", "created_at", "source", "name", "email", "subject", "message", "category", "urgency", "priority", "sentiment", "confidence", "summary", "reply", "department", "sla_hours", "status", "used_llm", "processing_ms"]
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(content="\ufeff" + buffer.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=atendimentos.csv"})

@app.get("/api/reports/export.json")
def export_json():
    rows = all_requests()
    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    return Response(content=payload, media_type="application/json; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=atendimentos.json"})
