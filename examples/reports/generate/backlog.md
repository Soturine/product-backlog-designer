# Horta comunitária

Run `PBD-RUN-2WZ6HVYX4GHG` · backlog digest `sha256:0712d2b25d6d9eb821390abdbc05fe3a44dd3931a7a1be24fa415705ca3aac02`

> Synthetic content.

## [epic] Reserva de canteiros `PBD-EPIC-NPEKP6TM4SYP`

Objetivo: Organizar o uso dos canteiros por temporada.
Fora do escopo
Pagamentos

Trace: PBD-CLM-8H4R0QRRZ99D (prd.md:4); PBD-CLM-5KKW0VR5HD9Y (prd.md:5); PBD-CLM-CWZDC8EVK1DQ (prd.md:6)

### [feature] Reservar canteiro por temporada `PBD-FEAT-TNMSCKNXVM6R`

Capacidade: Membros reservam canteiros livres.

Trace: PBD-CLM-8H4R0QRRZ99D (prd.md:4); PBD-CLM-5KKW0VR5HD9Y (prd.md:5); PBD-CLM-CWZDC8EVK1DQ (prd.md:6); PBD-CLM-9R4MSBKVHWVW (adr-001.md:2)

#### [story] Reservar um canteiro livre `PBD-STORY-FEMXQJK1YJE7`

Eu como membro, gostaria que o sistema reservasse um canteiro livre, para cultivar durante a temporada.

**Critérios de aceite**

- **CA-01** um canteiro livre na temporada, o membro solicita a reserva: a reserva é registrada
- **CA-02** um canteiro já reservado na temporada, outro membro solicita a reserva: nenhuma nova reserva é criada
- **CA-03** Uma reserva válida é confirmada automaticamente. → reserva confirmada sem aprovação manual

Trace: PBD-CLM-8H4R0QRRZ99D (prd.md:4); PBD-CLM-5KKW0VR5HD9Y (prd.md:5); PBD-CLM-9R4MSBKVHWVW (adr-001.md:2)

##### [task] Implementar verificação de disponibilidade `PBD-TASK-89WYNHWHZ9HT`

Objetivo: Validar se o canteiro está livre.
Verificação: Teste com canteiro ocupado.

Trace: PBD-CLM-5KKW0VR5HD9Y (prd.md:5)

#### [story] Consultar minhas reservas `PBD-STORY-YRP8WV3Y8NS2`

Eu como membro, gostaria que ver minhas reservas, para acompanhar a temporada.

**Critérios de aceite**

- **CA-01** A reserva registrada aparece em Minhas reservas. → reserva listada

Trace: PBD-CLM-CWZDC8EVK1DQ (prd.md:6)

## Questions

- Por quanto tempo uma temporada dura? — Limites da reserva.
