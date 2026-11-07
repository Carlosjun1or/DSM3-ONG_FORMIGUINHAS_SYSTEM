from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from usuario.models import Voluntario
from usuario.views import get_session_usuario, render_acesso_bloqueado
from usuario.paginacao import paginar_queryset

from .forms import EquipeForm, EquipeMembroForm
from .models import Equipe, EquipeMembro
from auditoria.services import registrar_evento, snapshot


def preencher_auditoria(objeto, usuario, criacao=False):
    nome = usuario.id_voluntario.nome
    tipo = usuario.tipo

    if criacao:
        objeto.cadastrado_por = usuario
        objeto.cadastrado_por_nome = nome
        objeto.cadastrado_por_tipo = tipo
        return

    objeto.ultimo_editado_por = usuario
    objeto.ultimo_editado_por_nome = nome
    objeto.ultimo_editado_por_tipo = tipo
    objeto.dt_ultima_edicao = timezone.now()


def equipe_queryset_para_usuario(usuario):
    equipes = Equipe.objects.select_related('praia').annotate(
        total_membros=Count(
            'membros',
            filter=Q(membros__status='ATIVO'),
        )
    )
    if usuario.tipo in ('ADMIN', 'COORDENADOR'):
        return equipes
    return equipes.none()


def usuario_pode_gerenciar_equipe(usuario, equipe):
    if usuario.tipo == 'ADMIN':
        return True
    return EquipeMembro.objects.filter(
        equipe=equipe,
        voluntario=usuario.id_voluntario,
        papel='COORDENADOR',
        status='ATIVO',
    ).exists()


def usuario_pode_adicionar_membro(usuario, equipe):
    return usuario_pode_gerenciar_equipe(usuario, equipe) and equipe.status == 'ATIVA'


def usuario_pode_remover_membro(usuario, equipe, membro):
    if not usuario_pode_adicionar_membro(usuario, equipe):
        return False
    return not (
        usuario.tipo == 'COORDENADOR'
        and membro.papel == EquipeMembro.PAPEL_COORDENADOR
        and membro.voluntario_id != usuario.id_voluntario_id
    )


def equipes_view(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo not in ('ADMIN', 'COORDENADOR'):
        return redirect('home')

    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    participacao = request.GET.get('participacao', '').strip()
    papel_equipe = request.GET.get('papel_equipe', '').strip()
    equipes = equipe_queryset_para_usuario(usuario).order_by('nome')

    if busca:
        equipes = equipes.filter(
            Q(nome__icontains=busca) | Q(descricao__icontains=busca)
        )
    if status in dict(Equipe.STATUS_CHOICES):
        equipes = equipes.filter(status=status)
    if usuario.tipo == 'COORDENADOR' and participacao == 'MINHAS':
        equipes = equipes.filter(
            membros__voluntario=usuario.id_voluntario,
            membros__status='ATIVO',
        )
    if usuario.tipo == 'COORDENADOR' and papel_equipe in dict(EquipeMembro.PAPEL_CHOICES):
        equipes = equipes.filter(
            membros__voluntario=usuario.id_voluntario,
            membros__papel=papel_equipe,
            membros__status='ATIVO',
        )
    equipes = equipes.distinct()

    pagina, filtros_query = paginar_queryset(request, equipes)
    base_queryset = equipe_queryset_para_usuario(usuario)
    return render(request, 'sistema/equipes.html', {
        'usuario': usuario,
        'equipes': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
        'status_selecionado': status,
        'status_choices': Equipe.STATUS_CHOICES,
        'participacao_selecionada': participacao,
        'papel_equipe_selecionado': papel_equipe,
        'papel_equipe_choices': EquipeMembro.PAPEL_CHOICES,
        'total_equipes': base_queryset.count(),
        'total_ativas': base_queryset.filter(status='ATIVA').count(),
    })


@transaction.atomic
def cadastro_equipe_view(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    if request.method == 'POST':
        form = EquipeForm(request.POST)
        if form.is_valid():
            equipe = form.save(commit=False)
            preencher_auditoria(equipe, usuario, criacao=True)
            equipe.save()
            registrar_evento(entidade='EQUIPE', instancia=equipe, acao='CRIACAO', usuario=usuario,
                             resumo=f'Equipe "{equipe.nome}" cadastrada.')
            messages.success(request, f'A equipe "{equipe.nome}" foi cadastrada com sucesso.')
            return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)
    else:
        form = EquipeForm(initial={'status': 'ATIVA'})

    return render(request, 'sistema/form-equipe.html', {
        'usuario': usuario,
        'form': form,
        'modo': 'cadastro',
    })


@transaction.atomic
def editar_equipe_view(request, equipe_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    equipe = get_object_or_404(
        Equipe.objects.select_related('praia'),
        id_equipe=equipe_id,
    )
    if request.method == 'POST':
        valores_anteriores = snapshot(equipe)
        form = EquipeForm(request.POST, instance=equipe)
        if form.is_valid():
            equipe = form.save(commit=False)
            preencher_auditoria(equipe, usuario)
            equipe.save()
            registrar_evento(entidade='EQUIPE', instancia=equipe, acao='EDICAO', usuario=usuario,
                             resumo=f'Equipe "{equipe.nome}" editada.',
                             valores_anteriores=valores_anteriores)
            messages.success(request, f'A equipe "{equipe.nome}" foi atualizada com sucesso.')
            return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)
    else:
        form = EquipeForm(instance=equipe)

    return render(request, 'sistema/form-equipe.html', {
        'usuario': usuario,
        'form': form,
        'equipe': equipe,
        'modo': 'edicao',
    })


def equipe_detalhe_view(request, equipe_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    if usuario.tipo not in ('ADMIN', 'COORDENADOR'):
        return redirect('equipes')

    busca_membro = request.GET.get('busca_membro', '').strip()
    papel_membro = request.GET.get('papel_membro', '').strip()
    membros = equipe.membros.select_related(
        'voluntario',
        'cadastrado_por__id_voluntario',
        'ultimo_editado_por__id_voluntario',
    ).filter(status='ATIVO').order_by('papel', 'voluntario__nome')
    historico_membros = equipe.membros.select_related(
        'voluntario',
        'ultimo_editado_por__id_voluntario',
    ).filter(status='INATIVO').order_by('-dt_saida', 'voluntario__nome')

    def aplicar_filtros_membros(queryset):
        if busca_membro:
            queryset = queryset.filter(
                Q(voluntario__nome__icontains=busca_membro)
                | Q(voluntario__email__icontains=busca_membro)
            )
        if papel_membro in dict(EquipeMembro.PAPEL_CHOICES):
            queryset = queryset.filter(papel=papel_membro)
        return queryset

    membros = aplicar_filtros_membros(membros)
    historico_membros = aplicar_filtros_membros(historico_membros)

    form = EquipeMembroForm(
        equipe=equipe,
        permitir_coordenador=usuario.tipo == 'ADMIN',
    )
    return render(request, 'sistema/detalhe-equipe.html', {
        'usuario': usuario,
        'equipe': equipe,
        'membros': membros,
        'historico_membros': historico_membros,
        'busca_membro': busca_membro,
        'papel_membro': papel_membro,
        'papel_choices': EquipeMembro.PAPEL_CHOICES,
        'form': form,
        'pode_adicionar': usuario_pode_adicionar_membro(usuario, equipe),
        'pode_editar_equipe': usuario.tipo == 'ADMIN',
    })


@transaction.atomic
def adicionar_membro_view(request, equipe_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    if request.method != 'POST':
        return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)
    if not usuario_pode_adicionar_membro(usuario, equipe):
        messages.error(
            request,
            f'Você não tem permissão para adicionar membros à equipe "{equipe.nome}".',
        )
        return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)

    try:
        voluntario_id = int(request.POST.get('voluntario', ''))
    except (TypeError, ValueError):
        voluntario_id = None
    if voluntario_id is not None:
        status_voluntario = Voluntario.objects.filter(
            id_voluntario=voluntario_id,
        ).values_list('status', flat=True).first()
        if status_voluntario and status_voluntario != 'ATIVO':
            voluntario = Voluntario.objects.get(id_voluntario=voluntario_id)
            messages.error(
                request,
                f'Não foi possível adicionar "{voluntario.nome}" à equipe "{equipe.nome}", '
                'pois o cadastro do voluntário não está ativo.',
            )
            return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)

    if voluntario_id is not None:
        membro_existente = EquipeMembro.objects.select_related('voluntario').filter(
            equipe=equipe,
            voluntario_id=voluntario_id,
            status='ATIVO',
        ).first()
        if membro_existente:
            messages.error(
                request,
                f'"{membro_existente.voluntario.nome}" já possui vínculo ativo '
                f'com a equipe "{equipe.nome}".',
            )
            return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)

    form = EquipeMembroForm(
        request.POST,
        equipe=equipe,
        permitir_coordenador=usuario.tipo == 'ADMIN',
    )
    if form.is_valid():
        membro = form.save(commit=False)
        membro.equipe = equipe
        if usuario.tipo != 'ADMIN':
            membro.papel = 'VOLUNTARIO'
        preencher_auditoria(membro, usuario, criacao=True)
        try:
            with transaction.atomic():
                membro.save()
        except IntegrityError:
            if not EquipeMembro.objects.filter(
                equipe=equipe,
                voluntario=membro.voluntario,
                status='ATIVO',
            ).exists():
                raise
            messages.error(
                request,
                f'"{membro.voluntario.nome}" já possui vínculo ativo '
                f'com a equipe "{equipe.nome}".',
            )
            return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)
        registrar_evento(entidade='EQUIPE_MEMBRO', instancia=membro, acao='VINCULO', usuario=usuario,
                         resumo=f'{membro.voluntario.nome} vinculado à equipe "{equipe.nome}".')
        preencher_auditoria(equipe, usuario)
        equipe.save(update_fields=[
            'ultimo_editado_por',
            'ultimo_editado_por_nome',
            'ultimo_editado_por_tipo',
            'dt_ultima_edicao',
        ])
        messages.success(
            request,
            f'O vínculo de "{membro.voluntario.nome}" com a equipe "{equipe.nome}" '
            'foi criado com sucesso.',
        )
    else:
        messages.error(
            request,
            f'Não foi possível adicionar o membro à equipe "{equipe.nome}". '
            'Verifique os dados e tente novamente.',
        )
    return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)


@transaction.atomic
def atualizar_funcao_membro_view(request, equipe_id, membro_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    membro = get_object_or_404(
        EquipeMembro,
        id_equipe_membro=membro_id,
        equipe=equipe,
        status='ATIVO',
    )
    if request.method == 'POST':
        if not usuario_pode_adicionar_membro(usuario, equipe):
            messages.error(
                request,
                f'Não é possível alterar funções de membros na equipe inativa '
                f'"{equipe.nome}".',
            )
            return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)
        papel = request.POST.get('papel')
        if papel in dict(EquipeMembro.PAPEL_CHOICES) and papel != membro.papel:
            valores_anteriores = snapshot(membro)
            membro.papel = papel
            preencher_auditoria(membro, usuario)
            membro.save(update_fields=[
                'papel',
                'ultimo_editado_por',
                'ultimo_editado_por_nome',
                'ultimo_editado_por_tipo',
                'dt_ultima_edicao',
            ])
            preencher_auditoria(equipe, usuario)
            equipe.save(update_fields=[
                'ultimo_editado_por',
                'ultimo_editado_por_nome',
                'ultimo_editado_por_tipo',
                'dt_ultima_edicao',
            ])
            registrar_evento(
                entidade='EQUIPE_MEMBRO',
                instancia=membro,
                acao='EDICAO',
                usuario=usuario,
                resumo=f'Função de {membro.voluntario.nome} alterada na equipe "{equipe.nome}".',
                valores_anteriores=valores_anteriores,
            )
            messages.success(
                request,
                f'A função de "{membro.voluntario.nome}" na equipe "{equipe.nome}" '
                'foi atualizada com sucesso.',
            )
        elif papel not in dict(EquipeMembro.PAPEL_CHOICES):
            messages.error(
                request,
                f'Não foi possível atualizar a função na equipe "{equipe.nome}". '
                'Selecione uma função válida.',
            )
        else:
            messages.info(
                request,
                f'"{membro.voluntario.nome}" já está como {membro.get_papel_display()} '
                f'na equipe "{equipe.nome}".',
            )
    return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)


@transaction.atomic
def remover_membro_view(request, equipe_id, membro_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    membro = get_object_or_404(
        EquipeMembro,
        id_equipe_membro=membro_id,
        equipe=equipe,
        status='ATIVO',
    )
    if request.method == 'POST' and usuario_pode_remover_membro(usuario, equipe, membro):
        valores_anteriores = snapshot(membro)
        membro.status = 'INATIVO'
        membro.dt_saida = timezone.now()
        preencher_auditoria(membro, usuario)
        membro.save(update_fields=[
            'status',
            'dt_saida',
            'ultimo_editado_por',
            'ultimo_editado_por_nome',
            'ultimo_editado_por_tipo',
            'dt_ultima_edicao',
        ])
        preencher_auditoria(equipe, usuario)
        equipe.save(update_fields=[
            'ultimo_editado_por',
            'ultimo_editado_por_nome',
            'ultimo_editado_por_tipo',
            'dt_ultima_edicao',
        ])
        registrar_evento(
            entidade='EQUIPE_MEMBRO',
            instancia=membro,
            acao='MUDANCA_STATUS',
            usuario=usuario,
            resumo=(
                f'{membro.voluntario.nome} saiu da equipe "{equipe.nome}".'
                if usuario.tipo == 'COORDENADOR'
                and membro.voluntario_id == usuario.id_voluntario_id
                else f'{membro.voluntario.nome} removido da equipe "{equipe.nome}".'
            ),
            valores_anteriores=valores_anteriores,
        )
        messages.success(
            request,
            (
                f'Você saiu da equipe "{equipe.nome}".'
                if usuario.tipo == 'COORDENADOR'
                and membro.voluntario_id == usuario.id_voluntario_id
                else (
                    f'O vínculo de "{membro.voluntario.nome}" com a equipe '
                    f'"{equipe.nome}" foi encerrado com sucesso.'
                )
            ),
        )
    elif (
        request.method == 'POST'
        and usuario_pode_adicionar_membro(usuario, equipe)
        and usuario.tipo == 'COORDENADOR'
        and membro.papel == EquipeMembro.PAPEL_COORDENADOR
        and membro.voluntario_id != usuario.id_voluntario_id
    ):
        messages.error(
            request,
            f'Você não pode remover outro coordenador da equipe "{equipe.nome}".',
        )
    elif request.method == 'POST':
        messages.error(
            request,
            f'Você não tem permissão para remover membros da equipe "{equipe.nome}".',
        )
    return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)


@transaction.atomic
def excluir_historico_membro_view(request, equipe_id, membro_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    membro = get_object_or_404(
        EquipeMembro,
        id_equipe_membro=membro_id,
        equipe=equipe,
        status='INATIVO',
    )
    if request.method == 'POST':
        if equipe.status != 'ATIVA':
            messages.error(
                request,
                f'Não é possível excluir registros de membros da equipe inativa '
                f'"{equipe.nome}".',
            )
            return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)
        valores_anteriores = snapshot(membro)
        membro_id_registro = membro.pk
        nome_membro = membro.voluntario.nome
        membro.delete()
        registrar_evento(
            entidade='EQUIPE_MEMBRO',
            id_registro=membro_id_registro,
            acao='EXCLUSAO',
            usuario=usuario,
            resumo=f'Histórico de membro removido da equipe "{equipe.nome}".',
            valores_anteriores=valores_anteriores,
        )
        preencher_auditoria(equipe, usuario)
        equipe.save(update_fields=[
            'ultimo_editado_por',
            'ultimo_editado_por_nome',
            'ultimo_editado_por_tipo',
            'dt_ultima_edicao',
        ])
        messages.success(
            request,
            f'O registro de participação de "{nome_membro}" na equipe '
            f'"{equipe.nome}" foi excluído do histórico com sucesso.',
        )
    return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)


@transaction.atomic
def atualizar_status_equipe_view(request, equipe_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in dict(Equipe.STATUS_CHOICES) and status != equipe.status:
            valores_anteriores = snapshot(equipe)
            equipe.status = status
            preencher_auditoria(equipe, usuario)
            equipe.save(update_fields=[
                'status',
                'ultimo_editado_por',
                'ultimo_editado_por_nome',
                'ultimo_editado_por_tipo',
                'dt_ultima_edicao',
            ])
            registrar_evento(
                entidade='EQUIPE',
                instancia=equipe,
                acao='MUDANCA_STATUS',
                usuario=usuario,
                resumo=f'Situação da equipe "{equipe.nome}" alterada.',
                valores_anteriores=valores_anteriores,
            )
            messages.success(
                request,
                f'O status da equipe "{equipe.nome}" foi atualizado para '
                f'{equipe.get_status_display()}.',
            )
        elif status not in dict(Equipe.STATUS_CHOICES):
            messages.error(
                request,
                f'Não foi possível atualizar o status da equipe "{equipe.nome}". '
                'Selecione um status válido.',
            )
        else:
            messages.info(
                request,
                f'A equipe "{equipe.nome}" já está com status {equipe.get_status_display()}.',
            )
    return redirect('equipes')


@transaction.atomic
def excluir_equipe_view(request, equipe_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    if request.method == 'POST':
        if equipe.membros.exists():
            messages.error(
                request,
                f'Não é possível excluir a equipe "{equipe.nome}", pois ela possui '
                'membros ou histórico. Inative-a para preservar os registros.',
            )
        else:
            try:
                valores_anteriores = snapshot(equipe)
                equipe_id_registro = equipe.pk
                equipe.delete()
                registrar_evento(
                    entidade='EQUIPE',
                    id_registro=equipe_id_registro,
                    acao='EXCLUSAO',
                    usuario=usuario,
                    resumo=f'Equipe "{valores_anteriores.get("nome", equipe_id_registro)}" excluída.',
                    valores_anteriores=valores_anteriores,
                )
                messages.success(
                    request,
                    f'A equipe "{equipe.nome}" foi excluída com sucesso.',
                )
            except ProtectedError:
                messages.error(
                    request,
                    f'Não foi possível excluir a equipe "{equipe.nome}". '
                    'Inative-a para preservar os registros relacionados.',
                )
    return redirect('equipes')
