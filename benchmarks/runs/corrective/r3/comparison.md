# Comparison

## left: left.json
- items: 5 {'epic': 1, 'story': 4}; criteria: 4
- covered 2/6, partial 2/6, not covered 1/6
- unmatched items: L-QL-4
- unsupported: L-QL-3, L-QL-3.AC1

## right: right.json
- items: 5 {'epic': 1, 'story': 4}; criteria: 4
- covered 2/6, partial 2/6, not covered 1/6
- unmatched items: R-QR-13
- unsupported: R-QR-12, R-QR-12.AC1, R-QR-13, R-QR-13.AC1

## Mappings

- L-QL-1 ↔ R-QR-10 (equivalent, 1:1): Épicos de contêiner.
- L-QL-2 ↔ R-QR-11 (overlap, 1:1): Ambos reservam em blocos de 1h; só a direita inclui o limite de 2.
- L-QL-3 ↔ R-QR-14 (divergent, 1:1): Ambos cancelam; esquerda fixa 24h, direita sem critérios.
- L-QL-5 ↔ R-QR-12 (divergent, 1:1): Catraca: esquerda registra dependência; direita inventa QR code e API REST.

## Obligations

- O1: left COVERED, right COVERED — Reservar quadra livre em blocos de 1 hora, entre 7h e 22h
- O2: left NOT_COVERED, right COVERED — Máximo de 2 reservas futuras por sócio ao mesmo tempo
- O3: left PARTIALLY_COVERED, right PARTIALLY_COVERED — Cancelar reserva; antecedência mínima ainda indefinida pela diretoria
- O4: left PARTIALLY_COVERED, right PARTIALLY_COVERED — Entrar pela catraca usando a reserva; API do fornecedor ainda sem documentação
- O5: left COVERED, right NOT_COVERED — Recepção vê a agenda do dia de cada quadra
- O6: left OUT_OF_SCOPE, right CONFLICTING — Cobrança de reservas está fora do escopo

## Findings

- [high] (left) Critério de no máximo 2 reservas futuras por sócio / Ausente → Acrescentar critério à história de reserva
- [medium] (left) Antecedência mínima indefinida, a ser decidida pela diretoria / Critério fixa 24 horas → Trocar por pergunta aberta
- [high] (right) História da agenda do dia da recepção / Ausente → Acrescentar história
- [high] (right) Integração com catraca dependente da API ainda não documentada / QR code e API REST do fornecedor afirmados → Remover o critério e registrar a dependência
- [high] (right) Cobrança fora do escopo / História de cobrança no cartão → Remover a história
- [medium] (right) Cancelamento com a antecedência registrada como pergunta aberta / História sem critérios → Adicionar critérios e a pergunta aberta
