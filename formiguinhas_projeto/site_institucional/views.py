"""
Site institucional público da ONG (sem autenticação).

As funções helper (mutiroes_concluidos, mutiroes_futuros) seguem o mesmo
padrão das views internas: MongoDB como fonte primária, SQLite como fallback.
"""
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator

from acao.models import Acao
from comunicado.models import Comunicado
from praia.models import Praia


def mutiroes_concluidos():
    """Retorna mutirões concluídos: MongoDB primeiro, SQLite como fallback."""
    try:
        from acao.mongo_services import consultar_acoes_mongo
        from acao.views import MongoAcaoAdapter
        docs, _ = consultar_acoes_mongo({'tipo': 'MUTIRAO', 'status': 'CONCLUIDA'}, por_pagina=1000)
        if docs:
            return [MongoAcaoAdapter(d) for d in docs]
    except Exception:
        pass
    try:
        return list(
            Acao.objects.filter(
                tipo=Acao.TIPO_MUTIRAO,
                status=Acao.STATUS_CONCLUIDA,
            )
            .select_related('praia')
            .prefetch_related('imagens_acao')
            .order_by('-data', '-horario')
        )
    except Exception:
        return []


def mutiroes_futuros():
    """Retorna mutirões planejados (futuros): MongoDB primeiro, SQLite como fallback."""
    try:
        from acao.mongo_services import consultar_acoes_mongo
        from acao.views import MongoAcaoAdapter
        docs, _ = consultar_acoes_mongo({'tipo': 'MUTIRAO', 'status': 'PLANEJADA'}, por_pagina=1000)
        if docs:
            return [MongoAcaoAdapter(d) for d in docs]
    except Exception:
        pass
    try:
        return list(
            Acao.objects.filter(
                tipo=Acao.TIPO_MUTIRAO,
                data__gte=timezone.now().date(),
                status=Acao.STATUS_PLANEJADA,
            )
            .select_related('praia')
            .order_by('data', 'horario')
        )
    except Exception:
        return []


def index(request):
    agora = timezone.now()
    ultimo_comunicado = None
    # Attempt to fetch the latest comunicado from MongoDB first.
    try:
        from comunicado.mongo_services import consultar_comunicados_mongo
        from comunicado.views import MongoComunicadoAdapter
        docs, _ = consultar_comunicados_mongo({'status': 'PUBLICADO', 'publico': 'TODOS'}, por_pagina=1)
        if docs:
            ultimo_comunicado = MongoComunicadoAdapter(docs[0])
    except Exception:
        # MongoDB unavailable or query failed – fall back to SQLite.
        pass
    # SQLite fallback – catch missing table or other DB errors.
    if not ultimo_comunicado:
        try:
            ultimo_comunicado = (
                Comunicado.objects.filter(
                    status=Comunicado.PUBLICADO,
                    publico=Comunicado.TODOS,
                    dt_publicacao__isnull=False,
                    dt_publicacao__lte=agora,
                )
                .filter(Q(dt_expiracao__isnull=True) | Q(dt_expiracao__gt=agora))
                .select_related('tema')
                .order_by('-dt_publicacao')
                .first()
            )
        except Exception:
            ultimo_comunicado = None
    concluidos = mutiroes_concluidos()
    futuros = mutiroes_futuros()
    return render(request, 'site_institucional/index.html', {
        'mutiroes': concluidos[:3],
        'proximo_mutirao': futuros[0] if futuros else None,
        'praias': praias_de_atuacao(),
        'ultimo_comunicado': ultimo_comunicado,
    })


def multiroes(request):
    mutiroes = mutiroes_concluidos()
    busca = request.GET.get('busca', '').strip()
    praia_id = request.GET.get('praia', '').strip()

    if busca:
        if hasattr(mutiroes, 'filter'):
            mutiroes = mutiroes.filter(
                Q(praia__nome__icontains=busca)
                | Q(praia__cidade__icontains=busca)
                | Q(local__icontains=busca)
                | Q(descricao__icontains=busca)
            )
        else:
            b = busca.casefold()
            mutiroes = [
                m for m in mutiroes
                if (b in (m.praia.nome if m.praia else '').casefold()
                    or b in (m.praia.cidade if m.praia else '').casefold()
                    or b in (m.local or '').casefold()
                    or b in (m.descricao or '').casefold())
            ]

    # Obter praias de atuação sem join relacional com a tabela acao
    praias = praias_de_atuacao()
    if praia_id.isdigit() and praias.filter(pk=praia_id).exists():
        pid = int(praia_id)
        if hasattr(mutiroes, 'filter'):
            mutiroes = mutiroes.filter(praia_id=pid)
        else:
            mutiroes = [
                m for m in mutiroes
                if getattr(m, 'praia_id', None) == pid
                or (m.praia and getattr(m.praia, 'id_praia', None) == pid)
                or (m.praia and getattr(m.praia, 'pk', None) == pid)
            ]
    else:
        praia_id = ''

    pagina = Paginator(mutiroes, 20).get_page(request.GET.get('page'))
    filtros = request.GET.copy()
    filtros.pop('page', None)

    return render(request, 'site_institucional/multiroes.html', {
        'mutiroes': pagina,
        'pagina': pagina,
        'filtros_query': filtros.urlencode(),
        'busca': busca,
        'praias_filtro': praias,
        'praia_selecionada': praia_id,
    })


def calendario(request):
    futuros = mutiroes_futuros()
    concluidos = mutiroes_concluidos()
    return render(request, 'site_institucional/calendario.html', {
        'mutiroes': futuros,
        'mutiroes_realizados': concluidos,
    })


def praias_de_atuacao():
    return Praia.objects.filter(praia_ativa='ATIVA').order_by('nome', 'cidade')


def praias_atuacao(request):
    return render(request, 'site_institucional/praias.html', {
        'praias': praias_de_atuacao(),
    })
