from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from acao.models import Acao
from auditoria.services import registrar_evento, snapshot
from doacao.models import Doacao
from equipe.models import Equipe
from residuo.models import ResiduoColetado
from usuario.paginacao import paginar_queryset
from usuario.views import get_session_usuario
from .forms import ComunicadoForm, TemaForm
from .models import (
    Comunicado,
    ComunicadoAcao,
    ComunicadoDoacao,
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
        'praias__praia', 'equipes__equipe',
        'acoes__acao', 'acoes__acao__residuos_coletados',
        'doacoes__doacao__financeira', 'doacoes__doacao__itens_materiais',
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
        'praias__praia', 'equipes__equipe',
        'acoes__acao', 'acoes__acao__residuos_coletados',
        'doacoes__doacao__financeira', 'doacoes__doacao__itens_materiais',
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
    page = Paginator(comunicados.order_by('-dt_publicacao'), 20).get_page(request.GET.get('page'))
    filtros = request.GET.copy()
    filtros.pop('page', None)
    return render(request, 'site_institucional/comunicados.html', {
        'comunicados': page, 'temas': Tema.objects.filter(ativo=True, noticias__in=_vigentes_publicos()).distinct(),
        'filtro_tipo': tipo, 'filtro_tema': tema,
        'pagina': page, 'filtros_query': filtros.urlencode(),
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
    base_comunicados = _vigentes_internos(usuario).annotate(
        foi_lido=Exists(
            ComunicadoLeitura.objects.filter(
                comunicado_id=OuterRef('pk'),
                usuario=usuario,
            )
        )
    ).distinct().order_by('-dt_publicacao')
    total_nao_lidos = base_comunicados.filter(foi_lido=False).count()
    total_lidos = base_comunicados.filter(foi_lido=True).count()

    comunicados = base_comunicados
    busca = request.GET.get('busca', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    leitura = request.GET.get('leitura', '').strip()
    if busca:
        comunicados = comunicados.filter(
            Q(titulo__icontains=busca)
            | Q(resumo__icontains=busca)
            | Q(conteudo__icontains=busca)
            | Q(tema__nome__icontains=busca)
        ).distinct()
    if tipo in dict(Comunicado.TIPO_CHOICES):
        comunicados = comunicados.filter(tipo=tipo)
    if leitura == 'nao_lidos':
        comunicados = comunicados.filter(foi_lido=False)
    elif leitura == 'lidos':
        comunicados = comunicados.filter(foi_lido=True)

    pagina, filtros_query = paginar_queryset(request, comunicados.order_by('-dt_publicacao'))
    return render(request, 'sistema/comunicados-central.html', {
        'comunicados': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
        'filtro_tipo': tipo,
        'filtro_leitura': leitura,
        'tipos': Comunicado.TIPO_CHOICES,
        'total_comunicados': base_comunicados.count(),
        'total_nao_lidos': total_nao_lidos,
        'total_lidos': total_lidos,
        'total_filtrados': comunicados.count(),
    })


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
    busca = request.GET.get('busca', '').strip()
    tipo = request.GET.get('tipo')
    status = request.GET.get('status')
    if busca:
        comunicados = comunicados.filter(
            Q(titulo__icontains=busca)
            | Q(resumo__icontains=busca)
            | Q(conteudo__icontains=busca)
        )
    if tipo in dict(Comunicado.TIPO_CHOICES):
        comunicados = comunicados.filter(tipo=tipo)
    if status in dict(Comunicado.STATUS_CHOICES):
        comunicados = comunicados.filter(status=status)
    total_filtrados = comunicados.count()
    pagina = Paginator(comunicados, 20).get_page(request.GET.get('page'))
    parametros_filtro = {
        chave: valor
        for chave, valor in (
            ('busca', busca),
            ('tipo', tipo),
            ('status', status),
        )
        if valor
    }
    return render(request, 'sistema/comunicados.html', {
        'usuario': usuario,
        'comunicados': pagina, 'pagina': pagina,
        'filtros_query': urlencode(parametros_filtro),
        'busca': busca,
        'filtro_tipo': tipo, 'filtro_status': status,
        'tipos': Comunicado.TIPO_CHOICES, 'status_choices': Comunicado.STATUS_CHOICES,
        'total_comunicados': Comunicado.objects.count(),
        'total_publicados': Comunicado.objects.filter(status=Comunicado.PUBLICADO).count(),
        'total_rascunhos': Comunicado.objects.filter(status=Comunicado.RASCUNHO).count(),
        'total_filtrados': total_filtrados,
        'total_arquivados': Comunicado.objects.filter(status=Comunicado.ARQUIVADO).count(),
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
    valores['doacoes_relacionadas'] = sorted(
        comunicado.doacoes.values_list('doacao_id', flat=True)
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
        doacoes = set(form.cleaned_data['doacoes'])
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
        ComunicadoDoacao.objects.filter(comunicado=item).delete()
        ComunicadoPraia.objects.bulk_create(
            [ComunicadoPraia(comunicado=item, praia=p) for p in praias]
        )
        ComunicadoEquipe.objects.bulk_create(
            [ComunicadoEquipe(comunicado=item, equipe=e) for e in equipes]
        )
        ComunicadoAcao.objects.bulk_create(
            [ComunicadoAcao(comunicado=item, acao=a) for a in acoes]
        )
        ComunicadoDoacao.objects.bulk_create(
            [ComunicadoDoacao(comunicado=item, doacao=doacao) for doacao in doacoes]
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
    doacao_ids = request.GET.getlist('doacao')
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
    residuos = ResiduoColetado.objects.filter(
        acao_id__in=acao_relacionada_ids,
    ).select_related('acao').order_by('acao__data', 'id_residuo')
    doacoes = Doacao.objects.filter(id_doacao__in=doacao_ids).select_related(
        'doador',
    ).order_by('-data_recebimento', '-id_doacao')

    return JsonResponse({
        'praia_ids': sorted(praia_ids),
        'equipe_ids': sorted(equipe_relacionada_ids),
        'acao_ids': sorted(acao_relacionada_ids),
        'acao_praia_ids': sorted(acao_praia_ids),
        'acao_equipe_ids': sorted(acao_equipe_ids),
        'equipe_praia_ids': sorted(
            equipes_relacionadas.exclude(praia_id=None).values_list('praia_id', flat=True)
        ),
        'residuos': [
            {
                'id': residuo.id_residuo,
                'acao_id': residuo.acao_id,
                'acao': f'{residuo.acao.get_tipo_display()} - {residuo.acao.data:%d/%m/%Y}',
                'tipo': residuo.get_tipo_display() or 'Resíduo sem tipo',
                'categoria': residuo.get_categoria_display() or 'Sem categoria',
                'quantidade': str(residuo.quantidade) if residuo.quantidade is not None else '',
                'unidade': residuo.get_unidade_display() if residuo.unidade else '',
            }
            for residuo in residuos
        ],
        'doacoes': [
            {
                'id': doacao.id_doacao,
                'tipo': doacao.get_tipo_display(),
                'data': doacao.data_recebimento.strftime('%d/%m/%Y'),
                'doador': 'Anônima' if doacao.anonima else (
                    doacao.doador.nome if doacao.doador_id else 'Doador não informado'
                ),
            }
            for doacao in doacoes
        ],
    })


def admin_status(request, comunicado_id, acao):
    usuario, resposta = _admin(request)
    if resposta:
        return resposta
    comunicado = get_object_or_404(Comunicado, id_comunicado=comunicado_id)
    if request.method != 'POST':
        return redirect('comunicados_admin')

    filtros = {
        chave: request.POST.get(chave)
        for chave in ('busca', 'tipo', 'page')
        if request.POST.get(chave)
    }
    if request.POST.get('filtro_status'):
        filtros['status'] = request.POST['filtro_status']
    url_lista = reverse('comunicados_admin')
    if filtros:
        url_lista = f'{url_lista}?{urlencode(filtros)}'

    operacoes = {
        'publicar': publicar,
        'despublicar': despublicar,
        'arquivar': arquivar,
        'desarquivar': desarquivar,
    }
    if acao == 'alterar_status':
        novo_status = request.POST.get('status')
        status_validos = {valor for valor, _ in Comunicado.STATUS_CHOICES}
        if novo_status not in status_validos:
            messages.error(request, 'Selecione um status válido para o comunicado.')
            return redirect(url_lista)
        if novo_status == comunicado.status:
            return redirect(url_lista)

        operacao = {
            Comunicado.PUBLICADO: publicar,
            Comunicado.ARQUIVADO: arquivar,
        }.get(novo_status)
        if novo_status == Comunicado.RASCUNHO:
            operacao = (
                despublicar if comunicado.status == Comunicado.PUBLICADO
                else desarquivar
            )
    else:
        operacao = operacoes.get(acao)
        if operacao is None:
            messages.error(request, 'Não foi possível alterar o status do comunicado.')
            return redirect(url_lista)

    try:
        operacao(comunicado, usuario)
    except ValidationError as erro:
        messages.error(request, ' '.join(erro.messages))
    else:
        messages.success(request, 'Status do comunicado atualizado com sucesso.')
    return redirect(url_lista)


def temas(request):
    usuario, resposta = _admin(request)
    if resposta:
        return resposta
    temas_cadastrados = Tema.objects.annotate(
        total_noticias=Count('noticias')
    ).order_by('nome')
    pagina, filtros_query = paginar_queryset(request, temas_cadastrados)
    return render(request, 'sistema/temas.html', {
        'temas': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'total_temas': Tema.objects.count(),
        'total_temas_ativos': Tema.objects.filter(ativo=True).count(),
        'total_temas_inativos': Tema.objects.filter(ativo=False).count(),
    })


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
