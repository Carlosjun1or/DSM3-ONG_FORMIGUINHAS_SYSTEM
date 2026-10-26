# Doações

O app `doacao` organiza o cadastro de doadores e as doações recebidas pela ONG,
incluindo contribuições financeiras e itens materiais.

## Funcionalidades

- Cadastrar e consultar doadores.
- Cadastrar doações e acompanhar seus detalhes e status.
- Registrar informações de doações financeiras.
- Descrever os itens incluídos em doações de materiais.

## Rotas

As rotas ficam sob `/doacao/`. A listagem de doações está em `/doacao/`, e os
doadores são administrados em `/doacao/doadores/`. Formulários e detalhes são
acessados a partir dessas listagens.

Os principais modelos são `Doador`, `Doacao`, `DoacaoFinanceira` e
`ItemDoacaoMaterial`. Quando uma doação material confirmada deve entrar no
saldo do estoque, a integração com o app `estoque` registra a movimentação
correspondente; não se deve ajustar o saldo manualmente por fora desse fluxo.
