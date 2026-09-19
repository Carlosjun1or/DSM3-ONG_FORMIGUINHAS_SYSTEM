from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

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
        'cadastrado_por__id_voluntario'
    ).all().order_by('nome')

    if busca:
        praias = praias.filter(
            Q(nome__icontains=busca) | Q(cidade__icontains=busca)
        )
    if status == 'ativa':
        praias = praias.filter(praia_ativa=True)
    elif status == 'inativa':
        praias = praias.filter(praia_ativa=False)

    return render(request, 'sistema/praias.html', {
        'usuario': usuario,
        'praias': praias,
        'busca': busca,
        'status_selecionado': status,
        'total_praias': Praia.objects.count(),
        'total_ativas': Praia.objects.filter(praia_ativa=True).count(),
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

    praia = get_object_or_404(Praia, id_praia=praia_id)
    if request.method == 'POST':
        form = PraiaForm(request.POST, instance=praia)
        if form.is_valid():
            form.save()
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

    if request.method == 'POST':
        praia = get_object_or_404(Praia, id_praia=praia_id)
        praia.praia_ativa = request.POST.get('praia_ativa') == 'true'
        praia.save(update_fields=['praia_ativa'])

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
