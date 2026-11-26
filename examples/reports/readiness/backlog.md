# Biblioteca do bairro

Run `PBD-RUN-22SJ2ZKQY1JD` · backlog digest `sha256:8071e8c29c1f8e461fa717aceca403da2a49ea0875b36b7f17190605320a43a2`

> Synthetic content.

## [epic] Empréstimos da biblioteca do bairro `PBD-EPIC-QY976CEAC4DM`

Objetivo: Leitores emprestam, renovam e acompanham livros.
Fora do escopo
Multas por atraso

Trace: PBD-CLM-XHZ0168EZBAV (prd.md:4); PBD-CLM-T2HJF2PNCDY0 (prd.md:5); PBD-CLM-0V5GFQCAEEG7 (prd.md:6); PBD-CLM-RN9ZK0DMNW0H (prd.md:7); PBD-CLM-6CSJZYW4QBHS (prd.md:9); PBD-CLM-9YQKSJ44W6FD (prd.md:10); PBD-CLM-7SQAQ6EKRRZ1 (prd.md:12)

### [feature] Empréstimo e renovação `PBD-FEAT-PY2FQJZF0N83`

Capacidade: Emprestar, renovar e consultar empréstimos no balcão.

Trace: PBD-CLM-XHZ0168EZBAV (prd.md:4); PBD-CLM-T2HJF2PNCDY0 (prd.md:5); PBD-CLM-0V5GFQCAEEG7 (prd.md:6); PBD-CLM-RN9ZK0DMNW0H (prd.md:7)

#### [story] Emprestar livros no balcão `PBD-STORY-FC41YFYWKJNM`

Eu como leitor, gostaria que o sistema registrasse o empréstimo com a data de devolução, para levar os livros para casa.

**Critérios de aceite**

- **CA-01** um leitor com 3 empréstimos ativos, ele tenta emprestar outro livro: o empréstimo é recusado
- **CA-02** um empréstimo registrado hoje, o sistema calcula a devolução: a devolução fica em 14 dias

Trace: PBD-CLM-XHZ0168EZBAV (prd.md:4); PBD-CLM-T2HJF2PNCDY0 (prd.md:5)

##### [task] Validar o limite de empréstimos ativos `PBD-TASK-PGGNDMJX0VQG`

Objetivo: Recusar um quarto empréstimo ativo.
Verificação: Teste com leitor que já tem 3 empréstimos.

Trace: PBD-CLM-XHZ0168EZBAV (prd.md:4)

##### [task] Registrar o empréstimo com devolução em 14 dias `PBD-TASK-7J1F7DBVJFAY`

Objetivo: Calcular a data de devolução.
Verificação: Teste da data calculada.

Trace: PBD-CLM-T2HJF2PNCDY0 (prd.md:5)

#### [story] Renovar um empréstimo `PBD-STORY-FXSEKWKGJGDZ`

Eu como leitor, gostaria que o sistema renovasse meu empréstimo uma vez, para ficar mais tempo com o livro.

**Critérios de aceite**

- **CA-01** um empréstimo sem reserva e sem renovação, o leitor pede a renovação: o empréstimo é renovado
- **CA-02** um empréstimo já renovado, o leitor pede outra renovação: a renovação é recusada

Trace: PBD-CLM-0V5GFQCAEEG7 (prd.md:6)

##### [task] Renovar uma vez quando não houver reserva `PBD-TASK-KC1WV0Y38JK7`

Objetivo: Permitir uma renovação e recusar livro reservado.
Verificação: Testes de segunda renovação e de livro reservado.

Trace: PBD-CLM-0V5GFQCAEEG7 (prd.md:6)

#### [story] Ver meus empréstimos `PBD-STORY-D7NGBMMA56WA`

Eu como leitor, gostaria que o sistema mostrasse meus empréstimos e as datas, para devolver no prazo.

**Critérios de aceite**

- **CA-01** A lista mostra cada livro emprestado com sua data de devolução. → livros e datas listados

Trace: PBD-CLM-RN9ZK0DMNW0H (prd.md:7)

##### [task] Listar empréstimos com as datas de devolução `PBD-TASK-G9WX7HETSHMR`

Objetivo: Consultar empréstimos ativos do leitor.
Verificação: Teste com dois empréstimos ativos.

Trace: PBD-CLM-RN9ZK0DMNW0H (prd.md:7)

### [feature] Quiosque de autoatendimento `PBD-FEAT-ZFAMEH6SWQJ6`

Capacidade: Emprestar sem atendente, lendo o cartão do leitor.

Trace: PBD-CLM-6CSJZYW4QBHS (prd.md:9); PBD-CLM-9YQKSJ44W6FD (prd.md:10)

#### [story] Emprestar pelo quiosque `PBD-STORY-WVQ1N83DN287`

Eu como leitor, gostaria que o quiosque registrasse o empréstimo ao ler meu cartão, para emprestar sem esperar atendimento.

**Critérios de aceite**

- **CA-01** um cartão de leitor válido no quiosque, o cartão é lido: o empréstimo é registrado para o leitor

Trace: PBD-CLM-6CSJZYW4QBHS (prd.md:9); PBD-CLM-9YQKSJ44W6FD (prd.md:10)

##### [task] Integrar o driver do leitor de cartões `PBD-TASK-19BSK3PQBHQP`

Objetivo: Ler o cartão pelo driver do modelo escolhido.
Verificação: Teste com o leitor físico escolhido.

Trace: PBD-CLM-9YQKSJ44W6FD (prd.md:10)

##### [task] Fluxo do quiosque com leitura de cartão simulada `PBD-TASK-Q15FSGX9V19A`

Objetivo: Construir o fluxo sobre um contrato simulado do leitor.
Verificação: Teste do fluxo com o simulador de cartão.

Trace: PBD-CLM-6CSJZYW4QBHS (prd.md:9)

##### [spike] Comparar os modelos candidatos de leitor de cartões `PBD-SPIKE-WCFGNQ9WPT89`

Pergunta a responder: Quais modelos atendem ao quiosque e com que protocolo?
Decisão esperada: Recomendação para a escolha do modelo.

Trace: PBD-CLM-9YQKSJ44W6FD (prd.md:10)

### [feature] Avisos de vencimento `PBD-FEAT-KKJ4FMFPJN03`

Capacidade: Avisar o leitor antes do vencimento.

Trace: PBD-CLM-7SQAQ6EKRRZ1 (prd.md:12)

#### [story] Receber aviso antes do vencimento `PBD-STORY-69QRZCN6V4RX`

Eu como leitor, gostaria que o sistema me avisasse antes do vencimento, para não atrasar a devolução.

**Critérios de aceite**

- **CA-01** O aviso chega antes do vencimento com a antecedência definida. → aviso enviado antes do vencimento

Trace: PBD-CLM-7SQAQ6EKRRZ1 (prd.md:12)

##### [task] Agendar o aviso de vencimento `PBD-TASK-5MWVTZM0FRVJ`

Objetivo: Agendar o aviso com antecedência parametrizada.
Verificação: Teste do agendamento com antecedência configurada.

Trace: PBD-CLM-7SQAQ6EKRRZ1 (prd.md:12)

## Questions

- Qual modelo de leitor de cartões o quiosque usará? — Sem o modelo, o driver não pode ser integrado.
- Quanto tempo antes do vencimento o aviso deve chegar? — Define a antecedência do aviso.
