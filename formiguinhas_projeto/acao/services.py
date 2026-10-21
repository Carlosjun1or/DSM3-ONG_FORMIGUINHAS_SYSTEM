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

    # 1. Tentar obter do MongoDB Atlas (onde residem as Ações e Participantes no Cenário C)
    try:
        from acao.mongo_services import get_acoes_collection
        col = get_acoes_collection()
        if col is not None:
            query = {}
            if voluntario_ids is not None:
                query['participantes.voluntario_id'] = {'$in': [int(v) for v in voluntario_ids]}
            v_filter = set(voluntario_ids) if voluntario_ids is not None else None
            docs = col.find(query, {'id_sql': 1, 'participantes': 1, 'historico_participantes': 1})
            encontrou = False
            for doc in docs:
                encontrou = True
                acao_id = doc.get('id_sql')
                for part in doc.get('participantes', []):
                    v_id = part.get('voluntario_id')
                    if v_filter and v_id not in v_filter:
                        continue
                    status = part.get('status')
                    if status in STATUS_CONSIDERADOS:
                        dados = participacoes[v_id]
                        dados['acoes'].add(acao_id)
                        if part.get('compareceu') or status == 'PRESENTE':
                            dados['presencas'].add(acao_id)
                for hist in doc.get('historico_participantes', []):
                    v_id = hist.get('voluntario_id')
                    if v_filter and v_id not in v_filter:
                        continue
                    status = hist.get('status')
                    if status in ('PRESENTE', 'NAO_COMPARECEU'):
                        dados = participacoes[v_id]
                        dados['acoes'].add(acao_id)
                        if hist.get('compareceu') or status == 'PRESENTE':
                            dados['presencas'].add(acao_id)
            if encontrou or col.count_documents({}) > 0:
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
    except Exception:
        pass

    # 2. Fallback para SQLite (caso a tabela relacional exista)
    try:
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
    except Exception:
        return {}
