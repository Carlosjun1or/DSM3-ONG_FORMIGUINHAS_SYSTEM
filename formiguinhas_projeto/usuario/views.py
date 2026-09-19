from django.db.models import Q
from django.shortcuts import render, redirect
from django.utils import timezone
from .forms import (
    LoginForm,
    VoluntarioForm,
    VoluntarioEdicaoForm,
    UsuarioForm,
    UsuarioEdicaoForm,
    CadastroForm,
    PerfilForm,
)
from .models import Usuario, Voluntario


# Create your views here.

def get_session_usuario(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None

    try:
        return Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return None


def coordenador_nao_pode_alterar_email(usuario_logado, voluntario, email_novo):
    return (
        usuario_logado.tipo == 'COORDENADOR'
        and Usuario.objects.filter(id_voluntario=voluntario).exists()
        and voluntario.id_voluntario != usuario_logado.id_voluntario_id
        and voluntario.email.casefold() != email_novo.casefold()
    )


def aplicar_restricoes_edicao(form, usuario_logado, voluntario):
    email_bloqueado = (
        usuario_logado.tipo == 'COORDENADOR'
        and Usuario.objects.filter(id_voluntario=voluntario).exists()
        and voluntario.id_voluntario != usuario_logado.id_voluntario_id
    )
    status_bloqueado = (
        usuario_logado.tipo != 'ADMIN'
        and hasattr(voluntario, 'usuario')
        and voluntario.usuario.tipo == 'COORDENADOR'
    )

    if email_bloqueado:
        form.fields['email'].disabled = True
    if status_bloqueado:
        form.fields['status'].disabled = True
        form.fields['status'].choices = [
            (voluntario.status, voluntario.get_status_display())
        ]

    return email_bloqueado, status_bloqueado

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


def voluntarios_view(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return redirect('login')

    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    voluntarios = Voluntario.objects.select_related(
        'usuario',
        'cadastrado_por__id_voluntario',
        'ultimo_editado_por__id_voluntario',
    ).all().order_by('nome')

    if busca:
        voluntarios = voluntarios.filter(
            Q(nome__icontains=busca) | Q(email__icontains=busca)
        )
    if status in dict(Voluntario.STATUS_CHOICES):
        voluntarios = voluntarios.filter(status=status)

    return render(request, 'sistema/voluntarios.html', {
        'usuario': usuario,
        'voluntarios': voluntarios,
        'busca': busca,
        'status_selecionado': status,
        'status_choices': Voluntario.STATUS_CHOICES,
        'total_voluntarios': Voluntario.objects.count(),
        'total_ativos': Voluntario.objects.filter(status='ATIVO').count(),
    })


def editar_voluntario_view(request, voluntario_id):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
        voluntario = Voluntario.objects.get(id_voluntario=voluntario_id)
    except (Usuario.DoesNotExist, Voluntario.DoesNotExist):
        request.session.flush()
        return redirect('login')

    if request.method == 'POST':
        form = VoluntarioEdicaoForm(request.POST, instance=voluntario)
        email_bloqueado, status_bloqueado = aplicar_restricoes_edicao(
            form, usuario, voluntario
        )
        formulario_valido = form.is_valid()
        email_proibido = coordenador_nao_pode_alterar_email(
            usuario,
            voluntario,
            request.POST.get('email', ''),
        )
        if email_proibido:
            form.add_error(
                'email',
                'Coordenadores não podem alterar o e-mail de um voluntário com usuário cadastrado.'
            )
        if formulario_valido:
            status_proibido = (
                usuario.tipo != 'ADMIN'
                and hasattr(voluntario, 'usuario')
                and voluntario.usuario.tipo == 'COORDENADOR'
                and form.cleaned_data['status'] != voluntario.status
            )
            if status_proibido:
                form.add_error(
                    'status',
                    'Somente um administrador pode alterar o status de um coordenador.'
                )
            if not email_proibido and not status_proibido:
                voluntario = form.save(commit=False)
                voluntario.ultimo_editado_por = usuario
                voluntario.ultimo_editado_por_nome = usuario.id_voluntario.nome
                voluntario.ultimo_editado_por_tipo = usuario.tipo
                voluntario.dt_ultima_edicao = timezone.now()
                voluntario.save()
                if voluntario.status == 'INATIVO':
                    from equipe.services import encerrar_vinculos_voluntario

                    encerrar_vinculos_voluntario(voluntario, usuario)
                return redirect('voluntarios')
    else:
        form = VoluntarioEdicaoForm(instance=voluntario)
        email_bloqueado, status_bloqueado = aplicar_restricoes_edicao(
            form, usuario, voluntario
        )

    return render(request, 'sistema/editar-voluntario.html', {
        'usuario': usuario,
        'voluntario': voluntario,
        'form': form,
        'email_bloqueado': email_bloqueado,
        'status_bloqueado': status_bloqueado,
    })


def atualizar_status_voluntario_view(request, voluntario_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')

    if request.method == 'POST':
        try:
            voluntario = Voluntario.objects.select_related('usuario').get(id_voluntario=voluntario_id)
        except Voluntario.DoesNotExist:
            return redirect('voluntarios')

        status = request.POST.get('status')
        status_validos = dict(Voluntario.STATUS_CHOICES)
        status_proibido_para_coordenador = (
            usuario.tipo != 'ADMIN'
            and hasattr(voluntario, 'usuario')
            and voluntario.usuario.tipo == 'COORDENADOR'
            and status != voluntario.status
        )
        status_proibido_para_admin = (
            hasattr(voluntario, 'usuario')
            and voluntario.usuario.tipo == 'ADMIN'
            and status != 'ATIVO'
        )
        if status in status_validos and not status_proibido_para_coordenador and not status_proibido_para_admin:
            voluntario.status = status
            voluntario.ultimo_editado_por = usuario
            voluntario.ultimo_editado_por_nome = usuario.id_voluntario.nome
            voluntario.ultimo_editado_por_tipo = usuario.tipo
            voluntario.dt_ultima_edicao = timezone.now()
            voluntario.save(update_fields=[
                'status',
                'ultimo_editado_por',
                'ultimo_editado_por_nome',
                'ultimo_editado_por_tipo',
                'dt_ultima_edicao',
            ])
            if voluntario.status == 'INATIVO':
                from equipe.services import encerrar_vinculos_voluntario

                encerrar_vinculos_voluntario(voluntario, usuario)

    return redirect('voluntarios')


def excluir_voluntario_view(request, voluntario_id):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
        voluntario = Voluntario.objects.get(id_voluntario=voluntario_id)
    except (Usuario.DoesNotExist, Voluntario.DoesNotExist):
        request.session.flush()
        return redirect('login')

    if usuario.tipo != 'ADMIN':
        return redirect('voluntarios')

    if request.method == 'POST':
        voluntario.delete()

    return redirect('voluntarios')


def usuarios_view(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return redirect('login')

    if usuario.tipo != 'ADMIN':
        return redirect('home')

    busca = request.GET.get('busca', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    usuarios = Usuario.objects.select_related(
        'id_voluntario',
        'cadastrado_por__id_voluntario',
        'ultimo_editado_por__id_voluntario',
    ).all().order_by('id_voluntario__nome')

    if busca:
        usuarios = usuarios.filter(
            Q(id_voluntario__nome__icontains=busca) |
            Q(id_voluntario__email__icontains=busca)
        )
    if tipo in dict(Usuario.TIPO_CHOICES):
        usuarios = usuarios.filter(tipo=tipo)

    return render(request, 'sistema/usuarios.html', {
        'usuario': usuario,
        'usuarios': usuarios,
        'busca': busca,
        'tipo_selecionado': tipo,
        'tipo_choices': Usuario.TIPO_CHOICES,
        'total_usuarios': Usuario.objects.count(),
    })


def atualizar_tipo_usuario_view(request, usuario_id):
    usuario_logado = get_session_usuario(request)
    if not usuario_logado:
        return redirect('login')
    if usuario_logado.tipo != 'ADMIN':
        return redirect('home')

    if request.method == 'POST' and usuario_id != usuario_logado.id_usuario:
        novo_tipo = request.POST.get('tipo')
        if novo_tipo in dict(Usuario.TIPO_CHOICES):
            usuario_editado = Usuario.objects.filter(id_usuario=usuario_id).first()
            if usuario_editado:
                usuario_editado.tipo = novo_tipo
                usuario_editado.ultimo_editado_por = usuario_logado
                usuario_editado.ultimo_editado_por_nome = usuario_logado.id_voluntario.nome
                usuario_editado.ultimo_editado_por_tipo = usuario_logado.tipo
                usuario_editado.dt_ultima_edicao = timezone.now()
                usuario_editado.save(update_fields=[
                    'tipo',
                    'ultimo_editado_por',
                    'ultimo_editado_por_nome',
                    'ultimo_editado_por_tipo',
                    'dt_ultima_edicao',
                ])

    return redirect('usuarios')


def editar_usuario_view(request, usuario_id):
    usuario_logado = get_session_usuario(request)
    if not usuario_logado:
        return redirect('login')
    if usuario_logado.tipo != 'ADMIN':
        return redirect('home')

    try:
        usuario_editado = Usuario.objects.select_related('id_voluntario').get(
            id_usuario=usuario_id
        )
    except Usuario.DoesNotExist:
        return redirect('usuarios')

    if request.method == 'POST':
        form = UsuarioEdicaoForm(request.POST)
        voluntario_form = VoluntarioEdicaoForm(
            request.POST,
            instance=usuario_editado.id_voluntario,
        )
        email_bloqueado, status_bloqueado = aplicar_restricoes_edicao(
            voluntario_form,
            usuario_logado,
            usuario_editado.id_voluntario,
        )
        if form.is_valid() and voluntario_form.is_valid():
            if coordenador_nao_pode_alterar_email(
                usuario_logado,
                usuario_editado.id_voluntario,
                voluntario_form.cleaned_data['email'],
            ):
                voluntario_form.add_error(
                    'email',
                    'Coordenadores não podem alterar o e-mail de um voluntário com usuário cadastrado.'
                )
            else:
                voluntario = voluntario_form.save(commit=False)
                voluntario.ultimo_editado_por = usuario_logado
                voluntario.ultimo_editado_por_nome = usuario_logado.id_voluntario.nome
                voluntario.ultimo_editado_por_tipo = usuario_logado.tipo
                voluntario.dt_ultima_edicao = timezone.now()
                voluntario.save()
                if voluntario.status == 'INATIVO':
                    from equipe.services import encerrar_vinculos_voluntario

                    encerrar_vinculos_voluntario(voluntario, usuario_logado)
                usuario_editado.tipo = form.cleaned_data['tipo']
                usuario_editado.ultimo_editado_por = usuario_logado
                usuario_editado.ultimo_editado_por_nome = usuario_logado.id_voluntario.nome
                usuario_editado.ultimo_editado_por_tipo = usuario_logado.tipo
                usuario_editado.dt_ultima_edicao = timezone.now()
                usuario_editado.save()
                return redirect('usuarios')
    else:
        form = UsuarioEdicaoForm(initial={'tipo': usuario_editado.tipo})
        voluntario_form = VoluntarioEdicaoForm(instance=usuario_editado.id_voluntario)
        email_bloqueado, status_bloqueado = aplicar_restricoes_edicao(
            voluntario_form,
            usuario_logado,
            usuario_editado.id_voluntario,
        )

    return render(request, 'sistema/editar-usuario.html', {
        'usuario': usuario_logado,
        'usuario_editado': usuario_editado,
        'form': form,
        'voluntario_form': voluntario_form,
        'email_bloqueado': email_bloqueado,
        'status_bloqueado': status_bloqueado,
    })


def excluir_usuario_view(request, usuario_id):
    usuario_logado = get_session_usuario(request)
    if not usuario_logado:
        return redirect('login')
    if usuario_logado.tipo != 'ADMIN':
        return redirect('home')

    if request.method == 'POST' and usuario_id != usuario_logado.id_usuario:
        usuario_excluido = Usuario.objects.filter(id_usuario=usuario_id).first()
        if usuario_excluido:
            usuario_excluido.delete()

    return redirect('usuarios')


def login_view(request):
    if get_session_usuario(request):
        return redirect('home')

    form = LoginForm()
    cadastro_form = CadastroForm()

    if request.method == 'POST':
        if request.POST.get('acao') == 'cadastrar_teste':
            usuario = get_session_usuario(request)
            if not usuario or usuario.tipo != 'ADMIN':
                return render(request, 'sistema/login.html', {
                    'form': form,
                    'cadastro_form': CadastroForm(),
                    'mensagem': 'Somente administradores podem realizar o cadastro completo.'
                })

            cadastro_form = CadastroForm(request.POST)
            if cadastro_form.is_valid():
                cadastro_form.save(cadastrado_por=usuario)
                return redirect('usuarios')
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
    usuario_logado = get_session_usuario(request)
    if not usuario_logado:
        return redirect('login')

    if request.method == 'POST':
        form = VoluntarioForm(request.POST)
        if form.is_valid():
            voluntario = form.save(commit=False)
            voluntario.cadastrado_por = usuario_logado
            voluntario.cadastrado_por_nome = usuario_logado.id_voluntario.nome
            voluntario.cadastrado_por_tipo = usuario_logado.tipo
            voluntario.save()
            return redirect('voluntarios')
    else:
        form = VoluntarioForm()

    return render(request, 'sistema/cadastro-voluntario.html', {'form': form})


def cadastro_usuario_view(request):
    usuario_logado = get_session_usuario(request)
    if not usuario_logado:
        return redirect('login')
    if usuario_logado.tipo != 'ADMIN':
        return redirect('home')

    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            voluntario = form.cleaned_data['voluntario']
            usuario = Usuario(
                id_voluntario=voluntario,
                tipo=form.cleaned_data['tipo'],
                cadastrado_por=usuario_logado,
                cadastrado_por_nome=usuario_logado.id_voluntario.nome,
                cadastrado_por_tipo=usuario_logado.tipo,
            )
            usuario.set_password(form.cleaned_data['senha'])
            usuario.save()
            return redirect('usuarios')
    else:
        form = UsuarioForm()

    return render(request, 'sistema/cadastro-usuario.html', {'form': form})


def cadastro_view(request):
    usuario_logado = get_session_usuario(request)
    if not usuario_logado:
        return redirect('login')
    if usuario_logado.tipo != 'ADMIN':
        return redirect('home')

    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            form.save(cadastrado_por=usuario_logado)
            return redirect('usuarios')
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
            if coordenador_nao_pode_alterar_email(
                usuario,
                voluntario,
                form.cleaned_data['email'],
            ):
                form.add_error(
                    'email',
                    'Coordenadores não podem alterar o e-mail de um voluntário com usuário cadastrado.'
                )
            else:
                voluntario = form.save(commit=False)
                voluntario.ultimo_editado_por = usuario
                voluntario.ultimo_editado_por_nome = usuario.id_voluntario.nome
                voluntario.ultimo_editado_por_tipo = usuario.tipo
                voluntario.dt_ultima_edicao = timezone.now()
                voluntario.save()
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

