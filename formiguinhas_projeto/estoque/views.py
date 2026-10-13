import csv

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from auditoria.services import registrar_evento, snapshot
from usuario.models import Usuario

from .forms import DoacaoForm, MaterialForm, MovimentacaoEstoqueForm
from .models import Doacao, Material, MovimentacaoEstoque
from .services import registrar_doacao, registrar_movimentacao

MSG_ADMIN = 'Permissão insuficiente: esta funcionalidade é restrita a administradores.'
MSG_HISTORICO = 'Acesso negado: a consulta ao histórico é restrita a administradores.'
MSG_LOGIN = 'Acesso restrito: faça login para acessar o controle de estoque.'


def get_session_usuario(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None

    try:
        return Usuario.objects.select_related('id_voluntario').get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return None


def autenticar(request, somente_admin=False, mensagem=MSG_ADMIN):
    """Retorna (usuario, redirecionamento). Se houver redirecionamento, a view deve devolvê-lo."""
    usuario = get_session_usuario(request)
    if not usuario:
        messages.error(request, mensagem if somente_admin else MSG_LOGIN)
        return None, redirect('login')
    if somente_admin and usuario.tipo != 'ADMIN':
        messages.error(request, mensagem)
        return usuario, redirect('materiais')
    return usuario, None


def _estoque_baixo():
    return Q(saldo_db__lte=0) | Q(saldo_db__lt=F('estoque_minimo'))


def _periodo(request):
    hoje = timezone.localdate()
    inicio = parse_date(request.GET.get('data_inicio', '')) or hoje.replace(day=1)
    fim = parse_date(request.GET.get('data_fim', '')) or hoje
    return inicio, fim


def _paginar(request, queryset, por_pagina=10):
    parametros = request.GET.copy()
    parametros.pop('page', None)
    pagina = Paginator(queryset, por_pagina).get_page(request.GET.get('page'))
    return pagina, parametros.urlencode()


def materiais_view(request):
    usuario, resposta = autenticar(request)
    if resposta:
        return resposta

    busca = request.GET.get('busca', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    situacao = request.GET.get('situacao', '').strip()
    origem = request.GET.get('origem', '').strip()
    inicio, fim = _periodo(request)

    materiais = Material.objects.com_saldo().order_by('nome')
    if busca:
        materiais = materiais.filter(Q(nome__icontains=busca) | Q(codigo__icontains=busca))
    if categoria:
        materiais = materiais.filter(categoria__iexact=categoria)
    if situacao == 'BAIXO':
        materiais = materiais.filter(_estoque_baixo())
    if origem == 'DONATIVO':
        materiais = materiais.filter(donativo=True)
    elif origem == 'COMPRADO':
        materiais = materiais.filter(donativo=False)

    doado = Doacao.objects.filter(
        dt_cadastro__date__gte=inicio, dt_cadastro__date__lte=fim
    ).aggregate(total=Sum('quantidade'), registros=Count('id_doacao'))

    return render(request, 'sistema/materiais.html', {
        'usuario': usuario,
        'materiais': materiais,
        'busca': busca,
        'categoria_selecionada': categoria,
        'situacao_selecionada': situacao,
        'origem_selecionada': origem if origem in ('DONATIVO', 'COMPRADO') else '',
        'categorias': Material.objects.order_by('categoria').values_list(
            'categoria', flat=True
        ).distinct(),
        'data_inicio': inicio.isoformat(),
        'data_fim': fim.isoformat(),
        'doado_total': doado['total'] or 0,
        'doado_registros': doado['registros'],
        'total_materiais': Material.objects.count(),
        'total_baixo_estoque': Material.objects.com_saldo().filter(_estoque_baixo()).count(),
    })


def _categorias():
    return Material.objects.order_by('categoria').values_list('categoria', flat=True).distinct()


def cadastrar_material_view(request):
    usuario, resposta = autenticar(
        request, True, 'Permissão insuficiente: apenas administradores podem cadastrar materiais.'
    )
    if resposta:
        return resposta

    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            material = form.save(commit=False)
            material.cadastrado_por = usuario
            material.cadastrado_por_nome = usuario.id_voluntario.nome
            material.save()
            registrar_evento(
                entidade='MATERIAL', instancia=material, acao='CRIACAO', usuario=usuario,
                resumo=f'Material "{material.nome}" cadastrado.',
            )
            messages.success(request, 'Material cadastrado com sucesso.')
            return redirect('materiais')
    else:
        form = MaterialForm()

    return render(request, 'sistema/cadastro-material.html', {
        'usuario': usuario,
        'form': form,
        'categorias': _categorias(),
        'modo_edicao': False,
    })


def editar_material_view(request, material_id):
    usuario, resposta = autenticar(
        request, True, 'Permissão insuficiente: apenas administradores podem editar materiais.'
    )
    if resposta:
        return resposta

    material = get_object_or_404(Material, id_material=material_id)
    if request.method == 'POST':
        valores_anteriores = snapshot(material)
        form = MaterialForm(request.POST, instance=material)
        if form.is_valid():
            material = form.save(commit=False)
            material.ultimo_editado_por = usuario
            material.ultimo_editado_por_nome = usuario.id_voluntario.nome
            material.dt_ultima_edicao = timezone.now()
            material.save()
            registrar_evento(
                entidade='MATERIAL', instancia=material, acao='EDICAO', usuario=usuario,
                resumo=f'Material "{material.nome}" editado.',
                valores_anteriores=valores_anteriores,
            )
            messages.success(request, 'Material atualizado com sucesso.')
            return redirect('materiais')
    else:
        form = MaterialForm(instance=material)

    return render(request, 'sistema/cadastro-material.html', {
        'usuario': usuario,
        'form': form,
        'material': material,
        'categorias': _categorias(),
        'modo_edicao': True,
    })


def cadastrar_movimentacao_estoque_view(request):
    usuario, resposta = autenticar(
        request, True,
        'Permissão insuficiente: apenas administradores podem registrar movimentações.',
    )
    if resposta:
        return resposta

    if request.method == 'POST':
        form = MovimentacaoEstoqueForm(request.POST)
        if form.is_valid():
            try:
                registrar_movimentacao(form.save(commit=False), usuario)
            except ValidationError as erro:
                form.add_error(None, erro)
            else:
                messages.success(request, 'Movimentação registrada com sucesso.')
                return redirect('movimentacoes_estoque')
    else:
        form = MovimentacaoEstoqueForm()

    return render(request, 'sistema/cadastro-movimentacao-estoque.html', {
        'usuario': usuario,
        'form': form,
    })


def _filtrar_movimentacoes(request):
    movimentacoes = MovimentacaoEstoque.objects.select_related(
        'material', 'doacao'
    ).order_by('-dt_cadastro', '-id_movimentacao')
    busca = request.GET.get('busca', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    origem = request.GET.get('origem', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()

    if busca:
        movimentacoes = movimentacoes.filter(
            Q(material__nome__icontains=busca) | Q(material__codigo__icontains=busca)
        )
    if tipo in dict(MovimentacaoEstoque.TIPO_CHOICES):
        movimentacoes = movimentacoes.filter(tipo=tipo)
    if origem in dict(MovimentacaoEstoque.ORIGEM_CHOICES):
        movimentacoes = movimentacoes.filter(origem=origem)
    else:
        origem = ''
    inicio = parse_date(data_inicio) if data_inicio else None
    fim = parse_date(data_fim) if data_fim else None
    if inicio:
        movimentacoes = movimentacoes.filter(dt_cadastro__date__gte=inicio)
    if fim:
        movimentacoes = movimentacoes.filter(dt_cadastro__date__lte=fim)

    return movimentacoes, {
        'busca': busca, 'tipo': tipo, 'origem': origem, 'data_inicio': data_inicio, 'data_fim': data_fim,
    }


def movimentacoes_estoque_view(request):
    usuario, resposta = autenticar(request, True, MSG_HISTORICO)
    if resposta:
        return resposta

    movimentacoes, filtros = _filtrar_movimentacoes(request)
    page_obj, querystring = _paginar(request, movimentacoes)
    return render(request, 'sistema/movimentacoes-estoque.html', {
        'usuario': usuario,
        'page_obj': page_obj,
        'filtros': filtros,
        'querystring': querystring,
        'tipo_choices': MovimentacaoEstoque.TIPO_CHOICES,
        'origem_choices': MovimentacaoEstoque.ORIGEM_CHOICES,
    })


def _csv_seguro(valor):
    """Evita injeção de fórmulas ao abrir o CSV em planilhas."""
    texto = '' if valor is None else str(valor)
    return "'" + texto if texto[:1] in ('=', '+', '-', '@') else texto


def exportar_movimentacoes_estoque_view(request):
    usuario, resposta = autenticar(request, True, MSG_HISTORICO)
    if resposta:
        return resposta

    movimentacoes, _ = _filtrar_movimentacoes(request)
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = (
        f'attachment; filename="movimentacoes_estoque_{timezone.localdate().isoformat()}.csv"'
    )
    resposta.write('\ufeff')
    escritor = csv.writer(resposta, delimiter=';')
    escritor.writerow([
        'Data/hora', 'Tipo', 'Material', 'Código', 'Quantidade', 'Unidade',
        'Responsável', 'Justificativa', 'Origem',
    ])
    for mov in movimentacoes:
        escritor.writerow([
            timezone.localtime(mov.dt_cadastro).strftime('%d/%m/%Y %H:%M'),
            mov.get_tipo_display(),
            _csv_seguro(mov.material.nome),
            _csv_seguro(mov.material.codigo),
            mov.quantidade,
            mov.material.get_unidade_display(),
            _csv_seguro(mov.registrado_por_nome or '-'),
            _csv_seguro(mov.justificativa),
            _csv_seguro(mov.origem_detalhada),
        ])
    return resposta


def doacoes_estoque_view(request):
    usuario, resposta = autenticar(
        request, True, 'Permissão insuficiente: apenas administradores podem ver as doações.'
    )
    if resposta:
        return resposta

    busca = request.GET.get('busca', '').strip()
    doacoes = Doacao.objects.select_related('material')
    if busca:
        doacoes = doacoes.filter(
            Q(doador__icontains=busca) | Q(material__nome__icontains=busca)
        )
    page_obj, querystring = _paginar(request, doacoes)
    return render(request, 'sistema/doacoes-estoque.html', {
        'usuario': usuario,
        'page_obj': page_obj,
        'busca': busca,
        'querystring': querystring,
        'total_doacoes': Doacao.objects.count(),
        'total_itens_doados': Doacao.objects.aggregate(total=Sum('quantidade'))['total'] or 0,
    })


def cadastrar_doacao_estoque_view(request):
    usuario, resposta = autenticar(
        request, True, 'Permissão insuficiente: apenas administradores podem registrar doações.'
    )
    if resposta:
        return resposta

    if request.method == 'POST':
        form = DoacaoForm(request.POST)
        if form.is_valid():
            registrar_doacao(form.save(commit=False), usuario)
            messages.success(request, 'Doação registrada e entrada lançada no estoque.')
            return redirect('doacoes_estoque')
    else:
        form = DoacaoForm()

    return render(request, 'sistema/cadastro-doacao-estoque.html', {
        'usuario': usuario,
        'form': form,
    })


def relatorio_estoque_view(request):
    usuario, resposta = autenticar(request)
    if resposta:
        return resposta

    materiais = list(Material.objects.com_saldo())
    donativos = [m for m in materiais if m.donativo]
    comprados = [m for m in materiais if not m.donativo]
    return render(request, 'sistema/relatorio-estoque.html', {
        'usuario': usuario,
        'total_materiais': len(materiais),
        'quantidade_total': sum(m.saldo for m in materiais),
        'total_donativos': len(donativos),
        'quantidade_donativos': sum(m.saldo for m in donativos),
        'total_comprados': len(comprados),
        'quantidade_comprados': sum(m.saldo for m in comprados),
    })
