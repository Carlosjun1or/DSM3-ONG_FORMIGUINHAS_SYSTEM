# Ações

O app `acao` organiza as atividades e campanhas realizadas pela ONG.

## Funcionalidades

- Cadastrar, consultar, editar e atualizar o status de ações.
- Gerenciar participantes, responsáveis e equipes relacionadas.
- Registrar presença e manter histórico de participação.
- Anexar imagens e registrar materiais utilizados.

## Rotas

As páginas internas ficam sob `/acao/`. A listagem está em `/acao/`, o
cadastro em `/acao/cadastrar/` e os detalhes em `/acao/<id>/`. Participantes,
imagens e materiais têm operações associadas à ação correspondente.

Os modelos incluem `Acao`, `AcaoEquipe`, `AcaoParticipante`,
`AcaoResponsavel`, `AcaoImagem` e `AcaoParticipanteHistorico`. O app também
possui código de integração com MongoDB; consulte a configuração geral do
projeto para as variáveis de ambiente.
