def payload(subject="Cobrança duplicada", message="Fui cobrado duas vezes pelo mesmo pedido e preciso de ajuda para resolver."):
    return {"name": "Cliente Teste", "email": "teste@example.com", "subject": subject, "message": message}

def test_health_without_llm(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["llm_enabled"] is False

def test_create_request_runs_four_agents_and_records_time(client):
    response = client.post("/api/requests?source=api", json=payload())
    assert response.status_code == 201
    item = response.json()
    assert item["category"] == "financeiro"
    assert item["urgency"] == "alta"
    assert item["department"] == "Financeiro"
    assert item["processing_ms"] > 0
    assert [step["agent"] for step in item["trace"]] == ["classificador", "analista", "respondente", "roteador"]
    assert item["used_llm"] is False

def test_critical_data_leak_routes_to_legal(client):
    response = client.post("/api/requests", json=payload("Possível vazamento de dados", "Identificamos um possível vazamento de dados de clientes e precisamos avaliar a gravidade."))
    assert response.status_code == 201
    item = response.json()
    assert item["category"] == "juridico"
    assert item["urgency"] == "critica"
    assert item["department"] == "Jurídico"
    assert item["status"] == "escalado"
    assert item["priority"] == 1

def test_list_and_get_by_id(client):
    created = client.post("/api/requests", json=payload()).json()
    listed = client.get("/api/requests?limit=10&offset=0")
    assert listed.status_code == 200
    assert any(row["id"] == created["id"] for row in listed.json())
    fetched = client.get(f"/api/requests/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["protocol"] == created["protocol"]

def test_get_missing_request_returns_404(client):
    response = client.get("/api/requests/99999")
    assert response.status_code == 404

def test_invalid_request_returns_422(client):
    response = client.post("/api/requests", json={"name": "x", "email": "a", "subject": "x", "message": "short"})
    assert response.status_code == 422

def test_summary_counts_created_requests_and_time(client):
    client.post("/api/requests", json=payload())
    response = client.get("/api/reports/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["avg_processing_ms"] > 0
    assert body["by_category"]["financeiro"] == 1

def test_csv_export_has_attachment_and_header(client):
    client.post("/api/requests", json=payload())
    response = client.get("/api/reports/export.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment; filename=atendimentos.csv" in response.headers["content-disposition"]
    assert "protocol" in response.text

def test_json_export_contains_full_request(client):
    created = client.post("/api/requests", json=payload()).json()
    response = client.get("/api/reports/export.json")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert "attachment; filename=atendimentos.json" in response.headers["content-disposition"]
    assert created["protocol"] in response.text
