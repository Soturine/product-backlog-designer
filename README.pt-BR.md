# Product Backlog Designer (PBD)

**Dos requisitos a backlogs de produto rastreáveis, revisáveis e acionáveis.**

![versão 0.9.0](https://img.shields.io/badge/versão-0.9.0-blue) ![python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) ![licença Apache-2.0](https://img.shields.io/badge/licença-Apache--2.0-green) ![trackers: pacote local e mock](https://img.shields.io/badge/trackers-local%20%2B%20mock-lightgrey)

[English](README.md) · [Documentação](docs/README.md) · [Relatórios de exemplo](examples/reports/README.md) · [Ledger de qualificação](benchmarks/qualification-ledger.json) · [Changelog](CHANGELOG.md)

> **Status — v0.9.0, primeira versão (0.x).** Pronta para gerar e revisar backlogs localmente; a qualificação é condicional, não completa. Os 18 gates de qualidade estão implementados e cada execução informa o que não conseguiu comprovar. Não existe acesso real ao Azure DevOps nem ao Jira: o trabalho com trackers é um pacote local mais um mock em memória. Os limites conhecidos estão em [Qualidade e evidências](#qualidade-e-evidências).

## O que faz

A PBD é uma skill de agente com um runtime Python pequeno e determinístico (`pbd`). Você indica ao seu agente (Claude Code, ou outro host que leia uma pasta de skill e execute um comando) as fontes de requisitos escolhidas e pede em linguagem natural. O agente lê e raciocina; o runtime confere.

- **Gerar** épicos, features, histórias de usuário, critérios de aceite, tasks e dependências a partir de um PRD ou de várias fontes (arquivos, pastas, arquivos compactados, PDFs, imagens, DOCX, XLSX). Backlog existente, documento técnico ou conta em tracker são opcionais.
- **Auditar, comparar e refinar** um backlog existente contra as fontes, alinhar dois backlogs sobre o mesmo inventário independente (sem "vencedor") e aplicar só as mudanças que você aprovar.
- **Planejar** sprints com a capacidade do seu time, um responsável por história e executores por task, na unidade de cada pessoa; **evoluir** o backlog quando um PRD ou ADR muda, preservando identidades e edições humanas.
- **Entregar** ao [Functional Test Designer](https://github.com/Soturine/functional-test-designer) para Test Cases funcionais e mapear os resultados do FTD de volta aos IDs da PBD.
- **Relatório**: um `report.html` offline (sem servidor e sem rede), mais JSON, Markdown, CSV, XLSX e um pacote local para Azure DevOps.

Como se mantém honesta: um leitor lógico por fonte declarada; cada claim aponta para citação e localização; um revisor relê as fontes antes de ver o design; quando o host não consegue rodar um revisor separado, a execução avisa (G13 BLOCKED). A validade determinística (identidade, grafo, rastreabilidade, renderização, segurança) é checada por código; a qualidade semântica é julgada pelos agentes e exposta, nunca presumida. Confirmado pela fonte não é o mesmo que pronto para construir: trabalho que depende de uma pergunta bloqueante em aberto fica bloqueado e ligado a ela, e uma contestação do revisor mantém o item fora da sprint até ser resolvida.

**O que a PBD não é:** não executa testes, não gerencia nem escreve em um tracker real e não garante que todo requisito esteja coberto — ela mostra o que foi coberto, tratado como pergunta, bloqueado ou não comprovado.

## Início rápido

Requisitos: Python 3.11+ e um host de agente. O runtime depende só de `jsonschema`; nenhuma API hospedada é obrigatória (o agente usa o próprio provedor de modelo).

**Windows (PowerShell)**
```powershell
python -m venv $HOME\pbd-venv
& $HOME\pbd-venv\Scripts\Activate.ps1
python -m pip install https://github.com/Soturine/product-backlog-designer/releases/download/v0.9.0/product_backlog_designer-0.9.0-py3-none-any.whl
pbd --version
pbd doctor
pbd skill install --scope user          # ou: --scope project --project C:\caminho\do\projeto
```

**macOS / Linux**
```sh
python3 -m venv ~/pbd-venv && . ~/pbd-venv/bin/activate
python -m pip install https://github.com/Soturine/product-backlog-designer/releases/download/v0.9.0/product_backlog_designer-0.9.0-py3-none-any.whl
pbd --version && pbd doctor
pbd skill install --scope user
```

A partir de um clone: `git clone https://github.com/Soturine/product-backlog-designer.git` e `python -m pip install ./product-backlog-designer`. Extras opcionais: `pdf` (camada de texto de PDF, `pypdf`) e `browser` (Playwright, para os testes do próprio relatório). A pasta da skill contém só instruções; o agente chama o `pbd` que você instalou.

Depois reinicie a sessão do agente e peça, por exemplo: *"Gere o backlog completo a partir de docs/prd.md e prepare um pacote local para Azure DevOps."* O agente informa onde está o relatório: `<raiz de artefatos>/runs/<id da execução>/output/report.html`. Codex: `pbd skill install --target <projeto>/.agents/skills/product-backlog-designer` e cite a skill no pedido (uso explícito verificado; descoberta automática não). Detalhes: [instalação](docs/install.md), [uso](docs/usage.md), [comandos](docs/commands.md).

### Exemplos de pedidos
- *"Gere o backlog a partir destas três fontes: docs/prd.pdf (funcional), adr/ (decisões), api.md (técnica)."*
- *"Audite o backlog em export/backlog.csv contra docs/prd.md"* · *"Compare backlog-a.json e backlog-b.json com o PRD"* · *"Acrescente o critério de limite que falta; aplique só essa mudança."*
- *"Planeje duas sprints de uma semana com dois desenvolvedores, um responsável por história; nossas estimativas são …"* · *"O PRD mudou (docs/v2/prd.md); atualize o backlog sem perder o que existe."*

## Modos e saídas

| Modo | O que você recebe |
|---|---|
| Gerar | Épicos → features → histórias/enablers/spikes/bugs → tasks, critérios de aceite (lista, tabela ou Gherkin), dependências, perguntas, prontidão |
| Auditar | Achados por obrigação da fonte, item e critério; gates com falha descrevem o backlog auditado |
| Comparar | Cobertura dos dois lados sobre um inventário independente, correspondências muitos-para-muitos, diferenças; sem vencedor nem nota |
| Refinar / Evoluir | Plano revisável, aprovação ligada ao digest, sem exclusão; decisões substituem claims e respondem perguntas; planos obsoletos detectados |
| Planejar | Ordem segura por dependências; sprints só com capacidade conhecida; responsável pela história x executor da task, proposto x atual x derivado; story points e horas nunca convertidos nem somados entre pai e filho; desconhecido nunca vira zero |
| Pacote | Pacote local para Azure DevOps (perfis Agile, Scrum, Basic, CMMI) → aprovação do plano exato → aplicação e releitura no **mock** (`MOCK_VERIFIED`); nunca escrita real |
| Handoff | `ftd-handoff.json` + `ftd-instructions.md` para o FTD; `pbd handoff ftd-map` liga os Test Cases do FTD aos IDs da PBD só por ID exato |

O relatório pode usar a **aparência** Genérica, Azure DevOps ou Jira (só ícones originais e cores). O Jira não tem adaptador, mapeamento nem exportação na PBD; a aparência não muda a hierarquia nem o perfil de destino. A interface alterna entre português, inglês e espanhol offline; o conteúdo do backlog mantém o próprio idioma. [Relatório](docs/reporting.md) · [Azure (mock)](docs/azure.md) · [Planejamento](docs/planning-engineering.md) · [Itens de trabalho](docs/work-items.md)

## Veja o relatório

![Demonstração: visão geral, trabalho bloqueado, detalhe do item, aparência Azure DevOps e Jira, explicação de gate, idioma e tema](docs/images/report/report-demo.png)

| Prontidão e decisões | Plano do time |
|---|---|
| ![Visão geral com contagens de pronto, parcial e bloqueado e a pergunta bloqueante](docs/images/report/readiness-overview-1440-light-pt.png) | ![Quadro de sprints com responsável pela história, executor da task e carga por pessoa](docs/images/report/plan-team-1280-light-pt.png) |

Mais capturas e exemplos sintéticos para baixar e abrir estão no [README em inglês](README.md#see-the-report) e em [docs/images/report](docs/images/report/).

## Qualidade e evidências

- **Gates.** G01–G18 implementados, cada um com PASS, FAIL, BLOCKED, NOT_RUN ou NOT_APPLICABLE e evidência; o limiar de um benchmark é diferente de um PASS de gate. O G18 (ida e volta real) fica sempre NOT_RUN: não existe tracker real. [Gates de qualidade](docs/quality-gates.md)
- **Qualificação determinística da v0.9.0** (só o agente principal, local): commit exato, testes, cobertura, catálogo de mutantes, Playwright, axe-core, empacotamento e execução em Linux em [docs/evidence/v0.9.0.md](docs/evidence/v0.9.0.md).
- **As evidências semânticas são de commits anteriores** e não são reivindicadas para esta versão: [rodada corretiva](docs/evidence/corrective-round.md) e [qualificação final](docs/evidence/final-qualification.md), incluindo uma execução real do FTD que projetou 48 Test Cases (projetados, não executados). Num caso pequeno, um agente sem a skill igualou a PBD no gold com um terço dos tokens; a diferença medida foi a verificabilidade, não a cobertura.
- **Acessibilidade.** O scan do axe-core reporta 0 violações em todas as visões; é um scan automático, não uma declaração de conformidade WCAG 2.2 AA.
- **Limites em aberto** ([ledger](benchmarks/qualification-ledger.json)): variação dos geradores ao classificar perguntas bloqueantes (QL-020), leitura nativa de DOCX/XLSX indisponível no host Claude Code (QL-017), descoberta automática no Codex (QL-015), revisão com leitor de tela (QL-011), o FTD não grava IDs da PBD nativamente (QL-021).

## Licença, atribuição e segurança

Licenciada sob a [Apache License 2.0](LICENSE) ([NOTICE](NOTICE)). Material de terceiros efetivamente adaptado está em [third_party/](third_party/README.md) e [ATTRIBUTION.md](ATTRIBUTION.md). Microsoft, Azure DevOps, Atlassian e Jira são marcas de seus donos; a PBD não é afiliada a eles e seus ícones são desenhos originais. Exemplos e benchmarks públicos são sintéticos; nunca publique fontes privadas ou credenciais. A PBD nunca contata um tracker. [Segurança](docs/security.md) · [Roadmap](docs/roadmap.md)
