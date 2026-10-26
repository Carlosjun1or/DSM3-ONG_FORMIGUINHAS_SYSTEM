# Estoque

O app `estoque` controla o catálogo de materiais, o saldo, as entradas e as
saídas da ONG. A tela principal está em `/estoque/`.

## Regras principais

- O saldo é calculado como `quantidade_inicial + entradas - saídas`; não é
  gravado como um valor independente.
- Entradas e saídas são registradas como movimentações. Movimentações não
  podem ser editadas nem excluídas pela interface.
- Doações materiais são cadastradas no app `doacao`. Ao confirmar uma doação
  válida, o fluxo registra uma entrada vinculada à doação e ao item recebido.
- Para entrar no estoque, o item deve ter quantidade inteira e não pode estar
  danificado. Depois que uma doação gera movimentação, ela não pode ser
  cancelada nem voltar ao status pendente, e seus itens ficam bloqueados para
  edição.
- O indicador de doações confirmadas é informativo; o saldo é atualizado
  exclusivamente pelas movimentações registradas. Os endereços antigos de
  doações dentro do estoque redirecionam para o app `doacao`.
- Os eventos de materiais e movimentações são registrados no app `auditoria`.
- A consulta e o histórico atualizam os resultados conforme os filtros
  selecionados (busca, categoria, situação, origem, tipo e datas). A exportação
  CSV respeita esses mesmos filtros.

## Páginas

- `/estoque/` — materiais e saldo
- `/estoque/movimentacoes/` — histórico de entradas e saídas
- `/estoque/relatorio/` — relatório por origem

O perfil `ADMIN` pode administrar materiais, movimentações e histórico;
`COORDENADOR` consulta o saldo e o relatório. A autenticação é compartilhada
com o app `usuario`.

Para criar registros demonstrativos no ambiente local, execute
`python manage.py simular_estoque` dentro de `formiguinhas_projeto`. O comando
identifica os registros de demonstração para evitar duplicação em execuções
repetidas.
