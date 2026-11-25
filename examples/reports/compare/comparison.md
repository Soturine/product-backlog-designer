# Comparison

## left: left.json
- items: 2 {'epic': 1, 'story': 1}; criteria: 2
- covered 2/4, partial 0/4, not covered 2/4
- unmatched items: -
- unsupported: -

## right: right.json
- items: 4 {'epic': 1, 'story': 3}; criteria: 2
- covered 2/4, partial 1/4, not covered 1/4
- unmatched items: R-B4
- unsupported: R-B4

## Mappings

- L-A1 ↔ R-A1 (equivalent, 1:1): mesmo épico
- L-A2 ↔ R-B2, R-B3 (split, 1:N): uma história vs duas

## Obligations

- O1: left COVERED, right COVERED — pode reservar um canteiro livre
- O2: left NOT_COVERED, right COVERED — não aceita nova reserva
- O3: left COVERED, right PARTIALLY_COVERED — Minhas reservas
- O5: left NOT_COVERED, right NOT_COVERED — confirmadas automaticamente

## Findings

- [high] (left) Rejeitar canteiro ocupado. / Sem critério. → Adicionar critério.
- [medium] (right) Pagamentos fora. / História de pagamento. → Remover.
