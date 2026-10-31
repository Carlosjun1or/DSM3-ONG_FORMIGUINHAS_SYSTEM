# Sistema Formiguinhas

Sistema web da ONG Formiguinhas, desenvolvido em Django. Reúne o site
institucional e as ferramentas internas para administrar voluntários, ações,
equipes, doações, estoque, coletas e parceiros.

## Organização do projeto

O projeto Django está em [`formiguinhas_projeto`](./formiguinhas_projeto/). Cada
app tem um README próprio com uma explicação de sua responsabilidade e das
principais rotas:

| App | Para que serve |
| --- | --- |
| [`site_institucional`](./formiguinhas_projeto/site_institucional/README.md) | Páginas públicas da ONG |
| [`usuario`](./formiguinhas_projeto/usuario/README.md) | Login, perfis de acesso e cadastro de voluntários |
| [`praia`](./formiguinhas_projeto/praia/README.md) | Cadastro e acompanhamento das praias |
| [`equipe`](./formiguinhas_projeto/equipe/README.md) | Equipes e participação de voluntários |
| [`acao`](./formiguinhas_projeto/acao/README.md) | Ações, participantes, responsáveis e materiais |
| [`residuo`](./formiguinhas_projeto/residuo/README.md) | Coletas, resíduos e destinações |
| [`condominio`](./formiguinhas_projeto/condominio/README.md) | Condomínios parceiros, bags e movimentações |
| [`doacao`](./formiguinhas_projeto/doacao/README.md) | Doadores e doações financeiras ou materiais |
| [`estoque`](./formiguinhas_projeto/estoque/README.md) | Materiais, saldo e movimentações do estoque |
| [`comunicado`](./formiguinhas_projeto/comunicado/README.md) | Comunicados públicos e internos |
| [`auditoria`](./formiguinhas_projeto/auditoria/README.md) | Registro e consulta de eventos do sistema |
| [`relatorios`](./formiguinhas_projeto/relatorios/README.md) | Consultas e indicadores de gestão |

## Requisitos

- Python instalado e compatível com a versão do Django definida em
  `formiguinhas_projeto/requirements.txt`.
- Windows para usar o inicializador `iniciar.bat`. Em outros sistemas, use os
  comandos manuais abaixo.

O banco relacional padrão é SQLite (`formiguinhas_projeto/db.sqlite3`). Algumas
integrações também podem usar MongoDB Atlas; sem uma conexão configurada, as
rotinas que dependem do Atlas podem não estar disponíveis.

## Executar no Windows

Na raiz do repositório, execute:

```bat
iniciar.bat
```

O script prepara o ambiente virtual, instala as dependências, aplica as
migrations, coleta os arquivos estáticos e inicia o servidor local. Ele usa a
porta 8000 ou procura a próxima porta livre. Quando aparecer o endereço no
terminal, abra-o no navegador (por padrão, `http://127.0.0.1:8000/`).

## Executar manualmente

Na raiz do repositório, crie e ative o ambiente virtual. No Windows PowerShell:

```powershell
cd formiguinhas_projeto
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py runserver
```

Em macOS ou Linux, use `python3 -m venv venv` e
`source venv/bin/activate` no lugar dos comandos de criação e ativação acima;
os demais comandos são os mesmos.

Depois, acesse `http://127.0.0.1:8000/`. Para executar os testes automatizados:

```bat
python manage.py test
```

## Configurações opcionais

As configurações locais são lidas de `formiguinhas_projeto/.env`. Para ativar
envio de e-mail por SMTP ou integrações com MongoDB Atlas, use
`formiguinhas_projeto/.env.example` como referência e configure os valores no
`.env` local. Não coloque senhas, tokens ou strings de conexão reais no Git.

Sem credenciais SMTP, o Django usa o backend de console para mensagens de
e-mail. O MongoDB não substitui o SQLite como banco padrão: a configuração do
Atlas é usada pelas integrações implementadas em alguns apps.

## Endereços principais

- `/` — site institucional
- `/usuario/` — acesso, usuários e voluntários
- `/praia/` — praias
- `/equipe/` — equipes
- `/acao/` — ações
- `/residuo/` — coletas e resíduos
- `/condominio/` — condomínios e bags
- `/doacao/` — doações e doadores
- `/estoque/` — materiais e movimentações
- `/comunicado/` — central e administração de comunicados
- `/auditoria/` — auditoria global
- `/relatorios/` — relatórios de gestão
- `/admin/` — administração do Django

As páginas internas podem exigir login e permissões de acordo com o perfil do
usuário.
