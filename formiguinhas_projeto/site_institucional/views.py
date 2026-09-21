from django.shortcuts import render
from django.utils import timezone
from datetime import datetime

from acao.models import Acao
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
    return render(request, 'site_institucional/index.html', {
        'mutiroes': mutiroes_concluidos()[:1],
        'praias': praias_de_atuacao(),
    })


def multiroes(request):
    return render(request, 'site_institucional/multiroes.html', {
        'mutiroes': mutiroes_concluidos(),
    })


def calendario(request):
    return render(request, 'site_institucional/calendario.html', {
        'mutiroes': mutiroes_futuros(),
    })


def praias_de_atuacao():
    return Praia.objects.filter(praia_ativa='ATIVA').order_by('nome', 'cidade')


def praias_atuacao(request):
    return render(request, 'site_institucional/praias.html', {
        'praias': praias_de_atuacao(),
    })
