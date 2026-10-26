# Praias

O app `praia` mantém o cadastro de praias atendidas pela ONG, que pode ser
associado a outras áreas, como condomínios parceiros e ações.

## Funcionalidades

- Listar e cadastrar praias.
- Localizar registros e editar seus dados.
- Atualizar o status ou excluir um cadastro conforme as permissões aplicadas
  pela tela.

## Rotas

O prefixo do app é `/praia/`. A listagem está disponível em `/praia/` e
`/praia/praias/`; as operações de cadastro, localização e edição ficam sob
`/praia/praias/`.

Os dados são mantidos pelo modelo `Praia` no banco relacional do projeto.
