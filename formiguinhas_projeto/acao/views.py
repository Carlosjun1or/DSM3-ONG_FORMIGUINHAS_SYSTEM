from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from praia.models import Praia
from usuario.views import get_session_usuario, render_acesso_bloqueado
from usuario.paginacao import paginar_queryset

from .forms import (
    AcaoForm,
    AcaoImagemForm,
    AcaoParticipanteForm,
    AcaoResponsavelForm,
)
from .models import (
    Acao,
    AcaoEquipe,
    AcaoImagem,
    AcaoParticipante,
    AcaoParticipanteHistorico,
    AcaoResponsavel,
    adicionar_coordenadores_automaticos_para_mutirao,
    adicionar_participantes_automaticos_para_mutirao,
)
from residuo.forms import DestinacaoResiduoForm, ResiduoColetadoForm
from auditoria.services import registrar_evento, snapshot
from estoque.models import MovimentacaoEstoque
from estoque.services import registrar_movimentacao
from .forms import MaterialUtilizadoForm
from config.mongodb import test_mongo_connection
from .mongo_services import (
    salvar_acao_mongo,
    remover_acao_mongo,
    consultar_acoes_mongo,
    obter_acao_mongo,
    obter_metricas_acoes_mongo,
)


class MongoAcaoAdapter:
    """Adapta documento BSON de Ação do MongoDB para a interface dos templates Django.
    
    O MongoDB retorna um documento rico (ação + praia + participantes + equipes + imagens).
    Este adapter 'achata' os campos aninhados e simula os métodos get_*_display() e
    as relations (.participantes, .praia) que os templates esperam de um Model Django.
    """
    def __init__(self, doc):
        self.doc = doc
        self.id = doc.get('id_sql')
        self.id_acao = doc.get('id_sql')
        self.pk = doc.get('id_sql')
        self.tipo = doc.get('tipo', '')
        self._tipo_display = doc.get('tipo_display', '')
        self.status = doc.get('status', '')
        self._status_display = doc.get('status_display', '')
        self.local = doc.get('local', '')
        self.descricao = doc.get('descricao', '')
        self.cadastrado_por_nome = doc.get('cadastrado_por_nome', '')
        self.ultimo_editado_por_nome = doc.get('ultimo_editado_por_nome', '')
        self.dt_cadastro = doc.get('dt_cadastro')
        self.dt_ultima_edicao = doc.get('dt_ultima_edicao')
        self.id_mongo = str(doc.get('_id', ''))
        self.total_residuos_kg = doc.get('total_residuos_kg', 0)
        self.total_participantes = doc.get('total_participantes', 0)

        # Data
        data_val = doc.get('data')
        if isinstance(data_val, str):
            from django.utils.dateparse import parse_date
            self.data = parse_date(data_val)
        else:
            self.data = data_val

        # Horário
        hora_val = doc.get('horario')
        if isinstance(hora_val, str):
            from django.utils.dateparse import parse_time
            self.horario = parse_time(hora_val)
        else:
            self.horario = hora_val

        # Praia
        praia_dict = doc.get('praia') or {}
        class PraiaAdapter:
            def __init__(self, p):
                self.id_praia = p.get('id', p.get('id_praia'))
                self.pk = self.id_praia
                self.nome = p.get('nome', '')
                self.cidade = p.get('cidade', '')
                self.latitude = p.get('latitude')
                self.longitude = p.get('longitude')
                self.localizacao_geo = p.get('localizacao_geo', {})
            def __str__(self):
                return self.nome
        self.praia = PraiaAdapter(praia_dict)

        # Participantes
        class ParticipantesManager(list):
            def count(self):
                return len(self)
        self.participantes = ParticipantesManager(doc.get('participantes', []))
        self.equipes_vinculadas = doc.get('equipes', [])
        self.responsaveis = doc.get('responsaveis', [])
        self.imagens_acao = doc.get('imagens', [])
        self.residuos_coletados = doc.get('residuos_coletados', [])

    def get_tipo_display(self):
        return self._tipo_display or self.tipo

    def get_status_display(self):
        return self._status_display or self.status



def preencher_auditoria(acao, usuario, criacao=False):
    nome = usuario.id_voluntario.nome
    tipo = usuario.tipo

    if criacao:
        acao.cadastrado_por = usuario
        acao.cadastrado_por_nome = nome
        acao.cadastrado_por_tipo = tipo
        return

    acao.ultimo_editado_por = usuario
    acao.ultimo_editado_por_nome = nome
    acao.ultimo_editado_por_tipo = tipo
    acao.dt_ultima_edicao = timezone.now()


def sincronizar_relacionamentos_mutirao(acao, usuario):
    for equipe in acao.praia.equipes.filter(status='ATIVA'):
        vinculacao, criada = AcaoEquipe.objects.get_or_create(acao=acao, equipe=equipe)
        if criada:
            registrar_evento(
                entidade='ACAO_EQUIPE',
                instancia=vinculacao,
                acao='VINCULO',
                usuario=usuario,
                resumo=f'Equipe "{equipe.nome}" vinculada à ação #{acao.pk}.',
            )

    participantes_existentes = set(
        acao.participantes.values_list('voluntario_id', flat=True)
    )
    participantes = adicionar_participantes_automaticos_para_mutirao(acao)
    for participante in participantes:
        if participante.voluntario_id not in participantes_existentes:
            registrar_evento(
                entidade='ACAO_PARTICIPANTE',
                instancia=participante,
                acao='VINCULO',
                usuario=usuario,
                resumo=f'{participante.voluntario.nome} inscrito automaticamente na ação #{acao.pk}.',
            )

    responsaveis_existentes = {
        responsavel.voluntario_id: snapshot(responsavel)
        for responsavel in acao.responsaveis.all()
    }
    responsaveis = adicionar_coordenadores_automaticos_para_mutirao(acao)
    for responsavel in responsaveis:
        valores_anteriores = responsaveis_existentes.get(responsavel.voluntario_id)
        valores_novos = snapshot(responsavel)
        if valores_anteriores is None or valores_anteriores != valores_novos:
            registrar_evento(
                entidade='ACAO_RESPONSAVEL',
                instancia=responsavel,
                acao='VINCULO' if valores_anteriores is None else 'EDICAO',
                usuario=usuario,
                resumo=f'{responsavel.voluntario.nome} definido como responsável pela ação #{acao.pk}.',
                valores_anteriores=valores_anteriores,
                valores_novos=valores_novos,
            )


def acoes_view(request):
    """
    Lista ações com filtros e métricas.
    
    Fonte primária: MongoDB Atlas (documentos ricos com participantes, equipes, etc.).
    Fallback: SQLite (Acao.objects com select_related/prefetch_related) quando MongoDB offline.
    """
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo not in ('ADMIN', 'COORDENADOR'):
        return redirect('home')

    # Fonte primária exclusiva: MongoDB Atlas
    mongo_ok, mongo_msg, mongo_info = test_mongo_connection()
    mongo_metricas = obter_metricas_acoes_mongo() if mongo_ok else {'total': 0, 'planejadas': 0}

    busca = request.GET.get('busca', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    status = request.GET.get('status', '').strip()
    praia_id = request.GET.get('praia', '').strip()
    participacao = request.GET.get('participacao', '').strip()

    if mongo_ok:
        filtros_mongo = {
            'busca': busca,
            'tipo': tipo,
            'status': status,
            'praia': praia_id,
            'voluntario_id': usuario.id_voluntario_id if participacao == 'MINHAS' else None,
        }
        docs, total_docs = consultar_acoes_mongo(filtros_mongo, pagina=1, por_pagina=1000)
        acoes_adaptadas = [MongoAcaoAdapter(d) for d in docs]
        pagina, filtros_query = paginar_queryset(request, acoes_adaptadas)
        total_acoes = mongo_metricas.get('total', len(docs))
        total_planejadas = mongo_metricas.get('planejadas', 0)
        fonte = 'mongo'
    else:
        fonte = 'sql'
        acoes_qs = Acao.objects.select_related('praia').prefetch_related('participantes')
        if busca:
            acoes_qs = acoes_qs.filter(Q(local__icontains=busca) | Q(descricao__icontains=busca))
        if tipo:
            acoes_qs = acoes_qs.filter(tipo=tipo)
        if status:
            acoes_qs = acoes_qs.filter(status=status)
        if praia_id.isdigit():
            acoes_qs = acoes_qs.filter(praia_id=praia_id)
        if participacao == 'MINHAS' and usuario.id_voluntario_id:
            acoes_qs = acoes_qs.filter(participantes__voluntario_id=usuario.id_voluntario_id)
        pagina, filtros_query = paginar_queryset(request, acoes_qs)
        total_acoes = Acao.objects.count()
        total_planejadas = Acao.objects.filter(status='PLANEJADA').count()

    return render(request, 'sistema/acoes.html', {
        'usuario': usuario,
        'acoes': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
        'tipo_selecionado': tipo,
        'status_selecionado': status,
        'praia_selecionada': praia_id,
        'participacao_selecionada': participacao,
        'tipo_choices': Acao.TIPO_CHOICES,
        'status_choices': Acao.STATUS_CHOICES,
        'praias': Praia.objects.order_by('nome'),
        'total_acoes': total_acoes,
        'total_planejadas': total_planejadas,
        'fonte_atual': fonte,
        'mongo_conectado': mongo_ok,
        'mongo_info': mongo_info,
        'mongo_metricas': mongo_metricas,
    })



@transaction.atomic
def cadastro_acao_view(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    if request.method == 'POST':
        form = AcaoForm(request.POST)
        if form.is_valid():
            acao = form.save(commit=False)
            preencher_auditoria(acao, usuario, criacao=True)
            acao.save()
            registrar_evento(entidade='ACAO', instancia=acao, acao='CRIACAO', usuario=usuario,
                             resumo=f'Ação #{acao.pk} cadastrada.')

            if acao.tipo == Acao.TIPO_MUTIRAO:
                sincronizar_relacionamentos_mutirao(acao, usuario)

            salvar_acao_mongo(acao)
            return redirect('acao_detalhe', acao_id=acao.id_acao)
    else:
        form = AcaoForm(initial={'status': Acao.STATUS_PLANEJADA})

    return render(request, 'sistema/cadastro-acao.html', {
        'usuario': usuario,
        'form': form,
        'modo': 'cadastro',
    })


@transaction.atomic
def editar_acao_view(request, acao_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    acao = get_object_or_404(Acao, id_acao=acao_id)
    valores_anteriores = snapshot(acao)
    if request.method == 'POST':
        form = AcaoForm(request.POST, instance=acao)
        if form.is_valid():
            acao = form.save(commit=False)
            preencher_auditoria(acao, usuario)
            acao.save()
            registrar_evento(entidade='ACAO', instancia=acao, acao='EDICAO', usuario=usuario,
                             resumo=f'Ação #{acao.pk} editada.', valores_anteriores=valores_anteriores)
            if acao.tipo == Acao.TIPO_MUTIRAO:
                sincronizar_relacionamentos_mutirao(acao, usuario)
            salvar_acao_mongo(acao)
            return redirect('acao_detalhe', acao_id=acao.id_acao)
    else:
        form = AcaoForm(instance=acao)

    return render(request, 'sistema/cadastro-acao.html', {
        'usuario': usuario,
        'form': form,
        'acao': acao,
        'modo': 'edicao',
    })


def acao_detalhe_view(request, acao_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo not in ('ADMIN', 'COORDENADOR'):
        return redirect('home')

    acao = get_object_or_404(
        Acao.objects.select_related(
            'praia',
            'cadastrado_por__id_voluntario',
            'ultimo_editado_por__id_voluntario',
        ).prefetch_related('imagens_acao'),
        id_acao=acao_id,
    )
    busca_participante = request.GET.get('busca_participante', '').strip()
    status_participante = request.GET.get('status_participante', '').strip()
    busca_equipe = request.GET.get('busca_equipe', '').strip()
    busca_responsavel = request.GET.get('busca_responsavel', '').strip()

    participantes = acao.participantes.select_related('voluntario').order_by(
        'voluntario__nome'
    )
    if busca_participante:
        participantes = participantes.filter(
            Q(voluntario__nome__icontains=busca_participante)
            | Q(voluntario__email__icontains=busca_participante)
        )
    if status_participante in dict(AcaoParticipante.STATUS_CHOICES):
        participantes = participantes.filter(status=status_participante)
    historico_participantes = acao.historico_participantes.filter(
        restaurado=False
    ).select_related(
        'voluntario',
        'movido_por__id_voluntario',
    ).order_by('-dt_movimentacao', 'voluntario__nome')

    equipes = acao.equipes_vinculadas.select_related('equipe__praia').order_by(
        'equipe__nome'
    )
    if busca_equipe:
        equipes = equipes.filter(
            Q(equipe__nome__icontains=busca_equipe)
            | Q(equipe__praia__nome__icontains=busca_equipe)
            | Q(equipe__praia__cidade__icontains=busca_equipe)
        )

    form = AcaoParticipanteForm(acao=acao)
    responsavel_form = AcaoResponsavelForm(acao=acao)
    imagem_form = AcaoImagemForm()
    residuo_form = ResiduoColetadoForm()
    materiais_utilizados = acao.movimentacoes_estoque.filter(
        tipo='SAIDA',
    ).select_related('material').order_by('-dt_cadastro')
    responsaveis = acao.responsaveis.select_related('voluntario').order_by(
        'papel',
        'voluntario__nome',
    )
    estado_formulario = request.session.pop(
        f'acao_material_utilizado_{acao.pk}',
        None,
    )
    if estado_formulario:
        material_utilizado_form = MaterialUtilizadoForm(
            data=estado_formulario['dados'],
        )
        for erro in estado_formulario['erros']:
            material_utilizado_form.add_error('quantidade', erro)
    else:
        material_utilizado_form = MaterialUtilizadoForm()
    if busca_responsavel:
        responsaveis = responsaveis.filter(
            Q(voluntario__nome__icontains=busca_responsavel)
            | Q(voluntario__email__icontains=busca_responsavel)
        )

    mongo_ok, _, _ = test_mongo_connection()
    doc_mongo = obter_acao_mongo(acao_id) if mongo_ok else None

    return render(request, 'sistema/detalhe-acao.html', {
        'usuario': usuario,
        'acao': acao,
        'id_mongo': str(doc_mongo.get('_id')) if doc_mongo else None,
        'doc_mongo': doc_mongo,
        'participantes': participantes,
        'historico_participantes': historico_participantes,
        'equipes': equipes,
        'busca_participante': busca_participante,
        'status_participante': status_participante,
        'status_participante_choices': AcaoParticipante.STATUS_CHOICES,
        'busca_equipe': busca_equipe,
        'busca_responsavel': busca_responsavel,
        'form': form,
        'responsavel_form': responsavel_form,
        'responsaveis': responsaveis,
        'imagens_acao': acao.imagens_acao.all(),
        'imagem_form': imagem_form,
        'residuos': acao.residuos_coletados.all(),
        'residuo_form': residuo_form,
        'destinacao_form': DestinacaoResiduoForm(),
        'material_utilizado_form': material_utilizado_form,
        'materiais_utilizados': materiais_utilizados,
    })


@transaction.atomic
def adicionar_material_utilizado_view(request, acao_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)
    if request.method != 'POST':
        return redirect('acao_detalhe', acao_id=acao_id)

    acao = get_object_or_404(Acao, id_acao=acao_id)
    form = MaterialUtilizadoForm(request.POST)
    erros = []
    formulario_valido = form.is_valid()
    if formulario_valido:
        material = form.cleaned_data['material']
        quantidade = form.cleaned_data['quantidade']
        movimentacao = MovimentacaoEstoque(
            material=material,
            acao=acao,
            tipo='SAIDA',
            quantidade=quantidade,
            justificativa=f'Uso na ação #{acao.pk}: {acao.get_tipo_display()} - {acao.data:%d/%m/%Y}',
        )
        try:
            registrar_movimentacao(movimentacao, usuario)
        except ValidationError as erro:
            erros.extend(erro.messages)
        else:
            messages.success(request, 'Material utilizado registrado e saldo atualizado.')
            return redirect('acao_detalhe', acao_id=acao.pk)

    if not formulario_valido:
        erros = []
    request.session[f'acao_material_utilizado_{acao.pk}'] = {
        'dados': {
            'material': request.POST.get('material', ''),
            'quantidade': request.POST.get('quantidade', ''),
        },
        'erros': erros,
    }
    return redirect('acao_detalhe', acao_id=acao.pk)


@transaction.atomic
def adicionar_participante_view(request, acao_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    acao = get_object_or_404(Acao, id_acao=acao_id)
    if request.method == 'POST':
        form = AcaoParticipanteForm(request.POST, acao=acao)
        if form.is_valid():
            participante = form.save(commit=False)
            participante.acao = acao
            participante.status = AcaoParticipante.STATUS_PENDENTE
            participante.save()
            registrar_evento(
                entidade='ACAO_PARTICIPANTE',
                instancia=participante,
                acao='VINCULO',
                usuario=usuario,
                resumo=f'{participante.voluntario.nome} vinculado à ação #{acao.pk}.',
            )
            salvar_acao_mongo(acao)
    return redirect('acao_detalhe', acao_id=acao.id_acao)


@transaction.atomic
def adicionar_responsavel_view(request, acao_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    acao = get_object_or_404(Acao, id_acao=acao_id)
    if request.method == 'POST':
        form = AcaoResponsavelForm(request.POST, acao=acao)
        if form.is_valid():
            responsavel = form.save(commit=False)
            responsavel.acao = acao
            responsavel.save()
            registrar_evento(
                entidade='ACAO_RESPONSAVEL',
                instancia=responsavel,
                acao='VINCULO',
                usuario=usuario,
                resumo=f'{responsavel.voluntario.nome} vinculado como responsável pela ação #{acao.pk}.',
            )
            salvar_acao_mongo(acao)
    return redirect('acao_detalhe', acao_id=acao.id_acao)


@transaction.atomic
def adicionar_imagens_acao_view(request, acao_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    acao = get_object_or_404(Acao, id_acao=acao_id)
    if request.method == 'POST':
        form = AcaoImagemForm(request.POST, request.FILES)
        if form.is_valid():
            descricao = form.cleaned_data['descricao']
            for imagem in form.cleaned_data['imagens']:
                imagem_acao = AcaoImagem.objects.create(
                    acao=acao,
                    imagem=imagem,
                    descricao=descricao,
                )
                registrar_evento(
                    entidade='ACAO_IMAGEM',
                    instancia=imagem_acao,
                    acao='CRIACAO',
                    usuario=usuario,
                    resumo=f'Imagem adicionada à ação #{acao.pk}.',
                )
            messages.success(request, 'Imagens adicionadas à ação com sucesso.')
            salvar_acao_mongo(acao)
        else:
            messages.error(request, 'Não foi possível adicionar as imagens. Verifique os arquivos selecionados.')
    return redirect('acao_detalhe', acao_id=acao.id_acao)


@transaction.atomic
def excluir_imagem_acao_view(request, acao_id, imagem_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    imagem = get_object_or_404(
        AcaoImagem,
        id_acao_imagem=imagem_id,
        acao_id=acao_id,
    )
    if request.method == 'POST':
        valores_anteriores = snapshot(imagem)
        imagem_id_registro = imagem.pk
        imagem.imagem.delete(save=False)
        imagem.delete()
        registrar_evento(
            entidade='ACAO_IMAGEM',
            id_registro=imagem_id_registro,
            acao='EXCLUSAO',
            usuario=usuario,
            resumo=f'Imagem removida da ação #{acao_id}.',
            valores_anteriores=valores_anteriores,
        )
        acao = Acao.objects.filter(pk=acao_id).first()
        if acao:
            salvar_acao_mongo(acao)
        messages.success(request, 'Imagem excluída com sucesso.')
    return redirect('acao_detalhe', acao_id=acao_id)


@transaction.atomic
def atualizar_status_acao_view(request, acao_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    acao = get_object_or_404(Acao, id_acao=acao_id)
    if request.method == 'POST':
        novo_status = request.POST.get('status')
        if novo_status in dict(Acao.STATUS_CHOICES) and novo_status != acao.status:
            status_anterior = acao.get_status_display()
            valores_anteriores = snapshot(acao)
            acao.status = novo_status
            preencher_auditoria(acao, usuario)
            acao.save(update_fields=[
                'status',
                'ultimo_editado_por',
                'ultimo_editado_por_nome',
                'ultimo_editado_por_tipo',
                'dt_ultima_edicao',
            ])
            registrar_evento(
                entidade='ACAO',
                instancia=acao,
                acao='MUDANCA_STATUS',
                usuario=usuario,
                resumo=f'Status da ação #{acao.pk} alterado de {status_anterior} para {acao.get_status_display()}.',
                valores_anteriores=valores_anteriores,
            )
            salvar_acao_mongo(acao)
            messages.success(
                request,
                f'Status da ação atualizado de {status_anterior} para {acao.get_status_display()}.',
            )
        else:
            messages.error(request, 'Status de ação inválido.')
    else:
        messages.error(request, 'Atualização de status inválida.')
    return redirect('acoes')


@transaction.atomic
def confirmar_participacao_view(request, acao_id, participante_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    participante = get_object_or_404(
        AcaoParticipante,
        id_acao_participante=participante_id,
        acao_id=acao_id,
    )
    if request.method == 'POST':
        status = request.POST.get('status', AcaoParticipante.STATUS_CONFIRMADO)
        if status in dict(AcaoParticipante.STATUS_CHOICES):
            if status in (
                AcaoParticipante.STATUS_RECUSADO,
                AcaoParticipante.STATUS_NAO_COMPARECEU,
            ):
                mover_participante_para_historico(participante, usuario, status)
            else:
                valores_anteriores = snapshot(participante)
                participante.status = status
                participante.dt_confirmacao = timezone.now()
                participante.save(update_fields=['status', 'dt_confirmacao'])
                registrar_evento(
                    entidade='ACAO_PARTICIPANTE',
                    instancia=participante,
                    acao='EDICAO',
                    usuario=usuario,
                    resumo=f'Situação de {participante.voluntario.nome} atualizada na ação #{acao_id}.',
                    valores_anteriores=valores_anteriores,
                )
                salvar_acao_mongo(participante.acao)
    return redirect('acao_detalhe', acao_id=acao_id)


@transaction.atomic
def registrar_comparecimento_view(request, acao_id, participante_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    participante = get_object_or_404(
        AcaoParticipante,
        id_acao_participante=participante_id,
        acao_id=acao_id,
    )
    if request.method == 'POST':
        presente = request.POST.get('compareceu') == 'on'
        novo_status = (
            AcaoParticipante.STATUS_PRESENTE
            if presente
            else AcaoParticipante.STATUS_NAO_COMPARECEU
        )
        if presente:
            valores_anteriores = snapshot(participante)
            participante.compareceu = True
            participante.status = novo_status
            participante.save(update_fields=['compareceu', 'status'])
            registrar_evento(
                entidade='ACAO_PARTICIPANTE',
                instancia=participante,
                acao='MUDANCA_STATUS',
                usuario=usuario,
                resumo=f'Comparecimento de {participante.voluntario.nome} registrado na ação #{acao_id}.',
                valores_anteriores=valores_anteriores,
            )
            salvar_acao_mongo(participante.acao)
        else:
            mover_participante_para_historico(participante, usuario, novo_status)
    return redirect('acao_detalhe', acao_id=acao_id)


@transaction.atomic
def restaurar_participante_view(request, acao_id, historico_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    historico = get_object_or_404(
        AcaoParticipanteHistorico,
        id_historico=historico_id,
        acao_id=acao_id,
    )
    if request.method == 'POST' and not historico.restaurado:
        valores_anteriores = snapshot(historico)
        participante, criado = AcaoParticipante.objects.get_or_create(
            acao_id=acao_id,
            voluntario=historico.voluntario,
            defaults={
                'status': AcaoParticipante.STATUS_PENDENTE,
                'compareceu': False,
                'observacao': historico.observacao,
                'dt_confirmacao': None,
                'dt_cadastro': historico.dt_cadastro,
            },
        )
        if not criado:
            participante.status = AcaoParticipante.STATUS_PENDENTE
            participante.compareceu = False
            participante.save(update_fields=['status', 'compareceu'])

        historico.restaurado = True
        historico.restaurado_em = timezone.now()
        historico.restaurado_por = usuario
        historico.restaurado_por_nome = usuario.id_voluntario.nome
        historico.restaurado_por_tipo = usuario.tipo
        historico.save(update_fields=[
            'restaurado',
            'restaurado_em',
            'restaurado_por',
            'restaurado_por_nome',
            'restaurado_por_tipo',
        ])
        registrar_evento(
            entidade='ACAO_PARTICIPANTE',
            instancia=participante,
            acao='VINCULO',
            usuario=usuario,
            resumo=f'{participante.voluntario.nome} restaurado na ação #{acao_id}.',
            valores_anteriores=valores_anteriores,
        )
        salvar_acao_mongo(participante.acao)

    return redirect('acao_detalhe', acao_id=acao_id)


@transaction.atomic
def mover_participante_para_historico(participante, usuario, status):
    valores_anteriores = snapshot(participante)
    acao_alvo = participante.acao
    historico = AcaoParticipanteHistorico.objects.create(
        acao=acao_alvo,
        voluntario=participante.voluntario,
        status=status,
        compareceu=participante.compareceu,
        observacao=participante.observacao,
        dt_cadastro=participante.dt_cadastro,
        movido_por=usuario,
        movido_por_nome=usuario.id_voluntario.nome,
        movido_por_tipo=usuario.tipo,
    )
    registrar_evento(
        entidade='ACAO_PARTICIPANTE',
        id_registro=participante.pk,
        acao='MUDANCA_STATUS',
        usuario=usuario,
        resumo=f'{participante.voluntario.nome} movido para o histórico da ação #{participante.acao_id}.',
        valores_anteriores=valores_anteriores,
        valores_novos=snapshot(historico),
    )
    participante.delete()
    salvar_acao_mongo(acao_alvo)


@transaction.atomic
def excluir_acao_view(request, acao_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    acao = get_object_or_404(Acao, id_acao=acao_id)
    if request.method == 'POST':
        valores_anteriores = snapshot(acao)
        acao_id_registro = acao.pk
        acao.delete()
        remover_acao_mongo(acao_id_registro)
        registrar_evento(
            entidade='ACAO',
            id_registro=acao_id_registro,
            acao='EXCLUSAO',
            usuario=usuario,
            resumo=f'Ação #{acao_id_registro} excluída.',
            valores_anteriores=valores_anteriores,
        )
    return redirect('acoes')
