# Auditoria global

O app `auditoria` registra eventos de criação, edição, status, vínculos,
exclusão e movimentação para todas as áreas do sistema. A tela está em
`/auditoria/`; `/condominio/auditoria/` permanece compatível e exibe a mesma
consulta.

Os snapshots são gerados por `auditoria.services.snapshot`: credenciais,
tokens, hashes e arquivos/imagens não são persistidos. A consulta permite
filtrar entidade, ação, usuário e intervalo de datas.
