# Horta comunitária

Run `PBD-RUN-PCVSY8VJDPW9` · backlog digest `sha256:17af3714b6f771182a541ed55f63518a06628f038e6e9f42b0b5704ba47e3907`

> Synthetic content.

## [epic] Reserva de canteiros `PBD-EPIC-CZ3FR06Y1GWF`

Objetivo: Organizar o uso dos canteiros por temporada.
Fora do escopo
Pagamentos

Trace: PBD-CLM-AH3D7NWYB9KY (prd.md:4); PBD-CLM-4DXZ717CK17R (prd.md:5); PBD-CLM-PAPX707T6B4A (prd.md:6)

### [feature] Reservar canteiro por temporada `PBD-FEAT-G4TJW4S1ERWV`

Capacidade: Membros reservam canteiros livres.

Trace: PBD-CLM-AH3D7NWYB9KY (prd.md:4); PBD-CLM-4DXZ717CK17R (prd.md:5); PBD-CLM-PAPX707T6B4A (prd.md:6); PBD-CLM-Y51KHPXB54HB (adr-001.md:2)

#### [story] Reservar um canteiro livre `PBD-STORY-35FJXKSC6W0M`

Eu como membro, gostaria que o sistema reservasse um canteiro livre, para cultivar durante a temporada.

**Critérios de aceite**

- **CA-01** um canteiro livre na temporada, o membro solicita a reserva: a reserva é registrada
- **CA-02** um canteiro já reservado na temporada, outro membro solicita a reserva: nenhuma nova reserva é criada
- **CA-03** Uma reserva válida é confirmada automaticamente. → reserva confirmada sem aprovação manual

Trace: PBD-CLM-AH3D7NWYB9KY (prd.md:4); PBD-CLM-4DXZ717CK17R (prd.md:5); PBD-CLM-Y51KHPXB54HB (adr-001.md:2)

##### [task] Implementar verificação de disponibilidade `PBD-TASK-3NXWJZE4MCHJ`

Objetivo: Validar se o canteiro está livre.
Verificação: Teste com canteiro ocupado.

Trace: PBD-CLM-4DXZ717CK17R (prd.md:5)

#### [story] Consultar minhas reservas `PBD-STORY-79579F7FEWHG`

Eu como membro, gostaria que ver minhas reservas, para acompanhar a temporada.

**Critérios de aceite**

- **CA-01** A reserva registrada aparece em Minhas reservas. → reserva listada

Trace: PBD-CLM-PAPX707T6B4A (prd.md:6)

## Questions

- Por quanto tempo uma temporada dura? — Limites da reserva.
