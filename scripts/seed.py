"""Create sample requests locally without calling the paid LLM API."""
import argparse
from app.schemas import RequestIn
from app.service import process_request

SAMPLES = [
    ("Cobrança duplicada", "Fui cobrado duas vezes pelo mesmo pedido e preciso de ajuda para resolver."),
    ("Sistema fora do ar", "O sistema está fora do ar para toda a equipe e precisamos de suporte urgente."),
    ("Possível vazamento de dados", "Identificamos um possível vazamento de dados de clientes e precisamos avaliar a gravidade."),
    ("Dúvida sobre contratação", "Gostaria de conhecer os planos disponíveis e solicitar informações comerciais."),
    ("Solicitação de férias", "Preciso verificar como solicitar minhas férias e consultar as regras de RH."),
    ("Dúvida geral", "Gostaria de entender como funciona o serviço e quais são as etapas para começar."),
]
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("count", nargs="?", type=int, default=20, help="Quantidade de solicitações de exemplo (padrão: 20)")
    args = parser.parse_args()
    if not 1 <= args.count <= 5000:
        parser.error("count deve ser entre 1 e 5000")
    for i in range(args.count):
        subject, message = SAMPLES[i % len(SAMPLES)]
        payload = RequestIn(name=f"Cliente Demo {i+1:03d}", email=f"cliente{i+1:03d}@example.com", subject=subject, message=message)
        process_request(payload, source="seed", force_local=True)
    print(f"{args.count} solicitações de exemplo processadas e registradas (modo local; sem chamadas à Anthropic).")
if __name__ == "__main__":
    main()
