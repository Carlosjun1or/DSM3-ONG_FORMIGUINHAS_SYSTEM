# Comunicados

O app `comunicado` publica avisos para o público e para usuários internos do
sistema. Os comunicados podem ser classificados por tema e associados a áreas
como praias, equipes, ações e doações.

## Funcionalidades

- Criar, editar e administrar comunicados e temas.
- Exibir comunicados públicos no site institucional.
- Disponibilizar uma central de comunicados internos.
- Registrar leituras de comunicados internos.
- Relacionar comunicados aos assuntos e registros pertinentes.

## Rotas

O prefixo é `/comunicado/`. A administração usa `/comunicado/admin/`, a central
interna `/comunicado/central/` e a listagem pública
`/comunicado/publicos/`.

O app tem integração com MongoDB configurável pelo projeto, além dos modelos
relacionais para temas, comunicados, relacionamentos e leituras. Os avisos de
notificação são disponibilizados pelo context processor do app.
