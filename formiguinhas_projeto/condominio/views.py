from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from usuario.models import Usuario

from .forms import BagForm, CondominioForm, MovimentacaoBagForm
from .models import AuditoriaControle, Bag, Condominio, MovimentacaoBag
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
    usuario = usuario_logado(request)
    if not usuario:
        return redirect('login')

    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    condominios = Condominio.objects.select_related('praia').prefetch_related('bags')
    if busca:
        condominios = condominios.filter(nome__icontains=busca)
    if status in dict(Condominio.STATUS_CHOICES):
        condominios = condominios.filter(status=status)

    return render(request, 'sistema/condominios.html', {
        'usuario': usuario,
        'condominios': condominios,
        'busca': busca,
        'status_selecionado': status,
        'status_choices': Condominio.STATUS_CHOICES,
        'total_condominios': Condominio.objects.count(),
        'total_bags': Bag.objects.count(),
        'bags_cheias': Bag.objects.filter(status='CHEIA').count(),
    })


def bags_view(request):
    usuario = usuario_logado(request)
    if not usuario:
        return redirect('login')

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

    return render(request, 'sistema/bags.html', {
        'usuario': usuario,
        'bags': bags,
        'busca': busca,
        'status_selecionado': status,
        'status_choices': Bag.STATUS_CHOICES,
        'total_bags': Bag.objects.count(),
        'bags_cheias': Bag.objects.filter(status='CHEIA').count(),
        'bags_em_uso': Bag.objects.filter(status='EM_USO').count(),
    })


def auditorias_view(request):
    """Compatibilidade com o endereço antigo; a tela agora é global."""
    from auditoria.views import global_auditoria
    return global_auditoria(request)


def cadastrar_condominio_view(request):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return redirect('condominios')

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
        return redirect('condominios')

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
    usuario = usuario_logado(request)
    if not usuario:
        return redirect('login')
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
        ).select_related('bag').order_by('-data_movimentacao')[:20],
        'auditorias': AuditoriaControle.objects.filter(
            entidade='CONDOMINIO',
            id_registro=condominio.id_condominio,
        ).select_related('usuario')[:30],
    })


def cadastrar_bag_view(request):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return redirect('condominios')

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
        return redirect('detalhe_bag', bag_id=bag_id)

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


def detalhe_bag_view(request, bag_id):
    usuario = usuario_logado(request)
    if not usuario:
        return redirect('login')
    bag = get_object_or_404(Bag.objects.select_related('condominio', 'condominio__praia'), id_bag=bag_id)
    return render(request, 'sistema/detalhe-bag.html', {
        'usuario': usuario,
        'bag': bag,
        'movimentacoes': bag.movimentacoes.select_related('registrado_por').all(),
        'auditorias': AuditoriaControle.objects.filter(
            entidade__in=('BAG', 'MOVIMENTACAO'),
            id_registro__in=(
                [bag.id_bag]
                + list(bag.movimentacoes.values_list('id_movimentacao', flat=True))
            ),
        ).select_related('usuario')[:50],
    })


def cadastrar_movimentacao_view(request, bag_id):
    usuario = exigir_admin(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return redirect('detalhe_bag', bag_id=bag_id)

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
