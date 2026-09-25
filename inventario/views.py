from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Material, Movimentacao
from .forms import MaterialForm, MovimentacaoForm, UsuarioForm
from django.db.models import Sum
from .models import Material

@login_required
def relatorio_estoque(request):
    total_materiais = Material.objects.count()
    quantidade_total = sum([m.saldo for m in Material.objects.all()])

    donativos = Material.objects.filter(is_donativo=True)
    comprados = Material.objects.filter(is_donativo=False)

    total_donativos = donativos.count()
    quantidade_donativos = sum([m.saldo for m in donativos])

    total_comprados = comprados.count()
    quantidade_comprados = sum([m.saldo for m in comprados])

    context = {
        'total_materiais': total_materiais,
        'quantidade_total': quantidade_total,
        'total_donativos': total_donativos,
        'quantidade_donativos': quantidade_donativos,
        'total_comprados': total_comprados,
        'quantidade_comprados': quantidade_comprados,
    }
    return render(request, 'inventario/relatorio_estoque.html', context)

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
from django.db.models import Sum

# Movimentações de estoque (formulário de registro)
@login_required
def movimentacao(request):
    if request.method == 'POST':
        form = MovimentacaoForm(request.POST)
        if form.is_valid():
            mov = form.save(commit=False)
            mov.usuario = request.user  # salva o usuário logado

            # Validação: impedir estoque negativo
            entradas = mov.material.movimentacao_set.filter(tipo='entrada').aggregate(total=Sum('quantidade'))['total'] or 0
            saidas = mov.material.movimentacao_set.filter(tipo='saida').aggregate(total=Sum('quantidade'))['total'] or 0
            saldo_atual = mov.material.quantidade_inicial + entradas - saidas

            if mov.tipo == 'saida' and mov.quantidade > saldo_atual:
                messages.error(request, "Movimentação inválida: saldo insuficiente.")
                return redirect('movimentacao')

            mov.save()
            return redirect('movimentacoes')  # use o nome correto da rota
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

            # Validação: impedir duplicidade de usernames
            if User.objects.filter(username=usuario.username).exists():
                messages.error(request, "Usuário já existe.")
                return redirect('usuarios')

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

    # Validação: impedir exclusão do próprio usuário logado
    if usuario == request.user:
        messages.error(request, "Você não pode excluir sua própria conta.")
        return redirect('usuarios')

    usuario.delete()
    return redirect('usuarios')


# Dashboard inicial
@login_required
def dashboard(request):
    total_materiais = Material.objects.count()
    total_usuarios = User.objects.count()
    ultimas_movimentacoes = Movimentacao.objects.order_by('-data')[:5]
    return render(request, 'inventario/dashboard.html', {
        'total_materiais': total_materiais,
        'total_usuarios': total_usuarios,
        'ultimas_movimentacoes': ultimas_movimentacoes
    })


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
