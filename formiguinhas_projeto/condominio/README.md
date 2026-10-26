# Condomínios e bags

O app `condominio` mantém os condomínios parceiros da ONG e acompanha as bags
usadas nas coletas.

## Funcionalidades

- Cadastrar, consultar e editar condomínios.
- Associar condomínios a praias e acompanhar seus dados de parceria.
- Cadastrar bags, consultar detalhes e acompanhar seu status.
- Registrar movimentações e consultar o histórico de auditoria relacionado.

## Rotas

O prefixo é `/condominio/`. A listagem de condomínios fica em
`/condominio/`; as bags ficam sob `/condominio/bags/`. A consulta legada de
auditoria em `/condominio/auditoria/` continua disponível junto da auditoria
global em `/auditoria/`.

O app possui integração com MongoDB para leitura e sincronização de dados de
condomínios. O modelo `Condominio` declara `managed = False`: sua estrutura de
tabela é mantida fora das migrations regulares do Django. `Bag` e
`MovimentacaoBag` registram o ciclo e as mudanças de estado das bags.
