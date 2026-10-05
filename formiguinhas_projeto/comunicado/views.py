from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from acao.models import Acao
from auditoria.services import registrar_evento, snapshot
from equipe.models import Equipe
from usuario.views import get_session_usuario
from .forms import ComunicadoForm, TemaForm
from .models import (
    Comunicado,
    ComunicadoAcao,
    ComunicadoEquipe,
    ComunicadoLeitura,
    ComunicadoPraia,
    Tema,
)
from .services import arquivar, desarquivar, despublicar, publicar


def _admin(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return None, redirect('login')
    if usuario.tipo != 'ADMIN':
        return usuario, render(
            request,
            'sistema/comunicado-acesso-negado.html',
            status=403,
        )
    return usuario, None


def _vigentes_publicos():
    agora = timezone.now()
    return Comunicado.objects.filter(
        status=Comunicado.PUBLICADO, publico=Comunicado.TODOS,
        dt_publicacao__isnull=False, dt_publicacao__lte=agora,
    ).filter(Q(dt_expiracao__isnull=True) | Q(dt_expiracao__gt=agora)).select_related('tema').prefetch_related(
        'praias__praia', 'equipes__equipe', 'acoes__acao'
    )


def _vigentes_internos(usuario):
    comunicados = Comunicado.objects.filter(
        status=Comunicado.PUBLICADO,
        dt_publicacao__isnull=False,
        dt_publicacao__lte=timezone.now(),
    ).filter(
        Q(dt_expiracao__isnull=True) | Q(dt_expiracao__gt=timezone.now())
    )
    if usuario.tipo != 'ADMIN':
        comunicados = comunicados.filter(
            Q(publico=Comunicado.TODOS) | Q(publico=Comunicado.COORDENADORES)
        )
    return comunicados.select_related('tema').prefetch_related(
        'praias__praia', 'equipes__equipe', 'acoes__acao'
    )


def publicos(request):
    comunicados = _vigentes_publicos()
    tipo = request.GET.get('tipo')
    tema = request.GET.get('tema')
    entidade = request.GET.get('entidade')
    if tipo in (Comunicado.AVISO, Comunicado.NOTICIA):
        comunicados = comunicados.filter(tipo=tipo)
    if tema:
        comunicados = comunicados.filter(tipo=Comunicado.NOTICIA, tema_id=tema)
    if entidade:
        comunicados = comunicados.filter(
            Q(praias__praia_id=entidade) | Q(equipes__equipe_id=entidade) | Q(acoes__acao_id=entidade)
        ).distinct()
    page = Paginator(comunicados.order_by('-dt_publicacao'), 10).get_page(request.GET.get('page'))
    return render(request, 'site_institucional/comunicados.html', {
        'comunicados': page, 'temas': Tema.objects.filter(ativo=True, noticias__in=_vigentes_publicos()).distinct(),
        'filtro_tipo': tipo, 'filtro_tema': tema,
    })


def publico_detalhe(request, comunicado_id):
    comunicado = get_object_or_404(_vigentes_publicos(), id_comunicado=comunicado_id)
    return render(request, 'site_institucional/comunicado-detalhe.html', {'comunicado': comunicado})


def internos(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo not in ('ADMIN', 'COORDENADOR'):
        return redirect('home')
    comunicados = _vigentes_internos(usuario)
    comunicados = comunicados.distinct().order_by('-dt_publicacao')
    ComunicadoLeitura.objects.bulk_create(
        [ComunicadoLeitura(comunicado=comunicado, usuario=usuario) for comunicado in comunicados],
        ignore_conflicts=True,
    )
    return render(request, 'sistema/comunicados-central.html', {'comunicados': comunicados})


def interno_detalhe(request, comunicado_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo not in ('ADMIN', 'COORDENADOR'):
        return redirect('home')
    comunicado = get_object_or_404(
        _vigentes_internos(usuario),
        id_comunicado=comunicado_id,
    )
    ComunicadoLeitura.objects.get_or_create(comunicado=comunicado, usuario=usuario)
    return render(request, 'sistema/comunicado-detalhe.html', {'comunicado': comunicado})


def admin_lista(request):
    usuario, resposta = _admin(request)
    if resposta:
        return resposta
    comunicados = Comunicado.objects.select_related(
        'tema', 'autor__id_voluntario', 'ultimo_editado_por__id_voluntario'
    ).order_by('-criado_em')
    tipo = request.GET.get('tipo')
    status = request.GET.get('status')
    if tipo in dict(Comunicado.TIPO_CHOICES):
        comunicados = comunicados.filter(tipo=tipo)
    if status in dict(Comunicado.STATUS_CHOICES):
        comunicados = comunicados.filter(status=status)
    return render(request, 'sistema/comunicados.html', {
        'usuario': usuario,
        'comunicados': comunicados, 'filtro_tipo': tipo, 'filtro_status': status,
        'tipos': Comunicado.TIPO_CHOICES, 'status_choices': Comunicado.STATUS_CHOICES,
        'total_comunicados': Comunicado.objects.count(),
        'total_publicados': Comunicado.objects.filter(status=Comunicado.PUBLICADO).count(),
        'total_rascunhos': Comunicado.objects.filter(status=Comunicado.RASCUNHO).count(),
    })


def _snapshot_comunicado_completo(comunicado):
    valores = snapshot(comunicado)
    valores['praias_relacionadas'] = sorted(
        comunicado.praias.values_list('praia_id', flat=True)
    )
    valores['equipes_relacionadas'] = sorted(
        comunicado.equipes.values_list('equipe_id', flat=True)
    )
    valores['acoes_relacionadas'] = sorted(
        comunicado.acoes.values_list('acao_id', flat=True)
    )
    return valores


@transaction.atomic
def admin_form(request, comunicado_id=None):
    usuario, resposta = _admin(request)
    if resposta:
        return resposta
    comunicado = get_object_or_404(Comunicado, id_comunicado=comunicado_id) if comunicado_id else None
    anterior = _snapshot_comunicado_completo(comunicado) if comunicado else {}
    form = ComunicadoForm(request.POST or None, instance=comunicado)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.autor = item.autor or usuario
        item.perfil_autor = item.perfil_autor or usuario.tipo
        item.ultimo_editado_por = usuario
        item.dt_ultima_edicao = timezone.now()
        item.full_clean()
        item.save()
        form.save_m2m()
        praias = set(form.cleaned_data['praias'])
        equipes = set(form.cleaned_data['equipes'])
        acoes = set(form.cleaned_data['acoes'])
        for equipe in equipes:
            if equipe.praia_id:
                praias.add(equipe.praia)
        for acao in acoes:
            if acao.praia_id:
                praias.add(acao.praia)
            equipes.update(
                Equipe.objects.filter(
                    id_equipe__in=acao.equipes_vinculadas.values_list('equipe_id', flat=True)
                ).select_related('praia')
            )
        for equipe in equipes:
            if equipe.praia_id:
                praias.add(equipe.praia)
        ComunicadoPraia.objects.filter(comunicado=item).delete()
        ComunicadoEquipe.objects.filter(comunicado=item).delete()
        ComunicadoAcao.objects.filter(comunicado=item).delete()
        ComunicadoPraia.objects.bulk_create(
            [ComunicadoPraia(comunicado=item, praia=p) for p in praias]
        )
        ComunicadoEquipe.objects.bulk_create(
            [ComunicadoEquipe(comunicado=item, equipe=e) for e in equipes]
        )
        ComunicadoAcao.objects.bulk_create(
            [ComunicadoAcao(comunicado=item, acao=a) for a in acoes]
        )
        registrar_evento(
            entidade='COMUNICADO',
            instancia=item,
            acao='EDICAO' if comunicado else 'CRIACAO',
            usuario=usuario,
            resumo='Comunicado salvo',
            valores_anteriores=anterior,
            valores_novos=_snapshot_comunicado_completo(item),
        )
        return redirect('comunicados_admin')
    return render(request, 'sistema/comunicado-form.html', {'form': form, 'comunicado': comunicado})


def relacionamentos(request):
    usuario, resposta = _admin(request)
    if resposta:
        return JsonResponse({'detail': 'Acesso negado.'}, status=403)

    equipe_ids = request.GET.getlist('equipe')
    acao_ids = request.GET.getlist('acao')
    equipes = Equipe.objects.filter(
        id_equipe__in=equipe_ids,
        status='ATIVA',
    )
    acoes = Acao.objects.filter(id_acao__in=acao_ids).prefetch_related(
        'equipes_vinculadas',
    )
    equipe_relacionada_ids = set(equipes.values_list('id_equipe', flat=True))
    praia_ids = set(equipes.exclude(praia_id=None).values_list('praia_id', flat=True))
    acao_relacionada_ids = set(acoes.values_list('id_acao', flat=True))
    acao_equipe_ids = set()
    acao_praia_ids = set(acoes.exclude(praia_id=None).values_list('praia_id', flat=True))
    for acao in acoes:
        if acao.praia_id:
            praia_ids.add(acao.praia_id)
        acao_equipe_ids.update(acao.equipes_vinculadas.values_list('equipe_id', flat=True))
    equipe_relacionada_ids.update(acao_equipe_ids)

    equipes_relacionadas = Equipe.objects.filter(
        id_equipe__in=equipe_relacionada_ids,
        status='ATIVA',
    )
    praia_ids.update(
        equipes_relacionadas.exclude(praia_id=None).values_list('praia_id', flat=True)
    )

    return JsonResponse({
        'praia_ids': sorted(praia_ids),
        'equipe_ids': sorted(equipe_relacionada_ids),
        'acao_ids': sorted(acao_relacionada_ids),
        'acao_praia_ids': sorted(acao_praia_ids),
        'acao_equipe_ids': sorted(acao_equipe_ids),
        'equipe_praia_ids': sorted(
            equipes_relacionadas.exclude(praia_id=None).values_list('praia_id', flat=True)
        ),
    })


def admin_status(request, comunicado_id, acao):
    usuario, resposta = _admin(request)
    if resposta:
        return resposta
    comunicado = get_object_or_404(Comunicado, id_comunicado=comunicado_id)
    if request.method == 'POST':
        operacoes = {
            'publicar': publicar,
            'despublicar': despublicar,
            'arquivar': arquivar,
            'desarquivar': desarquivar,
        }
        if acao not in operacoes:
            return redirect('comunicados_admin')
        operacoes[acao](comunicado, usuario)
    return redirect('comunicados_admin')


def temas(request):
    usuario, resposta = _admin(request)
    if resposta:
        return resposta
    return render(request, 'sistema/temas.html', {'temas': Tema.objects.all()})


def tema_form(request, tema_id=None):
    usuario, resposta = _admin(request)
    if resposta:
        return resposta
    tema = get_object_or_404(Tema, pk=tema_id) if tema_id else None
    form = TemaForm(request.POST or None, instance=tema)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.atualizado_por = usuario
        if not item.pk:
            item.criado_por = usuario
        item.save()
        registrar_evento(entidade='TEMA_COMUNICADO', instancia=item, acao='EDICAO' if tema else 'CRIACAO',
                         usuario=usuario, resumo='Tema de comunicados salvo')
        return redirect('temas_comunicados')
    return render(request, 'sistema/tema-form.html', {'form': form, 'tema': tema})
