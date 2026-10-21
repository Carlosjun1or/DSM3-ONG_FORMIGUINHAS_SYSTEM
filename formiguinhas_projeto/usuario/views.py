import logging
from decimal import Decimal
from smtplib import SMTPException

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Prefetch, Q, Sum
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone

from acao.models import Acao
from acao.services import calcular_frequencias_voluntarios
from doacao.models import Doacao, DoacaoFinanceira
from equipe.models import EquipeMembro

from .forms import (
    LoginForm,
    VoluntarioForm,
    VoluntarioEdicaoForm,
    UsuarioForm,
    UsuarioEdicaoForm,
    CadastroForm,
    PerfilForm,
    PasswordResetRequestForm,
    SetNewPasswordForm,
)
from .models import Usuario, Voluntario
from .paginacao import paginar_queryset
from .tokens import password_reset_token
from auditoria.services import registrar_evento, snapshot


# Create your views here.
logger = logging.getLogger(__name__)


def get_session_usuario(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None

    try:
        return Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return None


def render_acesso_bloqueado(request):
    return render(
        request,
        'sistema/acesso-bloqueado.html',
        status=403,
    )


def coordenador_nao_pode_alterar_email(usuario_logado, voluntario, email_novo):
    return (
        usuario_logado.tipo == 'COORDENADOR'
        and Usuario.objects.filter(id_voluntario=voluntario).exists()
        and voluntario.id_voluntario != usuario_logado.id_voluntario_id
        and voluntario.email.casefold() != email_novo.casefold()
    )


def coordenador_nao_pode_alterar_status(usuario_logado, voluntario, status_novo):
    return (
        usuario_logado.tipo == 'COORDENADOR'
        and status_novo != voluntario.status
    )


def aplicar_restricoes_edicao(form, usuario_logado, voluntario):
    email_bloqueado = (
        usuario_logado.tipo == 'COORDENADOR'
        and Usuario.objects.filter(id_voluntario=voluntario).exists()
        and voluntario.id_voluntario != usuario_logado.id_voluntario_id
    )
    status_bloqueado = usuario_logado.tipo != 'ADMIN'

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

    hoje = timezone.localdate()
    acoes_hoje = Acao.objects.filter(data=hoje).exclude(
        status=Acao.STATUS_CANCELADA,
    )
    total_doacoes_confirmadas = DoacaoFinanceira.objects.filter(
        doacao__status=Doacao.CONFIRMADA,
    ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    return render(request, 'sistema/home.html', {
        'usuario': usuario,
        'hoje': hoje,
        'total_voluntarios_ativos': Voluntario.objects.filter(
            status='ATIVO',
        ).count(),
        'atividades_hoje': acoes_hoje.count(),
        'total_doacoes_confirmadas': total_doacoes_confirmadas,
        'acoes_proximas': Acao.objects.filter(
            data__gte=hoje,
        ).exclude(
            status=Acao.STATUS_CANCELADA,
        ).select_related(
            'praia',
        ).order_by(
            'data',
            'horario',
            'id_acao',
        )[:3],
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
    voluntario_id = request.GET.get('voluntario', '').strip()
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
    voluntario_destacado = None
    if voluntario_id.isdigit():
        voluntario_destacado = int(voluntario_id)
        voluntarios = voluntarios.filter(id_voluntario=voluntario_destacado)

    pagina, filtros_query = paginar_queryset(request, voluntarios)
    voluntarios = pagina.object_list
    frequencias = calcular_frequencias_voluntarios(
        voluntarios.values_list('id_voluntario', flat=True),
    )
    for voluntario in voluntarios:
        frequencia = frequencias.get(voluntario.id_voluntario, {
            'total': 0,
            'presencas': 0,
            'percentual': None,
            'nivel': 'Sem participação',
        })
        voluntario.frequencia_total = frequencia['total']
        voluntario.frequencia_presencas = frequencia['presencas']
        voluntario.frequencia_percentual = frequencia['percentual']
        voluntario.frequencia_nivel = frequencia['nivel']

    return render(request, 'sistema/voluntarios.html', {
        'usuario': usuario,
        'voluntarios': voluntarios,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
        'status_selecionado': status,
        'voluntario_destacado': voluntario_destacado,
        'status_choices': Voluntario.STATUS_CHOICES,
        'total_voluntarios': Voluntario.objects.count(),
        'total_ativos': Voluntario.objects.filter(status='ATIVO').count(),
    })


@transaction.atomic
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
        valores_anteriores = snapshot(voluntario)
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
            status_proibido = coordenador_nao_pode_alterar_status(
                usuario,
                voluntario,
                form.cleaned_data['status'],
            )
            if status_proibido:
                form.add_error(
                    'status',
                    'Somente um administrador pode alterar o status de um voluntário.'
                )
            if not email_proibido and not status_proibido:
                status_anterior = voluntario.status
                voluntario = form.save(commit=False)
                voluntario.ultimo_editado_por = usuario
                voluntario.ultimo_editado_por_nome = usuario.id_voluntario.nome
                voluntario.ultimo_editado_por_tipo = usuario.tipo
                voluntario.dt_ultima_edicao = timezone.now()
                voluntario.save()
                registrar_evento(entidade='VOLUNTARIO', instancia=voluntario,
                                 acao='MUDANCA_STATUS' if status_anterior != voluntario.status else 'EDICAO',
                                 usuario=usuario, resumo=f'Voluntário "{voluntario.nome}" editado.',
                                 valores_anteriores=valores_anteriores)
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


@transaction.atomic
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
        status_proibido_para_coordenador = coordenador_nao_pode_alterar_status(
            usuario,
            voluntario,
            status,
        )
        status_proibido_para_admin = (
            hasattr(voluntario, 'usuario')
            and voluntario.usuario.tipo == 'ADMIN'
            and status != 'ATIVO'
        )
        if (
            status in status_validos
            and status != voluntario.status
            and not status_proibido_para_coordenador
            and not status_proibido_para_admin
        ):
            valores_anteriores = snapshot(voluntario)
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
            registrar_evento(entidade='VOLUNTARIO', instancia=voluntario, acao='MUDANCA_STATUS',
                             usuario=usuario, resumo=f'Status de "{voluntario.nome}" alterado.',
                             valores_anteriores=valores_anteriores)
            if voluntario.status == 'INATIVO':
                from equipe.services import encerrar_vinculos_voluntario

                encerrar_vinculos_voluntario(voluntario, usuario)

    return redirect('voluntarios')


@transaction.atomic
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
        valores_anteriores = snapshot(voluntario)
        usuario_vinculado = Usuario.objects.filter(id_voluntario=voluntario).first()
        valores_usuario_vinculado = (
            snapshot(usuario_vinculado) if usuario_vinculado else None
        )
        usuario_vinculado_id = usuario_vinculado.pk if usuario_vinculado else None
        voluntario.delete()
        registrar_evento(entidade='VOLUNTARIO', id_registro=voluntario_id, acao='EXCLUSAO',
                         usuario=usuario, resumo=f'Voluntário "{valores_anteriores.get("nome", voluntario_id)}" excluído.',
                         valores_anteriores=valores_anteriores)
        if usuario_vinculado_id is not None:
            registrar_evento(
                entidade='USUARIO',
                id_registro=usuario_vinculado_id,
                acao='EXCLUSAO',
                usuario=usuario,
                resumo=f'Usuário de "{valores_anteriores.get("nome", voluntario_id)}" excluído junto com o voluntário.',
                valores_anteriores=valores_usuario_vinculado,
            )

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
        return render_acesso_bloqueado(request)

    busca = request.GET.get('busca', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    usuarios = Usuario.objects.select_related(
        'id_voluntario',
        'cadastrado_por__id_voluntario',
        'ultimo_editado_por__id_voluntario',
    ).prefetch_related(
        Prefetch(
            'id_voluntario__equipes',
            queryset=EquipeMembro.objects.filter(
                papel=EquipeMembro.PAPEL_COORDENADOR,
                status='ATIVO',
            ).select_related('equipe__praia').order_by(
                'equipe__praia__nome',
                'equipe__nome',
            ),
            to_attr='equipes_coordenadas',
        ),
    ).all().order_by('id_voluntario__nome')

    if busca:
        usuarios = usuarios.filter(
            Q(id_voluntario__nome__icontains=busca) |
            Q(id_voluntario__email__icontains=busca)
        )
    if tipo in dict(Usuario.TIPO_CHOICES):
        usuarios = usuarios.filter(tipo=tipo)

    pagina, filtros_query = paginar_queryset(request, usuarios)
    usuarios = pagina.object_list
    for usuario_item in usuarios:
        praias = {}
        for membro in usuario_item.id_voluntario.equipes_coordenadas:
            if membro.equipe.praia_id:
                praias[membro.equipe.praia_id] = membro.equipe.praia
        usuario_item.praias_coordenador = list(
            sorted(praias.values(), key=lambda praia: praia.nome.casefold())
        )

    return render(request, 'sistema/usuarios.html', {
        'usuario': usuario,
        'usuarios': usuarios,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
        'tipo_selecionado': tipo,
        'tipo_choices': Usuario.TIPO_CHOICES,
        'total_usuarios': Usuario.objects.count(),
    })


@transaction.atomic
def atualizar_tipo_usuario_view(request, usuario_id):
    usuario_logado = get_session_usuario(request)
    if not usuario_logado:
        return redirect('login')
    if usuario_logado.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    if request.method == 'POST' and usuario_id != usuario_logado.id_usuario:
        novo_tipo = request.POST.get('tipo')
        if novo_tipo in dict(Usuario.TIPO_CHOICES):
            usuario_editado = Usuario.objects.filter(id_usuario=usuario_id).first()
            if usuario_editado and usuario_editado.tipo != novo_tipo:
                valores_anteriores = snapshot(usuario_editado)
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
                registrar_evento(
                    entidade='USUARIO',
                    instancia=usuario_editado,
                    acao='EDICAO',
                    usuario=usuario_logado,
                    resumo=f'Tipo de usuário de "{usuario_editado.id_voluntario.nome}" alterado.',
                    valores_anteriores=valores_anteriores,
                )

    return redirect('usuarios')


@transaction.atomic
def editar_usuario_view(request, usuario_id):
    usuario_logado = get_session_usuario(request)
    if not usuario_logado:
        return redirect('login')
    if usuario_logado.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

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
                status_anterior = usuario_editado.id_voluntario.status
                voluntario_anterior = snapshot(usuario_editado.id_voluntario)
                usuario_anterior = snapshot(usuario_editado)
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
                registrar_evento(
                    entidade='VOLUNTARIO',
                    instancia=voluntario,
                    acao=(
                        'MUDANCA_STATUS'
                        if status_anterior != voluntario.status
                        else 'EDICAO'
                    ),
                    usuario=usuario_logado,
                    resumo=f'Voluntário "{voluntario.nome}" editado pelo controle de usuários.',
                    valores_anteriores=voluntario_anterior,
                )
                registrar_evento(
                    entidade='USUARIO',
                    instancia=usuario_editado,
                    acao='EDICAO',
                    usuario=usuario_logado,
                    resumo=f'Usuário de "{voluntario.nome}" editado.',
                    valores_anteriores=usuario_anterior,
                )
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


@transaction.atomic
def excluir_usuario_view(request, usuario_id):
    usuario_logado = get_session_usuario(request)
    if not usuario_logado:
        return redirect('login')
    if usuario_logado.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    if request.method == 'POST' and usuario_id != usuario_logado.id_usuario:
        usuario_excluido = Usuario.objects.filter(id_usuario=usuario_id).first()
        if usuario_excluido:
            usuario_anterior = snapshot(usuario_excluido)
            voluntario = usuario_excluido.id_voluntario
            voluntario_anterior = snapshot(voluntario)
            usuario_excluido.delete()
            registrar_evento(
                entidade='USUARIO',
                id_registro=usuario_id,
                acao='EXCLUSAO',
                usuario=usuario_logado,
                resumo=f'Usuário de "{voluntario_anterior.get("nome", usuario_id)}" excluído.',
                valores_anteriores=usuario_anterior,
            )
            registrar_evento(
                entidade='VOLUNTARIO',
                id_registro=voluntario.pk,
                acao='EXCLUSAO',
                usuario=usuario_logado,
                resumo=f'Voluntário "{voluntario_anterior.get("nome", voluntario.pk)}" excluído junto com seu usuário.',
                valores_anteriores=voluntario_anterior,
            )

    return redirect('usuarios')


@transaction.atomic
def login_view(request):
    usuario_logado = get_session_usuario(request)
    if usuario_logado:
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
                voluntario, novo_usuario = cadastro_form.save(cadastrado_por=usuario)
                registrar_evento(
                    entidade='VOLUNTARIO',
                    instancia=voluntario,
                    acao='CRIACAO',
                    usuario=usuario,
                    resumo=f'Voluntário "{voluntario.nome}" cadastrado com usuário.',
                )
                registrar_evento(
                    entidade='USUARIO',
                    instancia=novo_usuario,
                    acao='CRIACAO',
                    usuario=usuario,
                    resumo=f'Usuário de "{voluntario.nome}" cadastrado.',
                )
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


def recuperar_senha_view(request):
    form = PasswordResetRequestForm(
        request.POST if request.method == 'POST' else None
    )
    email_enviado = False

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        usuario = Usuario.objects.select_related('id_voluntario').filter(
            id_voluntario__email__iexact=email,
            id_voluntario__status='ATIVO',
        ).first()

        if usuario:
            url_redefinicao = request.build_absolute_uri(reverse(
                'redefinir_senha',
                args=[usuario.id_usuario, password_reset_token.make_token(usuario)],
            ))
            try:
                send_mail(
                    subject='Recuperação de senha | Formiguinhas da Praia',
                    message=(
                        f'Olá, {usuario.id_voluntario.nome}.\n\n'
                        'Recebemos uma solicitação para redefinir a senha da sua conta. '
                        'Acesse o link abaixo para cadastrar uma nova senha:\n\n'
                        f'{url_redefinicao}\n\n'
                        'Se você não solicitou esta alteração, ignore este e-mail.'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[usuario.id_voluntario.email],
                    fail_silently=False,
                )
            except (OSError, SMTPException):
                logger.exception('Falha ao enviar e-mail de recuperação de senha.')
                form.add_error(
                    None,
                    'Não foi possível enviar o e-mail agora. Tente novamente mais tarde.',
                )
            else:
                email_enviado = True
        else:
            email_enviado = True

    return render(request, 'sistema/recuperar-senha.html', {
        'form': form,
        'email_enviado': email_enviado,
    })


def redefinir_senha_view(request, usuario_id, token):
    usuario = Usuario.objects.select_related('id_voluntario').filter(
        id_usuario=usuario_id,
        id_voluntario__status='ATIVO',
    ).first()
    token_valido = bool(usuario and password_reset_token.check_token(usuario, token))

    if not token_valido:
        return render(
            request,
            'sistema/redefinir-senha.html',
            {'token_valido': False},
            status=400,
        )

    form = SetNewPasswordForm(
        request.POST if request.method == 'POST' else None
    )
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            usuario = Usuario.objects.select_for_update().get(id_usuario=usuario_id)
            if not password_reset_token.check_token(usuario, token):
                return render(
                    request,
                    'sistema/redefinir-senha.html',
                    {'token_valido': False},
                    status=400,
                )

            usuario.set_password(form.cleaned_data['senha'])
            usuario.save(update_fields=['senha'])

        messages.success(request, 'Sua senha foi redefinida. Você já pode entrar.')
        return redirect('login')

    return render(request, 'sistema/redefinir-senha.html', {
        'form': form,
        'token_valido': True,
    })


def logout_view(request):
    request.session.flush()
    return render(request, 'sistema/logout.html')


@transaction.atomic
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
            registrar_evento(
                entidade='VOLUNTARIO',
                instancia=voluntario,
                acao='CRIACAO',
                usuario=usuario_logado,
                resumo=f'Voluntário "{voluntario.nome}" cadastrado.',
            )
            return redirect('voluntarios')
    else:
        form = VoluntarioForm()

    return render(request, 'sistema/cadastro-voluntario.html', {'form': form})


@transaction.atomic
def cadastro_usuario_view(request):
    usuario_logado = get_session_usuario(request)
    if not usuario_logado:
        return redirect('login')
    if usuario_logado.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

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
            registrar_evento(
                entidade='USUARIO',
                instancia=usuario,
                acao='CRIACAO',
                usuario=usuario_logado,
                resumo=f'Usuário de "{voluntario.nome}" cadastrado.',
            )
            return redirect('usuarios')
    else:
        form = UsuarioForm()

    return render(request, 'sistema/cadastro-usuario.html', {'form': form})


@transaction.atomic
def cadastro_view(request):
    usuario_logado = get_session_usuario(request)
    if not usuario_logado:
        return redirect('login')
    if usuario_logado.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            voluntario, novo_usuario = form.save(cadastrado_por=usuario_logado)
            registrar_evento(
                entidade='VOLUNTARIO',
                instancia=voluntario,
                acao='CRIACAO',
                usuario=usuario_logado,
                resumo=f'Voluntário "{voluntario.nome}" cadastrado com usuário.',
            )
            registrar_evento(
                entidade='USUARIO',
                instancia=novo_usuario,
                acao='CRIACAO',
                usuario=usuario_logado,
                resumo=f'Usuário de "{voluntario.nome}" cadastrado.',
            )
            return redirect('usuarios')
    else:
        form = CadastroForm()

    return render(request, 'sistema/cadastro.html', {'form': form})


@transaction.atomic
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
                valores_anteriores = snapshot(voluntario)
                voluntario = form.save(commit=False)
                voluntario.ultimo_editado_por = usuario
                voluntario.ultimo_editado_por_nome = usuario.id_voluntario.nome
                voluntario.ultimo_editado_por_tipo = usuario.tipo
                voluntario.dt_ultima_edicao = timezone.now()
                voluntario.save()
                registrar_evento(
                    entidade='VOLUNTARIO',
                    instancia=voluntario,
                    acao='EDICAO',
                    usuario=usuario,
                    resumo=f'Perfil do voluntário "{voluntario.nome}" atualizado.',
                    valores_anteriores=valores_anteriores,
                )
                usuario = Usuario.objects.get(id_usuario=usuario_id)
                return render(request, 'sistema/perfil.html', {
                    'usuario': usuario,
                    'form': form,
                    'mensagem': 'Dados do perfil atualizados com sucesso!'
                })
    else:
        form = PerfilForm(instance=voluntario)

    return render(request, 'sistema/perfil.html', {'usuario': usuario, 'form': form})


@transaction.atomic
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
        registrar_evento(
            entidade='USUARIO',
            instancia=usuario,
            acao='EDICAO',
            usuario=usuario,
            resumo='Senha do usuário alterada; credenciais não são armazenadas na auditoria.',
            valores_novos={'senha_alterada': True},
        )
        return render(request, 'sistema/perfil.html', {'usuario': usuario, 'mensagem': 'Senha alterada com sucesso!'})

    return render(request, 'sistema/alterar-senha.html')
