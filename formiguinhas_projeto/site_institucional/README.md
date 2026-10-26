# Site institucional

O app `site_institucional` apresenta publicamente a ONG e suas atividades. Ele
serve as páginas informativas do site e não mantém modelos próprios de banco de
dados.

## Páginas

As rotas são incluídas na raiz do projeto:

- `/` — página inicial
- `/multiroes/` — mutirões
- `/praias-atuacao/` — praias de atuação
- `/calendario/` — calendário

As páginas usam templates em `templates/site_institucional/`. O conteúdo
dinâmico relacionado a outras áreas, como comunicados, é fornecido pelos apps
correspondentes.
