from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from django.test import TestCase
from django.urls import reverse

from acao.models import Acao, AcaoParticipante
from residuo.models import ColetaResiduo, ItemColetaResiduo, ResiduoColetado
from doacao.models import Doador, Doacao, DoacaoFinanceira
from estoque.models import Material, MovimentacaoEstoque
from praia.models import Praia
from usuario.models import Usuario, Voluntario


class RelatoriosTestCase(TestCase):
    def setUp(self):
        self.voluntario = Voluntario.objects.create(
            nome='Admin Teste',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua Teste, 1',
            telefone='13999990000',
            email='admin-relatorios@teste.org',
        )
        self.admin = Usuario.objects.create(
            id_voluntario=self.voluntario,
            tipo='ADMIN',
            senha='!',
        )
        self.entrar(self.admin)
        self.praia = Praia.objects.create(
            nome='Praia Teste',
            cidade='Santos',
            latitude=Decimal('-23.9600'),
            longitude=Decimal('-46.3300'),
        )
        self.acao = Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=date.today(),
            local='Praia Teste',
            status=Acao.STATUS_CONCLUIDA,
            praia=self.praia,
        )
        self.material = Material.objects.create(
            nome='Saco reutilizável',
            codigo='REL-001',
            categoria='Coleta',
            quantidade_inicial=10,
            estoque_minimo=2,
            unidade='UNIDADE',
        )

    def entrar(self, usuario):
        sessao = self.client.session
        sessao['usuario_id'] = usuario.id_usuario
        sessao['usuario_nome'] = usuario.id_voluntario.nome
        sessao['usuario_tipo'] = usuario.tipo
        sessao.save()


class AcessoRelatoriosTests(RelatoriosTestCase):
    def test_administrador_pode_acessar_relatorios(self):
        resposta = self.client.get(reverse('relatorios'))

        self.assertEqual(resposta.status_code, 200)

    def test_relatorios_exibem_breadcrumb_central_de_relatorios(self):
        resposta = self.client.get(reverse('relatorios'))

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            '<span aria-current="page">Central de Relatórios</span>',
        )

    def test_redireciona_usuario_sem_sessao(self):
        self.client.logout()
        sessao = self.client.session
        sessao.flush()
        sessao.save()

        resposta = self.client.get(reverse('relatorios'))

        self.assertRedirects(resposta, reverse('login'))

    def test_coordenador_nao_pode_acessar_relatorios(self):
        coordenador_voluntario = Voluntario.objects.create(
            nome='Coordenador Teste',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua Teste, 2',
            telefone='13999990001',
            email='coord-relatorios@teste.org',
        )
        coordenador = Usuario.objects.create(
            id_voluntario=coordenador_voluntario,
            tipo='COORDENADOR',
            senha='!',
        )
        self.entrar(coordenador)

        resposta = self.client.get(reverse('relatorios'))

        self.assertEqual(resposta.status_code, 403)


class RenderizacaoRelatoriosTests(RelatoriosTestCase):
    def filtros(self):
        hoje = date.today().isoformat()
        return {'data_inicio': hoje, 'data_fim': hoje}

    def test_rota_padrao_abre_relatorio_geral(self):
        resposta = self.client.get(reverse('relatorios'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, '<h2>Relatório geral</h2>')
        self.assertContains(resposta, 'name="relatorio"')
        self.assertContains(resposta, 'aria-current="page"')
        self.assertContains(resposta, '<span>Geral</span>')

    def test_renderiza_os_oito_tipos_de_relatorio(self):
        tipos = ('geral', 'indicadores', 'acoes', 'voluntarios', 'presenca', 'residuos', 'estoque', 'doacoes')
        for tipo in tipos:
            with self.subTest(tipo=tipo):
                resposta = self.client.get(
                    reverse('relatorios'),
                    {'relatorio': tipo, **self.filtros()},
                )
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, 'Central de relatórios')

    def test_datas_padrao_sao_adequadas_a_cada_relatorio(self):
        hoje = date.today()
        inicio_mes = hoje.replace(day=1)
        inicio_mes_anterior = (inicio_mes - timedelta(days=1)).replace(day=1)
        ultimo_dia_mes = hoje.replace(day=monthrange(hoje.year, hoje.month)[1])
        datas_esperadas = {
            'geral': (inicio_mes, hoje),
            'indicadores': (inicio_mes, hoje),
            'acoes': (inicio_mes_anterior, ultimo_dia_mes),
            'voluntarios': (hoje - timedelta(days=90), hoje),
            'presenca': (hoje - timedelta(days=90), hoje),
            'residuos': (inicio_mes_anterior, hoje),
            'estoque': (inicio_mes_anterior, hoje),
            'doacoes': (inicio_mes_anterior, hoje),
        }

        for tipo, (inicio_esperado, fim_esperado) in datas_esperadas.items():
            with self.subTest(tipo=tipo):
                resposta = self.client.get(reverse('relatorios'), {'relatorio': tipo})

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(
                    resposta.context['form']['data_inicio'].value(),
                    inicio_esperado.isoformat(),
                )
                self.assertEqual(
                    resposta.context['form']['data_fim'].value(),
                    fim_esperado.isoformat(),
                )

    def test_graficos_tem_estrutura_e_tipos_esperados_por_relatorio(self):
        tipos_esperados = {
            'geral': {'bar', 'doughnut'},
            'indicadores': {'bar'},
            'acoes': {'bar'},
            'voluntarios': {'bar'},
            'presenca': set(),
            'residuos': {'bar'},
            'estoque': {'bar'},
            'doacoes': {'bar', 'doughnut'},
        }
        for tipo, tipos_grafico in tipos_esperados.items():
            with self.subTest(tipo=tipo):
                resposta = self.client.get(
                    reverse('relatorios'),
                    {'relatorio': tipo, **self.filtros()},
                )

                self.assertEqual(resposta.status_code, 200)
                graficos = resposta.context['report']['charts']
                self.assertEqual({grafico['tipo'] for grafico in graficos}, tipos_grafico)
                for grafico in graficos:
                    self.assertTrue({
                        'id', 'tipo', 'titulo', 'labels', 'datasets',
                        'table_headers', 'table_rows', 'has_data',
                    }.issubset(grafico))

    def test_relatorio_geral_calcula_voluntarios_presentes(self):
        participante = Voluntario.objects.create(
            nome='Presente no geral',
            dt_nascimento=date(1995, 5, 10),
            endereco='Rua Praia, 10',
            telefone='13988887777',
            email='presente-geral@teste.org',
        )
        AcaoParticipante.objects.create(
            acao=self.acao,
            voluntario=participante,
            status=AcaoParticipante.STATUS_PRESENTE,
            compareceu=True,
        )

        resposta = self.client.get(
            reverse('relatorios'),
            {'relatorio': 'geral', **self.filtros()},
        )

        metricas = dict(resposta.context['report']['metrics'])
        self.assertEqual(metricas['Voluntários presentes'], 1)

    def test_graficos_de_residuos_separam_unidades(self):
        coleta = ColetaResiduo.objects.create(
            origem='ACAO',
            acao=self.acao,
            registrado_por=self.admin,
            registrado_por_nome='Admin Teste',
            registrado_por_tipo='ADMIN',
        )
        ItemColetaResiduo.objects.create(
            coleta=coleta,
            tipo='PLASTICO',
            categoria='RECICLAVEL',
            quantidade=Decimal('2.00'),
            unidade='KG',
            registrado_por=self.admin,
            registrado_por_nome='Admin Teste',
            registrado_por_tipo='ADMIN',
        )
        ResiduoColetado.objects.create(
            acao=self.acao,
            tipo='VIDRO',
            categoria='RECICLAVEL',
            quantidade=Decimal('3.00'),
            unidade='LITRO',
            registrado_por=self.admin,
            registrado_por_nome='Admin Teste',
            registrado_por_tipo='ADMIN',
        )

        resposta = self.client.get(
            reverse('relatorios'),
            {'relatorio': 'residuos', **self.filtros()},
        )

        graficos = resposta.context['report']['charts']
        rotulos_datasets = {
            dataset['label']
            for grafico in graficos
            for dataset in grafico['datasets']
        }
        self.assertEqual(rotulos_datasets, {'Quilograma (kg)', 'Litro (L)'})
        self.assertEqual(len(graficos), 4)

    def test_relatorio_geral_reune_indicadores_e_resumos_dos_modulos(self):
        resposta = self.client.get(
            reverse('relatorios'),
            {'relatorio': 'geral', **self.filtros()},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Relatório geral')
        self.assertContains(resposta, 'Voluntários cadastrados')
        self.assertContains(resposta, 'Ações por situação')
        self.assertContains(resposta, 'Resíduos coletados por mês e unidade')
        self.assertContains(resposta, 'Resumo de doações confirmadas')
        self.assertContains(resposta, 'Estoque disponível')

    def test_filtro_com_datas_invertidas_exibe_erro(self):
        resposta = self.client.get(reverse('relatorios'), {
            'relatorio': 'acoes',
            'data_inicio': '2026-10-20',
            'data_fim': '2026-10-01',
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertContains(resposta, 'A data final deve ser igual', status_code=400)

    def test_telas_de_acoes_residuos_e_estoque_redirecionam_ao_relatorio_correto(self):
        casos = (
            ('acoes', reverse('acoes'), 'relatorio=acoes', 'Relatório de ações'),
            ('residuos', reverse('residuos'), 'relatorio=residuos', 'Relatório de resíduos'),
            ('materiais', reverse('materiais'), 'relatorio=estoque', 'Relatório'),
        )
        for nome, url, query, rotulo in casos:
            with self.subTest(tela=nome):
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, query)
                self.assertContains(resposta, rotulo)

    def test_relatorio_de_presenca_tem_cabecalho_por_acao_e_assinatura(self):
        participante = Voluntario.objects.create(
            nome='Voluntária Presente',
            dt_nascimento=date(1995, 5, 10),
            endereco='Rua Praia, 10',
            telefone='13988887777',
            email='presenca@teste.org',
        )
        AcaoParticipante.objects.create(
            acao=self.acao,
            voluntario=participante,
            status=AcaoParticipante.STATUS_PRESENTE,
            compareceu=True,
        )

        resposta = self.client.get(
            reverse('relatorios'),
            {
                'relatorio': 'presenca',
                'acao': self.acao.pk,
                **self.filtros(),
            },
        )

        self.assertContains(resposta, 'Voluntária Presente')
        self.assertContains(resposta, 'Assinatura')
        self.assertContains(resposta, self.acao.data.strftime('%d/%m/%Y'))

    def test_relatorio_de_acoes_inclui_acoes_planejadas_no_periodo(self):
        acao_planejada = Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=date.today(),
            local='Ponto de encontro',
            status=Acao.STATUS_PLANEJADA,
            praia=self.praia,
        )

        resposta = self.client.get(
            reverse('relatorios'),
            {'relatorio': 'acoes', **self.filtros()},
        )

        self.assertEqual(resposta.status_code, 200)
        relatorio = resposta.context['report']
        self.assertEqual(relatorio['metrics'][0], ('Ações no período', 2))
        self.assertEqual(len(relatorio['sections'][0]['rows']), 2)
        self.assertIn(
            ['Praia Teste', 2],
            relatorio['charts'][0]['table_rows'],
        )
        self.assertTrue(any(
            linha[2] == 'Praia Teste'
            and linha[3] == 'Ponto de encontro'
            and linha[4] == 'Planejada'
            for linha in relatorio['sections'][0]['rows']
        ))

    def test_presenca_padrao_inclui_dados_dos_ultimos_90_dias(self):
        participante = Voluntario.objects.create(
            nome='Presença no período padrão',
            dt_nascimento=date(1995, 5, 10),
            endereco='Rua Praia, 11',
            telefone='13988887776',
            email='presenca-periodo@teste.org',
        )
        AcaoParticipante.objects.create(
            acao=self.acao,
            voluntario=participante,
            status=AcaoParticipante.STATUS_PRESENTE,
            compareceu=True,
        )

        resposta = self.client.get(reverse('relatorios'), {'relatorio': 'presenca'})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Presença no período padrão')
        self.assertEqual(resposta.context['report']['metrics'], [
            ('Ações no período', 1),
            ('Presenças registradas', 1),
        ])

    def test_relatorio_de_residuos_inclui_itens_de_coletas_e_acoes(self):
        coleta = ColetaResiduo.objects.create(
            origem='ACAO',
            acao=self.acao,
            registrado_por=self.admin,
            registrado_por_nome='Admin Teste',
            registrado_por_tipo='ADMIN',
        )
        ItemColetaResiduo.objects.create(
            coleta=coleta,
            tipo='PLASTICO',
            categoria='RECICLAVEL',
            quantidade=Decimal('4.50'),
            unidade='KG',
            registrado_por=self.admin,
            registrado_por_nome='Admin Teste',
            registrado_por_tipo='ADMIN',
        )
        ResiduoColetado.objects.create(
            acao=self.acao,
            tipo='VIDRO',
            categoria='RECICLAVEL',
            quantidade=Decimal('2.00'),
            unidade='KG',
            registrado_por=self.admin,
            registrado_por_nome='Admin Teste',
            registrado_por_tipo='ADMIN',
        )

        resposta = self.client.get(
            reverse('relatorios'),
            {'relatorio': 'residuos', **self.filtros()},
        )

        self.assertContains(resposta, 'Plástico')
        self.assertContains(resposta, 'Vidro')
        self.assertContains(resposta, '6.50 Quilograma (kg)')

    def test_exporta_excel_e_pdf_para_todos_os_relatorios(self):
        for tipo in ('geral', 'indicadores', 'acoes', 'voluntarios', 'presenca', 'residuos', 'estoque', 'doacoes'):
            for formato, content_type in (
                ('xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('pdf', 'application/pdf'),
            ):
                with self.subTest(tipo=tipo, formato=formato):
                    resposta = self.client.get(
                        reverse('relatorios'),
                        {'relatorio': tipo, 'formato': formato, **self.filtros()},
                    )
                    self.assertEqual(resposta.status_code, 200)
                    self.assertEqual(resposta['Content-Type'], content_type)
                    if formato == 'xlsx':
                        with ZipFile(BytesIO(resposta.content)) as arquivo:
                            self.assertIn('xl/workbook.xml', arquivo.namelist())
                    else:
                        self.assertTrue(resposta.content.startswith(b'%PDF'))


class MateriaisUtilizadosTests(RelatoriosTestCase):
    def test_material_e_residuo_na_acao_abrem_as_listas_filtradas(self):
        MovimentacaoEstoque.objects.create(
            material=self.material,
            acao=self.acao,
            tipo='SAIDA',
            quantidade=2,
            justificativa='Uso em teste',
            registrado_por=self.admin,
            registrado_por_nome='Admin Teste',
        )
        ResiduoColetado.objects.create(
            acao=self.acao,
            tipo='PLASTICO',
            categoria='RECICLAVEL',
            quantidade=Decimal('1.00'),
            unidade='KG',
            registrado_por=self.admin,
            registrado_por_nome='Admin Teste',
            registrado_por_tipo='ADMIN',
        )

        resposta = self.client.get(reverse('acao_detalhe', args=[self.acao.pk]))

        self.assertContains(
            resposta,
            f'href="{reverse("materiais")}?busca={self.material.codigo}"',
        )
        self.assertContains(
            resposta,
            f'href="{reverse("residuos")}?acao={self.acao.pk}&amp;tipo=PLASTICO"',
        )

    def test_detalhe_da_acao_permite_pesquisar_material(self):
        resposta = self.client.get(reverse('acao_detalhe', args=[self.acao.pk]))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Digite o nome ou código do material')
        self.assertContains(resposta, 'data-material-search')
        self.assertContains(resposta, 'material-combobox.js')

    def test_registro_na_acao_cria_saida_e_atualiza_saldo(self):
        resposta = self.client.post(
            reverse('adicionar_material_utilizado_acao', args=[self.acao.pk]),
            {'material': self.material.pk, 'quantidade': 3},
        )

        self.assertRedirects(
            resposta,
            reverse('acao_detalhe', args=[self.acao.pk]),
            fetch_redirect_response=False,
        )
        resposta_detalhe = self.client.get(resposta.url)
        self.assertContains(
            resposta_detalhe,
            'Material utilizado registrado e saldo atualizado.',
        )
        self.assertContains(resposta_detalhe, 'alert-success')
        movimento = MovimentacaoEstoque.objects.get(acao=self.acao)
        self.assertEqual(movimento.tipo, 'SAIDA')
        self.assertEqual(movimento.quantidade, 3)
        self.assertEqual(self.material.calcular_saldo(), 7)

        resposta_relatorio = self.client.get(
            reverse('relatorios'),
            {
                'relatorio': 'acoes',
                'data_inicio': date.today().isoformat(),
                'data_fim': date.today().isoformat(),
            },
        )
        self.assertContains(resposta_relatorio, 'Saco reutilizável: 3 Unidade')

    def test_saida_acima_do_saldo_nao_e_registrada(self):
        resposta = self.client.post(
            reverse('adicionar_material_utilizado_acao', args=[self.acao.pk]),
            {'material': self.material.pk, 'quantidade': 11},
            follow=True,
        )

        self.assertEqual(
            resposta.redirect_chain,
            [(reverse('acao_detalhe', args=[self.acao.pk]), 302)],
        )
        self.assertContains(
            resposta,
            'A quantidade utilizada não pode superar o saldo atual.',
        )
        self.assertContains(resposta, 'value="11"')
        self.assertFalse(MovimentacaoEstoque.objects.filter(acao=self.acao).exists())
        self.assertEqual(self.material.calcular_saldo(), 10)


class DoacoesRelatorioTests(RelatoriosTestCase):
    def test_doacoes_padrao_inclui_confirmadas_do_mes_anterior(self):
        doador = Doador.objects.create(
            tipo=Doador.PESSOA_FISICA,
            nome='Doador no período padrão',
            telefone='13999990003',
            cadastrado_por_nome='Admin Teste',
        )
        doacao = Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            doador=doador,
            data_recebimento=date.today() - timedelta(days=10),
            status=Doacao.CONFIRMADA,
            registrado_por_nome='Admin Teste',
            registrado_por_tipo='ADMIN',
        )
        DoacaoFinanceira.objects.create(
            doacao=doacao,
            valor=Decimal('15.00'),
            forma_recebimento=DoacaoFinanceira.PIX,
        )

        resposta = self.client.get(reverse('relatorios'), {'relatorio': 'doacoes'})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Doador no período padrão')
        self.assertEqual(resposta.context['report']['metrics'][0], ('Doações confirmadas', 1))

    def test_doacoes_canceladas_sao_excluidas_e_csv_e_exportado(self):
        doador = Doador.objects.create(
            tipo=Doador.PESSOA_FISICA,
            nome='Doador Teste',
            telefone='13999990002',
            cadastrado_por_nome='Admin Teste',
        )
        cancelada = Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            doador=doador,
            data_recebimento=date.today(),
            status=Doacao.CANCELADA,
            registrado_por_nome='Admin Teste',
            registrado_por_tipo='ADMIN',
        )
        DoacaoFinanceira.objects.create(
            doacao=cancelada,
            valor=Decimal('900.00'),
            forma_recebimento=DoacaoFinanceira.PIX,
        )
        confirmada = Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            doador=doador,
            data_recebimento=date.today(),
            status=Doacao.CONFIRMADA,
            registrado_por_nome='Admin Teste',
            registrado_por_tipo='ADMIN',
        )
        DoacaoFinanceira.objects.create(
            doacao=confirmada,
            valor=Decimal('25.00'),
            forma_recebimento=DoacaoFinanceira.PIX,
        )

        resposta = self.client.get(reverse('relatorios'), {
            'relatorio': 'doacoes',
            'formato': 'csv',
            'data_inicio': date.today().isoformat(),
            'data_fim': date.today().isoformat(),
        })

        self.assertEqual(resposta.status_code, 200)
        conteudo = resposta.content.decode('utf-8-sig')
        self.assertIn('25.00', conteudo)
        self.assertNotIn('900.00', conteudo)
