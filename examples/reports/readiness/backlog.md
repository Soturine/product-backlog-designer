# Biblioteca do bairro

Run `PBD-RUN-R3C50QRRHV1P` · backlog digest `sha256:268ec07b7ab738a53c2eec52709977caf743d01f95636ddc6faf63e8978c2843`

> Synthetic content.

## [epic] Empréstimos da biblioteca do bairro `PBD-EPIC-JJBBNJM0G3HW`

Objetivo: Leitores emprestam, renovam e acompanham livros.
Fora do escopo
Multas por atraso

Trace: PBD-CLM-X6BDAS7PZ67G (prd.md:4); PBD-CLM-38FK6BWZNBTN (prd.md:5); PBD-CLM-612R97A5W5ZP (prd.md:6); PBD-CLM-3T1ETZBPXBC6 (prd.md:7); PBD-CLM-YZM4925E7NX5 (prd.md:9); PBD-CLM-BM1VH63GJGT7 (prd.md:10); PBD-CLM-FMEVD0K6S75G (prd.md:12)

### [feature] Empréstimo e renovação `PBD-FEAT-BB1Q3N8BCTVS`

Capacidade: Emprestar, renovar e consultar empréstimos no balcão.

Trace: PBD-CLM-X6BDAS7PZ67G (prd.md:4); PBD-CLM-38FK6BWZNBTN (prd.md:5); PBD-CLM-612R97A5W5ZP (prd.md:6); PBD-CLM-3T1ETZBPXBC6 (prd.md:7)

#### [story] Emprestar livros no balcão `PBD-STORY-CFJG10WJE8TY`

Eu como leitor, gostaria que o sistema registrasse o empréstimo com a data de devolução, para levar os livros para casa.

**Critérios de aceite**

- **CA-01** um leitor com 3 empréstimos ativos, ele tenta emprestar outro livro: o empréstimo é recusado
- **CA-02** um empréstimo registrado hoje, o sistema calcula a devolução: a devolução fica em 14 dias

Trace: PBD-CLM-X6BDAS7PZ67G (prd.md:4); PBD-CLM-38FK6BWZNBTN (prd.md:5)

##### [task] Validar o limite de empréstimos ativos `PBD-TASK-B03M89G4XBG0`

Objetivo: Recusar um quarto empréstimo ativo.
Verificação: Teste com leitor que já tem 3 empréstimos.

Trace: PBD-CLM-X6BDAS7PZ67G (prd.md:4)

##### [task] Registrar o empréstimo com devolução em 14 dias `PBD-TASK-9EFZCXJF6ET7`

Objetivo: Calcular a data de devolução.
Verificação: Teste da data calculada.

Trace: PBD-CLM-38FK6BWZNBTN (prd.md:5)

#### [story] Renovar um empréstimo `PBD-STORY-2DVGB62J6NBB`

Eu como leitor, gostaria que o sistema renovasse meu empréstimo uma vez, para ficar mais tempo com o livro.

**Critérios de aceite**

- **CA-01** um empréstimo sem reserva e sem renovação, o leitor pede a renovação: o empréstimo é renovado
- **CA-02** um empréstimo já renovado, o leitor pede outra renovação: a renovação é recusada

Trace: PBD-CLM-612R97A5W5ZP (prd.md:6)

##### [task] Renovar uma vez quando não houver reserva `PBD-TASK-G524XWR2WQBW`

Objetivo: Permitir uma renovação e recusar livro reservado.
Verificação: Testes de segunda renovação e de livro reservado.

Trace: PBD-CLM-612R97A5W5ZP (prd.md:6)

#### [story] Ver meus empréstimos `PBD-STORY-68WXA0TWX6G6`

Eu como leitor, gostaria que o sistema mostrasse meus empréstimos e as datas, para devolver no prazo.

**Critérios de aceite**

- **CA-01** A lista mostra cada livro emprestado com sua data de devolução. → livros e datas listados

Trace: PBD-CLM-3T1ETZBPXBC6 (prd.md:7)

##### [task] Listar empréstimos com as datas de devolução `PBD-TASK-3V5TWDKK57WQ`

Objetivo: Consultar empréstimos ativos do leitor.
Verificação: Teste com dois empréstimos ativos.

Trace: PBD-CLM-3T1ETZBPXBC6 (prd.md:7)

### [feature] Quiosque de autoatendimento `PBD-FEAT-HDPFHDPRPJ8D`

Capacidade: Emprestar sem atendente, lendo o cartão do leitor.

Trace: PBD-CLM-YZM4925E7NX5 (prd.md:9); PBD-CLM-BM1VH63GJGT7 (prd.md:10)

#### [story] Emprestar pelo quiosque `PBD-STORY-Y2G59AESDQYC`

Eu como leitor, gostaria que o quiosque registrasse o empréstimo ao ler meu cartão, para emprestar sem esperar atendimento.

**Critérios de aceite**

- **CA-01** um cartão de leitor válido no quiosque, o cartão é lido: o empréstimo é registrado para o leitor

Trace: PBD-CLM-YZM4925E7NX5 (prd.md:9); PBD-CLM-BM1VH63GJGT7 (prd.md:10)

##### [task] Integrar o driver do leitor de cartões `PBD-TASK-EYZQ67WBBK24`

Objetivo: Ler o cartão pelo driver do modelo escolhido.
Verificação: Teste com o leitor físico escolhido.

Trace: PBD-CLM-BM1VH63GJGT7 (prd.md:10)

##### [task] Fluxo do quiosque com leitura de cartão simulada `PBD-TASK-2A8T8MYBTDWK`

Objetivo: Construir o fluxo sobre um contrato simulado do leitor.
Verificação: Teste do fluxo com o simulador de cartão.

Trace: PBD-CLM-YZM4925E7NX5 (prd.md:9)

##### [spike] Comparar os modelos candidatos de leitor de cartões `PBD-SPIKE-948DDGYCFXHB`

Pergunta a responder: Quais modelos atendem ao quiosque e com que protocolo?
Decisão esperada: Recomendação para a escolha do modelo.

Trace: PBD-CLM-BM1VH63GJGT7 (prd.md:10)

### [feature] Avisos de vencimento `PBD-FEAT-261409PP108H`

Capacidade: Avisar o leitor antes do vencimento.

Trace: PBD-CLM-FMEVD0K6S75G (prd.md:12)

#### [story] Receber aviso antes do vencimento `PBD-STORY-6DWQ9Y1QNDVP`

Eu como leitor, gostaria que o sistema me avisasse antes do vencimento, para não atrasar a devolução.

**Critérios de aceite**

- **CA-01** O aviso chega antes do vencimento com a antecedência definida. → aviso enviado antes do vencimento

Trace: PBD-CLM-FMEVD0K6S75G (prd.md:12)

##### [task] Agendar o aviso de vencimento `PBD-TASK-XQ9RARSCVA8P`

Objetivo: Agendar o aviso com antecedência parametrizada.
Verificação: Teste do agendamento com antecedência configurada.

Trace: PBD-CLM-FMEVD0K6S75G (prd.md:12)

## Questions

- Qual modelo de leitor de cartões o quiosque usará? — Sem o modelo, o driver não pode ser integrado.
- Quanto tempo antes do vencimento o aviso deve chegar? — Define a antecedência do aviso.
