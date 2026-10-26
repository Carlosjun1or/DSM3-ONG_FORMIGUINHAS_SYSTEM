# Equipes

O app `equipe` organiza os grupos de trabalho da ONG. Cada equipe pode reunir
voluntários e manter registros de participação e função.

## Funcionalidades

- Criar, consultar, editar e atualizar o status das equipes.
- Ver os detalhes de uma equipe.
- Adicionar membros, alterar suas funções ou removê-los.
- Consultar e administrar o histórico de participação dos membros.

## Rotas

As páginas são servidas sob `/equipe/`: a listagem fica em `/equipe/`, o
cadastro em `/equipe/cadastrar/` e os detalhes em `/equipe/<id>/`. As operações
de membros são subordinadas ao endereço da equipe.

O app usa os modelos `Equipe` e `EquipeMembro`; o cadastro de membros se
relaciona com os voluntários gerenciados pelo app `usuario`.
