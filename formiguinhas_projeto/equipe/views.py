from django.contrib import messages
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from usuario.views import get_session_usuario

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

    base_queryset = equipe_queryset_para_usuario(usuario)
    return render(request, 'sistema/equipes.html', {
        'usuario': usuario,
        'equipes': equipes,
        'busca': busca,
        'status_selecionado': status,
        'status_choices': Equipe.STATUS_CHOICES,
        'participacao_selecionada': participacao,
        'papel_equipe_selecionado': papel_equipe,
        'papel_equipe_choices': EquipeMembro.PAPEL_CHOICES,
        'total_equipes': base_queryset.count(),
        'total_ativas': base_queryset.filter(status='ATIVA').count(),
    })


def cadastro_equipe_view(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('equipes')

    if request.method == 'POST':
        form = EquipeForm(request.POST)
        if form.is_valid():
            equipe = form.save(commit=False)
            preencher_auditoria(equipe, usuario, criacao=True)
            equipe.save()
            registrar_evento(entidade='EQUIPE', instancia=equipe, acao='CRIACAO', usuario=usuario,
                             resumo=f'Equipe "{equipe.nome}" cadastrada.')
            return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)
    else:
        form = EquipeForm(initial={'status': 'ATIVA'})

    return render(request, 'sistema/form-equipe.html', {
        'usuario': usuario,
        'form': form,
        'modo': 'cadastro',
    })


def editar_equipe_view(request, equipe_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('equipes')

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


def adicionar_membro_view(request, equipe_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    if request.method != 'POST' or not usuario_pode_adicionar_membro(usuario, equipe):
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
        membro.save()
        registrar_evento(entidade='EQUIPE_MEMBRO', instancia=membro, acao='VINCULO', usuario=usuario,
                         resumo=f'{membro.voluntario.nome} vinculado à equipe "{equipe.nome}".')
        preencher_auditoria(equipe, usuario)
        equipe.save(update_fields=[
            'ultimo_editado_por',
            'ultimo_editado_por_nome',
            'ultimo_editado_por_tipo',
            'dt_ultima_edicao',
        ])
    return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)


def atualizar_funcao_membro_view(request, equipe_id, membro_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('equipe_detalhe', equipe_id=equipe_id)

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    membro = get_object_or_404(
        EquipeMembro,
        id_equipe_membro=membro_id,
        equipe=equipe,
        status='ATIVO',
    )
    if request.method == 'POST':
        papel = request.POST.get('papel')
        if papel in dict(EquipeMembro.PAPEL_CHOICES):
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
    return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)


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
    if request.method == 'POST' and usuario_pode_adicionar_membro(usuario, equipe):
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
    return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)


def excluir_historico_membro_view(request, equipe_id, membro_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('equipe_detalhe', equipe_id=equipe_id)

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    membro = get_object_or_404(
        EquipeMembro,
        id_equipe_membro=membro_id,
        equipe=equipe,
        status='INATIVO',
    )
    if request.method == 'POST':
        membro.delete()
        preencher_auditoria(equipe, usuario)
        equipe.save(update_fields=[
            'ultimo_editado_por',
            'ultimo_editado_por_nome',
            'ultimo_editado_por_tipo',
            'dt_ultima_edicao',
        ])
    return redirect('equipe_detalhe', equipe_id=equipe.id_equipe)


def atualizar_status_equipe_view(request, equipe_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('equipes')

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in dict(Equipe.STATUS_CHOICES):
            equipe.status = status
            preencher_auditoria(equipe, usuario)
            equipe.save(update_fields=[
                'status',
                'ultimo_editado_por',
                'ultimo_editado_por_nome',
                'ultimo_editado_por_tipo',
                'dt_ultima_edicao',
            ])
    return redirect('equipes')


def excluir_equipe_view(request, equipe_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('equipes')

    equipe = get_object_or_404(Equipe, id_equipe=equipe_id)
    if request.method == 'POST':
        if equipe.membros.exists():
            messages.error(
                request,
                'Não é possível excluir uma equipe que possui membros ou histórico. Inative-a para preservar os registros.',
            )
        else:
            try:
                equipe.delete()
                messages.success(request, 'Equipe excluída com sucesso.')
            except ProtectedError:
                messages.error(
                    request,
                    'Não é possível excluir esta equipe. Inative-a para preservar os registros.',
                )
    return redirect('equipes')
