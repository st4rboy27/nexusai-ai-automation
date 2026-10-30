from pydantic import BaseModel, ConfigDict, Field
from typing import Any

class RequestIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    subject: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=10, max_length=10000)

class AgentStep(BaseModel):
    agent: str
    output: dict[str, Any]
    used_llm: bool
    duration_ms: float
    error: str | None = None

class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    protocol: str
    created_at: str
    source: str
    name: str
    email: str
    subject: str
    message: str
    category: str
    urgency: str
    priority: int
    sentiment: str
    confidence: float
    summary: str
    analysis: dict[str, Any]
    reply: str
    department: str
    sla_hours: int
    status: str
    used_llm: bool
    processing_ms: float
    trace: list[dict[str, Any]]
