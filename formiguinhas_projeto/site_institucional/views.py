from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator

from acao.models import Acao
from comunicado.models import Comunicado
from praia.models import Praia


def mutiroes_concluidos():
    return (
        Acao.objects.filter(
            tipo=Acao.TIPO_MUTIRAO,
            status=Acao.STATUS_CONCLUIDA,
        )
        .select_related('praia')
        .prefetch_related(
            'imagens_acao',
        )
        .order_by('-data', '-horario')
    )


def mutiroes_futuros():
    return (
        Acao.objects.filter(
            tipo=Acao.TIPO_MUTIRAO,
            data__gte=timezone.now().date(),
            status=Acao.STATUS_PLANEJADA,
        )
        .select_related('praia')
        .order_by('data', 'horario')
    )


def index(request):
    agora = timezone.now()
    ultimo_comunicado = Comunicado.objects.filter(
        status=Comunicado.PUBLICADO,
        publico=Comunicado.TODOS,
        dt_publicacao__isnull=False,
        dt_publicacao__lte=agora,
    ).filter(
        Q(dt_expiracao__isnull=True) | Q(dt_expiracao__gt=agora)
    ).select_related('tema').order_by('-dt_publicacao').first()
    return render(request, 'site_institucional/index.html', {
        'mutiroes': mutiroes_concluidos()[:1],
        'proximo_mutirao': mutiroes_futuros().first(),
        'praias': praias_de_atuacao(),
        'ultimo_comunicado': ultimo_comunicado,
    })


def multiroes(request):
    mutiroes = mutiroes_concluidos()
    busca = request.GET.get('busca', '').strip()
    praia_id = request.GET.get('praia', '').strip()

    if busca:
        mutiroes = mutiroes.filter(
            Q(praia__nome__icontains=busca)
            | Q(praia__cidade__icontains=busca)
            | Q(local__icontains=busca)
            | Q(descricao__icontains=busca)
        )

    praias = Praia.objects.filter(
        acoes__tipo=Acao.TIPO_MUTIRAO,
        acoes__status=Acao.STATUS_CONCLUIDA,
    ).distinct().order_by('nome', 'cidade')
    if praia_id.isdigit() and praias.filter(pk=praia_id).exists():
        mutiroes = mutiroes.filter(praia_id=praia_id)
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
    return render(request, 'site_institucional/calendario.html', {
        'mutiroes': mutiroes_futuros(),
        'mutiroes_realizados': mutiroes_concluidos(),
    })


def praias_de_atuacao():
    return Praia.objects.filter(praia_ativa='ATIVA').order_by('nome', 'cidade')


def praias_atuacao(request):
    return render(request, 'site_institucional/praias.html', {
        'praias': praias_de_atuacao(),
    })
