"""Fictitious notification helper (implementation evidence snapshot)."""
QUEUE = "notificacoes"


def build_message(resident_id: str, code: str) -> dict:
    return {"queue": QUEUE, "to": resident_id, "text": f"Seu código de retirada é {code}"}
