from urllib.parse import urlencode

from django.contrib import messages
from django.db import models, transaction
from django.db.models import Avg, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from usuario.models import Usuario
from usuario.views import render_acesso_bloqueado
from usuario.paginacao import paginar_queryset

from .forms import BagForm, CondominioForm, MovimentacaoBagForm
from auditoria.models import EventoAuditoria

from .models import Bag, Condominio, MovimentacaoBag
from .services import registrar_auditoria, snapshot
from config.mongodb import test_mongo_connection
from .mongo_services import (
    salvar_condominio_mongo,
    salvar_condominio_por_bag,
    remover_condominio_mongo,
    consultar_condominios_mongo,
    obter_condominio_mongo,
    obter_metricas_condominios_mongo,
)


class MongoBagAdapter:
    """
    Adapta um documento de Bag vindo do MongoDB (dict) para a interface
    que o template espera (objeto com atributos). O MongoDB armazena bags
    embutidas dentro do documento do condomínio, então o adapter recebe
    o dict da bag já 'desembalado' e constrói um proxy do condomínio pai.
    """
    def __init__(self, item):
        self.item = item
        self.id_bag = item.get('id') or item.get('id_bag')
        self.pk = self.id_bag
        self.codigo = item.get('codigo', '')
        self.status = item.get('status', '')
        self._status_display = item.get('status_display', '')
        self.peso_atual_kg = item.get('peso_atual_kg', 0)
        self.percentual_ocupacao = item.get('percentual_ocupacao', 0)
        
        cond_data = item.get('condominio') or {}
        praia_data = cond_data.get('praia')
        self.condominio = type('CondominioProxy', (), {
            'id_condominio': cond_data.get('id_condominio') or item.get('condominio_id'),
            'pk': cond_data.get('id_condominio') or item.get('condominio_id'),
            'nome': cond_data.get('nome') or item.get('condominio_nome', ''),
            'cidade': cond_data.get('cidade', ''),
            'estado': cond_data.get('estado', ''),
            'praia': MongoPraiaAdapter(praia_data) if praia_data else None,
        })()
        self.movimentacoes = type('MovRel', (), {'all': lambda self: []})()

    def get_status_display(self):
        return self._status_display or self.status


class MongoBagsRelAdapter:
    """Simula o related_manager 'bags' de um Condominio do Django ORM.
    Permite que templates chamem condominio.bags.all() tanto no caminho MongoDB quanto SQLite."""
    def __init__(self, bags_list):
        self._bags = [MongoBagAdapter(b) for b in bags_list]

    def all(self):
        return self._bags

    def count(self):
        return len(self._bags)


class MongoPraiaAdapter:
    """Proxy leve de Praia para documentos do MongoDB (apenas os campos usados pelos templates)."""
    def __init__(self, praia_dict):
        self.praia = praia_dict or {}
        self.id = self.praia.get('id')
        self.nome = self.praia.get('nome', '')
        self.cidade = self.praia.get('cidade', '')


class MongoCondominioAdapter:
    """Adapta documento de Condomínio do MongoDB para a interface esperada pelos templates.
    
    O MongoDB retorna um dict com campos aninhados (responsavel.nome, endereco.cidade).
    O template Django acessa por atributo (condominio.responsavel_nome, condominio.cidade).
    Este adapter 'achata' os campos aninhados e fornece os métodos get_*_display()
    que os templates chamam para renderizar choices (porte, status, confiabilidade).
    """
    def __init__(self, doc):
        self.doc = doc
        self.id_condominio = doc.get('id_sql')
        self.pk = doc.get('id_sql')
        self.id = doc.get('id_sql')
        self.nome = doc.get('nome', '')
        resp = doc.get('responsavel') or {}
        self.responsavel_nome = resp.get('nome', '')
        self.responsavel_telefone = resp.get('telefone', '')
        self.responsavel_email = resp.get('email', '')
        end = doc.get('endereco') or {}
        self.endereco = end.get('logradouro', '')
        self.numero = end.get('numero', '')
        self.complemento = end.get('complemento', '')
        self.bairro = end.get('bairro', '')
        self.cidade = end.get('cidade', '')
        self.estado = end.get('estado', '')
        self.cep = end.get('cep', '')
        praia_data = doc.get('praia')
        self.praia = MongoPraiaAdapter(praia_data) if praia_data else None
        self.porte = doc.get('porte', '')
        self._porte_display = doc.get('porte_display', '')
        self.confiabilidade = doc.get('confiabilidade', '')
        self._confiabilidade_display = doc.get('confiabilidade_display', '')
        self.status = doc.get('status', '')
        self._status_display = doc.get('status_display', '')
        self.observacoes = doc.get('observacoes', '')
        self.cadastrado_por_nome = doc.get('cadastrado_por_nome', '')
        self.ultimo_editado_por_nome = doc.get('ultimo_editado_por_nome', '')
        self.dt_cadastro = doc.get('dt_cadastro')
        self.dt_ultima_edicao = doc.get('dt_ultima_edicao')
        self.bags = MongoBagsRelAdapter(doc.get('bags', []))
        self.is_from_mongo = True

    def get_porte_display(self):
        return self._porte_display or self.porte

    def get_confiabilidade_display(self):
        return self._confiabilidade_display or self.confiabilidade

    def get_status_display(self):
        return self._status_display or self.status


def get_session_usuario(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None
    try:
        return Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return None


def usuario_logado(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return None
    return usuario


def exigir_admin(request):
    usuario = usuario_logado(request)
    if not usuario:
        return None
    if usuario.tipo != 'ADMIN':
        messages.error(request, 'Somente administradores podem alterar o controle de bags.')
        return False
    return usuario


def condominios_view(request):
    """
    Lista condomínios com métricas e filtros.
    
    Fonte de leitura: MongoDB Atlas (primária) com fallback para SQLite.
    O MongoDB armazena documentos ricos (condomínio + bags embutidas + praia).
    Se o MongoDB estiver offline, consulta o SQLite (tables nativas do Django ORM)
    para não deixar o usuário sem dados.
    """
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)

    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()

    # Fonte primária: MongoDB Atlas | Fallback: SQLite
    mongo_ok, mongo_msg, mongo_info = test_mongo_connection()

    if mongo_ok:
        # --- Fonte MongoDB ---
        mongo_stats = obter_metricas_condominios_mongo()
        filtros_mql = {'busca': busca, 'status': status}
        docs, total_docs = consultar_condominios_mongo(filtros_mql, pagina=1, por_pagina=1000)
        lista_adaptada = [MongoCondominioAdapter(d) for d in docs]
        pagina, filtros_query = paginar_queryset(request, lista_adaptada)

        total_condominios = mongo_stats.get('total', 0)
        condominios_ativos = mongo_stats.get('ativos', 0)
        condominios_em_avaliacao = mongo_stats.get('em_avaliacao', 0)
        total_bags = mongo_stats.get('total_bags', 0)
        bags_cheias = mongo_stats.get('bags_cheias', 0)
        bags_disponiveis = mongo_stats.get('bags_disponiveis', 0)
        fonte = 'mongo'
    else:
        # --- Fallback SQLite ---
        fonte = 'sql'
        condominios_qs = Condominio.objects.select_related('praia').prefetch_related('bags')
        if busca:
            condominios_qs = condominios_qs.filter(
                Q(nome__icontains=busca)
                | Q(endereco__icontains=busca)
                | Q(bairro__icontains=busca)
                | Q(cidade__icontains=busca)
                | Q(responsavel_nome__icontains=busca)
            )
        if status:
            condominios_qs = condominios_qs.filter(status=status)
        pagina, filtros_query = paginar_queryset(request, condominios_qs)

        total_condominios = Condominio.objects.count()
        condominios_ativos = Condominio.objects.filter(status='ATIVO').count()
        condominios_em_avaliacao = Condominio.objects.filter(confiabilidade='EM_AVALIACAO').count()
        total_bags = Bag.objects.count()
        bags_cheias = Bag.objects.filter(status='CHEIA').count()
        bags_disponiveis = Bag.objects.filter(status='DISPONIVEL').count()

    return render(request, 'sistema/condominios.html', {
        'usuario': usuario,
        'condominios': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
        'status_selecionado': status,
        'status_choices': Condominio.STATUS_CHOICES,
        'total_condominios': total_condominios,
        'condominios_ativos': condominios_ativos,
        'condominios_em_avaliacao': condominios_em_avaliacao,
        'total_bags': total_bags,
        'bags_cheias': bags_cheias,
        'bags_disponiveis': bags_disponiveis,
        # Metadados de persistência poliglota
        'fonte_atual': fonte,
        'mongo_conectado': mongo_ok,
        'mongo_info': mongo_info,
        'mongo_msg': mongo_msg,
        'mongo_stats': mongo_stats if mongo_ok else {'total': 0},
    })


def bags_view(request):
    """
    Lista todas as bags com filtros e métricas.
    
    No MongoDB as bags estão embutidas nos documentos de condomínio (sub-documentos).
    No SQLite fallback, bags são uma tabela separada com FK para condominio.
    O adapter MongoBagAdapter uniformiza os dois caminhos para o template.
    """
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)

    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()

    # Fonte primária: MongoDB Atlas | Fallback: SQLite
    mongo_ok, mongo_msg, mongo_info = test_mongo_connection()

    if mongo_ok:
        # --- Fonte MongoDB ---
        filtros_mql = {}
        docs, _ = consultar_condominios_mongo(filtros_mql, pagina=1, por_pagina=1000)
        # Desembala as bags de todos os condomínios
        bags_raw = []
        for doc in docs:
            cond_nome = doc.get('nome', '')
            cond_id = doc.get('id_sql')
            cond_end = doc.get('endereco') or {}
            cond_cidade = cond_end.get('cidade', '')
            cond_estado = cond_end.get('estado', '')
            cond_praia = doc.get('praia')
            for b in doc.get('bags', []):
                b['condominio'] = {
                    'id_condominio': cond_id,
                    'nome': cond_nome,
                    'cidade': cond_cidade,
                    'estado': cond_estado,
                    'praia': cond_praia,
                }
                b['condominio_nome'] = cond_nome
                b['condominio_id'] = cond_id
                bags_raw.append(b)
        # Filtragem em memória
        if busca:
            busca_lower = busca.lower()
            bags_raw = [
                b for b in bags_raw
                if busca_lower in (b.get('codigo') or '').lower()
                or busca_lower in (b.get('condominio_nome') or '').lower()
            ]
        if status:
            bags_raw = [b for b in bags_raw if b.get('status') == status]

        bags_adaptadas = [MongoBagAdapter(b) for b in bags_raw]
        pagina, filtros_query = paginar_queryset(request, bags_adaptadas)

        total_bags = len(bags_raw)
        bags_cheias = sum(1 for b in bags_raw if b.get('status') == 'CHEIA')
        bags_em_uso = sum(1 for b in bags_raw if b.get('status') == 'EM_USO')
        bags_disponiveis = sum(1 for b in bags_raw if b.get('status') == 'DISPONIVEL')
        bags_danificadas = sum(1 for b in bags_raw if b.get('status') == 'DANIFICADA')
        ocupacao_media = (
            sum(b.get('percentual_ocupacao', 0) for b in bags_raw) / len(bags_raw)
            if bags_raw else 0
        )
    else:
        # --- Fallback SQLite ---
        bags_qs = Bag.objects.select_related('condominio', 'condominio__praia')
        if busca:
            bags_qs = bags_qs.filter(
                Q(codigo__icontains=busca)
                | Q(condominio__nome__icontains=busca)
            )
        if status:
            bags_qs = bags_qs.filter(status=status)
        pagina, filtros_query = paginar_queryset(request, bags_qs)

        total_bags = Bag.objects.count()
        bags_cheias = Bag.objects.filter(status='CHEIA').count()
        bags_em_uso = Bag.objects.filter(status='EM_USO').count()
        bags_disponiveis = Bag.objects.filter(status='DISPONIVEL').count()
        bags_danificadas = Bag.objects.filter(status='DANIFICADA').count()
        ocupacao_media = (
            Bag.objects.aggregate(media=Avg('percentual_ocupacao'))['media'] or 0
        )

    return render(request, 'sistema/bags.html', {
        'usuario': usuario,
        'bags': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
        'status_selecionado': status,
        'status_choices': Bag.STATUS_CHOICES,
        'total_bags': total_bags,
        'bags_cheias': bags_cheias,
        'bags_em_uso': bags_em_uso,
        'bags_disponiveis': bags_disponiveis,
        'bags_danificadas': bags_danificadas,
        'ocupacao_media': ocupacao_media,
        'mongo_conectado': mongo_ok,
        'mongo_msg': mongo_msg,
        'mongo_info': mongo_info,
    })


def auditorias_view(request):
    """Compatibilidade com o endereço antigo; a tela agora é global."""
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    from auditoria.views import global_auditoria
    return global_auditoria(request)


@transaction.atomic
def cadastrar_condominio_view(request):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)

    form = CondominioForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        condominio = form.save(commit=False)
        condominio.cadastrado_por = usuario
        condominio.cadastrado_por_nome = usuario.id_voluntario.nome
        condominio.save()
        registrar_auditoria(
            entidade='CONDOMINIO',
            instancia=condominio,
            acao='CRIACAO',
            usuario=usuario,
            resumo=f'Condomínio "{condominio.nome}" cadastrado.',
        )
        # Persistencia Poliglota: salvar no MongoDB Atlas
        salvar_condominio_mongo(condominio)
        messages.success(request, 'Condomínio cadastrado com sucesso.')
        return redirect('detalhe_condominio', condominio_id=condominio.id_condominio)
    return render(request, 'sistema/cadastro-condominio.html', {'usuario': usuario, 'form': form})


@transaction.atomic
def editar_condominio_view(request, condominio_id):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)

    condominio = get_object_or_404(Condominio, id_condominio=condominio_id)
    valores_anteriores = snapshot(condominio)
    form = CondominioForm(request.POST or None, instance=condominio)
    if request.method == 'POST' and form.is_valid():
        condominio = form.save(commit=False)
        condominio.ultimo_editado_por = usuario
        condominio.ultimo_editado_por_nome = usuario.id_voluntario.nome
        condominio.dt_ultima_edicao = timezone.now()
        condominio.save()
        registrar_auditoria(
            entidade='CONDOMINIO',
            instancia=condominio,
            acao='EDICAO',
            usuario=usuario,
            resumo=f'Condomínio "{condominio.nome}" editado.',
            valores_anteriores=valores_anteriores,
        )
        # Persistencia Poliglota: salvar no MongoDB Atlas
        salvar_condominio_mongo(condominio)
        messages.success(request, 'Condomínio atualizado com sucesso.')
        return redirect('detalhe_condominio', condominio_id=condominio.id_condominio)
    return render(request, 'sistema/cadastro-condominio.html', {
        'usuario': usuario,
        'form': form,
        'condominio': condominio,
        'modo_edicao': True,
    })


def detalhe_condominio_view(request, condominio_id):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    condominio = get_object_or_404(
        Condominio.objects.select_related('praia'),
        id_condominio=condominio_id,
    )
    bags = condominio.bags.all()
    return render(request, 'sistema/detalhe-condominio.html', {
        'usuario': usuario,
        'condominio': condominio,
        'bags': bags,
        'movimentacoes': MovimentacaoBag.objects.filter(
            bag__condominio=condominio,
        ).select_related('bag', 'registrado_por').order_by(
            '-data_movimentacao',
            '-id_movimentacao',
        )[:20],
        'auditorias': EventoAuditoria.objects.filter(
            entidade='CONDOMINIO',
            id_registro=condominio.id_condominio,
        ).select_related('usuario')[:30],
    })


@transaction.atomic
def cadastrar_bag_view(request):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)

    form = BagForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        bag = form.save(commit=False)
        bag.cadastrado_por = usuario
        bag.cadastrado_por_nome = usuario.id_voluntario.nome
        bag.save()
        registrar_auditoria(
            entidade='BAG',
            instancia=bag,
            acao='CRIACAO',
            usuario=usuario,
            resumo=f'Bag "{bag.codigo}" cadastrada.',
        )
        # Persistencia Poliglota: salvar no MongoDB Atlas
        salvar_condominio_por_bag(bag)
        messages.success(request, 'Bag grande cadastrada com sucesso.')
        return redirect('detalhe_bag', bag_id=bag.id_bag)
    return render(request, 'sistema/cadastro-bag.html', {'usuario': usuario, 'form': form})


@transaction.atomic
def editar_bag_view(request, bag_id):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)

    bag = get_object_or_404(Bag, id_bag=bag_id)
    valores_anteriores = snapshot(bag)
    form = BagForm(request.POST or None, instance=bag)
    if request.method == 'POST' and form.is_valid():
        bag = form.save(commit=False)
        bag.ultimo_editado_por = usuario
        bag.ultimo_editado_por_nome = usuario.id_voluntario.nome
        bag.dt_ultima_edicao = timezone.now()
        bag.save()
        registrar_auditoria(
            entidade='BAG',
            instancia=bag,
            acao='EDICAO',
            usuario=usuario,
            resumo=f'Bag "{bag.codigo}" editada.',
            valores_anteriores=valores_anteriores,
        )
        # Persistencia Poliglota: salvar no MongoDB Atlas
        salvar_condominio_por_bag(bag)
        messages.success(request, 'Bag atualizada com sucesso.')
        return redirect('detalhe_bag', bag_id=bag.id_bag)
    return render(request, 'sistema/cadastro-bag.html', {
        'usuario': usuario,
        'form': form,
        'bag': bag,
        'modo_edicao': True,
    })


@transaction.atomic
def atualizar_status_bag_view(request, bag_id):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    bag = get_object_or_404(Bag, id_bag=bag_id)

    filtros = {}
    if request.POST.get('busca'):
        filtros['busca'] = request.POST['busca']
    if request.POST.get('filtro_status'):
        filtros['status'] = request.POST['filtro_status']
    destino = 'bags'
    if request.method != 'POST':
        return redirect(destino)

    novo_status = request.POST.get('status', '')
    if novo_status not in dict(Bag.STATUS_CHOICES):
        messages.error(request, 'Selecione um status válido para a bag.')
    elif novo_status != bag.status:
        status_anterior = bag.get_status_display()
        valores_anteriores = snapshot(bag)
        movimentacao = MovimentacaoBag.objects.create(
            bag_id=bag.pk,
            tipo='OUTRO',
            status_anterior=bag.status,
            status_novo=novo_status,
            data_movimentacao=timezone.now(),
            observacao='Status alterado diretamente pelo controle de bags.',
            registrado_por=usuario,
            registrado_por_nome=usuario.id_voluntario.nome,
        )
        registrar_auditoria(
            entidade='MOVIMENTACAO',
            instancia=movimentacao,
            acao='MOVIMENTACAO',
            usuario=usuario,
            resumo=(
                f'Status da bag "{bag.codigo}" alterado de {status_anterior} '
                f'para {dict(Bag.STATUS_CHOICES)[novo_status]}.'
            ),
        )
        bag.status = novo_status
        bag.ultimo_editado_por = usuario
        bag.ultimo_editado_por_nome = usuario.id_voluntario.nome
        bag.dt_ultima_edicao = timezone.now()
        bag.save(update_fields=[
            'status', 'ultimo_editado_por', 'ultimo_editado_por_nome',
            'dt_ultima_edicao',
        ])
        registrar_auditoria(
            entidade='BAG',
            instancia=bag,
            acao='MUDANCA_STATUS',
            usuario=usuario,
            resumo=f'Status da bag "{bag.codigo}" alterado.',
            valores_anteriores=valores_anteriores,
            valores_novos=snapshot(bag),
        )
        # Persistencia Poliglota: salvar no MongoDB Atlas
        salvar_condominio_por_bag(bag)
        messages.success(request, 'Status da bag atualizado com movimentação registrada.')
    return redirect(f'{reverse("bags")}?{urlencode(filtros)}' if filtros else destino)


def detalhe_bag_view(request, bag_id):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    bag = get_object_or_404(Bag.objects.select_related('condominio', 'condominio__praia'), id_bag=bag_id)
    from residuo.models import ColetaResiduo
    movimentacoes = bag.movimentacoes.select_related('registrado_por').all()
    return render(request, 'sistema/detalhe-bag.html', {
        'usuario': usuario,
        'bag': bag,
        'movimentacoes': movimentacoes,
        'auditorias': EventoAuditoria.objects.filter(
            models.Q(entidade='BAG', id_registro=bag.id_bag)
            | models.Q(
                entidade='MOVIMENTACAO',
                id_registro__in=movimentacoes.values('id_movimentacao'),
            ),
        ).select_related('usuario').order_by('-data_evento', '-id')[:50],
        'coletas_residuos': ColetaResiduo.objects.filter(
            bag_id=bag.pk,
        ).prefetch_related('itens').order_by('-data_coleta'),
    })


@transaction.atomic
def cadastrar_movimentacao_view(request, bag_id):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)

    bag = get_object_or_404(Bag, id_bag=bag_id)
    form = MovimentacaoBagForm(request.POST or None, bag=bag)
    if request.method == 'POST' and form.is_valid():
        movimentacao = form.save(commit=False)
        movimentacao.bag = bag
        movimentacao.status_anterior = bag.status
        movimentacao.registrado_por = usuario
        movimentacao.registrado_por_nome = usuario.id_voluntario.nome
        movimentacao.save()
        registrar_auditoria(
            entidade='MOVIMENTACAO',
            instancia=movimentacao,
            acao='MOVIMENTACAO',
            usuario=usuario,
            resumo=f'Movimentação "{movimentacao.get_tipo_display()}" registrada para a bag "{bag.codigo}".',
        )
        status_anterior = bag.get_status_display()
        bag.status = movimentacao.status_novo
        bag.ultimo_editado_por = usuario
        bag.ultimo_editado_por_nome = usuario.id_voluntario.nome
        bag.dt_ultima_edicao = timezone.now()
        bag.save(update_fields=[
            'status', 'ultimo_editado_por', 'ultimo_editado_por_nome', 'dt_ultima_edicao',
        ])
        registrar_auditoria(
            entidade='BAG',
            instancia=bag,
            acao='MUDANCA_STATUS',
            usuario=usuario,
            resumo=f'Status da bag "{bag.codigo}" alterado.',
            valores_anteriores={'status': status_anterior},
            valores_novos={'status': bag.get_status_display()},
        )
        # Persistencia Poliglota: salvar no MongoDB Atlas
        salvar_condominio_por_bag(bag)
        messages.success(request, 'Movimentação registrada e status da bag atualizado.')
        return redirect('detalhe_bag', bag_id=bag.id_bag)
    return render(request, 'sistema/cadastro-movimentacao-bag.html', {
        'usuario': usuario,
        'form': form,
        'bag': bag,
    })
