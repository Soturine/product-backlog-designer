# PRD — Biblioteca de Ferramentas do Bairro (fictício)

## 1. Objetivo
Permitir que moradores cadastrados emprestem ferramentas do acervo comunitário do bairro.

## 2. Usuários
- Morador: pessoa cadastrada que pega ferramentas emprestadas.
- Voluntário: pessoa que registra devoluções e mantém o acervo.

## 3. Requisitos funcionais
RF01 O morador consulta o catálogo de ferramentas com nome, categoria e disponibilidade.
RF02 O morador solicita o empréstimo de uma ferramenta disponível por até 7 dias.
RF03 Um morador pode ter no máximo 2 empréstimos ativos ao mesmo tempo.
RF04 Uma solicitação que exceda o limite de empréstimos ativos é recusada com a mensagem "Limite de empréstimos atingido".
RF05 O voluntário registra a devolução e informa se a ferramenta voltou danificada.
RF06 Ferramenta devolvida danificada fica indisponível até o voluntário marcá-la como reparada.
RF07 O morador recebe um lembrete por e-mail 1 dia antes do vencimento do empréstimo.
RF08 Empréstimos em atraso impedem novas solicitações do morador até a devolução.

## 4. Requisitos não funcionais
RNF01 O catálogo deve ser utilizável em celulares.

## 5. Fora do escopo
- Cobrança de multas e pagamentos.
- Entrega de ferramentas em domicílio.
