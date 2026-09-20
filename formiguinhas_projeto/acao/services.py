from collections import defaultdict

from .models import (
    AcaoParticipante,
    AcaoParticipanteHistorico,
)


STATUS_CONSIDERADOS = {
    AcaoParticipante.STATUS_CONFIRMADO,
    AcaoParticipante.STATUS_PRESENTE,
    AcaoParticipante.STATUS_NAO_COMPARECEU,
}


def calcular_frequencias_voluntarios(voluntario_ids=None):
    """Calcula a frequência atual sem armazenar o resultado no banco."""
    participacoes = defaultdict(lambda: {
        'acoes': set(),
        'presencas': set(),
    })

    participantes_atuais = AcaoParticipante.objects.filter(
        status__in=STATUS_CONSIDERADOS,
    ).values(
        'voluntario_id',
        'acao_id',
        'status',
        'compareceu',
    )
    if voluntario_ids is not None:
        participantes_atuais = participantes_atuais.filter(
            voluntario_id__in=voluntario_ids,
        )

    pares_atuais = set()
    for participante in participantes_atuais:
        par = (participante['voluntario_id'], participante['acao_id'])
        pares_atuais.add(par)
        dados = participacoes[participante['voluntario_id']]
        dados['acoes'].add(participante['acao_id'])
        if (
            participante['compareceu']
            or participante['status'] == AcaoParticipante.STATUS_PRESENTE
        ):
            dados['presencas'].add(participante['acao_id'])

    historicos = AcaoParticipanteHistorico.objects.filter(
        status__in={
            AcaoParticipante.STATUS_PRESENTE,
            AcaoParticipante.STATUS_NAO_COMPARECEU,
        },
    ).values(
        'voluntario_id',
        'acao_id',
        'status',
        'compareceu',
    )
    if voluntario_ids is not None:
        historicos = historicos.filter(voluntario_id__in=voluntario_ids)

    for historico in historicos:
        par = (historico['voluntario_id'], historico['acao_id'])
        if par in pares_atuais:
            continue
        dados = participacoes[historico['voluntario_id']]
        dados['acoes'].add(historico['acao_id'])
        if (
            historico['compareceu']
            or historico['status'] == AcaoParticipante.STATUS_PRESENTE
        ):
            dados['presencas'].add(historico['acao_id'])

    resultado = {}
    for voluntario_id, dados in participacoes.items():
        total = len(dados['acoes'])
        presencas = len(dados['presencas'])
        percentual = round((presencas / total) * 100, 1) if total else None
        if percentual is None:
            nivel = 'Sem participação'
        elif percentual < 50:
            nivel = 'Baixa'
        elif percentual < 80:
            nivel = 'Média'
        else:
            nivel = 'Alta'

        resultado[voluntario_id] = {
            'total': total,
            'presencas': presencas,
            'percentual': percentual,
            'nivel': nivel,
        }

    return resultado
