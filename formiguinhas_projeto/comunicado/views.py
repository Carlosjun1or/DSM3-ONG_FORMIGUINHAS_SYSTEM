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
from usuario.views import get_session_usuario, render_acesso_bloqueado
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
from config.mongodb import test_mongo_connection
from .mongo_services import (
    salvar_comunicado_mongo,
    remover_comunicado_mongo,
    consultar_comunicados_mongo,
    obter_comunicado_mongo,
    obter_metricas_comunicados_mongo,
    registrar_leitura_comunicado_mongo,
)


class MongoTemaAdapter:
    def __init__(self, data):
        self.data = data or {}
        self.id = self.data.get('id')
        self.pk = self.data.get('id')
        self.nome = self.data.get('nome', '')


class MongoComunicadoAdapter:
    """Adapta documentos BSON do MongoDB Atlas para a interface esperada pelos templates."""
    def __init__(self, doc):
        self.doc = doc
        self.id_comunicado = doc.get('id_sql')
        self.pk = doc.get('id_sql')
        self.id = doc.get('id_sql')
        self.tipo = doc.get('tipo', '')
        self._tipo_display = doc.get('tipo_display', '')
        self.titulo = doc.get('titulo', '')
        self.resumo = doc.get('resumo', '')
        self.conteudo = doc.get('conteudo', '')
        self.publico = doc.get('publico', '')
        self._publico_display = doc.get('publico_display', '')
        self.status = doc.get('status', '')
        self._status_display = doc.get('status_display', '')
        self.dt_publicacao = doc.get('dt_publicacao')
        self.dt_expiracao = doc.get('dt_expiracao')
        self.criado_em = doc.get('criado_em')
        self.atualizado_em = doc.get('atualizado_em')
        self.dt_ultima_edicao = doc.get('dt_ultima_edicao')
        tema_data = doc.get('tema')
        self.tema = MongoTemaAdapter(tema_data) if tema_data else None
        autor_data = doc.get('autor') or {}
        self.autor = type('Autor', (), {'id_voluntario': type('Vol', (), {'nome': autor_data.get('nome', '')})()})()
        self.ultimo_editado_por_nome = doc.get('ultimo_editado_por_nome', '')
        self.is_from_mongo = True

    def get_tipo_display(self):
        return self._tipo_display or self.tipo

    def get_status_display(self):
        return self._status_display or self.status

    def get_publico_display(self):
        return self._publico_display or self.publico


def _admin(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return None, redirect('login')
    if usuario.tipo != 'ADMIN':
        return usuario, render_acesso_bloqueado(request)
    return usuario, None


def _vigentes_publicos():
    try:
        docs, _ = consultar_comunicados_mongo({'status': 'PUBLICADO', 'publico': 'TODOS'}, pagina=1, por_pagina=1000)
        if docs:
            return [MongoComunicadoAdapter(d) for d in docs]
    except Exception:
        pass
    return []


def _vigentes_internos(usuario):
    try:
        filtros = {'status': 'PUBLICADO'}
        if usuario.tipo != 'ADMIN':
            filtros['publico'] = {'$in': ['TODOS', 'COORDENADORES']}
        docs, _ = consultar_comunicados_mongo(filtros, pagina=1, por_pagina=1000)
        if docs:
            return [MongoComunicadoAdapter(d) for d in docs]
    except Exception:
        pass
    return []


def publicos(request):
    comunicados = _vigentes_publicos()
    tipo = request.GET.get('tipo')
    tema = request.GET.get('tema')
    if tipo in (Comunicado.AVISO, Comunicado.NOTICIA):
        comunicados = [c for c in comunicados if c.tipo == tipo]
    if tema:
        comunicados = [
            c for c in comunicados
            if c.tipo == Comunicado.NOTICIA and getattr(c.tema, 'id', None) == int(tema)
        ]
    page = Paginator(comunicados, 20).get_page(request.GET.get('page'))
    filtros = request.GET.copy()
    filtros.pop('page', None)
    return render(request, 'site_institucional/comunicados.html', {
        'comunicados': page,
        'temas': Tema.objects.filter(ativo=True).distinct(),
        'filtro_tipo': tipo,
        'filtro_tema': tema,
        'pagina': page,
        'filtros_query': filtros.urlencode(),
    })


def publico_detalhe(request, comunicado_id):
    doc = obter_comunicado_mongo(comunicado_id)
    if not doc:
        from django.http import Http404
        raise Http404("Comunicado não encontrado.")
    comunicado = MongoComunicadoAdapter(doc)
    return render(request, 'site_institucional/comunicado-detalhe.html', {'comunicado': comunicado})


def internos(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo not in ('ADMIN', 'COORDENADOR'):
        return redirect('home')

    lista_base = _vigentes_internos(usuario)
    total_nao_lidos = 0
    total_lidos = 0
    comunicados_com_status = []
    for c in lista_base:
        leituras = c.doc.get('leituras', []) if hasattr(c, 'doc') else []
        c.foi_lido = any(l.get('usuario_id') == usuario.pk for l in leituras)
        if c.foi_lido:
            total_lidos += 1
        else:
            total_nao_lidos += 1
        comunicados_com_status.append(c)

    busca = request.GET.get('busca', '').strip().lower()
    tipo = request.GET.get('tipo', '').strip()
    leitura = request.GET.get('leitura', '').strip()

    filtrados = []
    for c in comunicados_com_status:
        if busca:
            tema_nome = getattr(c.tema, 'nome', '') if c.tema else ''
            if (busca not in (c.titulo or '').lower() and
                busca not in (c.resumo or '').lower() and
                busca not in (c.conteudo or '').lower() and
                busca not in tema_nome.lower()):
                continue
        if tipo and c.tipo != tipo:
            continue
        if leitura == 'nao_lidos' and c.foi_lido:
            continue
        if leitura == 'lidos' and not c.foi_lido:
            continue
        filtrados.append(c)

    pagina, filtros_query = paginar_queryset(request, filtrados)
    return render(request, 'sistema/comunicados-central.html', {
        'comunicados': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
        'filtro_tipo': tipo,
        'filtro_leitura': leitura,
        'tipos': Comunicado.TIPO_CHOICES,
        'total_comunicados': len(lista_base),
        'total_nao_lidos': total_nao_lidos,
        'total_lidos': total_lidos,
        'total_filtrados': len(filtrados),
    })


@transaction.atomic
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
    leitura, criada = ComunicadoLeitura.objects.get_or_create(
        comunicado=comunicado,
        usuario=usuario,
    )
    if criada:
        registrar_evento(
            entidade='COMUNICADO_LEITURA',
            instancia=leitura,
            acao='VINCULO',
            usuario=usuario,
            resumo=f'{usuario.id_voluntario.nome} leu o comunicado "{comunicado.titulo}".',
        )
        # Sincroniza leitura no MongoDB Atlas
        registrar_leitura_comunicado_mongo(comunicado.id_comunicado, usuario)
    return render(request, 'sistema/comunicado-detalhe.html', {'comunicado': comunicado})


def admin_lista(request):
    usuario, resposta = _admin(request)
    if resposta:
        return resposta

    mongo_ok, mongo_msg, mongo_info = test_mongo_connection()
    mongo_stats = obter_metricas_comunicados_mongo() if mongo_ok else {'total': 0}

    fonte = 'mongo' if mongo_ok else 'sql'

    busca = request.GET.get('busca', '').strip()
    tipo = request.GET.get('tipo')
    status = request.GET.get('status')

    if fonte == 'mongo' and mongo_ok:
        filtros_mql = {'busca': busca, 'tipo': tipo, 'status': status}
        docs, total_filtrados = consultar_comunicados_mongo(filtros_mql, pagina=1, por_pagina=1000)
        lista_adaptada = [MongoComunicadoAdapter(d) for d in docs]
        pagina = Paginator(lista_adaptada, 20).get_page(request.GET.get('page'))
        total_comunicados = mongo_stats.get('total', 0)
        total_publicados = mongo_stats.get('publicados', 0)
        total_rascunhos = mongo_stats.get('rascunhos', 0)
        total_arquivados = mongo_stats.get('arquivados', 0)
    else:
        fonte = 'sql'
        comunicados = Comunicado.objects.select_related(
            'tema', 'autor__id_voluntario', 'ultimo_editado_por__id_voluntario'
        ).order_by('-criado_em')
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
        total_comunicados = Comunicado.objects.count()
        total_publicados = Comunicado.objects.filter(status=Comunicado.PUBLICADO).count()
        total_rascunhos = Comunicado.objects.filter(status=Comunicado.RASCUNHO).count()
        total_arquivados = Comunicado.objects.filter(status=Comunicado.ARQUIVADO).count()

    parametros_filtro = {
        chave: valor
        for chave, valor in (
            ('busca', busca),
            ('tipo', tipo),
            ('status', status),
            ('fonte', fonte if fonte == 'mongo' else None),
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
        'total_comunicados': total_comunicados,
        'total_publicados': total_publicados,
        'total_rascunhos': total_rascunhos,
        'total_filtrados': total_filtrados,
        'total_arquivados': total_arquivados,
        # Metadados de persistência poliglota
        'fonte_atual': fonte,
        'mongo_conectado': mongo_ok,
        'mongo_info': mongo_info,
        'mongo_stats': mongo_stats,
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
        # Persistência Poliglota: salvar no MongoDB Atlas
        salvar_comunicado_mongo(item)
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
    ).order_by('dt_registro', 'id_residuo')
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


@transaction.atomic
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


@transaction.atomic
def tema_form(request, tema_id=None):
    usuario, resposta = _admin(request)
    if resposta:
        return resposta
    tema = get_object_or_404(Tema, pk=tema_id) if tema_id else None
    valores_anteriores = snapshot(tema) if tema else {}
    form = TemaForm(request.POST or None, instance=tema)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.atualizado_por = usuario
        if not item.pk:
            item.criado_por = usuario
        item.save()
        registrar_evento(entidade='TEMA_COMUNICADO', instancia=item, acao='EDICAO' if tema else 'CRIACAO',
                         usuario=usuario, resumo='Tema de comunicados salvo',
                         valores_anteriores=valores_anteriores)
        return redirect('temas_comunicados')
    return render(request, 'sistema/tema-form.html', {'form': form, 'tema': tema})
