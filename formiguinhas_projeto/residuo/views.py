from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from acao.models import Acao
from auditoria.services import registrar_evento, snapshot
from usuario.views import get_session_usuario

from .forms import (
    ColetaResiduoForm,
    DestinacaoResiduoForm,
    ItemColetaResiduoForm,
    ResiduoColetadoForm,
)
from .models import ColetaResiduo, DestinacaoResiduo, ItemColetaResiduo, ResiduoColetado


def usuario_admin(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return None
    if usuario.tipo != 'ADMIN':
        return False
    return usuario


def residuos_view(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo not in ('ADMIN', 'COORDENADOR'):
        return redirect('home')

    busca = request.GET.get('busca', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    destinacao = request.GET.get('destinacao', '').strip()
    acao_id = request.GET.get('acao', '').strip()

    residuos = ResiduoColetado.objects.select_related(
        'acao',
        'acao__praia',
        'registrado_por__id_voluntario',
    ).prefetch_related(
        'destinacoes__registrado_por__id_voluntario',
    )
    if busca:
        residuos = residuos.filter(
            Q(tipo__icontains=busca)
            | Q(categoria__icontains=busca)
            | Q(observacao__icontains=busca)
            | Q(acao__local__icontains=busca)
            | Q(acao__descricao__icontains=busca)
            | Q(registrado_por_nome__icontains=busca)
        )
    if tipo in dict(ResiduoColetado.TIPO_CHOICES):
        residuos = residuos.filter(tipo=tipo)
    if categoria in dict(ResiduoColetado.CATEGORIA_CHOICES):
        residuos = residuos.filter(categoria=categoria)
    if destinacao in dict(DestinacaoResiduo.TIPO_CHOICES):
        residuos = residuos.filter(destinacoes__tipo=destinacao).distinct()
    if acao_id.isdigit():
        residuos = residuos.filter(acao_id=acao_id)

    return render(request, 'sistema/residuos.html', {
        'usuario': usuario,
        'residuos': residuos,
        'acoes': Acao.objects.order_by('-data', '-id_acao'),
        'busca': busca,
        'tipo_selecionado': tipo,
        'categoria_selecionada': categoria,
        'destinacao_selecionada': destinacao,
        'acao_selecionada': acao_id,
        'tipo_choices': ResiduoColetado.TIPO_CHOICES,
        'categoria_choices': ResiduoColetado.CATEGORIA_CHOICES,
        'destinacao_choices': DestinacaoResiduo.TIPO_CHOICES,
        'total_residuos': ResiduoColetado.objects.count(),
        'total_destinacoes': DestinacaoResiduo.objects.count(),
        'total_acoes_com_residuos': ResiduoColetado.objects.values('acao_id').distinct().count(),
        'coletas': ColetaResiduo.objects.select_related(
            'acao', 'acao__praia', 'bag', 'bag__condominio',
        ).prefetch_related('itens__destinacoes'),
        'total_coletas': ColetaResiduo.objects.count(),
    })


@transaction.atomic
def registrar_coleta_bag_view(request, bag_id):
    usuario = usuario_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        messages.error(request, 'Somente administradores podem registrar coletas.')
        return redirect('detalhe_bag', bag_id=bag_id)

    from condominio.models import Bag
    bag = get_object_or_404(Bag, id_bag=bag_id)
    coleta_form = ColetaResiduoForm(request.POST or None)
    item_form = ItemColetaResiduoForm(request.POST or None)
    if request.method == 'POST' and coleta_form.is_valid() and item_form.is_valid():
        coleta = coleta_form.save(commit=False)
        coleta.origem = 'BAG'
        coleta.bag = bag
        coleta.registrado_por = usuario
        coleta.registrado_por_nome = usuario.id_voluntario.nome
        coleta.registrado_por_tipo = usuario.tipo
        coleta.save()
        item = item_form.save(commit=False)
        item.coleta = coleta
        item.registrado_por = usuario
        item.registrado_por_nome = usuario.id_voluntario.nome
        item.registrado_por_tipo = usuario.tipo
        item.save()
        registrar_evento(
            entidade='COLETA_RESIDUO', instancia=coleta, acao='CRIACAO',
            usuario=usuario, resumo=f'Coleta #{coleta.pk} registrada para a bag {bag.codigo}.',
        )
        messages.success(request, 'Coleta da bag registrada com sucesso.')
        return redirect('detalhe_coleta_residuo', coleta_id=coleta.pk)
    return render(request, 'sistema/cadastro-coleta-residuo.html', {
        'usuario': usuario, 'bag': bag, 'coleta_form': coleta_form,
        'item_form': item_form, 'origem_label': f'Bag {bag.codigo}',
    })


def detalhe_coleta_residuo_view(request, coleta_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    coleta = get_object_or_404(
        ColetaResiduo.objects.select_related('acao', 'bag', 'bag__condominio')
        .prefetch_related('itens__destinacoes'),
        id_coleta=coleta_id,
    )
    return render(request, 'sistema/detalhe-coleta-residuo.html', {
        'usuario': usuario, 'coleta': coleta, 'item_form': ItemColetaResiduoForm(),
    })


@transaction.atomic
def adicionar_item_coleta_view(request, coleta_id):
    usuario = usuario_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        messages.error(request, 'Somente administradores podem adicionar itens.')
        return redirect('detalhe_coleta_residuo', coleta_id=coleta_id)
    coleta = get_object_or_404(ColetaResiduo, id_coleta=coleta_id)
    if request.method == 'POST':
        form = ItemColetaResiduoForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.coleta = coleta
            item.registrado_por = usuario
            item.registrado_por_nome = usuario.id_voluntario.nome
            item.registrado_por_tipo = usuario.tipo
            item.save()
            registrar_evento(
                entidade='ITEM_COLETA_RESIDUO', instancia=item, acao='CRIACAO',
                usuario=usuario, resumo=f'Item de resíduo #{item.pk} adicionado à coleta #{coleta.pk}.',
            )
            messages.success(request, 'Tipo de resíduo adicionado à coleta.')
    return redirect('detalhe_coleta_residuo', coleta_id=coleta_id)


@transaction.atomic
def registrar_residuo_view(request, acao_id):
    usuario = usuario_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        messages.error(request, 'Somente administradores podem registrar resíduos.')
        return redirect('acao_detalhe', acao_id=acao_id)

    acao = get_object_or_404(Acao, id_acao=acao_id)
    if request.method == 'POST':
        form = ResiduoColetadoForm(request.POST)
        if form.is_valid():
            residuo = form.save(commit=False)
            residuo.acao = acao
            residuo.registrado_por = usuario
            residuo.registrado_por_nome = usuario.id_voluntario.nome
            residuo.registrado_por_tipo = usuario.tipo
            residuo.save()
            coleta = ColetaResiduo.objects.create(
                origem='ACAO',
                acao=acao,
                data_coleta=residuo.dt_registro,
                observacao=residuo.observacao,
                registrado_por=usuario,
                registrado_por_nome=usuario.id_voluntario.nome,
                registrado_por_tipo=usuario.tipo,
            )
            item = ItemColetaResiduo.objects.create(
                coleta=coleta,
                tipo=residuo.tipo,
                categoria=residuo.categoria,
                quantidade=residuo.quantidade,
                unidade=residuo.unidade,
                observacao=residuo.observacao,
                registrado_por=usuario,
                registrado_por_nome=usuario.id_voluntario.nome,
                registrado_por_tipo=usuario.tipo,
            )
            registrar_evento(
                entidade='RESIDUO',
                instancia=residuo,
                acao='CRIACAO',
                usuario=usuario,
                resumo=f'Resíduo #{residuo.pk} registrado na ação #{acao.pk}.',
            )
            registrar_evento(
                entidade='COLETA_RESIDUO',
                instancia=coleta,
                acao='CRIACAO',
                usuario=usuario,
                resumo=f'Coleta #{coleta.pk} registrada na ação #{acao.pk}.',
            )
            messages.success(request, 'Resíduo registrado com sucesso.')
        else:
            messages.error(request, 'Não foi possível registrar o resíduo. Verifique os dados informados.')
    return redirect('acao_detalhe', acao_id=acao_id)


@transaction.atomic
def registrar_destinacao_view(request, acao_id, residuo_id):
    usuario = usuario_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        messages.error(request, 'Somente administradores podem registrar destinações.')
        return redirect('acao_detalhe', acao_id=acao_id)

    residuo = get_object_or_404(
        ResiduoColetado,
        id_residuo=residuo_id,
        acao_id=acao_id,
    )
    if request.method == 'POST':
        form = DestinacaoResiduoForm(request.POST)
        if form.is_valid():
            destinacao = form.save(commit=False)
            destinacao.residuo = residuo
            destinacao.registrado_por = usuario
            destinacao.registrado_por_nome = usuario.id_voluntario.nome
            destinacao.registrado_por_tipo = usuario.tipo
            destinacao.save()
            registrar_evento(
                entidade='DESTINACAO_RESIDUO',
                instancia=destinacao,
                acao='CRIACAO',
                usuario=usuario,
                resumo=f'Destinação #{destinacao.pk} registrada para o resíduo #{residuo.pk}.',
            )
            messages.success(request, 'Destinação registrada com sucesso.')
        else:
            messages.error(request, 'Não foi possível registrar a destinação. Verifique os dados informados.')
            return redirect('acao_detalhe', acao_id=acao_id)
    else:
        form = DestinacaoResiduoForm()
    return render(request, 'sistema/destinacao-residuo.html', {
        'usuario': usuario,
        'acao': residuo.acao,
        'residuo': residuo,
        'form': form,
    })


def editar_residuo_view(request, acao_id, residuo_id):
    usuario = usuario_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        messages.error(request, 'Somente administradores podem editar resíduos.')
        return redirect('acao_detalhe', acao_id=acao_id)
    residuo = get_object_or_404(ResiduoColetado, id_residuo=residuo_id, acao_id=acao_id)
    form = ResiduoColetadoForm(request.POST or None, instance=residuo)
    if request.method == 'POST' and form.is_valid():
        anteriores = snapshot(residuo)
        residuo = form.save(commit=False)
        residuo.ultimo_editado_por = usuario
        residuo.ultimo_editado_por_nome = usuario.id_voluntario.nome
        residuo.ultimo_editado_por_tipo = usuario.tipo
        residuo.dt_ultima_edicao = timezone.now()
        residuo.save()
        registrar_evento(entidade='RESIDUO', instancia=residuo, acao='EDICAO',
                         usuario=usuario, resumo=f'Resíduo #{residuo.pk} editado.',
                         valores_anteriores=anteriores)
        messages.success(request, 'Resíduo atualizado com sucesso.')
        return redirect('acao_detalhe', acao_id=acao_id)
    return render(request, 'sistema/editar-residuo.html', {
        'usuario': usuario, 'acao': residuo.acao, 'residuo': residuo, 'form': form,
    })


def excluir_residuo_view(request, acao_id, residuo_id):
    usuario = usuario_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        messages.error(request, 'Somente administradores podem excluir resíduos.')
        return redirect('acao_detalhe', acao_id=acao_id)
    residuo = get_object_or_404(ResiduoColetado, id_residuo=residuo_id, acao_id=acao_id)
    if request.method == 'POST':
        registro_id = residuo.pk
        registrar_evento(entidade='RESIDUO', id_registro=registro_id, acao='EXCLUSAO',
                         usuario=usuario, resumo=f'Resíduo #{registro_id} excluído.',
                         valores_anteriores=snapshot(residuo))
        residuo.delete()
        messages.success(request, 'Resíduo excluído com sucesso.')
    return redirect('acao_detalhe', acao_id=acao_id)


def editar_destinacao_view(request, acao_id, residuo_id, destinacao_id):
    usuario = usuario_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        messages.error(request, 'Somente administradores podem editar destinações.')
        return redirect('acao_detalhe', acao_id=acao_id)
    destinacao = get_object_or_404(
        DestinacaoResiduo,
        id_destinacao=destinacao_id,
        residuo_id=residuo_id,
        residuo__acao_id=acao_id,
    )
    form = DestinacaoResiduoForm(request.POST or None, instance=destinacao)
    if request.method == 'POST' and form.is_valid():
        anteriores = snapshot(destinacao)
        destinacao = form.save(commit=False)
        destinacao.ultimo_editado_por = usuario
        destinacao.ultimo_editado_por_nome = usuario.id_voluntario.nome
        destinacao.ultimo_editado_por_tipo = usuario.tipo
        destinacao.dt_ultima_edicao = timezone.now()
        destinacao.save()
        registrar_evento(entidade='DESTINACAO_RESIDUO', instancia=destinacao, acao='EDICAO',
                         usuario=usuario, resumo=f'Destinação #{destinacao.pk} editada.',
                         valores_anteriores=anteriores)
        messages.success(request, 'Destinação atualizada com sucesso.')
        return redirect('acao_detalhe', acao_id=acao_id)
    return render(request, 'sistema/destinacao-residuo.html', {
        'usuario': usuario, 'acao': destinacao.residuo.acao,
        'residuo': destinacao.residuo, 'destinacao': destinacao, 'form': form,
    })


def excluir_destinacao_view(request, acao_id, residuo_id, destinacao_id):
    usuario = usuario_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        messages.error(request, 'Somente administradores podem excluir destinações.')
        return redirect('acao_detalhe', acao_id=acao_id)
    destinacao = get_object_or_404(
        DestinacaoResiduo,
        id_destinacao=destinacao_id,
        residuo_id=residuo_id,
        residuo__acao_id=acao_id,
    )
    if request.method == 'POST':
        registro_id = destinacao.pk
        registrar_evento(entidade='DESTINACAO_RESIDUO', id_registro=registro_id, acao='EXCLUSAO',
                         usuario=usuario, resumo=f'Destinação #{registro_id} excluída.',
                         valores_anteriores=snapshot(destinacao))
        destinacao.delete()
        messages.success(request, 'Destinação excluída com sucesso.')
    return redirect('acao_detalhe', acao_id=acao_id)
