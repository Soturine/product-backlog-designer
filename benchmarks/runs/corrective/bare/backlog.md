# Backlog — Quadras do Clube Vila Serena

Fonte: `sources/prd.md`. Fora do escopo: cobrança de reservas.

## Resumo de prontidão
- Prontas para construir: S1, S2, S3, S7.
- Parcialmente bloqueada: S4 (prazo de cancelamento, Q1).
- Bloqueadas: S5, S6 (API do fornecedor, Q2; identificação e tolerância, Q3).

## Épicos e Features
- **E1 Reserva de quadras**: F1 Consulta de disponibilidade; F2 Criação de reserva com regras de negócio
- **E2 Cancelamento de reservas**: F3 Cancelamento pelo sócio
- **E3 Acesso por catraca**: F4 Integração com catracas; F5 Validação de entrada pela reserva
- **E4 Agenda da recepção**: F6 Visualização da agenda diária

## Histórias

### S1 (F1) Ver horários livres por quadra — PRONTA
Como sócio, quero ver os horários livres de cada quadra de tênis e futsal por data, para escolher quando jogar.
- Dado uma data e um esporte, vejo as quadras e blocos de 1h entre 7h e 22h com status livre ou ocupado.
- Bloco já reservado aparece indisponível e não é selecionável.
- O último bloco é 21h–22h; nada fora de 7h–22h.

Tasks: T1 modelo de quadras e API de disponibilidade; T2 tela no app.

### S2 (F2) Reservar uma quadra livre em bloco de 1 hora — PRONTA
Como sócio, quero reservar uma quadra livre em um bloco de 1 hora, para garantir meu horário de jogo.
- Bloco livre em 7h–22h: reserva criada e bloco passa a ocupado.
- Bloco já reservado: recusa com mensagem.
- Tentativas simultâneas no mesmo bloco: apenas uma é confirmada.
- Não aceita fora de 7h–22h nem duração diferente de 1h.
- Nenhuma cobrança é gerada.

Tasks: T3 modelo e endpoint; T4 unicidade e concorrência; T5 fluxo no app.

### S3 (F2) Limitar a 2 reservas futuras por sócio — PRONTA
Como diretoria, quero que cada sócio tenha no máximo 2 reservas futuras ao mesmo tempo.
- Com 2 futuras, a terceira é recusada com mensagem.
- Cancelar uma libera nova reserva.
- Reservas passadas não contam.
- Verificação atômica.

Tasks: T6 regra atômica; T7 mensagem no app.

### S4 (F3) Cancelar uma reserva — PARCIALMENTE BLOQUEADA (Q1)
Como sócio, quero cancelar uma reserva minha, para liberar o horário.
- Dentro da regra de antecedência: reserva cancelada e bloco liberado.
- Fora do prazo: recusa informando o prazo.
- Só o dono cancela.
- Antecedência é parâmetro configurável.

Tasks: T8 endpoint; T9 parâmetro configurável; T10 validação do prazo (bloqueada); T11 ação no app.

### S5 (F4) Integrar com o sistema de catracas — BLOQUEADA (Q2)
Como clube, quero integrar o aplicativo ao sistema de catracas.
- Segue a documentação oficial da API (contrato, autenticação, erros).
- Falhas são registradas sem corromper reservas.
- Há ambiente de teste ou simulador.

Tasks: T12 spike da documentação; T13 cliente da API.

### S6 (F5) Entrar pela catraca usando a reserva — BLOQUEADA (Q2, Q3)
Como sócio, quero entrar pela catraca ao chegar usando minha reserva.
- Reserva ativa dentro da janela: entrada liberada.
- Sem reserva válida ou cancelada: negada.
- Tolerância de horário definida e aplicada.
- Tentativas registradas.

Tasks: T14 regra de autorização e tolerância; T15 registro de acessos.

### S7 (F6) Agenda do dia de cada quadra na recepção — PRONTA
Como recepcionista, quero ver a agenda do dia de cada quadra.
- Cada quadra com blocos 7h–22h mostrando sócio ou livre.
- Atualização em até 1 minuto após criação ou cancelamento.
- Consulta de outra data.
- Acesso restrito ao perfil da recepção.

Tasks: T16 endpoint com controle de perfil; T17 tela.

## Dependências
- S2 depende de S1; S3 e S4 dependem de S2; S7 depende de S2.
- S4 depende da decisão Q1.
- S5 depende da documentação do fornecedor (Q2); S6 depende de S5, S2 e S4.
- T10 depende de T9; T13 de T12; T4 e T6 de T3.

## Perguntas em aberto
| Id | Pergunta | Bloqueante | Afeta |
|---|---|---|---|
| Q1 | Antecedência mínima para cancelar; há exceções (mau tempo, manutenção)? | Sim | S4, T10 |
| Q2 | Quando o fornecedor entrega a documentação da API; há ambiente de teste? | Sim | S5, S6, T12-T15 |
| Q3 | Como o sócio se identifica na catraca e qual a tolerância de horário? | Sim | S6, T14 |
| Q4 | Quantos dias de antecedência para reservar; pode reservar bloco já iniciado? | Não | S1, S2 |
| Q5 | Limite de 2 soma tênis e futsal? Reserva em andamento conta? | Não | S3 |
| Q6 | Recepção usa app ou painel web? Pode reservar/cancelar pelo sócio? | Não | S7 |
| Q7 | Quantas quadras por esporte; bloqueios por manutenção ou eventos? | Não | S1, S2 |
| Q8 | Quem é sócio apto e como é a autenticação? | Não | S2 |

## Premissas
- A1: sócio já autenticado no app existente; login fora deste backlog.
- A2: limite de 2 é global (tênis e futsal somados).
- A3: fuso do clube; último bloco 21h–22h.
- A4: não se reserva bloco passado.
- A5: reserva futura é a que ainda não terminou.
- A6: recepção tem perfil próprio, somente leitura.
- A7: sem cobrança (fora do escopo).
- A8: cancelar libera o bloco imediatamente.
