from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import LoginForm
from .models import Usuario


def get_session_usuario(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None

    try:
        return Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return None


def login_view(request):
    if get_session_usuario(request):
        return redirect('materiais')

    form = LoginForm()

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            usuario = form.usuario
            request.session['usuario_id'] = usuario.id_usuario
            request.session['usuario_nome'] = usuario.id_voluntario.nome
            request.session['usuario_tipo'] = usuario.tipo
            usuario.data_ultimo_acesso = timezone.now()
            usuario.save()
            return redirect('materiais')

    return render(request, 'sistema/login.html', {'form': form})


def logout_view(request):
    request.session.flush()
    return render(request, 'sistema/logout.html', {'mensagem': 'Logout realizado com sucesso!'})
