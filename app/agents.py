"""Four-agent support pipeline with Anthropic and a deterministic local fallback."""
import json
import re
from typing import Any
try:
    from anthropic import Anthropic
except ImportError:  # permite executar o modo local antes de instalar o SDK
    Anthropic = None  # type: ignore[assignment,misc]
from app.config import settings

CATEGORIES = {"financeiro", "suporte_tecnico", "comercial", "rh", "juridico", "geral"}
URGENCIES = {"baixa", "media", "alta", "critica"}
SENTIMENTS = {"neutro", "positivo", "negativo"}

class AgentError(RuntimeError):
    pass

def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise AgentError("O modelo não retornou um objeto JSON válido.")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise AgentError("A resposta do modelo não é um objeto JSON.")
    return value

def _ask_anthropic(system_prompt: str, content: str, max_tokens: int = 500) -> dict[str, Any]:
    if not settings.anthropic_api_key:
        raise AgentError("Chave da Anthropic não configurada.")
    if Anthropic is None:
        raise AgentError("SDK anthropic não instalado. Execute: pip install -r requirements.txt")
    client = Anthropic(api_key=settings.anthropic_api_key, timeout=settings.llm_timeout_seconds, max_retries=0)
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        temperature=0,
        system=system_prompt + " Responda somente com JSON válido, sem markdown.",
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")
    return _extract_json(text)

def _classify_local(subject: str, message: str) -> dict[str, Any]:
    text = f"{subject} {message}".casefold()
    patterns = {
        "juridico": ["vazamento", "dados de clientes", "lgpd", "contrato", "rescisão", "rescisao", "processo judicial", "advogado"],
        "financeiro": ["cobrança", "cobranca", "fatura", "pagamento", "estorno", "reembolso", "boleto", "duplicada"],
        "suporte_tecnico": ["login", "senha", "sistema fora do ar", "erro", "bug", "não funciona", "nao funciona", "acesso"],
        "rh": ["folha de pagamento", "férias", "ferias", "benefício", "beneficio", "rh", "funcionário", "funcionario"],
        "comercial": ["orçamento", "orcamento", "preço", "preco", "plano", "contratar", "vendas"],
    }
    category = next((cat for cat, words in patterns.items() if any(word in text for word in words)), "geral")
    critical_words = ["vazamento", "fraude", "sistema fora do ar", "dados de clientes", "risco à vida", "risco a vida"]
    high_words = ["cobrança duplicada", "cobranca duplicada", "cobrado duas vezes", "cobrada duas vezes", "urgente", "bloqueado", "parado"]
    urgency = "critica" if any(word in text for word in critical_words) else "alta" if any(word in text for word in high_words) else "baixa" if category == "geral" else "media"
    sentiment = "negativo" if any(word in text for word in ["absurdo", "insatisfeito", "péssimo", "pessimo", "não consigo", "nao consigo", "problema", "erro"]) else "positivo" if any(word in text for word in ["obrigado", "obrigada", "excelente", "satisfeito", "satisfeita"]) else "neutro"
    return {"category": category, "urgency": urgency, "sentiment": sentiment, "confidence": 0.88}

def classify_agent(subject: str, message: str) -> tuple[dict[str, Any], bool]:
    try:
        result = _ask_anthropic(
            "Você é o agente classificador de uma central de solicitações. Campos: category (financeiro, suporte_tecnico, comercial, rh, juridico, geral), urgency (baixa, media, alta, critica), sentiment (neutro, positivo, negativo), confidence (0 a 1).",
            f"Assunto: {subject}\nMensagem: {message}", 250,
        )
        if result.get("category") not in CATEGORIES or result.get("urgency") not in URGENCIES or result.get("sentiment") not in SENTIMENTS:
            raise AgentError("Campos fora do vocabulário permitido.")
        result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        return result, True
    except Exception:
        return _classify_local(subject, message), False

def analyze_agent(subject: str, message: str, category: str) -> tuple[dict[str, Any], bool]:
    try:
        result = _ask_anthropic(
            "Você é o agente analista. Produza summary (resumo breve), probable_cause (causa provável sem afirmar fatos não verificados) e recommended_actions (lista de 2 a 4 ações).",
            f"Categoria: {category}\nAssunto: {subject}\nMensagem: {message}", 350,
        )
        actions = result.get("recommended_actions")
        if not isinstance(actions, list) or not actions:
            raise AgentError("A análise não trouxe recommended_actions.")
        return {"summary": str(result.get("summary", message))[:500], "probable_cause": str(result.get("probable_cause", "Requer verificação da equipe."))[:500], "recommended_actions": [str(a)[:250] for a in actions[:4]]}, True
    except Exception:
        actions = {
            "financeiro": ["Conferir o histórico de cobranças do cliente", "Validar duplicidade ou valor indevido", "Solicitar estorno ou ajuste, se confirmado"],
            "juridico": ["Preservar evidências relevantes", "Encaminhar ao setor Jurídico para avaliação", "Avaliar obrigações legais aplicáveis"],
            "suporte_tecnico": ["Reproduzir o problema", "Verificar logs e permissões", "Registrar resultado da investigação"],
        }.get(category, ["Validar os dados informados", "Identificar a equipe responsável", "Registrar a solução adotada"])
        return {"summary": message.strip()[:500], "probable_cause": "Não determinada automaticamente; requer verificação da equipe.", "recommended_actions": actions}, False

def response_agent(name: str, subject: str, message: str, summary: str, protocol: str) -> tuple[str, bool]:
    try:
        result = _ask_anthropic(
            "Você é o agente respondente de atendimento. Escreva uma resposta cordial em português brasileiro. Não afirme que houve reembolso, correção ou investigação concluída se isso não foi confirmado. Inclua o protocolo informado.",
            f"Nome: {name}\nAssunto: {subject}\nMensagem: {message}\nResumo: {summary}\nProtocolo: {protocol}\nRetorne JSON com o campo reply.", 300,
        )
        reply = str(result.get("reply", "")).strip()
        if not reply:
            raise AgentError("Resposta vazia.")
        return reply[:2500], True
    except Exception:
        return (f"Olá, {name}! Obrigado pelo contato. Recebemos sua solicitação e nossa equipe irá verificar as informações antes de confirmar qualquer ação. Seu protocolo é {protocol}. Atenciosamente, equipe NexusAI."), False

def route_agent(category: str, urgency: str) -> tuple[dict[str, Any], bool]:
    departments = {
        "financeiro": ("Financeiro", 4), "suporte_tecnico": ("Suporte Técnico", 4),
        "comercial": ("Comercial", 24), "rh": ("Recursos Humanos", 24),
        "juridico": ("Jurídico", 4), "geral": ("Atendimento Geral", 24),
    }
    try:
        result = _ask_anthropic(
            "Você é o agente roteador. Escolha department em Financeiro, Suporte Técnico, Comercial, Recursos Humanos, Jurídico, Atendimento Geral; retorne sla_hours inteiro (1, 4, 24) e status encaminhado ou escalado.",
            f"Categoria: {category}\nUrgência: {urgency}", 200,
        )
        allowed = {"Financeiro", "Suporte Técnico", "Comercial", "Recursos Humanos", "Jurídico", "Atendimento Geral"}
        if result.get("department") not in allowed or result.get("status") not in {"encaminhado", "escalado"}:
            raise AgentError("Roteamento inválido.")
        result["sla_hours"] = max(1, min(72, int(result.get("sla_hours", 24))))
        if urgency == "critica":
            result["status"] = "escalado"
        return result, True
    except Exception:
        department, standard_sla = departments.get(category, ("Atendimento Geral", 24))
        return {"department": department, "sla_hours": 1 if urgency == "critica" else standard_sla, "status": "escalado" if urgency == "critica" else "encaminhado"}, False
