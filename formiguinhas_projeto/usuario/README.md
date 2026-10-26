# Usuários e voluntários

O app `usuario` mantém os cadastros de voluntários e as credenciais de acesso
usadas pelas áreas internas do sistema. Um voluntário pode existir sem ter
login; quando há uma conta, ela fica associada a um voluntário.

## Responsabilidades

- Autenticar e encerrar sessões de usuário.
- Cadastrar, editar e consultar voluntários.
- Administrar usuários e seus tipos de acesso (`ADMIN` e `COORDENADOR`).
- Exibir perfil, permitir alteração de senha e iniciar recuperação de senha.

As credenciais são implementadas pelos modelos próprios do app e armazenadas
no banco relacional configurado pelo projeto. O fluxo usa sessão própria; não
é o modelo `django.contrib.auth.User`.

## Rotas

As rotas ficam sob `/usuario/`, incluindo `/usuario/login/`,
`/usuario/recuperar-senha/`, `/usuario/voluntarios/`, `/usuario/usuarios/`,
`/usuario/perfil/` e `/usuario/alterar-senha/`. Algumas operações de edição e
status recebem o identificador do registro na URL.

Para envio real de recuperação de senha, configure SMTP no arquivo `.env` do
projeto. Sem SMTP, o backend de console escreve a mensagem no terminal.
