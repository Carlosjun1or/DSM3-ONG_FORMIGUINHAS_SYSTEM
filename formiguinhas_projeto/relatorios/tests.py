from datetime import date
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

        self.assertRedirects(resposta, reverse('acao_detalhe', args=[self.acao.pk]))
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
        )

        self.assertRedirects(resposta, reverse('acao_detalhe', args=[self.acao.pk]))
        self.assertFalse(MovimentacaoEstoque.objects.filter(acao=self.acao).exists())
        self.assertEqual(self.material.calcular_saldo(), 10)


class DoacoesRelatorioTests(RelatoriosTestCase):
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
