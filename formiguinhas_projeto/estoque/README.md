# Estoque

Controle de materiais da ONG: cadastro, saldo, entradas e saídas, histórico com
exportação CSV e relatório por origem. Tela em `/estoque/`.

- Autenticação e perfis: sessão do app `usuario`. `ADMIN` cadastra, edita,
  movimenta e vê o histórico; `COORDENADOR` consulta o saldo e o relatório.
- O saldo não é gravado: é `quantidade_inicial + entradas - saídas`, calculado
  a partir das movimentações. Movimentações não podem ser editadas nem excluídas.
- Doações são cadastradas em `/doacao/`. Cada item deve ser associado a um
  material do catálogo; ao confirmar a doação, o sistema registra uma entrada
  auditada e vinculada ao item e à doação. A entrada aparece no histórico de
  movimentações e atualiza o saldo calculado.
- Para entrar no estoque, o item precisa ter quantidade inteira e não pode estar
  danificado. Uma doação que já movimentou o estoque não pode ser cancelada ou
  voltar a pendente, e seus itens ficam bloqueados para edição.
- O indicador de doações confirmadas continua sendo informativo; o saldo é
  atualizado exclusivamente pelas movimentações geradas. Os links antigos de
  doações dentro do estoque redirecionam para o módulo oficial.
- Os eventos de estoque vão para o app `auditoria` (entidades `MATERIAL` e
  `MOVIMENTACAO_ESTOQUE`); doações são auditadas pelo próprio módulo `doacao`.
- Consulta (`/estoque/`) e histórico (`/estoque/movimentacoes/`) filtram em tempo
  real enquanto o usuário digita ou altera os filtros (busca, categoria, situação,
  origem, tipo e datas). O CSV exportado respeita os mesmos filtros.
- Para preencher o ambiente local com registros fictícios, execute
  `python manage.py simular_estoque` na pasta `formiguinhas_projeto`. O comando cria
  quatro materiais, entradas e saídas auditadas e uma doação confirmada vinculada
  ao estoque. Os registros são identificados como demonstrativos; executar o
  comando novamente não duplica materiais nem movimentações.
