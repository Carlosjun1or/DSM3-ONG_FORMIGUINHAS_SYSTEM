# Formiguinhas - Módulo de Estoque (isolado)

Versão do projeto contendo apenas o módulo de **Estoque** e o mínimo necessário para testá-lo:

- `estoque`: materiais, movimentações, doações, histórico (CSV) e relatório.
- `usuario`: modelos `Voluntario`/`Usuario`, login e logout (autenticação por sessão).
- `auditoria`: modelo e serviço de registro de eventos usados pelo estoque (consulta via `/admin/`).

Os demais módulos (praia, equipe, ação, condomínio, site institucional) foram removidos.
