from urllib.parse import urlencode

from django.contrib import messages
from django.db import models, transaction
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
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)

    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    condominios = Condominio.objects.select_related('praia').prefetch_related('bags')
    if busca:
        condominios = condominios.filter(nome__icontains=busca)
    if status in dict(Condominio.STATUS_CHOICES):
        condominios = condominios.filter(status=status)

    pagina, filtros_query = paginar_queryset(request, condominios)
    return render(request, 'sistema/condominios.html', {
        'usuario': usuario,
        'condominios': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
        'status_selecionado': status,
        'status_choices': Condominio.STATUS_CHOICES,
        'total_condominios': Condominio.objects.count(),
        'total_bags': Bag.objects.count(),
        'bags_cheias': Bag.objects.filter(status='CHEIA').count(),
    })


def bags_view(request):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)

    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    bags = Bag.objects.select_related(
        'condominio',
        'condominio__praia',
        'cadastrado_por',
        'ultimo_editado_por',
    ).prefetch_related('movimentacoes')
    if busca:
        bags = bags.filter(
            models.Q(codigo__icontains=busca)
            | models.Q(condominio__nome__icontains=busca)
        )
    if status in dict(Bag.STATUS_CHOICES):
        bags = bags.filter(status=status)

    pagina, filtros_query = paginar_queryset(request, bags)
    return render(request, 'sistema/bags.html', {
        'usuario': usuario,
        'bags': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
        'status_selecionado': status,
        'status_choices': Bag.STATUS_CHOICES,
        'total_bags': Bag.objects.count(),
        'bags_cheias': Bag.objects.filter(status='CHEIA').count(),
        'bags_em_uso': Bag.objects.filter(status='EM_USO').count(),
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
        messages.success(request, 'Condomínio cadastrado com sucesso.')
        return redirect('detalhe_condominio', condominio_id=condominio.id_condominio)
    return render(request, 'sistema/cadastro-condominio.html', {'usuario': usuario, 'form': form})


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
        messages.success(request, 'Bag grande cadastrada com sucesso.')
        return redirect('detalhe_bag', bag_id=bag.id_bag)
    return render(request, 'sistema/cadastro-bag.html', {'usuario': usuario, 'form': form})


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
            bag=bag,
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
            bag=bag,
        ).prefetch_related('itens').order_by('-data_coleta'),
    })


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
        messages.success(request, 'Movimentação registrada e status da bag atualizado.')
        return redirect('detalhe_bag', bag_id=bag.id_bag)
    return render(request, 'sistema/cadastro-movimentacao-bag.html', {
        'usuario': usuario,
        'form': form,
        'bag': bag,
    })
