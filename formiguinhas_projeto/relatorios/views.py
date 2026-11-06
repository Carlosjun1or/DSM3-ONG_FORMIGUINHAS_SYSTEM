"""
App de relatórios: gera tabelas e permite exportação em CSV, Excel e XML.

Todos os dados de ações são lidos do MongoDB (via mongo_services). Os dados de
estoque, doações e voluntários vêm do SQLite. A função _criar_relatorio() é o
núcleo — recebe os filtros do formulário e monta a estrutura {metrics, sections}
que o template usa tanto para exibição em tela quanto para exportação.
"""
import csv
import io
import logging
from collections import defaultdict
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from xml.sax.saxutils import escape

from django import forms
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from acao.models import Acao, AcaoParticipante
from doacao.models import Doacao, DoacaoFinanceira, ItemDoacaoMaterial
from estoque.models import Material, MovimentacaoEstoque
from praia.models import Praia
from residuo.models import ColetaResiduo, ItemColetaResiduo, ResiduoColetado
from usuario.models import Usuario, Voluntario
from usuario.views import render_acesso_bloqueado


logger = logging.getLogger(__name__)

RELATORIOS = [
    ('geral', 'Relatório geral'),
    ('indicadores', 'Indicadores por período / praia'),
    ('acoes', 'Relatório de ações'),
    ('voluntarios', 'Relatório de voluntários'),
    ('presenca', 'Relatório de presença'),
    ('residuos', 'Relatório de resíduos'),
    ('estoque', 'Relatório de estoque'),
    ('doacoes', 'Relatório de doações'),
]
GRUPOS_RELATORIOS = [
    ('Visão geral', [
        ('geral', 'Geral', 'reports'),
        ('indicadores', 'Indicadores por praia', 'beach'),
    ]),
    ('Operação', [
        ('acoes', 'Ações', 'actions'),
        ('voluntarios', 'Voluntários', 'volunteers'),
        ('presenca', 'Presença', 'audit'),
    ]),
    ('Recursos', [
        ('residuos', 'Resíduos', 'residue'),
        ('estoque', 'Estoque', 'package'),
        ('doacoes', 'Doações', 'gift'),
    ]),
]
ICONES_GRUPOS_METRICAS = {
    'Voluntários': 'volunteers',
    'Ações': 'actions',
    'Resíduos': 'residue',
    'Estoque': 'package',
    'Doações': 'gift',
}
ICONES_RELATORIOS = {
    'geral': 'reports',
    'indicadores': 'beach',
    'acoes': 'actions',
    'voluntarios': 'volunteers',
    'presenca': 'audit',
    'residuos': 'residue',
    'estoque': 'package',
    'doacoes': 'gift',
}
PERIODOS = [('MES', 'Mês atual'), ('TRIMESTRE', 'Trimestre atual'), ('ANO', 'Ano atual')]


class RelatorioFiltroForm(forms.Form):
    relatorio = forms.ChoiceField(label='Relatório', choices=RELATORIOS)
    data_inicio = forms.DateField(
        label='Data inicial',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    data_fim = forms.DateField(
        label='Data final',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    periodo = forms.ChoiceField(label='Período do painel', choices=PERIODOS, required=False)
    praia = forms.ModelChoiceField(
        label='Praia / local',
        queryset=Praia.objects.none(),
        required=False,
        empty_label='Todas as praias',
    )
    acao = forms.ChoiceField(
        label='Ação',
        choices=[('', 'Todas as ações')],
        required=False,
    )
    tipo_acao = forms.ChoiceField(
        label='Tipo de ação',
        choices=[('', 'Todos os tipos')] + list(Acao.TIPO_CHOICES),
        required=False,
    )
    tipo_residuo = forms.ChoiceField(
        label='Tipo de resíduo',
        choices=[('', 'Todos os tipos')] + list(ResiduoColetado.TIPO_CHOICES),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoje = timezone.localdate()
        if not self.is_bound:
            self.initial.setdefault('relatorio', 'geral')
            self.initial.setdefault('data_inicio', hoje.replace(day=1))
            self.initial.setdefault('data_fim', hoje)
            self.initial.setdefault('periodo', 'MES')
        self.fields['praia'].queryset = Praia.objects.order_by('nome')
        acoes_choices = [('', 'Todas as ações')]
        try:
            from acao.mongo_services import get_acoes_collection
            col = get_acoes_collection()
            if col is not None:
                for doc in col.find({}, {'id_sql': 1, 'tipo_display': 1, 'tipo': 1, 'data': 1, 'praia': 1}).sort('data', -1):
                    praia_nome = doc.get('praia', {}).get('nome', '') if isinstance(doc.get('praia'), dict) else ''
                    label = f"{doc.get('tipo_display') or doc.get('tipo', 'Ação')} ({doc.get('data', '')}) - {praia_nome}".strip(' - ')
                    acoes_choices.append((str(doc.get('id_sql')), label))
        except Exception as erro:
            logger.warning('Não foi possível carregar ações do MongoDB para os filtros: %s', erro)
        self.fields['acao'].choices = acoes_choices
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        dados = super().clean()
        inicio = dados.get('data_inicio')
        fim = dados.get('data_fim')
        if inicio and fim and inicio > fim:
            self.add_error('data_fim', 'A data final deve ser igual ou posterior à data inicial.')
        return dados


def _periodo_efetivo(dados):
    hoje = timezone.localdate()
    if dados['relatorio'] != 'indicadores':
        return dados.get('data_inicio') or date(1900, 1, 1), dados.get('data_fim') or hoje

    periodo = dados.get('periodo') or 'MES'
    if periodo == 'ANO':
        return hoje.replace(month=1, day=1), hoje
    if periodo == 'TRIMESTRE':
        mes_inicial = ((hoje.month - 1) // 3) * 3 + 1
        return hoje.replace(month=mes_inicial, day=1), hoje
    return hoje.replace(day=1), hoje


def _periodo_padrao_relatorio(tipo, hoje):
    inicio_mes = hoje.replace(day=1)
    inicio_mes_anterior = (inicio_mes - timedelta(days=1)).replace(day=1)
    if tipo == 'acoes':
        return inicio_mes_anterior, hoje.replace(day=monthrange(hoje.year, hoje.month)[1])
    if tipo in ('presenca', 'voluntarios'):
        return hoje - timedelta(days=90), hoje
    if tipo in ('residuos', 'estoque', 'doacoes'):
        return inicio_mes_anterior, hoje
    return inicio_mes, hoje


def _presenca_filter():
    return Q(compareceu=True) | Q(status=AcaoParticipante.STATUS_PRESENTE)


def _residuos_no_periodo(inicio, fim, tipo='', praia_id=None, acao_id=None):
    """Consolida registros de resíduos de duas fontes:
    1. ItemColetaResiduo (tabela SQLite, ligado a ColetaResiduo que pode vir de bag ou ação)
    2. ResiduoColetado (tabela SQLite, ligado diretamente a uma ação)
    
    Quando filtra por praia, busca os IDs de ações/bags da praia no MongoDB para
    usar como filtro no SQLite (join cross-database via lista de IDs).
    Retorna lista de linhas já ordenadas por data para exibição/exportação.
    """
    linhas = []
    itens_registrados = ItemColetaResiduo.objects.filter(
        coleta__data_coleta__date__range=(inicio, fim),
    ).select_related('coleta').order_by('coleta__data_coleta', 'id_item')
    if tipo:
        itens_registrados = itens_registrados.filter(tipo=tipo)
    if praia_id:
        acoes_p = []
        bags_p = []
        try:
            from acao.mongo_services import get_acoes_collection
            col = get_acoes_collection()
            if col is not None:
                acoes_p = [d['id_sql'] for d in col.find({'praia.id': int(praia_id)}, {'id_sql': 1})]
        except Exception as erro:
            logger.warning(
                'Não foi possível consultar ações da praia %s no MongoDB ao consolidar resíduos: %s',
                praia_id,
                erro,
            )
            acoes_p = []
        try:
            from condominio.mongo_services import get_condominios_collection
            col_c = get_condominios_collection()
            if col_c is not None:
                for doc in col_c.find({'praia.id': int(praia_id)}, {'bags': 1}):
                    for b in doc.get('bags', []):
                        bid = b.get('id') or b.get('id_bag')
                        if bid:
                            bags_p.append(bid)
        except Exception as erro:
            logger.warning(
                'Não foi possível consultar bags da praia %s no MongoDB ao consolidar resíduos: %s',
                praia_id,
                erro,
            )
            bags_p = []
        itens_registrados = itens_registrados.filter(
            Q(coleta__acao_id__in=acoes_p) | Q(coleta__bag_id__in=bags_p)
        )
    if acao_id:
        itens_registrados = itens_registrados.filter(coleta__acao_id=acao_id)

    for item in itens_registrados:
        coleta = item.coleta
        acao = coleta.acao
        bag = coleta.bag
        linhas.append([
            timezone.localtime(coleta.data_coleta).strftime('%d/%m/%Y'),
            'Ação' if coleta.origem == 'ACAO' else 'Bag',
            str(acao) if acao else '-',
            bag.codigo if bag else '-',
            (acao.praia.nome if acao else bag.condominio.praia.nome if bag and bag.condominio.praia else '-'),
            item.get_tipo_display() or 'Não informado',
            item.get_categoria_display() or 'Não informada',
            str(item.quantidade or 0),
            item.get_unidade_display() or 'Não informada',
        ])

    residuos_acao = ResiduoColetado.objects.filter(
        dt_registro__date__range=(inicio, fim),
    ).order_by('dt_registro', 'id_residuo')
    if tipo:
        residuos_acao = residuos_acao.filter(tipo=tipo)
    if praia_id:
        if acoes_p:
            residuos_acao = residuos_acao.filter(acao_id__in=acoes_p)
        else:
            residuos_acao = residuos_acao.none()
    if acao_id:
        residuos_acao = residuos_acao.filter(acao_id=acao_id)
    for residuo in residuos_acao:
        praia_nome = '-'
        if residuo.acao and hasattr(residuo.acao, 'praia') and residuo.acao.praia:
            praia_nome = getattr(residuo.acao.praia, 'nome', '-')
        linhas.append([
            timezone.localtime(residuo.dt_registro).strftime('%d/%m/%Y'),
            'Ação',
            str(residuo.acao),
            '-',
            praia_nome,
            residuo.get_tipo_display() or 'Não informado',
            residuo.get_categoria_display() or 'Não informada',
            str(residuo.quantidade or 0),
            residuo.get_unidade_display() or 'Não informada',
        ])
    return sorted(linhas, key=lambda linha: datetime.strptime(linha[0], '%d/%m/%Y'))


def _resumo_quantidades_por_unidade(linhas):
    totais = defaultdict(Decimal)
    for linha in linhas:
        quantidade = Decimal(linha[7] or 0)
        totais[linha[8]] += quantidade
    return ', '.join(f'{quantidade:g} {unidade}' for unidade, quantidade in sorted(totais.items())) or '0'


def _resumo_saldos(materiais):
    totais = defaultdict(int)
    for material in materiais:
        totais[material.get_unidade_display()] += material.saldo
    return ', '.join(f'{quantidade} {unidade}' for unidade, quantidade in sorted(totais.items())) or '0'


def _grafico(
    identificador,
    tipo,
    titulo,
    labels,
    datasets,
    cabecalhos,
    linhas,
    tem_dados=None,
):
    if tem_dados is None:
        tem_dados = bool(labels and any(dados for dados in datasets))
    return {
        'id': identificador,
        'tipo': tipo,
        'titulo': titulo,
        'labels': labels,
        'datasets': datasets,
        'table_headers': cabecalhos,
        'table_rows': linhas,
        'has_data': tem_dados,
    }



def _criar_relatorio(dados, inicio, fim):
    tipo = dados['relatorio']
    praia_id = dados.get('praia').pk if dados.get('praia') else None
    acao_raw = dados.get('acao')
    acao_id = int(acao_raw) if acao_raw and str(acao_raw).isdigit() else None
    tipo_acao = dados.get('tipo_acao') or ''
    tipo_residuo = dados.get('tipo_residuo') or ''
    periodo_label = f'{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}'

    relatorio = {
        'title': dict(RELATORIOS)[tipo],
        'period': periodo_label,
        'metrics': [],
        'sections': [],
        'charts': [],
        'metric_groups': [],
        'attendance_action': (
            Acao.objects.filter(pk=acao_id).select_related('praia').first()
            if tipo == 'presenca' and acao_id
            else None
        ),
    }

    if tipo == 'geral':
        status_acoes_dict = defaultdict(int)
        total_acoes = 0
        acoes_concluidas = 0
        acoes_p = []
        bags_p = []
        try:
            from acao.mongo_services import get_acoes_collection
            col = get_acoes_collection()
            if col is not None:
                q_acao = {'data': {'$gte': str(inicio), '$lte': str(fim)}}
                if praia_id:
                    q_acao['praia.id'] = int(praia_id)
                for doc in col.find(q_acao, {'status': 1, 'id_sql': 1}):
                    st = doc.get('status', 'PLANEJADA')
                    status_acoes_dict[st] += 1
                    total_acoes += 1
                    if st == 'CONCLUIDA':
                        acoes_concluidas += 1
                    if doc.get('id_sql') is not None:
                        acoes_p.append(doc['id_sql'])
        except Exception as erro:
            logger.warning(
                'Não foi possível carregar ações do MongoDB para o relatório geral: %s',
                erro,
            )

        try:
            from condominio.mongo_services import get_condominios_collection
            col_c = get_condominios_collection()
            if col_c is not None:
                q_cond = {'praia.id': int(praia_id)} if praia_id else {}
                for doc in col_c.find(q_cond, {'bags': 1}):
                    for b in doc.get('bags', []):
                        bid = b.get('id') or b.get('id_bag')
                        if bid:
                            bags_p.append(bid)
        except Exception as erro:
            logger.warning(
                'Não foi possível carregar bags do MongoDB para o relatório geral: %s',
                erro,
            )

        linhas_status_acoes = [
            [dict(Acao.STATUS_CHOICES).get(item[0], item[0]), item[1]]
            for item in sorted(status_acoes_dict.items())
        ]

        doacoes = Doacao.objects.filter(
            data_recebimento__range=(inicio, fim),
            status=Doacao.CONFIRMADA,
        )
        linhas_residuos = _residuos_no_periodo(inicio, fim, praia_id=praia_id)
        materiais = list(Material.objects.com_saldo().order_by('nome'))
        if praia_id:
            doacoes = doacoes.filter(Q(praia_id=praia_id) | Q(acao_id__in=acoes_p))
            linhas_residuos = [linha for linha in linhas_residuos if linha[4] == dados['praia'].nome]

        linhas_residuos_mes = []
        por_mes_unidade = defaultdict(Decimal)
        for linha in linhas_residuos:
            mes = datetime.strptime(linha[0], '%d/%m/%Y').strftime('%Y-%m')
            por_mes_unidade[(mes, linha[8])] += Decimal(linha[7] or 0)
        linhas_residuos_mes = [
            [f'{mes[5:7]}/{mes[:4]}', unidade, f'{quantidade:g}']
            for (mes, unidade), quantidade in sorted(por_mes_unidade.items())
        ]
        financeiro_por_doacao = {
            item['doacao_id']: item['valor']
            for item in DoacaoFinanceira.objects.filter(
                doacao__in=doacoes,
            ).values('doacao_id', 'valor')
        }
        total_financeiro = sum(financeiro_por_doacao.values(), Decimal('0'))
        itens_doacao = list(
            ItemDoacaoMaterial.objects.filter(doacao__in=doacoes).select_related('doacao')
        )
        linhas_doacoes = [
            ['Financeiras', doacoes.filter(tipo=Doacao.FINANCEIRA).count(), f'R$ {total_financeiro:.2f}'],
            ['Materiais', doacoes.filter(tipo=Doacao.MATERIAL).count(), len(itens_doacao)],
        ]

        q_bags = {'origem': 'BAG', 'data_coleta__date__range': (inicio, fim)}
        if praia_id:
            q_bags['bag_id__in'] = bags_p
        presencas = AcaoParticipante.objects.filter(
            acao__data__range=(inicio, fim),
        ).filter(_presenca_filter())
        if praia_id:
            presencas = presencas.filter(acao__praia_id=praia_id)

        relatorio['metrics'] = [
            ('Voluntários cadastrados', Voluntario.objects.count()),
            ('Voluntários ativos', Voluntario.objects.filter(status='ATIVO').count()),
            ('Ações no período', total_acoes),
            ('Ações concluídas', acoes_concluidas),
            ('Voluntários presentes', presencas.values('voluntario_id').distinct().count()),
            ('Resíduos coletados', _resumo_quantidades_por_unidade(linhas_residuos)),
            ('Bags coletadas', ColetaResiduo.objects.filter(**q_bags).count()),
            ('Itens com estoque baixo', sum(material.baixo_estoque for material in materiais)),
            ('Saldo atual em estoque', _resumo_saldos(materiais)),
            ('Doações confirmadas', doacoes.count()),
            ('Total financeiro doado', f'R$ {total_financeiro:.2f}'),
        ]
        relatorio['sections'] = [
            {
                'title': 'Ações por situação',
                'headers': ['Situação', 'Quantidade'],
                'rows': linhas_status_acoes,
            },
            {
                'title': 'Resíduos coletados por mês e unidade',
                'headers': ['Mês/ano', 'Unidade', 'Quantidade'],
                'rows': linhas_residuos_mes,
            },
            {
                'title': 'Resumo de doações confirmadas',
                'headers': ['Tipo', 'Quantidade de doações', 'Total'],
                'rows': linhas_doacoes,
            },
            {
                'title': 'Estoque disponível',
                'headers': ['Material', 'Código', 'Saldo', 'Unidade', 'Estoque mínimo', 'Situação'],
                'rows': [[
                    material.nome,
                    material.codigo,
                    material.saldo,
                    material.get_unidade_display(),
                    material.estoque_minimo,
                    'Baixo' if material.baixo_estoque else 'Normal',
                ] for material in materiais],
            },
        ]
        metricas_por_assunto = {
            'Voluntários': {'Voluntários cadastrados', 'Voluntários ativos', 'Voluntários presentes'},
            'Ações': {'Ações no período', 'Ações concluídas', 'Bags coletadas'},
            'Resíduos': {'Resíduos coletados'},
            'Estoque': {'Itens com estoque baixo', 'Saldo atual em estoque'},
            'Doações': {'Doações confirmadas', 'Total financeiro doado'},
        }
        relatorio['metric_groups'] = [
            {
                'title': assunto,
                'icon': ICONES_GRUPOS_METRICAS[assunto],
                'metrics': [
                    item for item in relatorio['metrics']
                    if item[0] in rotulos
                ],
            }
            for assunto, rotulos in metricas_por_assunto.items()
        ]
        relatorio['metric_groups'] = [
            grupo for grupo in relatorio['metric_groups'] if grupo['metrics']
        ]

        status_labels = [linha[0] for linha in linhas_status_acoes]
        status_values = [linha[1] for linha in linhas_status_acoes]
        relatorio['charts'].append(_grafico(
            'geral-acoes-status',
            'doughnut',
            'Ações por situação',
            status_labels,
            [{'label': 'Ações', 'data': status_values}],
            ['Situação', 'Quantidade'],
            [[label, value] for label, value in zip(status_labels, status_values)],
            tem_dados=total_acoes > 0,
        ))

        residuos_por_unidade = defaultdict(dict)
        meses_residuos = sorted(
            {linha[0] for linha in linhas_residuos_mes},
            key=lambda valor: datetime.strptime(valor, '%m/%Y'),
        )
        for mes_label, unidade, quantidade in linhas_residuos_mes:
            residuos_por_unidade[unidade][mes_label] = float(Decimal(quantidade))
        for indice, (unidade, quantidades) in enumerate(sorted(residuos_por_unidade.items())):
            valores = [quantidades.get(mes, 0) for mes in meses_residuos]
            relatorio['charts'].append(_grafico(
                f'geral-residuos-{indice}',
                'bar',
                f'Resíduos coletados por mês ({unidade})',
                meses_residuos,
                [{'label': unidade, 'data': valores}],
                ['Mês/ano', unidade],
                [[mes, valor] for mes, valor in zip(meses_residuos, valores)],
                tem_dados=any(valores),
            ))
        if not residuos_por_unidade:
            relatorio['charts'].append(_grafico(
                'geral-residuos-vazio',
                'bar',
                'Resíduos coletados por mês',
                [],
                [],
                ['Mês/ano', 'Quantidade'],
                [],
                tem_dados=False,
            ))

    elif tipo == 'acoes':
        acoes = Acao.objects.filter(
            data__range=(inicio, fim),
        ).exclude(
            status=Acao.STATUS_CANCELADA,
        ).select_related('praia').order_by('-data', 'id_acao')
        if acao_id:
            acoes = acoes.filter(pk=acao_id)
        if tipo_acao:
            acoes = acoes.filter(tipo=tipo_acao)
        if praia_id:
            acoes = acoes.filter(praia_id=praia_id)

        linhas = []
        total_participantes = 0
        total_material = 0
        acoes_por_praia = defaultdict(int)
        for acao in acoes:
            acoes_por_praia[acao.praia.nome] += 1
            participantes = list(
                acao.participantes.filter(_presenca_filter()).select_related('voluntario')
                .order_by('voluntario__nome')
            )
            total_participantes += len(participantes)
            nomes = '; '.join(
                f'{p.voluntario.nome} ({p.voluntario.telefone})' for p in participantes
            ) or '-'
            movimentos = list(
                acao.movimentacoes_estoque.filter(tipo='SAIDA').select_related('material')
            )
            materiais = '; '.join(
                f'{mov.material.nome}: {mov.quantidade} {mov.material.get_unidade_display()}'
                for mov in movimentos
            ) or '-'
            total_material += len(movimentos)
            residuos = _residuos_no_periodo(inicio, fim, acao_id=acao.pk)
            linhas.append([
                acao.data.strftime('%d/%m/%Y'),
                acao.get_tipo_display(),
                acao.praia.nome,
                acao.local or '-',
                acao.get_status_display(),
                nomes,
                materiais,
                _resumo_quantidades_por_unidade(residuos),
            ])
        relatorio['metrics'] = [
            ('Ações no período', len(linhas)),
            ('Participações', total_participantes),
            ('Saídas de materiais vinculadas', total_material),
        ]
        relatorio['sections'] = [{
            'title': 'Ações e resultados',
            'headers': ['Data', 'Tipo', 'Praia', 'Local', 'Status', 'Participantes e telefones', 'Materiais utilizados', 'Resíduos coletados'],
            'rows': linhas,
        }]
        labels_praias = sorted(acoes_por_praia)
        valores_praias = [acoes_por_praia[praia] for praia in labels_praias]
        relatorio['charts'].append(_grafico(
            'acoes-por-praia',
            'bar',
            'Ações por praia',
            labels_praias,
            [{'label': 'Ações', 'data': valores_praias}],
            ['Praia', 'Ações'],
            [[praia, quantidade] for praia, quantidade in zip(labels_praias, valores_praias)],
        ))

    elif tipo == 'voluntarios':
        filtro_presenca = Q(acoes_participadas__compareceu=True) | Q(
            acoes_participadas__status=AcaoParticipante.STATUS_PRESENTE
        )
        acoes_filtro = Q(
            acoes_participadas__acao__data__range=(inicio, fim),
            acoes_participadas__acao__status=Acao.STATUS_CONCLUIDA,
        ) & filtro_presenca
        if tipo_acao:
            acoes_filtro &= Q(acoes_participadas__acao__tipo=tipo_acao)
        voluntarios = list(Voluntario.objects.annotate(
            participacoes=Count(
                'acoes_participadas',
                filter=acoes_filtro,
                distinct=True,
            )
        ).order_by('-participacoes', 'nome'))
        total_cadastrados = Voluntario.objects.count()
        relatorio['metrics'] = [
            ('Voluntários cadastrados', total_cadastrados),
            ('Voluntários participantes no período', sum(v.participacoes > 0 for v in voluntarios)),
            ('Participações no período', sum(v.participacoes for v in voluntarios)),
        ]
        relatorio['sections'] = [{
            'title': 'Participação dos voluntários',
            'headers': ['Nome', 'Telefone', 'Status cadastral', 'Ações frequentadas no período'],
            'rows': [[v.nome, v.telefone, v.get_status_display(), v.participacoes] for v in voluntarios],
        }]
        mais_participativos = [v for v in voluntarios if v.participacoes > 0][:10]
        labels_voluntarios = [v.nome for v in mais_participativos]
        valores_participacoes = [v.participacoes for v in mais_participativos]
        relatorio['charts'].append(_grafico(
            'voluntarios-participacoes',
            'bar',
            'Ações frequentadas por voluntário',
            labels_voluntarios,
            [{'label': 'Ações frequentadas', 'data': valores_participacoes}],
            ['Voluntário', 'Ações frequentadas'],
            [[nome, quantidade] for nome, quantidade in zip(labels_voluntarios, valores_participacoes)],
        ))

    elif tipo == 'presenca':
        participantes = AcaoParticipante.objects.filter(
            acao__data__range=(inicio, fim),
        ).filter(_presenca_filter()).select_related(
            'acao__praia', 'voluntario'
        ).order_by('acao__data', 'acao__id_acao', 'voluntario__nome')
        if acao_id:
            participantes = participantes.filter(acao_id=acao_id)
        if tipo_acao:
            participantes = participantes.filter(acao__tipo=tipo_acao)
        if praia_id:
            participantes = participantes.filter(acao__praia_id=praia_id)
        por_acao = defaultdict(list)
        for participante in participantes:
            por_acao[participante.acao].append([
                participante.voluntario.nome,
                participante.voluntario.telefone,
                '________________________',
            ])
        relatorio['metrics'] = [
            ('Ações no período', len(por_acao)),
            ('Presenças registradas', sum(len(linhas) for linhas in por_acao.values())),
        ]
        relatorio['sections'] = [
            {
                'title': f'{acao} — {acao.data:%d/%m/%Y}',
                'headers': ['Nome completo', 'Telefone', 'Assinatura'],
                'rows': linhas,
            }
            for acao, linhas in por_acao.items()
        ] or [{
            'title': 'Lista de presença',
            'headers': ['Nome completo', 'Telefone', 'Assinatura'],
            'rows': [],
        }]

    elif tipo == 'residuos':
        linhas = _residuos_no_periodo(inicio, fim, tipo_residuo, praia_id, acao_id)
        por_mes_unidade = defaultdict(lambda: defaultdict(Decimal))
        por_tipo_unidade = defaultdict(lambda: defaultdict(Decimal))
        for linha in linhas:
            partes = linha[0].split('/')
            chave = (partes[2], partes[1])
            unidade = linha[8]
            quantidade = Decimal(linha[7] or 0)
            por_mes_unidade[unidade][chave] += quantidade
            por_tipo_unidade[unidade][linha[5]] += quantidade
        resumo_mensal = [
            [f'{mes}/{ano}', unidade, f'{quantidade:g}']
            for unidade, meses in sorted(por_mes_unidade.items())
            for (ano, mes), quantidade in sorted(meses.items())
        ]
        relatorio['metrics'] = [
            ('Registros de coleta', len(linhas)),
            ('Quantidade por unidade', _resumo_quantidades_por_unidade(linhas)),
        ]
        relatorio['sections'] = [
            {
                'title': 'Quantidade coletada por mês e unidade',
                'headers': ['Mês/ano', 'Unidade', 'Quantidade total'],
                'rows': resumo_mensal,
            },
            {
                'title': 'Ações e bags coletadas',
                'headers': ['Data', 'Origem', 'Ação', 'Bag', 'Praia', 'Tipo', 'Categoria', 'Quantidade', 'Unidade'],
                'rows': linhas,
            },
        ]
        for indice, unidade in enumerate(sorted(por_mes_unidade)):
            meses = por_mes_unidade[unidade]
            chaves_mes = sorted(meses)
            labels_mes = [f'{mes}/{ano}' for ano, mes in chaves_mes]
            valores_mes = [float(meses[chave]) for chave in chaves_mes]
            relatorio['charts'].append(_grafico(
                f'residuos-mes-{indice}',
                'bar',
                f'Quantidade coletada por mês ({unidade})',
                labels_mes,
                [{'label': unidade, 'data': valores_mes}],
                ['Mês/ano', unidade],
                [[mes, valor] for mes, valor in zip(labels_mes, valores_mes)],
            ))
            tipos = por_tipo_unidade[unidade]
            labels_tipos = sorted(tipos)
            valores_tipos = [float(tipos[tipo_nome]) for tipo_nome in labels_tipos]
            relatorio['charts'].append(_grafico(
                f'residuos-tipo-{indice}',
                'bar',
                f'Quantidade coletada por tipo ({unidade})',
                labels_tipos,
                [{'label': unidade, 'data': valores_tipos}],
                ['Tipo de resíduo', unidade],
                [[nome, valor] for nome, valor in zip(labels_tipos, valores_tipos)],
            ))
        if not por_mes_unidade:
            relatorio['charts'].extend([
                _grafico(
                    'residuos-mes-vazio',
                    'bar',
                    'Quantidade coletada por mês',
                    [],
                    [],
                    ['Mês/ano', 'Quantidade'],
                    [],
                    tem_dados=False,
                ),
                _grafico(
                    'residuos-tipo-vazio',
                    'bar',
                    'Quantidade coletada por tipo',
                    [],
                    [],
                    ['Tipo de resíduo', 'Quantidade'],
                    [],
                    tem_dados=False,
                ),
            ])

    elif tipo == 'estoque':
        materiais = list(Material.objects.com_saldo().order_by('nome'))
        linhas_saldo = [[
            material.nome,
            material.codigo,
            material.categoria,
            material.saldo,
            material.get_unidade_display(),
            material.estoque_minimo,
            'Baixo' if material.baixo_estoque else 'Normal',
        ] for material in materiais]
        movimentos = MovimentacaoEstoque.objects.filter(
            dt_cadastro__date__range=(inicio, fim),
        ).select_related('material').order_by('-dt_cadastro')
        linhas_movimentos = [[
            timezone.localtime(m.dt_cadastro).strftime('%d/%m/%Y %H:%M'),
            m.get_tipo_display(),
            m.material.nome,
            m.quantidade,
            m.material.get_unidade_display(),
            str(m.acao) if m.acao_id else '-',
            m.registrado_por_nome or '-',
            m.justificativa or '-',
        ] for m in movimentos]
        relatorio['metrics'] = [
            ('Itens cadastrados', len(materiais)),
            ('Quantidade total em estoque', _resumo_saldos(materiais)),
            ('Itens com estoque baixo', sum(m.baixo_estoque for m in materiais)),
            ('Movimentações no período', len(linhas_movimentos)),
        ]
        relatorio['sections'] = [
            {
                'title': 'Saldo atual e nível mínimo',
                'headers': ['Material', 'Código', 'Categoria', 'Saldo disponível', 'Unidade', 'Estoque mínimo', 'Situação'],
                'rows': linhas_saldo,
            },
            {
                'title': 'Histórico de entradas e saídas',
                'headers': ['Data/hora', 'Movimentação', 'Material', 'Quantidade', 'Unidade', 'Ação', 'Responsável', 'Justificativa'],
                'rows': linhas_movimentos,
            },
        ]
        materiais_com_minimo = [m for m in materiais if m.estoque_minimo > 0]
        labels_materiais = [m.nome for m in materiais_com_minimo]
        percentuais = [
            round(m.saldo / m.estoque_minimo * 100, 1)
            for m in materiais_com_minimo
        ]
        relatorio['charts'].append(_grafico(
            'estoque-percentual-minimo',
            'bar',
            'Saldo atual em relação ao estoque mínimo',
            labels_materiais,
            [
                {
                    'label': 'Saldo em relação ao mínimo (%)',
                    'data': percentuais,
                    'backgroundColor': [
                        '#f4e01e' if percentual < 100 else '#0058b9'
                        for percentual in percentuais
                    ],
                    'borderColor': '#00306b',
                    'borderWidth': 2,
                },
                {
                    'label': 'Mínimo (100%)',
                    'type': 'line',
                    'data': [100] * len(labels_materiais),
                    'borderColor': '#6b7280',
                    'borderDash': [6, 4],
                    'pointRadius': 0,
                    'borderWidth': 2,
                },
            ],
            ['Material', 'Saldo do mínimo (%)'],
            [[nome, f'{percentual:g}%'] for nome, percentual in zip(labels_materiais, percentuais)],
            tem_dados=bool(labels_materiais),
        ))

    elif tipo == 'indicadores':
        acoes = Acao.objects.filter(
            data__range=(inicio, fim),
            status=Acao.STATUS_CONCLUIDA,
        )
        presencas = AcaoParticipante.objects.filter(
            acao__data__range=(inicio, fim),
            acao__status=Acao.STATUS_CONCLUIDA,
            voluntario__status='ATIVO',
        ).filter(_presenca_filter())
        if praia_id:
            acoes = acoes.filter(praia_id=praia_id)
            presencas = presencas.filter(acao__praia_id=praia_id)
        linhas_residuos = _residuos_no_periodo(inicio, fim, praia_id=praia_id)
        materiais = list(Material.objects.com_saldo())
        praias = Praia.objects.order_by('nome')
        if praia_id:
            praias = praias.filter(pk=praia_id)
        linhas_praia = []
        for praia in praias:
            residuos_praia = [linha for linha in linhas_residuos if linha[4] == praia.nome]
            presencas_praia = presencas.filter(acao__praia=praia).values(
                'voluntario_id'
            ).distinct().count()
            linhas_praia.append([
                praia.nome,
                acoes.filter(praia=praia).count(),
                presencas_praia,
                len(residuos_praia),
                _resumo_quantidades_por_unidade(residuos_praia),
            ])
        relatorio['metrics'] = [
            ('Voluntários ativos participantes', presencas.values('voluntario_id').distinct().count()),
            ('Ações concluídas', acoes.count()),
            ('Registros de resíduos', len(linhas_residuos)),
            ('Materiais cadastrados', len(materiais)),
            ('Saldo em estoque', _resumo_saldos(materiais)),
        ]
        relatorio['sections'] = [{
            'title': 'Indicadores por praia',
            'headers': ['Praia', 'Ações concluídas', 'Voluntários ativos', 'Registros de resíduo', 'Quantidade coletada por unidade'],
            'rows': linhas_praia,
        }]
        labels_praias = [linha[0] for linha in linhas_praia]
        valores_acoes = [linha[1] for linha in linhas_praia]
        valores_voluntarios = [linha[2] for linha in linhas_praia]
        valores_residuos = [linha[3] for linha in linhas_praia]
        relatorio['charts'].append(_grafico(
            'indicadores-por-praia',
            'bar',
            'Comparativo por praia',
            labels_praias,
            [
                {'label': 'Ações concluídas', 'data': valores_acoes},
                {'label': 'Voluntários ativos', 'data': valores_voluntarios},
                {'label': 'Registros de resíduo', 'data': valores_residuos},
            ],
            ['Praia', 'Ações concluídas', 'Voluntários ativos', 'Registros de resíduo'],
            [
                [praia, acoes, voluntarios, residuos]
                for praia, acoes, voluntarios, residuos
                in zip(labels_praias, valores_acoes, valores_voluntarios, valores_residuos)
            ],
            tem_dados=any(valores_acoes + valores_voluntarios + valores_residuos),
        ))

    elif tipo == 'doacoes':
        doacoes = Doacao.objects.filter(
            data_recebimento__range=(inicio, fim),
            status=Doacao.CONFIRMADA,
        ).select_related('doador').order_by('-data_recebimento', '-id_doacao')
        itens = ItemDoacaoMaterial.objects.filter(
            doacao__in=doacoes,
        ).select_related('doacao__doador').order_by('nome')
        valores_financeiros = {
            item['doacao_id']: item['valor']
            for item in DoacaoFinanceira.objects.filter(
                doacao__in=doacoes,
            ).values('doacao_id', 'valor')
        }
        total_financeiro = sum(valores_financeiros.values(), Decimal('0'))
        itens_por_doacao = defaultdict(list)
        materiais_por_nome = defaultdict(Decimal)
        materiais_por_doador = defaultdict(lambda: defaultdict(Decimal))
        for item in itens:
            doador = item.doacao.doador.nome if item.doacao.doador_id else 'Anônimo'
            itens_por_doacao[item.doacao_id].append(
                f'{item.nome}: {item.quantidade:g} {item.unidade}'
            )
            chave_material = (item.nome, item.unidade)
            materiais_por_nome[chave_material] += item.quantidade
            materiais_por_doador[doador][item.unidade] += item.quantidade
        linhas_doacoes = []
        contribuicoes = defaultdict(lambda: {'count': 0, 'financeiro': Decimal('0'), 'materiais': defaultdict(Decimal)})
        doacoes_por_tipo = defaultdict(int)
        for doacao in doacoes:
            doador = doacao.doador.nome if doacao.doador_id else 'Anônimo'
            valor = valores_financeiros.get(doacao.pk, Decimal('0'))
            doacoes_por_tipo[doacao.get_tipo_display()] += 1
            linhas_doacoes.append([
                doacao.data_recebimento.strftime('%d/%m/%Y'),
                doacao.get_tipo_display(),
                doador,
                f'R$ {valor:.2f}' if valor else '-',
                '; '.join(itens_por_doacao[doacao.pk]) or '-',
                doacao.get_finalidade_display(),
            ])
            contribuicoes[doador]['count'] += 1
            contribuicoes[doador]['financeiro'] += valor
        for item in itens:
            doador = item.doacao.doador.nome if item.doacao.doador_id else 'Anônimo'
            contribuicoes[doador]['materiais'][item.unidade] += item.quantidade
        linhas_materiais = [
            [nome, unidade, f'{quantidade:g}']
            for (nome, unidade), quantidade in sorted(materiais_por_nome.items())
        ]
        linhas_doadores = [
            [
                nome,
                resumo['count'],
                f'R$ {resumo["financeiro"]:.2f}',
                ', '.join(f'{q:g} {unidade}' for unidade, q in sorted(resumo['materiais'].items())) or '-',
            ]
            for nome, resumo in sorted(
                contribuicoes.items(),
                key=lambda item: (-item[1]['count'], -item[1]['financeiro'], item[0]),
            )
        ]
        relatorio['metrics'] = [
            ('Doações confirmadas', doacoes.count()),
            ('Total financeiro', f'R$ {total_financeiro:.2f}'),
            ('Materiais recebidos', len(itens)),
            ('Doadores identificados', doacoes.exclude(doador__isnull=True).values('doador_id').distinct().count()),
        ]
        relatorio['sections'] = [
            {
                'title': 'Doações confirmadas',
                'headers': ['Data', 'Tipo', 'Doador', 'Valor financeiro', 'Materiais e quantidades', 'Finalidade'],
                'rows': linhas_doacoes,
            },
            {
                'title': 'Materiais recebidos',
                'headers': ['Material', 'Unidade', 'Quantidade total'],
                'rows': linhas_materiais,
            },
            {
                'title': 'Doadores que mais contribuíram',
                'headers': ['Doador', 'Doações', 'Total financeiro', 'Materiais doados'],
                'rows': linhas_doadores,
            },
        ]
        maiores_doadores = [
            (nome, resumo['financeiro'])
            for nome, resumo in sorted(
                contribuicoes.items(),
                key=lambda item: (-item[1]['financeiro'], item[0]),
            )
            if resumo['financeiro'] > 0
        ][:10]
        labels_doadores = [nome for nome, _ in maiores_doadores]
        valores_doadores = [float(valor) for _, valor in maiores_doadores]
        relatorio['charts'].extend([
            _grafico(
                'doacoes-financeiro-por-doador',
                'bar',
                'Total financeiro por doador',
                labels_doadores,
                [{'label': 'Total financeiro (R$)', 'data': valores_doadores}],
                ['Doador', 'Total financeiro (R$)'],
                [[nome, f'R$ {valor:.2f}'] for nome, valor in maiores_doadores],
            ),
            _grafico(
                'doacoes-por-tipo',
                'doughnut',
                'Doações por tipo',
                list(doacoes_por_tipo),
                [{'label': 'Doações', 'data': list(doacoes_por_tipo.values())}],
                ['Tipo', 'Quantidade'],
                [[nome, quantidade] for nome, quantidade in doacoes_por_tipo.items()],
                tem_dados=bool(doacoes_por_tipo),
            ),
        ])

    return relatorio


def _resposta_excel(relatorio, tipo, hoje):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    workbook = Workbook()
    resumo = workbook.active
    resumo.title = 'Resumo'
    resumo.append([relatorio['title']])
    resumo.append([f'Período: {relatorio["period"]}'])
    resumo.append([])
    resumo.append(['Indicador', 'Resultado'])
    for celula in resumo[4]:
        celula.font = Font(bold=True, color='FFFFFF')
        celula.fill = PatternFill('solid', fgColor='155E4B')
    for rotulo, valor in relatorio['metrics']:
        resumo.append([rotulo, str(valor)])
        resumo.cell(resumo.max_row, 2).data_type = 's'
    resumo.freeze_panes = 'A5'
    resumo.column_dimensions['A'].width = 38
    resumo.column_dimensions['B'].width = 36

    for indice, secao in enumerate(relatorio['sections'], start=1):
        nome = ''.join(char for char in secao['title'] if char not in '[]:*?/\\')[:31]
        planilha = workbook.create_sheet(nome or f'Relatório {indice}')
        planilha.append([relatorio['title']])
        planilha.append([f'Período: {relatorio["period"]}'])
        planilha.append([])
        planilha.append(secao['headers'])
        for celula in planilha[4]:
            celula.font = Font(bold=True, color='FFFFFF')
            celula.fill = PatternFill('solid', fgColor='155E4B')
        for linha in secao['rows']:
            planilha.append([
                str(valor) if valor is not None else ''
                for valor in linha
            ])
            for celula in planilha[planilha.max_row]:
                celula.data_type = 's'
        planilha.freeze_panes = 'A5'
        planilha.auto_filter.ref = f'A4:{planilha.cell(planilha.max_row, len(secao["headers"])).coordinate}'
        for coluna in planilha.columns:
            largura = min(max(len(str(c.value or '')) for c in coluna) + 2, 48)
            planilha.column_dimensions[coluna[0].column_letter].width = max(largura, 12)
    conteudo = io.BytesIO()
    workbook.save(conteudo)
    resposta = HttpResponse(
        conteudo.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resposta['Content-Disposition'] = (
        f'attachment; filename="{tipo}_{hoje.isoformat()}.xlsx"'
    )
    return resposta


def _resposta_pdf(relatorio, tipo, hoje):
    import os
    from django.conf import settings
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.pdfgen import canvas
    from reportlab.platypus import (
        Image,
        KeepTogether,
        LongTable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    tem_capa = (tipo == 'geral')

    # Caminho do mascote oficial da ONG extraído fielmente do SVG original do projeto
    caminho_mascote = os.path.join(
        settings.BASE_DIR,
        'relatorios',
        'static',
        'relatorios',
        'img',
        'mascote-formiguinha-oficial.png',
    )
    tem_mascote = os.path.exists(caminho_mascote)

    class DocumentoInstitucionalRetratoCanvas(canvas.Canvas):
        """
        Canvas oficial institucional em formato A4 Retrato (210 x 297 mm):
        - Cálculo de numeração em duas fases ('Página X de Y').
        - Na capa (página 1 de relatório geral), omite cabeçalho e rodapé repetitivos.
        - Em todas as páginas internas de conteúdo, desenha cabeçalho corporativo compacto e rodapé com numeração.
        """
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.desenhar_moldura(num_pages)
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

        def desenhar_moldura(self, page_count):
            self.saveState()
            w, h = A4  # 210 x 297 mm

            # Na capa de relatório geral, não exibe cabeçalho/rodapé de página interna
            if tem_capa and self._pageNumber == 1:
                self.restoreState()
                return

            margem_x = 12 * mm

            # --- CABEÇALHO COMPACTO DE PÁGINA INTERNA ---
            y_linha = h - 17 * mm
            # Linha institucional Azul Profundo com detalhe Amarelo Solar
            self.setFillColor(HexColor('#00306b'))
            self.rect(margem_x, y_linha, w - (2 * margem_x), 1.6, fill=True, stroke=False)
            self.setFillColor(HexColor('#f4e01e'))
            self.rect(margem_x, y_linha - 0.8, 32 * mm, 1.2, fill=True, stroke=False)

            # Mini mascote oficial no cabeçalho interno
            if tem_mascote:
                try:
                    self.drawImage(
                        caminho_mascote,
                        margem_x,
                        h - 15.5 * mm,
                        width=7.5 * mm,
                        height=8.2 * mm,
                        mask='auto',
                        preserveAspectRatio=True,
                    )
                except Exception:
                    pass

            offset_logo = 10 * mm if tem_mascote else 0

            self.setFont('Helvetica-Bold', 8.5)
            self.setFillColor(HexColor('#00306b'))
            self.drawString(margem_x + offset_logo, h - 11.5 * mm, 'ONG FORMIGUINHAS DA PRAIA')

            self.setFont('Helvetica', 7)
            self.setFillColor(HexColor('#536574'))
            self.drawString(margem_x + offset_logo, h - 15 * mm, 'Sistema Integrado de Gestão Socioambiental')

            # Metadados à direita
            self.setFont('Helvetica-Bold', 7.5)
            self.setFillColor(HexColor('#00306b'))
            self.drawRightString(w - margem_x, h - 11.5 * mm, escape(relatorio['title']))

            self.setFont('Helvetica', 7)
            self.setFillColor(HexColor('#536574'))
            self.drawRightString(
                w - margem_x,
                h - 15 * mm,
                f'Emissão: {hoje.strftime("%d/%m/%Y")} • Período: {escape(relatorio["period"])}',
            )

            # --- RODAPÉ DISCRETO PADRONIZADO ---
            y_rodape = 11 * mm
            self.setStrokeColor(HexColor('#dbe4e7'))
            self.setLineWidth(0.5)
            self.line(margem_x, y_rodape, w - margem_x, y_rodape)

            self.setFont('Helvetica', 7)
            self.setFillColor(HexColor('#768b9a'))
            self.drawString(
                margem_x,
                y_rodape - 4 * mm,
                'ONG Formiguinhas da Praia • Documento oficial emitido eletronicamente',
            )

            pag_texto = f'Página {self._pageNumber} de {page_count}'
            self.drawRightString(w - margem_x, y_rodape - 4 * mm, pag_texto)

            self.restoreState()

    def calcular_larguras_retrato(headers, largura_total):
        """Distribui com precisão as colunas no espaço A4 Retrato (186 mm útil)."""
        pesos = []
        for h in headers:
            h_lower = str(h).lower()
            if any(k in h_lower for k in ['id', 'código', 'cod', '#', 'ano']):
                pesos.append(0.5)
            elif any(k in h_lower for k in ['data', 'mês', 'mes', 'unidade', 'frequência', 'presença']):
                pesos.append(0.8)
            elif any(k in h_lower for k in ['status', 'situação', 'tipo', 'categoria', 'papel']):
                pesos.append(0.95)
            elif any(k in h_lower for k in ['resíduo', 'quantidade', 'total', 'valor', 'saldo', 'kg', 'peso', 'mínimo', 'minimo', 'pontos']):
                pesos.append(0.85)
            elif any(k in h_lower for k in ['praia', 'local', 'equipe', 'responsável', 'responsavel']):
                pesos.append(1.25)
            elif any(k in h_lower for k in ['nome', 'voluntário', 'doador', 'material', 'descrição', 'descricao', 'observação', 'motivo']):
                pesos.append(1.6)
            else:
                pesos.append(1.0)

        soma = sum(pesos) if pesos else 1.0
        return [(p / soma) * largura_total for p in pesos]

    buffer = io.BytesIO()

    # Formato A4 Retrato (210 x 297 mm) com margens laterais de 12 mm
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=22 * mm,
        bottomMargin=16 * mm,
    )

    largura_util = documento.width  # 186 mm

    estilos = getSampleStyleSheet()

    titulo_pagina_style = ParagraphStyle(
        'DocTituloPagina',
        parent=estilos['Title'],
        fontName='Helvetica-Bold',
        fontSize=13.5,
        leading=16,
        alignment=TA_LEFT,
        textColor=HexColor('#00306b'),
        spaceAfter=2,
    )

    subtitulo_pagina_style = ParagraphStyle(
        'DocSubtituloPagina',
        parent=estilos['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        alignment=TA_LEFT,
        textColor=HexColor('#536574'),
    )

    secao_titulo_style = ParagraphStyle(
        'DocSecao',
        parent=estilos['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=HexColor('#00306b'),
        spaceBefore=7,
        spaceAfter=4,
    )

    tabela_cabecalho_style = ParagraphStyle(
        'DocTh',
        parent=estilos['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.8,
        leading=8.5,
        textColor=colors.white,
    )

    tabela_celula_style = ParagraphStyle(
        'DocTd',
        parent=estilos['Normal'],
        fontName='Helvetica',
        fontSize=6.8,
        leading=8.5,
        textColor=HexColor('#1f2937'),
    )

    kpi_rotulo_style = ParagraphStyle(
        'DocKpiRotulo',
        parent=estilos['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.8,
        leading=8.5,
        textColor=HexColor('#536574'),
        alignment=TA_CENTER,
    )

    kpi_valor_style = ParagraphStyle(
        'DocKpiValor',
        parent=estilos['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=13,
        textColor=HexColor('#00306b'),
        alignment=TA_CENTER,
    )

    elementos = []

    # =========================================================
    # 1. CAPA INSTITUCIONAL ELEGANTE (A4 RETRATO)
    # =========================================================
    if tem_capa:
        elementos.append(Spacer(1, 8 * mm))

        # Tarja superior decorativa
        faixa_capa = Table([['']], colWidths=[largura_util], rowHeights=[4 * mm])
        faixa_capa.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#00306b')),
            ('LINEBELOW', (0, 0), (-1, -1), 2, HexColor('#f4e01e')),
        ]))
        elementos.append(faixa_capa)
        elementos.append(Spacer(1, 14 * mm))

        # Apresentação do Mascote Oficial e Cabeçalho da Entidade
        col_mascote = [Image(caminho_mascote, width=28 * mm, height=30.6 * mm)] if tem_mascote else ['']
        col_cabecalho_capa = [
            Paragraph('ONG FORMIGUINHAS DA PRAIA', ParagraphStyle('CapaMarca', fontName='Helvetica-Bold', fontSize=17, leading=20, textColor=HexColor('#00306b'))),
            Paragraph('Associação Comunitária e Socioambiental de Conservação Litorânea', ParagraphStyle('CapaSub', fontName='Helvetica', fontSize=9, leading=12, textColor=HexColor('#536574'))),
            Spacer(1, 2.5 * mm),
            Paragraph(escape(relatorio['title']).upper(), ParagraphStyle('CapaTituloDoc', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=HexColor('#00306b'))),
            Paragraph(f'Demonstrativo Consolidado de Gestão • Período: {escape(relatorio["period"])}', ParagraphStyle('CapaDescDoc', fontName='Helvetica', fontSize=9.5, leading=13, textColor=HexColor('#0058b9'))),
        ]

        tabela_capa_marca = Table(
            [[col_mascote, col_cabecalho_capa]],
            colWidths=[33 * mm, largura_util - 33 * mm] if tem_mascote else [0, largura_util],
        )
        tabela_capa_marca.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elementos.append(tabela_capa_marca)
        elementos.append(Spacer(1, 14 * mm))

        # Painel Institucional e Cadastral
        estilo_label_cad = ParagraphStyle('CadLabel', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=HexColor('#00306b'))
        estilo_val_cad = ParagraphStyle('CadVal', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=HexColor('#1f2937'))

        col_w_label = 32 * mm
        col_w_val = (largura_util / 2) - col_w_label

        dados_cadastro = [
            [
                Paragraph('Razão Social / Entidade:', estilo_label_cad),
                Paragraph('ONG Formiguinhas da Praia', estilo_val_cad),
                Paragraph('Data de Emissão:', estilo_label_cad),
                Paragraph(hoje.strftime('%d/%m/%Y'), estilo_val_cad),
            ],
            [
                Paragraph('CNPJ:', estilo_label_cad),
                Paragraph('[CNPJ A CONFIRMAR]', estilo_val_cad),
                Paragraph('Período de Referência:', estilo_label_cad),
                Paragraph(escape(relatorio['period']), estilo_val_cad),
            ],
            [
                Paragraph('Endereço Institucional:', estilo_label_cad),
                Paragraph('[ENDEREÇO A CONFIRMAR] - Litoral Paulista, SP', estilo_val_cad),
                Paragraph('Finalidade do Relatório:', estilo_label_cad),
                Paragraph('Prestação de Contas e Acompanhamento Socioambiental', estilo_val_cad),
            ],
            [
                Paragraph('Contatos Oficiais:', estilo_label_cad),
                Paragraph('(13) 99728-4132  •  contato@formiguinhasdapraia.org.br', estilo_val_cad),
                Paragraph('Portal Institucional:', estilo_label_cad),
                Paragraph('www.formiguinhasdapraia.org.br', estilo_val_cad),
            ],
        ]

        tabela_cadastral = Table(
            dados_cadastro,
            colWidths=[col_w_label, col_w_val, col_w_label, col_w_val],
        )
        tabela_cadastral.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f9f6ee')),
            ('BOX', (0, 0), (-1, -1), 0.8, HexColor('#dbe4e7')),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, HexColor('#eef2f5')),
            ('LINELEFT', (0, 0), (0, -1), 3, HexColor('#00306b')),
            ('TOPPADDING', (0, 0), (-1, -1), 3 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3 * mm),
            ('LEFTPADDING', (0, 0), (-1, -1), 2.5 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2.5 * mm),
        ]))
        elementos.append(tabela_cadastral)
        elementos.append(Spacer(1, 14 * mm))

        # Nota Institucional da Capa
        nota_capa = Paragraph(
            '<i>Este documento oficial consolida informações operacionais, socioambientais e administrativas '
            'apuradas no período referenciado, com finalidade de registro histórico, prestação de contas à diretoria, '
            'conselhos comunitários, órgãos ambientais e parceiros institucionais.</i>',
            ParagraphStyle('NotaCapa', fontName='Helvetica', fontSize=7.8, leading=11.5, textColor=HexColor('#768b9a'), alignment=TA_CENTER),
        )
        elementos.append(nota_capa)
        elementos.append(PageBreak())

    # =========================================================
    # 2. CABEÇALHO DO CONTEÚDO (Páginas internas)
    # =========================================================
    elementos.append(Paragraph(escape(relatorio['title']), titulo_pagina_style))
    elementos.append(
        Paragraph(
            f'<b>Período apurado:</b> {escape(relatorio["period"])} &nbsp;&nbsp;•&nbsp;&nbsp; '
            f'<b>Emissão:</b> {hoje.strftime("%d/%m/%Y")} &nbsp;&nbsp;•&nbsp;&nbsp; '
            f'<b>Entidade:</b> ONG Formiguinhas da Praia ([CNPJ A CONFIRMAR])',
            subtitulo_pagina_style,
        )
    )
    elementos.append(Spacer(1, 4))

    # Caso especial para ação de presença
    if relatorio.get('attendance_action'):
        acao_obj = relatorio['attendance_action']
        elementos.append(
            Paragraph(
                f'<b>Ação Selecionada:</b> {escape(str(acao_obj))} &nbsp;&nbsp;|&nbsp;&nbsp; '
                f'<b>Data da Realização:</b> {acao_obj.data.strftime("%d/%m/%Y") if acao_obj.data else "-"}',
                secao_titulo_style,
            )
        )
        elementos.append(Spacer(1, 3))

    # =========================================================
    # 3. INDICADORES DO PERÍODO (Painel de KPIs em cards A4)
    # =========================================================
    if relatorio.get('metrics'):
        elementos.append(Paragraph('Indicadores Sintéticos do Período', secao_titulo_style))

        metricas = relatorio['metrics']
        # No formato Retrato, 3 ou 4 colunas para não espremer os valores
        qtd_colunas = 4 if len(metricas) >= 4 else len(metricas)
        linhas_kpis = []
        linha_atual = []

        for rotulo, valor in metricas:
            card_conteudo = [
                [Paragraph(escape(str(rotulo)).upper(), kpi_rotulo_style)],
                [Paragraph(escape(str(valor)), kpi_valor_style)],
            ]
            mini_card = Table(card_conteudo, colWidths=['100%'])
            mini_card.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f9f6ee')),
                ('BOX', (0, 0), (-1, -1), 0.7, HexColor('#dbe4e7')),
                ('LINEBELOW', (0, 0), (-1, 0), 1.2, HexColor('#f4e01e')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, 0), 4),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 1.5),
                ('TOPPADDING', (0, 1), (-1, 1), 1.5),
                ('BOTTOMPADDING', (0, 1), (-1, 1), 4),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            linha_atual.append(mini_card)

            if len(linha_atual) == qtd_colunas:
                linhas_kpis.append(linha_atual)
                linha_atual = []

        if linha_atual:
            while len(linha_atual) < qtd_colunas:
                linha_atual.append('')
            linhas_kpis.append(linha_atual)

        largura_col_kpi = largura_util / max(qtd_colunas, 1)
        kpi_table = Table(
            linhas_kpis,
            colWidths=[largura_col_kpi] * qtd_colunas,
        )
        kpi_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elementos.extend([kpi_table, Spacer(1, 7)])

    # =========================================================
    # 4. TABELAS ANALÍTICAS (A4 RETRATO COM REPETIÇÃO DE CABEÇALHO)
    # =========================================================
    for indice, secao in enumerate(relatorio.get('sections', [])):
        elementos.append(Paragraph(escape(secao['title']), secao_titulo_style))

        headers = secao.get('headers', [])
        rows = secao.get('rows') or []

        cabecalho_formatado = [Paragraph(escape(str(item)), tabela_cabecalho_style) for item in headers]
        dados_tabela = [cabecalho_formatado]

        if not rows:
            vazio_texto = [Paragraph('<i>Nenhum registro encontrado para os filtros selecionados.</i>', tabela_celula_style)]
            vazio_texto.extend([''] * (len(headers) - 1))
            dados_tabela.append(vazio_texto)
        else:
            for linha in rows:
                dados_tabela.append([
                    Paragraph(escape(str(item if item is not None else '-')), tabela_celula_style)
                    for item in linha
                ])

        col_widths = calcular_larguras_retrato(headers, largura_util)

        tabela_secao = LongTable(
            dados_tabela,
            colWidths=col_widths,
            repeatRows=1,
        )
        tabela_secao.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#00306b')),
            ('LINEBELOW', (0, 0), (-1, 0), 1.8, HexColor('#f4e01e')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8fafc')]),
            ('GRID', (0, 0), (-1, -1), 0.3, HexColor('#e5e7eb')),
            ('BOX', (0, 0), (-1, -1), 0.6, HexColor('#d1d5db')),
            ('TOPPADDING', (0, 0), (-1, 0), 3.5),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 3.5),
            ('TOPPADDING', (0, 1), (-1, -1), 2.8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 2.8),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))

        elementos.extend([tabela_secao, Spacer(1, 8)])

        # Quebra controlada quando houver seções longas consecutivas
        if indice < len(relatorio['sections']) - 1 and len(rows) > 35:
            elementos.append(PageBreak())

    documento.build(elementos, canvasmaker=DocumentoInstitucionalRetratoCanvas)
    resposta = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    resposta['Content-Disposition'] = f'attachment; filename="{tipo}_{hoje.isoformat()}.pdf"'
    return resposta

def _resposta_csv(relatorio, tipo, hoje):
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = f'attachment; filename="{tipo}_{hoje.isoformat()}.csv"'
    resposta.write('\ufeff')
    escritor = csv.writer(resposta, delimiter=';')
    for secao in relatorio['sections']:
        escritor.writerow([secao['title']])
        escritor.writerow(secao['headers'])
        for linha in secao['rows']:
            seguro = [
                "'" + str(valor) if str(valor).startswith(('=', '+', '-', '@')) else valor
                for valor in linha
            ]
            escritor.writerow(seguro)
        escritor.writerow([])
    return resposta


def relatorios_view(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        messages.error(request, 'Acesso restrito: faça login para acessar os relatórios.')
        return redirect('login')
    try:
        usuario = Usuario.objects.select_related('id_voluntario').get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    parametros = request.GET.copy()
    hoje = timezone.localdate()
    parametros.setdefault('relatorio', 'geral')
    parametros.setdefault('periodo', 'MES')
    inicio_padrao, fim_padrao = _periodo_padrao_relatorio(parametros['relatorio'], hoje)
    parametros.setdefault('data_inicio', inicio_padrao.isoformat())
    parametros.setdefault('data_fim', fim_padrao.isoformat())
    form = RelatorioFiltroForm(parametros)
    if not form.is_valid():
        return render(request, 'sistema/relatorios.html', {
            'usuario': usuario,
            'form': form,
            'report': None,
            'report_types': RELATORIOS,
            'report_groups': GRUPOS_RELATORIOS,
            'report_icon': ICONES_RELATORIOS.get(parametros.get('relatorio'), 'reports'),
        }, status=400)

    dados = form.cleaned_data
    inicio, fim = _periodo_efetivo(dados)
    report = _criar_relatorio(dados, inicio, fim)
    formato = request.GET.get('formato', '')
    tipo = dados['relatorio']
    hoje = timezone.localdate()
    if formato == 'xlsx':
        return _resposta_excel(report, tipo, hoje)
    if formato == 'pdf':
        return _resposta_pdf(report, tipo, hoje)
    if formato == 'csv' and tipo == 'doacoes':
        return _resposta_csv(report, tipo, hoje)

    return render(request, 'sistema/relatorios.html', {
        'usuario': usuario,
        'form': form,
        'report': report,
        'report_types': RELATORIOS,
        'report_groups': GRUPOS_RELATORIOS,
        'report_icon': ICONES_RELATORIOS.get(tipo, 'reports'),
        'is_dashboard': tipo == 'indicadores',
    })
