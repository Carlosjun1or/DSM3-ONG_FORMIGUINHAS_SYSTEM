# Auditoria

O app `auditoria` registra eventos de criação, edição, alteração de status,
vínculos, exclusões e movimentações gerados pelas áreas do sistema. A tela
global fica em `/auditoria/`; `/condominio/auditoria/` continua disponível por
compatibilidade e apresenta a mesma consulta.

Os snapshots são produzidos por `auditoria.services.snapshot`. Credenciais,
tokens, hashes e arquivos/imagens não são persistidos nos snapshots. A consulta
permite filtrar por entidade, ação, usuário e intervalo de datas.

O app também controla o estado de leitura das notificações de auditoria.
Integrações de persistência e leitura em MongoDB são implementadas em
`mongo_services.py`; os eventos de estoque usam as entidades
`MATERIAL` e `MOVIMENTACAO_ESTOQUE`.
