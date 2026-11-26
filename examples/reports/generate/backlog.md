# Horta comunitária

Run `PBD-RUN-6MXFR2V65JFW` · backlog digest `sha256:ad4642d2505b8461165b67399384558ac12863ca26405491e4b5bd6c95d0b595`

> Synthetic content.

## [epic] Reserva de canteiros `PBD-EPIC-BDH3XTJJSB8N`

Objetivo: Organizar o uso dos canteiros por temporada.
Fora do escopo
Pagamentos

Trace: PBD-CLM-PJ9GVFD5M058 (prd.md:4); PBD-CLM-QFCD07SZ7PXK (prd.md:5); PBD-CLM-N2G7KS5Q3FCZ (prd.md:6)

### [feature] Reservar canteiro por temporada `PBD-FEAT-5807A6XR8DRB`

Capacidade: Membros reservam canteiros livres.

Trace: PBD-CLM-PJ9GVFD5M058 (prd.md:4); PBD-CLM-QFCD07SZ7PXK (prd.md:5); PBD-CLM-N2G7KS5Q3FCZ (prd.md:6); PBD-CLM-0P8HY1B00TK7 (adr-001.md:2)

#### [story] Reservar um canteiro livre `PBD-STORY-2Q2DG1M753MX`

Eu como membro, gostaria que o sistema reservasse um canteiro livre, para cultivar durante a temporada.

**Critérios de aceite**

- **CA-01** um canteiro livre na temporada, o membro solicita a reserva: a reserva é registrada
- **CA-02** um canteiro já reservado na temporada, outro membro solicita a reserva: nenhuma nova reserva é criada
- **CA-03** Uma reserva válida é confirmada automaticamente. → reserva confirmada sem aprovação manual

Trace: PBD-CLM-PJ9GVFD5M058 (prd.md:4); PBD-CLM-QFCD07SZ7PXK (prd.md:5); PBD-CLM-0P8HY1B00TK7 (adr-001.md:2)

##### [task] Implementar verificação de disponibilidade `PBD-TASK-DG1DZWFGTN97`

Objetivo: Validar se o canteiro está livre.
Verificação: Teste com canteiro ocupado.

Trace: PBD-CLM-QFCD07SZ7PXK (prd.md:5)

#### [story] Consultar minhas reservas `PBD-STORY-JEJJG2ENRS9B`

Eu como membro, gostaria que ver minhas reservas, para acompanhar a temporada.

**Critérios de aceite**

- **CA-01** A reserva registrada aparece em Minhas reservas. → reserva listada

Trace: PBD-CLM-N2G7KS5Q3FCZ (prd.md:6)

## Questions

- Por quanto tempo uma temporada dura? — Limites da reserva.
