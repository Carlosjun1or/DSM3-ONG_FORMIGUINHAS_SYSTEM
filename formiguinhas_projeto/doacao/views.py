from decimal import Decimal
from datetime import datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from auditoria.services import registrar_evento, snapshot

from auditoria.models import EventoAuditoria
from estoque.services import registrar_entradas_doacao
from usuario.views import get_session_usuario, render_acesso_bloqueado
from usuario.paginacao import paginar_queryset

from .forms import (
    DoadorForm,
    DoadorInlineForm,
    DoacaoFinanceiraForm,
    DoacaoForm,
    ItemDoacaoMaterialFormSet,
)
from .models import Doador, Doacao, DoacaoFinanceira


def _usuario_com_acesso(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return None
    if usuario.tipo != 'ADMIN':
        return False
    return usuario


def _preencher_auditoria(instancia, usuario, criacao=False):
    nome = usuario.id_voluntario.nome
    if criacao:
        instancia.registrado_por = usuario
        instancia.registrado_por_nome = nome
        instancia.registrado_por_tipo = usuario.tipo
    else:
        instancia.ultimo_editado_por = usuario
        instancia.ultimo_editado_por_nome = nome
        instancia.ultimo_editado_por_tipo = usuario.tipo
        instancia.dt_ultima_edicao = timezone.now()


def _periodo(request):
    def converter(valor):
        valor = (valor or '').strip()
        if not valor:
            return None
        return parse_date(valor) or _parse_data_br(valor)

    inicio = converter(request.GET.get('inicio'))
    fim = converter(request.GET.get('fim'))
    return inicio, fim


def _parse_data_br(valor):
    try:
        return datetime.strptime(valor, '%d/%m/%Y').date()
    except ValueError:
        return None


def doacoes_view(request):
    usuario = _usuario_com_acesso(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)

    inicio, fim = _periodo(request)
    tipo = request.GET.get('tipo', '').strip()
    status = request.GET.get('status', '').strip()
    finalidade = request.GET.get('finalidade', '').strip()
    doacoes = Doacao.objects.select_related(
        'doador',
        'praia',
        'acao',
        'registrado_por__id_voluntario',
    ).prefetch_related('itens_materiais', 'financeira')
    if inicio:
        doacoes = doacoes.filter(data_recebimento__gte=inicio)
    if fim:
        doacoes = doacoes.filter(data_recebimento__lte=fim)
    if tipo in dict(Doacao.TIPO_CHOICES):
        doacoes = doacoes.filter(tipo=tipo)
    if status in dict(Doacao.STATUS_CHOICES):
        doacoes = doacoes.filter(status=status)
    if finalidade in dict(Doacao.FINALIDADE_CHOICES):
        doacoes = doacoes.filter(finalidade=finalidade)

    confirmado = Doacao.objects.filter(status=Doacao.CONFIRMADA)
    if inicio:
        confirmado = confirmado.filter(data_recebimento__gte=inicio)
    if fim:
        confirmado = confirmado.filter(data_recebimento__lte=fim)
    total_financeiro = confirmado.filter(
        tipo=Doacao.FINANCEIRA,
    ).aggregate(
        total=Coalesce(
            Sum('financeira__valor'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    )['total']
    quantidade_materiais = confirmado.filter(
        tipo=Doacao.MATERIAL,
    ).aggregate(
        total=Coalesce(
            Sum('itens_materiais__quantidade'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    )['total']

    doacoes = doacoes.order_by('-data_recebimento', '-id_doacao')
    pagina, filtros_query = paginar_queryset(request, doacoes)
    return render(request, 'sistema/doacoes.html', {
        'usuario': usuario,
        'doacoes': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'inicio': request.GET.get('inicio', ''),
        'fim': request.GET.get('fim', ''),
        'tipo_selecionado': tipo,
        'status_selecionado': status,
        'finalidade_selecionada': finalidade,
        'tipo_choices': Doacao.TIPO_CHOICES,
        'status_choices': Doacao.STATUS_CHOICES,
        'finalidade_choices': Doacao.FINALIDADE_CHOICES,
        'total_financeiro': total_financeiro,
        'quantidade_doacoes': confirmado.count(),
        'quantidade_pendentes': Doacao.objects.filter(status=Doacao.PENDENTE).count(),
        'quantidade_materiais': quantidade_materiais,
    })


def _formulario_doacao(request, doacao=None):
    form = DoacaoForm(request.POST or None, instance=doacao)
    estoque_bloqueado = bool(doacao and doacao.movimentacoes_estoque.exists())
    if estoque_bloqueado:
        form.fields['tipo'].disabled = True
        form.fields['status'].disabled = True
    financeira = getattr(doacao, 'financeira', None) if doacao else None
    financeira_form = DoacaoFinanceiraForm(
        request.POST or None,
        instance=financeira,
        prefix='financeira',
    )
    itens_formset = ItemDoacaoMaterialFormSet(
        request.POST or None,
        instance=doacao,
        prefix='itens',
    )
    doador_inline_form = DoadorInlineForm(
        request.POST or None,
        prefix='novo_doador',
    )
    return form, financeira_form, itens_formset, doador_inline_form


def _novo_doador_informado(request):
    campos = ('tipo', 'nome', 'documento', 'email', 'telefone', 'voluntario')
    return any(request.POST.get(f'novo_doador-{campo}', '').strip() for campo in campos)


def _validar_doacao_forms(form, financeira_form, itens_formset, doador_inline_form, request):
    principal_valida = form.is_valid()
    tipo = request.POST.get('tipo')
    financeira_valida = (
        tipo != Doacao.FINANCEIRA or financeira_form.is_valid()
    )
    if principal_valida and tipo == Doacao.MATERIAL:
        itens_formset.instance.status = form.cleaned_data['status']
    itens_validos = tipo != Doacao.MATERIAL or itens_formset.is_valid()
    inline_informado = _novo_doador_informado(request)
    inline_valido = not inline_informado or doador_inline_form.is_valid()
    if inline_informado and not request.POST.get('doador'):
        form.errors.pop('doador', None)
        principal_valida = not form.errors
    if inline_informado and request.POST.get('doador'):
        form.add_error(
            'doador',
            'Selecione um doador existente ou preencha o cadastro de novo doador, não os dois.',
        )
        principal_valida = False
    if request.POST.get('anonima') and inline_informado:
        doador_inline_form.add_error(
            None,
            'Doações anônimas não podem cadastrar um doador identificado.',
        )
        inline_valido = False
    return principal_valida and financeira_valida and itens_validos and inline_valido


def _salvar_doador_inline(request, usuario, inline_form, doacao_form):
    if not _novo_doador_informado(request):
        return doacao_form.cleaned_data.get('doador')
    doador = inline_form.save(commit=False)
    doador.cadastrado_por = usuario
    doador.cadastrado_por_nome = usuario.id_voluntario.nome
    doador.save()
    registrar_evento(
        entidade='DOADOR',
        instancia=doador,
        acao='CRIACAO',
        usuario=usuario,
        resumo=f'Doador #{doador.pk} cadastrado junto com a doação.',
    )
    return doador


@transaction.atomic
def cadastro_doacao_view(request):
    usuario = _usuario_com_acesso(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    form, financeira_form, itens_formset, doador_inline_form = _formulario_doacao(request)
    if request.method == 'POST':
        if _validar_doacao_forms(
            form, financeira_form, itens_formset, doador_inline_form, request
        ):
            doacao = form.save(commit=False)
            doacao.doador = _salvar_doador_inline(
                request, usuario, doador_inline_form, form
            )
            _preencher_auditoria(doacao, usuario, criacao=True)
            doacao.save()
            if doacao.tipo == Doacao.FINANCEIRA:
                financeira = financeira_form.save(commit=False)
                financeira.doacao = doacao
                financeira.save()
            else:
                itens_formset.instance = doacao
                itens_formset.save()
                if doacao.status == Doacao.CONFIRMADA:
                    registrar_entradas_doacao(doacao, usuario)
            registrar_evento(
                entidade='DOACAO',
                instancia=doacao,
                acao='CRIACAO',
                usuario=usuario,
                resumo=f'Doação #{doacao.pk} cadastrada.',
            )
            messages.success(request, 'Doação cadastrada com sucesso.')
            return redirect('doacao_detalhe', doacao_id=doacao.pk)
        messages.error(
            request,
            'Não foi possível cadastrar a doação. Verifique os erros informados.',
        )
    return render(request, 'sistema/cadastro-doacao.html', {
        'usuario': usuario,
        'form': form,
        'financeira_form': financeira_form,
        'itens_formset': itens_formset,
        'doador_inline_form': doador_inline_form,
        'modo': 'cadastro',
    })


@transaction.atomic
def editar_doacao_view(request, doacao_id):
    usuario = _usuario_com_acesso(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    doacao = get_object_or_404(Doacao, pk=doacao_id)
    valores_anteriores = snapshot(doacao)
    form, financeira_form, itens_formset, doador_inline_form = _formulario_doacao(request, doacao)
    if request.method == 'POST':
        if _validar_doacao_forms(
            form, financeira_form, itens_formset, doador_inline_form, request
        ):
            doacao = form.save(commit=False)
            doacao.doador = _salvar_doador_inline(
                request, usuario, doador_inline_form, form
            )
            _preencher_auditoria(doacao, usuario)
            doacao.save()
            if doacao.tipo == Doacao.FINANCEIRA:
                financeira = financeira_form.save(commit=False)
                financeira.doacao = doacao
                financeira.save()
                doacao.itens_materiais.all().delete()
            else:
                DoacaoFinanceira.objects.filter(doacao=doacao).delete()
                itens_formset.instance = doacao
                itens_formset.save()
                if (
                    doacao.status == Doacao.CONFIRMADA
                    and not doacao.movimentacoes_estoque.exists()
                ):
                    registrar_entradas_doacao(doacao, usuario)
            registrar_evento(
                entidade='DOACAO',
                instancia=doacao,
                acao='EDICAO',
                usuario=usuario,
                resumo=f'Doação #{doacao.pk} editada.',
                valores_anteriores=valores_anteriores,
            )
            messages.success(request, 'Doação atualizada com sucesso.')
            return redirect('doacao_detalhe', doacao_id=doacao.pk)
        messages.error(
            request,
            'Não foi possível atualizar a doação. Verifique os erros informados.',
        )
    return render(request, 'sistema/cadastro-doacao.html', {
        'usuario': usuario,
        'form': form,
        'financeira_form': financeira_form,
        'itens_formset': itens_formset,
        'doador_inline_form': doador_inline_form,
        'doacao': doacao,
        'modo': 'edicao',
        'estoque_bloqueado': bool(doacao.movimentacoes_estoque.exists()),
    })



def doacao_detalhe_view(request, doacao_id):
    usuario = _usuario_com_acesso(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)

    doacao = get_object_or_404(
        Doacao.objects.select_related(
            'doador',
            'praia',
            'acao',
            'registrado_por__id_voluntario',
            'ultimo_editado_por__id_voluntario',
        ).prefetch_related(
            'itens_materiais__material',
            'itens_materiais__movimentacao_estoque',
        ),
        pk=doacao_id,
    )
    estoque_movimentacoes = doacao.movimentacoes_estoque.select_related(
        'material',
        'item_doacao',
    )
    tem_movimentacoes_estoque = estoque_movimentacoes.exists()

    auditorias = EventoAuditoria.objects.filter(
        entidade='DOACAO',
        id_registro=doacao.pk,
    ).select_related('usuario').order_by('-data_evento', '-id')

    return render(request, 'sistema/detalhe-doacao.html', {
        'usuario': usuario,
        'doacao': doacao,
        'status_choices': [
            choice for choice in Doacao.STATUS_CHOICES
            if not tem_movimentacoes_estoque or choice[0] == doacao.status
        ],
        'auditorias': auditorias,
        'tem_movimentacoes_estoque': tem_movimentacoes_estoque,
    })



@transaction.atomic
def atualizar_status_doacao_view(request, doacao_id):
    usuario = _usuario_com_acesso(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    doacao = get_object_or_404(Doacao, pk=doacao_id)
    retornar_aos_detalhes = request.POST.get('retorno') == 'detalhe'
    destino = 'doacao_detalhe' if retornar_aos_detalhes else 'doacoes'
    novo_status = request.POST.get('status', '')
    if request.method != 'POST' or novo_status not in dict(Doacao.STATUS_CHOICES):
        messages.error(request, 'Situação de doação inválida.')
        return redirect(destino, **({'doacao_id': doacao.pk} if retornar_aos_detalhes else {}))
    if novo_status == Doacao.CANCELADA and usuario.tipo != 'ADMIN':
        messages.error(request, 'Somente administradores podem cancelar doações.')
        return redirect(destino, **({'doacao_id': doacao.pk} if retornar_aos_detalhes else {}))
    if novo_status != Doacao.CONFIRMADA and doacao.movimentacoes_estoque.exists():
        messages.error(
            request,
            'Não é possível retirar a confirmação: a doação já gerou movimentações no estoque.',
        )
        return redirect(destino, **({'doacao_id': doacao.pk} if retornar_aos_detalhes else {}))
    status_anterior = doacao.get_status_display()
    try:
        with transaction.atomic():
            doacao.status = novo_status
            _preencher_auditoria(doacao, usuario)
            doacao.save(update_fields=[
                'status', 'ultimo_editado_por', 'ultimo_editado_por_nome',
                'ultimo_editado_por_tipo', 'dt_ultima_edicao',
            ])
            if (
                novo_status == Doacao.CONFIRMADA
                and doacao.tipo == Doacao.MATERIAL
                and not doacao.movimentacoes_estoque.exists()
            ):
                registrar_entradas_doacao(doacao, usuario)
            registrar_evento(
                entidade='DOACAO',
                instancia=doacao,
                acao='MUDANCA_STATUS',
                usuario=usuario,
                resumo=f'Doação #{doacao.pk}: {status_anterior} para {doacao.get_status_display()}.',
            )
    except ValidationError as erro:
        messages.error(request, 'Não foi possível confirmar a doação: ' + ' '.join(erro.messages))
        return redirect(destino, **({'doacao_id': doacao.pk} if retornar_aos_detalhes else {}))
    messages.success(request, 'Situação da doação atualizada.')
    return redirect(destino, **({'doacao_id': doacao.pk} if retornar_aos_detalhes else {}))


def doadores_view(request):
    usuario = _usuario_com_acesso(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    busca = request.GET.get('busca', '').strip()
    doadores = Doador.objects.select_related('voluntario').all()
    if busca:
        doadores = doadores.filter(
            Q(nome__icontains=busca)
            | Q(documento__icontains=busca)
            | Q(email__icontains=busca)
        )
    doadores = doadores.order_by('-dt_cadastro', '-id_doador')
    pagina, filtros_query = paginar_queryset(request, doadores)
    return render(request, 'sistema/doadores.html', {
        'usuario': usuario,
        'doadores': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
    })


def doador_detalhe_view(request, doador_id):
    usuario = _usuario_com_acesso(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    doador = get_object_or_404(
        Doador.objects.select_related(
            'voluntario',
            'cadastrado_por__id_voluntario',
            'ultimo_editado_por__id_voluntario',
        ).prefetch_related('doacoes'),
        pk=doador_id,
    )
    auditorias = EventoAuditoria.objects.filter(
            entidade='DOADOR',
            id_registro=doador.pk,
        ).select_related('usuario').order_by('-data_evento', '-id')
    return render(request, 'sistema/detalhe-doador.html', {
        'usuario': usuario,
        'doador': doador,
        'auditorias': auditorias,
    })


@transaction.atomic
def atualizar_status_doador_view(request, doador_id):
    usuario = _usuario_com_acesso(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    if usuario.tipo != 'ADMIN':
        messages.error(request, 'Somente administradores podem alterar a situação de doadores.')
        return redirect('doadores')

    doador = get_object_or_404(Doador, pk=doador_id)
    retornar_aos_detalhes = request.POST.get('retorno') == 'detalhe'
    destino = 'doador_detalhe' if retornar_aos_detalhes else 'doadores'
    novo_status = request.POST.get('status', '')
    if request.method != 'POST' or novo_status not in ('ATIVO', 'INATIVO'):
        messages.error(request, 'Situação de doador inválida.')
        return redirect(destino, **({'doador_id': doador.pk} if retornar_aos_detalhes else {}))

    ativo_anterior = doador.ativo
    doador.ativo = novo_status == 'ATIVO'
    doador.ultimo_editado_por = usuario
    doador.ultimo_editado_por_nome = usuario.id_voluntario.nome
    doador.dt_ultima_edicao = timezone.now()
    doador.save(update_fields=[
        'ativo', 'ultimo_editado_por', 'ultimo_editado_por_nome', 'dt_ultima_edicao',
    ])
    registrar_evento(
        entidade='DOADOR',
        instancia=doador,
        acao='MUDANCA_STATUS',
        usuario=usuario,
        resumo=f'Doador #{doador.pk}: '
        f'{"Ativo" if ativo_anterior else "Inativo"} para '
        f'{"Ativo" if doador.ativo else "Inativo"}.',
    )
    messages.success(request, 'Situação do doador atualizada.')
    return redirect(destino, **({'doador_id': doador.pk} if retornar_aos_detalhes else {}))


def cadastro_doador_view(request):
    usuario = _usuario_com_acesso(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    if usuario.tipo != 'ADMIN':
        messages.error(request, 'Somente administradores podem gerenciar doadores.')
        return redirect('doacoes')
    form = DoadorForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        doador = form.save(commit=False)
        doador.cadastrado_por = usuario
        doador.cadastrado_por_nome = usuario.id_voluntario.nome
        doador.save()
        registrar_evento(
            entidade='DOADOR',
            instancia=doador,
            acao='CRIACAO',
            usuario=usuario,
            resumo=f'Doador #{doador.pk} cadastrado.',
        )
        messages.success(request, 'Doador cadastrado com sucesso.')
        return redirect('doadores')
    if request.method == 'POST':
        messages.error(
            request,
            'Não foi possível cadastrar o doador. Verifique os erros informados.',
        )
    return render(request, 'sistema/cadastro-doador.html', {
        'usuario': usuario,
        'form': form,
        'modo': 'cadastro',
    })


def editar_doador_view(request, doador_id):
    usuario = _usuario_com_acesso(request)
    if usuario is None:
        return redirect('login')
    if usuario is False:
        return render_acesso_bloqueado(request)
    if usuario.tipo != 'ADMIN':
        messages.error(request, 'Somente administradores podem gerenciar doadores.')
        return redirect('doacoes')
    doador = get_object_or_404(Doador, pk=doador_id)
    valores_anteriores = snapshot(doador)
    form = DoadorForm(request.POST or None, instance=doador)
    if request.method == 'POST' and form.is_valid():
        doador = form.save(commit=False)
        doador.ultimo_editado_por = usuario
        doador.ultimo_editado_por_nome = usuario.id_voluntario.nome
        doador.dt_ultima_edicao = timezone.now()
        doador.save()
        registrar_evento(
            entidade='DOADOR',
            instancia=doador,
            acao='EDICAO',
            usuario=usuario,
            resumo=f'Doador #{doador.pk} editado.',
            valores_anteriores=valores_anteriores,
        )
        messages.success(request, 'Doador atualizado com sucesso.')
        return redirect('doadores')
    if request.method == 'POST':
        messages.error(
            request,
            'Não foi possível atualizar o doador. Verifique os erros informados.',
        )
    return render(request, 'sistema/cadastro-doador.html', {
        'usuario': usuario,
        'form': form,
        'doador': doador,
        'modo': 'edicao',
    })
