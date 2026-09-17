from django.shortcuts import render, redirect
from django.utils import timezone
from .forms import LoginForm, VoluntarioForm, UsuarioForm, CadastroForm, PerfilForm
from .models import Usuario


# Create your views here.

def index(request):
    return render(request, "index.html")


def home_view(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return redirect('login')

    return render(request, 'sistema/home.html', {
        'usuario': usuario,
        'mensagem': 'Bem-vindo ao sistema da ONG Formiguinhas.'
    })


def login_view(request):
    form = LoginForm()
    cadastro_form = CadastroForm()

    if request.method == 'POST':
        if request.POST.get('acao') == 'cadastrar_teste':
            cadastro_form = CadastroForm(request.POST)
            if cadastro_form.is_valid():
                cadastro_form.save()
                return render(request, 'sistema/login.html', {
                    'form': form,
                    'cadastro_form': CadastroForm(),
                    'mensagem': 'Cadastro de teste criado com sucesso!'
                })
        else:
            form = LoginForm(request.POST)
            if form.is_valid():
                usuario = form.usuario
                request.session['usuario_id'] = usuario.id_usuario
                request.session['usuario_nome'] = usuario.id_voluntario.nome
                request.session['usuario_tipo'] = usuario.tipo
                usuario.data_ultimo_acesso = timezone.now()
                usuario.save()
                return redirect('home')

    return render(request, 'sistema/login.html', {'form': form, 'cadastro_form': cadastro_form})


def logout_view(request):
    request.session.flush()
    return render(request, 'sistema/logout.html', {'mensagem': 'Logout realizado com sucesso!'})


def cadastro_voluntario_view(request):
    if request.method == 'POST':
        form = VoluntarioForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('cadastro_usuario')
    else:
        form = VoluntarioForm()

    return render(request, 'sistema/cadastro-voluntario.html', {'form': form})


def cadastro_usuario_view(request):
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            voluntario = form.cleaned_data['voluntario']
            usuario = Usuario(
                id_voluntario=voluntario,
                tipo=form.cleaned_data['tipo']
            )
            usuario.set_password(form.cleaned_data['senha'])
            usuario.save()
            return redirect('login')
    else:
        form = UsuarioForm()

    return render(request, 'sistema/cadastro-usuario.html', {'form': form})


def cadastro_view(request):
    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = CadastroForm()

    return render(request, 'sistema/cadastro.html', {'form': form})


def perfil_view(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return redirect('login')

    voluntario = usuario.id_voluntario

    if request.method == 'POST':
        form = PerfilForm(request.POST, instance=voluntario)
        if form.is_valid():
            form.save()
            usuario = Usuario.objects.get(id_usuario=usuario_id)
            return render(request, 'sistema/perfil.html', {
                'usuario': usuario,
                'form': form,
                'mensagem': 'Dados do perfil atualizados com sucesso!'
            })
    else:
        form = PerfilForm(instance=voluntario)

    return render(request, 'sistema/perfil.html', {'usuario': usuario, 'form': form})


def alterar_senha_view(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return redirect('login')

    if request.method == 'POST':
        senha_atual = request.POST.get('senha_atual')
        nova_senha = request.POST.get('nova_senha')
        confirmar_nova_senha = request.POST.get('confirmar_nova_senha')

        if not senha_atual or not nova_senha or not confirmar_nova_senha:
            return render(request, 'sistema/alterar-senha.html', {'mensagem': 'Preencha a senha atual, a nova senha e a confirmação.'})

        if not usuario.check_password(senha_atual):
            return render(request, 'sistema/alterar-senha.html', {'mensagem': 'A senha atual está incorreta.'})

        if nova_senha != confirmar_nova_senha:
            return render(request, 'sistema/alterar-senha.html', {'mensagem': 'As novas senhas não coincidem.'})

        if nova_senha == senha_atual:
            return render(request, 'sistema/alterar-senha.html', {'mensagem': 'A nova senha deve ser diferente da senha atual.'})

        usuario.set_password(nova_senha)
        usuario.save()
        return render(request, 'sistema/perfil.html', {'usuario': usuario, 'mensagem': 'Senha alterada com sucesso!'})

    return render(request, 'sistema/alterar-senha.html')

