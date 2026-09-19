from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from usuario.models import Usuario

from .forms import PraiaForm
from .models import Praia


def get_session_usuario(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None

    try:
        return Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return None


def praias_view(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')

    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    praias = Praia.objects.select_related(
        'cadastrado_por__id_voluntario',
        'ultimo_editado_por__id_voluntario',
    ).all().order_by('nome')

    if busca:
        praias = praias.filter(
            Q(nome__icontains=busca) | Q(cidade__icontains=busca)
        )
    if status in dict(Praia.STATUS_CHOICES):
        praias = praias.filter(praia_ativa=status)

    return render(request, 'sistema/praias.html', {
        'usuario': usuario,
        'praias': praias,
        'busca': busca,
        'status_selecionado': status,
        'status_choices': Praia.STATUS_CHOICES,
        'total_praias': Praia.objects.count(),
        'total_ativas': Praia.objects.filter(praia_ativa='ATIVA').count(),
    })


def cadastrar_praia_view(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('praias')

    if request.method == 'POST':
        form = PraiaForm(request.POST)
        if form.is_valid():
            praia = form.save(commit=False)
            praia.cadastrado_por = usuario
            praia.cadastrado_por_nome = usuario.id_voluntario.nome
            praia.cadastrado_por_tipo = usuario.tipo
            praia.ultimo_editado_por = None
            praia.ultimo_editado_por_nome = None
            praia.ultimo_editado_por_tipo = None
            praia.dt_ultima_edicao = None
            praia.save()
            return redirect('praias')
    else:
        form = PraiaForm()

    return render(request, 'sistema/cadastro-praia.html', {
        'usuario': usuario,
        'form': form,
        'modo_edicao': False,
    })


def editar_praia_view(request, praia_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('praias')

    praia = get_object_or_404(Praia, id_praia=praia_id)
    if request.method == 'POST':
        form = PraiaForm(request.POST, instance=praia)
        if form.is_valid():
            praia = form.save(commit=False)
            praia.ultimo_editado_por = usuario
            praia.ultimo_editado_por_nome = usuario.id_voluntario.nome
            praia.ultimo_editado_por_tipo = usuario.tipo
            praia.dt_ultima_edicao = timezone.now()
            praia.save()
            return redirect('praias')
    else:
        form = PraiaForm(instance=praia)

    return render(request, 'sistema/cadastro-praia.html', {
        'usuario': usuario,
        'form': form,
        'praia': praia,
        'modo_edicao': True,
    })


def atualizar_status_praia_view(request, praia_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('praias')

    if request.method == 'POST':
        praia = get_object_or_404(Praia, id_praia=praia_id)
        status = request.POST.get('praia_ativa')
        if status in dict(Praia.STATUS_CHOICES):
            praia.praia_ativa = status
            praia.ultimo_editado_por = usuario
            praia.ultimo_editado_por_nome = usuario.id_voluntario.nome
            praia.ultimo_editado_por_tipo = usuario.tipo
            praia.dt_ultima_edicao = timezone.now()
            praia.save(update_fields=['praia_ativa', 'ultimo_editado_por', 'ultimo_editado_por_nome', 'ultimo_editado_por_tipo', 'dt_ultima_edicao'])

    return redirect('praias')


def excluir_praia_view(request, praia_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('praias')

    if request.method == 'POST':
        praia = get_object_or_404(Praia, id_praia=praia_id)
        praia.delete()

    return redirect('praias')
