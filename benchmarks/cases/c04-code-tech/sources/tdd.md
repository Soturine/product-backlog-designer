# TDD — Armários de Retirada (fictício)

- Os códigos são gerados pelo serviço locker-api por meio de POST /lockers/{id}/codes.
- Avisos ao morador usam a fila de mensagens "notificacoes" já existente no condomínio.
- O bloqueio por tentativas incorretas é executado pelo firmware do armário; o software apenas registra o evento de bloqueio.
- A consulta de ocupação usa GET /lockers?status=occupied.
