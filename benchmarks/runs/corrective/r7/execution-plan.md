# Plano de execução

## SCN-001

_Ordem: ordem canônica_

1. [TC-001](test-cases-md/TC-001.md) — Reservar uma quadra de tênis livre pelo aplicativo
2. [TC-002](test-cases-md/TC-002.md) — Reservar uma quadra de futsal livre pelo aplicativo
3. [TC-003](test-cases-md/TC-003.md) — Reserva criada em nome do sócio que reservou
4. [TC-004](test-cases-md/TC-004.md) — Bloco reservado deixa de aparecer como livre
5. [TC-005](test-cases-md/TC-005.md) — Recusar reserva de bloco já reservado na quadra
6. [TC-006](test-cases-md/TC-006.md) — Reserva ocupa exatamente 1 hora
7. [TC-015](test-cases-md/TC-015.md) — Recusar pedido único de reserva com 2 horas de duração
8. [TC-023](test-cases-md/TC-023.md) — Caracterizar pedido com início fora da hora cheia
9. [TC-026](test-cases-md/TC-026.md) — Confirmar bloco exibido como livre que outro sócio já reservou
10. [TC-027](test-cases-md/TC-027.md) — Reserva abandonada sem confirmar não ocupa o bloco
11. [TC-030](test-cases-md/TC-030.md) — Pedido com vários motivos de recusa ao mesmo tempo
12. [TC-031](test-cases-md/TC-031.md) — Dois sócios disputam o mesmo bloco ao mesmo tempo
13. [TC-033](test-cases-md/TC-033.md) — Confirmar duas vezes a mesma reserva gera uma só
14. [TC-037](test-cases-md/TC-037.md) — Conexão perdida ao confirmar e restabelecida em seguida
15. [TC-040](test-cases-md/TC-040.md) — Falha parcial na confirmação não deixa bloco preso sem reserva
16. [TC-041](test-cases-md/TC-041.md) — Sessão expirada durante a reserva não deixa reserva sem titular
17. [TC-044](test-cases-md/TC-044.md) — Blocos adjacentes da mesma quadra não se sobrepõem

## SCN-002

_Ordem: ordem canônica_

1. [TC-007](test-cases-md/TC-007.md) — Aceitar bloco dentro da janela de 7h a 22h
2. [TC-008](test-cases-md/TC-008.md) — Recusar bloco fora da janela de 7h a 22h
3. [TC-017](test-cases-md/TC-017.md) — Aceitar o primeiro bloco da janela, das 7h às 8h
4. [TC-018](test-cases-md/TC-018.md) — Aceitar o bloco que termina às 22h
5. [TC-019](test-cases-md/TC-019.md) — Recusar bloco que começa uma hora antes da abertura
6. [TC-020](test-cases-md/TC-020.md) — Caracterizar o bloco que começa às 22h

## SCN-003

_Ordem: ordem canônica_

1. [TC-009](test-cases-md/TC-009.md) — Criar reserva quando o sócio tem menos de 2 futuras
2. [TC-010](test-cases-md/TC-010.md) — Recusar terceira reserva futura do sócio
3. [TC-021](test-cases-md/TC-021.md) — Primeira reserva de um sócio sem reservas futuras
4. [TC-022](test-cases-md/TC-022.md) — Reservas passadas não consomem o limite de futuras
5. [TC-028](test-cases-md/TC-028.md) — Limite de 2 vale somando tênis e futsal
6. [TC-029](test-cases-md/TC-029.md) — Cancelamento devolve ao sócio uma vaga no limite de reservas
7. [TC-032](test-cases-md/TC-032.md) — Pedidos simultâneos não furam o limite de 2 reservas

## SCN-004

_Ordem: ordem canônica_

1. [TC-011](test-cases-md/TC-011.md) — Sócio cancela a própria reserva futura
2. [TC-012](test-cases-md/TC-012.md) — Bloco cancelado volta a ficar disponível
3. [TC-025](test-cases-md/TC-025.md) — Cancelar uma de duas reservas preserva a outra
4. [TC-034](test-cases-md/TC-034.md) — Caracterizar o cancelamento de uma reserva já cancelada
5. [TC-043](test-cases-md/TC-043.md) — Sócio tenta cancelar a reserva de outro sócio

## SCN-005

_Ordem: ordem canônica_

1. [TC-013](test-cases-md/TC-013.md) — Catraca libera o sócio que usa a reserva do horário
2. [TC-016](test-cases-md/TC-016.md) — Catraca não libera sócio que não reservou a quadra
3. [TC-035](test-cases-md/TC-035.md) — Caracterizar a entrada na catraca antes do horário reservado
4. [TC-036](test-cases-md/TC-036.md) — Catraca não libera quem usa uma reserva cancelada
5. [TC-038](test-cases-md/TC-038.md) — API de catracas indisponível não altera reservas nem agenda
6. [TC-039](test-cases-md/TC-039.md) — Catraca com defeito não perde a reserva do sócio

## SCN-006

_Ordem: ordem canônica_

1. [TC-014](test-cases-md/TC-014.md) — Recepção vê a agenda do dia de cada quadra
2. [TC-024](test-cases-md/TC-024.md) — Agenda do dia de quadra sem reservas aparece vazia
3. [TC-042](test-cases-md/TC-042.md) — Sócio comum tentando abrir a agenda da recepção
4. [TC-045](test-cases-md/TC-045.md) — Reserva criada aparece na agenda da quadra para a recepção
5. [TC-046](test-cases-md/TC-046.md) — Reserva cancelada some da agenda do dia

## Casos de uso ponta a ponta (E2E)

_Ordem: ordem de execução_

1. [TC-047](test-cases-md/TC-047.md) — Jornada: reservar, conferir na agenda, cancelar e liberar o bloco
2. [TC-048](test-cases-md/TC-048.md) — Jornada: reservar e entrar pela catraca no horário

## Carga e concorrência

_Ordem: ordem de execução_

1. [TC-031](test-cases-md/TC-031.md) — Dois sócios disputam o mesmo bloco ao mesmo tempo
2. [TC-032](test-cases-md/TC-032.md) — Pedidos simultâneos não furam o limite de 2 reservas

## Físicos / dispositivos

_Ordem: ordem de execução_

1. [TC-013](test-cases-md/TC-013.md) — Catraca libera o sócio que usa a reserva do horário
2. [TC-016](test-cases-md/TC-016.md) — Catraca não libera sócio que não reservou a quadra
3. [TC-035](test-cases-md/TC-035.md) — Caracterizar a entrada na catraca antes do horário reservado
4. [TC-036](test-cases-md/TC-036.md) — Catraca não libera quem usa uma reserva cancelada
5. [TC-039](test-cases-md/TC-039.md) — Catraca com defeito não perde a reserva do sócio
6. [TC-048](test-cases-md/TC-048.md) — Jornada: reservar e entrar pela catraca no horário

## Chaos / resiliência

_Ordem: ordem de execução_

1. [TC-037](test-cases-md/TC-037.md) — Conexão perdida ao confirmar e restabelecida em seguida
2. [TC-041](test-cases-md/TC-041.md) — Sessão expirada durante a reserva não deixa reserva sem titular
3. [TC-038](test-cases-md/TC-038.md) — API de catracas indisponível não altera reservas nem agenda
