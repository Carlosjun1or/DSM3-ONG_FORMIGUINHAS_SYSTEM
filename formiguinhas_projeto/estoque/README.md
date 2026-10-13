# Estoque

Controle de materiais da ONG: cadastro, saldo, entradas e saídas, doações,
histórico com exportação CSV e relatório por origem. Tela em `/estoque/`.

- Autenticação e perfis: sessão do app `usuario`. `ADMIN` cadastra, edita,
  movimenta, registra doações e vê o histórico; `COORDENADOR` consulta o saldo
  e o relatório.
- O saldo não é gravado: é `quantidade_inicial + entradas - saídas`, calculado
  a partir das movimentações. Movimentações e doações não podem ser editadas
  nem excluídas.
- Doações só entram pelo registro de doação, que gera a entrada automática.
- Todos os eventos vão para o app `auditoria` (entidades `MATERIAL`, `DOACAO`
  e `MOVIMENTACAO_ESTOQUE`).
- Consulta (`/estoque/`) e histórico (`/estoque/movimentacoes/`) filtram em tempo
  real enquanto o usuário digita ou altera os filtros (busca, categoria, situação,
  origem, tipo e datas). O CSV exportado respeita os mesmos filtros.
