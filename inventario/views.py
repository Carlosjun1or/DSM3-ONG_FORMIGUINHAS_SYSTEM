from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from .models import Material, Movimentacao
from .forms import MaterialForm, MovimentacaoForm, UsuarioForm


# Cadastro de materiais
@login_required
def cadastro_material(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('consulta_estoque')
    else:
        form = MaterialForm()
    return render(request, 'inventario/cadastro_material.html', {'form': form})


# Movimentações de estoque (formulário de registro)
@login_required
def movimentacao(request):
    if request.method == 'POST':
        form = MovimentacaoForm(request.POST)
        if form.is_valid():
            mov = form.save(commit=False)
            mov.usuario = request.user  # salva o usuário logado
            mov.save()
            return redirect('historico_movimentacoes')
    else:
        form = MovimentacaoForm()
    return render(request, 'inventario/movimentacao.html', {'form': form})


# Página de listagem de movimentações
@login_required
def movimentacoes(request):
    movimentacoes = Movimentacao.objects.all().order_by('-data')
    return render(request, 'inventario/movimentacoes.html', {'movimentacoes': movimentacoes})



# Cadastro e listagem de usuários
@login_required
def usuarios(request):
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            usuario = form.save(commit=False)
            usuario.password = make_password(form.cleaned_data['password'])
            usuario.save()
            return redirect('usuarios')
    else:
        form = UsuarioForm()

    usuarios = User.objects.all()
    return render(request, 'inventario/usuarios.html', {
        'form': form,
        'usuarios': usuarios
    })


@login_required
def remover_usuario(request, usuario_id):
    usuario = get_object_or_404(User, id=usuario_id)
    usuario.delete()
    return redirect('usuarios')


# Dashboard inicial
@login_required
def dashboard(request):
    return render(request, 'inventario/dashboard.html')


# Consulta de estoque
@login_required
def consulta_estoque(request):
    materiais = Material.objects.all()
    return render(request, 'inventario/consulta.html', {'materiais': materiais})


# Histórico de movimentações com filtros e paginação
@login_required
def historico_movimentacoes(request):
    movimentacoes = Movimentacao.objects.all().order_by('-data')

    # Filtros
    material_id = request.GET.get('material')
    if material_id:
        movimentacoes = movimentacoes.filter(material_id=material_id)

    tipo = request.GET.get('tipo')
    if tipo:
        movimentacoes = movimentacoes.filter(tipo=tipo)

    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    if data_inicio and data_fim:
        movimentacoes = movimentacoes.filter(data__range=[data_inicio, data_fim])
    elif data_inicio:
        movimentacoes = movimentacoes.filter(data__gte=data_inicio)
    elif data_fim:
        movimentacoes = movimentacoes.filter(data__lte=data_fim)

    # Paginação
    paginator = Paginator(movimentacoes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    materiais = Material.objects.all()
    return render(
        request,
        'inventario/historico.html',
        {'page_obj': page_obj, 'materiais': materiais}
    )
