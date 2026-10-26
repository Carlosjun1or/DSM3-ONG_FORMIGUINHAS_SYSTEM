# Resíduos

O app `residuo` registra coletas e o destino dado aos resíduos recolhidos pela
ONG. As coletas podem ser associadas a uma bag do app `condominio`.

## Funcionalidades

- Consultar coletas e seus itens.
- Abrir os detalhes de uma coleta e adicionar itens.
- Registrar o resíduo coletado e sua destinação.
- Consultar os registros de destinação.

## Rotas

As rotas usam o prefixo `/residuo/`. A listagem fica em `/residuo/` e os
detalhes e operações de itens são organizados a partir de
`/residuo/coleta/<id>/`.

Os modelos `ColetaResiduo`, `ItemColetaResiduo`, `ResiduoColetado` e
`DestinacaoResiduo` representam essas etapas. Os dados relacionais usam o banco
SQLite padrão do projeto.
