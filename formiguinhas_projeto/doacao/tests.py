from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acao.models import Acao
from auditoria.models import EventoAuditoria
from estoque.models import Material, MovimentacaoEstoque
from praia.models import Praia
from usuario.models import Usuario, Voluntario

from .forms import DoadorForm, DoadorInlineForm, DoacaoForm, ItemDoacaoMaterialForm
from .models import Doador, Doacao, DoacaoFinanceira, ItemDoacaoMaterial


class DoacaoTestCase(TestCase):
    def setUp(self):
        voluntario = Voluntario.objects.create(
            nome='Administrador',
            dt_nascimento='1990-01-01',
            endereco='Rua A',
            telefone='11999999999',
            email='admin@example.com',
        )
        self.usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='hash',
        )
        session = self.client.session
        session['usuario_id'] = self.usuario.pk
        session['usuario_tipo'] = self.usuario.tipo
        session['usuario_nome'] = voluntario.nome
        session.save()
        self.client.cookies['sessionid'] = session.session_key
        self.doador = Doador.objects.create(
            tipo=Doador.PESSOA_FISICA,
            nome='Doador Teste',
            cadastrado_por=self.usuario,
            cadastrado_por_nome=voluntario.nome,
        )

    def test_categoria_do_item_e_definida_pelo_material_selecionado(self):
        material = Material.objects.create(
            nome='Arroz',
            codigo='ALIM-01',
            categoria='Alimentação',
            unidade='KG',
        )
        form = ItemDoacaoMaterialForm(data={
            'material': material.pk,
            'nome': 'Arroz',
            'categoria': 'Categoria divergente',
            'quantidade': '5',
            'condicao': ItemDoacaoMaterial.CONDICAO_NOVO,
            'observacoes': '',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['categoria'], 'Alimentação')
        self.assertIn('data-categoria="Alimentação"', str(form['material']))

    def test_categoria_existente_e_reutilizada_ao_cadastrar_material_na_doacao(self):
        Material.objects.create(
            nome='Detergente',
            codigo='LIMP-01',
            categoria='Limpeza',
            unidade='LITRO',
        )
        form = ItemDoacaoMaterialForm(data={
            'material': '',
            'nome': 'Sabonete',
            'categoria': '  limpeza  ',
            'unidade_nova': 'UNIDADE',
            'quantidade': '4',
            'condicao': ItemDoacaoMaterial.CONDICAO_NOVO,
            'observacoes': '',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['categoria'], 'Limpeza')

    def test_novo_material_da_doacao_e_cadastrado_e_recebe_estoque(self):
        response = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.MATERIAL,
            'doador': self.doador.pk,
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'financeira-valor': '',
            'financeira-forma_recebimento': '',
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
            'itens-0-material': '',
            'itens-0-nome': 'Sabonete',
            'itens-0-categoria': 'Higiene',
            'itens-0-unidade_nova': 'UNIDADE',
            'itens-0-quantidade': '4',
            'itens-0-condicao': ItemDoacaoMaterial.CONDICAO_NOVO,
            'itens-0-observacoes': '',
        })

        self.assertEqual(response.status_code, 302)
        material = Material.objects.get(nome='Sabonete')
        item = ItemDoacaoMaterial.objects.get(nome='Sabonete')
        movimentacao = MovimentacaoEstoque.objects.get(item_doacao=item)
        self.assertEqual(item.material, material)
        self.assertEqual(item.categoria, 'Higiene')
        self.assertEqual(material.unidade, 'UNIDADE')
        self.assertEqual(material.calcular_saldo(), 4)
        self.assertEqual(movimentacao.origem, 'DOACAO')

    def test_formulario_permite_pesquisar_material_e_categoria(self):
        Material.objects.create(
            nome='Água mineral',
            codigo='BEB-01',
            categoria='Bebidas',
            unidade='LITRO',
        )

        response = self.client.get(reverse('cadastro_doacao'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pesquise e selecione um material existente')
        self.assertContains(response, 'data-nome="Água mineral"')
        self.assertContains(response, 'data-categoria="Bebidas"')
        self.assertContains(response, 'data-categoria-combobox')
        self.assertContains(response, 'data-categoria-options')
        self.assertContains(response, 'data-value="Bebidas"')

    @patch(
        'acao.mongo_services.consultar_acoes_mongo',
        return_value=([{
            'id_sql': 987,
            'tipo': 'COLETA_VOLUNTARIA',
            'data': '2026-10-30',
            'local': 'Orla',
            'praia': {'id': 321, 'nome': 'Praia Central', 'cidade': 'Santos'},
        }], 1),
    )
    def test_formulario_exibe_acoes_na_lista_de_busca(self, consultar_acoes):
        response = self.client.get(reverse('cadastro_doacao'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-id="987"')
        self.assertContains(response, 'data-praia-id="321"')
        self.assertContains(
            response,
            'data-search="coleta voluntária praia central 30/10/2026 orla"',
        )
        self.assertContains(response, 'Coleta voluntária · Praia Central')
        consultar_acoes.assert_called_once_with(por_pagina=100)

    def test_cadastro_doacao_exibe_breadcrumb_hierarquico(self):
        response = self.client.get(reverse('cadastro_doacao'))

        self.assertContains(response, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            response,
            'href="/doacao/">Controle de Doações</a>',
        )
        self.assertContains(
            response,
            '<span aria-current="page">Cadastro de Doação</span>',
        )

    def test_detalhe_doacao_exibe_breadcrumb_com_tipo_e_doador(self):
        tipos_e_rotulos = (
            (Doacao.FINANCEIRA, 'Financeira'),
            (Doacao.MATERIAL, 'Material'),
        )

        for tipo, rotulo in tipos_e_rotulos:
            with self.subTest(tipo=tipo):
                doacao = Doacao.objects.create(
                    tipo=tipo,
                    doador=self.doador,
                    data_recebimento=timezone.localdate(),
                    registrado_por=self.usuario,
                    registrado_por_nome='Administrador',
                    registrado_por_tipo='ADMIN',
                )

                response = self.client.get(
                    reverse('doacao_detalhe', args=[doacao.pk])
                )

                self.assertContains(
                    response,
                    'href="/usuario/home/">Início</a>',
                )
                self.assertContains(
                    response,
                    'href="/doacao/">Controle de Doações</a>',
                )
                self.assertContains(
                    response,
                    f'<span aria-current="page">Detalhes da Doação {rotulo} - Doador Teste</span>',
                )

    def test_edicao_doacao_exibe_breadcrumb_com_tipo_e_doador(self):
        tipos_e_rotulos = (
            (Doacao.FINANCEIRA, 'Financeira'),
            (Doacao.MATERIAL, 'Material'),
        )

        for tipo, rotulo in tipos_e_rotulos:
            with self.subTest(tipo=tipo):
                doacao = Doacao.objects.create(
                    tipo=tipo,
                    doador=self.doador,
                    data_recebimento=timezone.localdate(),
                    registrado_por=self.usuario,
                    registrado_por_nome='Administrador',
                    registrado_por_tipo='ADMIN',
                )

                response = self.client.get(
                    reverse('editar_doacao', args=[doacao.pk])
                )

                self.assertContains(
                    response,
                    'href="/usuario/home/">Início</a>',
                )
                self.assertContains(
                    response,
                    'href="/doacao/">Controle de Doações</a>',
                )
                self.assertContains(
                    response,
                    f'<span aria-current="page">Edição de Doação {rotulo} - Doador Teste</span>',
                )

    def test_doacao_anonima_nao_exige_doador(self):
        form = DoacaoForm(data={
            'tipo': Doacao.FINANCEIRA,
            'anonima': 'on',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'doador': '',
            'praia': '',
            'acao': '',
            'descricao_finalidade': '',
            'observacoes': '',
            'referencia_comprovante': '',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_cadastro_financeiro_registra_responsavel_e_auditoria(self):
        response = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.FINANCEIRA,
            'doador': self.doador.pk,
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': 'PIX-123',
            'financeira-valor': '125.50',
            'financeira-forma_recebimento': DoacaoFinanceira.PIX,
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(response.status_code, 302)
        doacao = Doacao.objects.get()
        self.assertEqual(doacao.registrado_por, self.usuario)
        self.assertEqual(doacao.financeira.valor, Decimal('125.50'))

    def test_cadastro_financeiro_disponibiliza_doador_ativo(self):
        resposta_lista = self.client.get(reverse('cadastro_doacao'))
        self.assertContains(resposta_lista, f'data-id="{self.doador.pk}"')

        resposta_cadastro = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.FINANCEIRA,
            'doador': self.doador.pk,
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'financeira-valor': '25.00',
            'financeira-forma_recebimento': DoacaoFinanceira.PIX,
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
        })

        self.assertEqual(resposta_cadastro.status_code, 302)
        self.assertEqual(Doacao.objects.get().doador, self.doador)
        self.assertEqual(Doador.objects.count(), 1)

    def test_cadastro_financeiro_nao_disponibiliza_doador_inativo(self):
        self.doador.ativo = False
        self.doador.save()

        resposta_lista = self.client.get(reverse('cadastro_doacao'))
        self.assertNotIn(
            self.doador,
            resposta_lista.context['form'].fields['doador'].queryset,
        )
        resposta_cadastro = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.FINANCEIRA,
            'doador': self.doador.pk,
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'financeira-valor': '25.00',
            'financeira-forma_recebimento': DoacaoFinanceira.PIX,
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
        })

        self.assertEqual(resposta_cadastro.status_code, 200)
        self.assertTrue(resposta_cadastro.context['form'].has_error('doador'))
        self.assertEqual(Doacao.objects.count(), 0)

    def test_cadastro_financeiro_reutiliza_doador_de_doacao_material(self):
        Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=self.doador,
            data_recebimento=timezone.localdate(),
            status=Doacao.CONFIRMADA,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )

        resposta = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.FINANCEIRA,
            'doador': self.doador.pk,
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'financeira-valor': '40.00',
            'financeira-forma_recebimento': DoacaoFinanceira.PIX,
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
        })

        self.assertEqual(resposta.status_code, 302)
        doacao_financeira = Doacao.objects.get(tipo=Doacao.FINANCEIRA)
        self.assertEqual(doacao_financeira.doador, self.doador)
        self.assertEqual(Doador.objects.count(), 1)

    def test_formulario_novo_doador_fica_fechado_sem_dados_inline(self):
        resposta = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.FINANCEIRA,
            'doador': self.doador.pk,
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'financeira-valor': '',
            'financeira-forma_recebimento': DoacaoFinanceira.PIX,
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
        })

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.context['exibir_form_doador_inline'])
        self.assertContains(resposta, 'id="novo-doador-fields" class="inline-donor-card" hidden')

    def test_cadastro_financeiro_exige_valor_e_forma_de_recebimento(self):
        dados_base = {
            'tipo': Doacao.FINANCEIRA,
            'doador': self.doador.pk,
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'financeira-valor': '25.00',
            'financeira-forma_recebimento': DoacaoFinanceira.PIX,
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
        }

        for campo in ('financeira-valor', 'financeira-forma_recebimento'):
            with self.subTest(campo=campo):
                dados = dados_base.copy()
                dados[campo] = ''
                resposta = self.client.post(reverse('cadastro_doacao'), dados)

                self.assertEqual(resposta.status_code, 200)
                self.assertIn(campo.removeprefix('financeira-'), resposta.context['financeira_form'].errors)
                self.assertEqual(Doacao.objects.count(), 0)

    def test_total_do_painel_considera_apenas_confirmadas(self):
        for status, valor in [
            (Doacao.CONFIRMADA, '10.00'),
            (Doacao.PENDENTE, '90.00'),
        ]:
            doacao = Doacao.objects.create(
                tipo=Doacao.FINANCEIRA,
                doador=self.doador,
                data_recebimento=timezone.localdate(),
                status=status,
                registrado_por=self.usuario,
                registrado_por_nome='Administrador',
                registrado_por_tipo='ADMIN',
            )
            DoacaoFinanceira.objects.create(
                doacao=doacao,
                valor=valor,
                forma_recebimento=DoacaoFinanceira.PIX,
            )
        response = self.client.get(reverse('doacoes'))
        self.assertContains(response, '10.00')
        self.assertNotContains(response, '100.00')

    def test_filtro_de_data_em_doacoes_preserva_datas_e_permite_seletor_nativo(self):
        hoje = timezone.localdate()
        datas = (hoje - timedelta(days=2), hoje, hoje + timedelta(days=2))
        doacoes = [
            Doacao.objects.create(
                tipo=Doacao.FINANCEIRA,
                doador=self.doador,
                data_recebimento=data,
                status=Doacao.PENDENTE,
                registrado_por=self.usuario,
                registrado_por_nome='Administrador',
                registrado_por_tipo='ADMIN',
            )
            for data in datas
        ]

        resposta = self.client.get(
            reverse('doacoes'),
            {
                'inicio': datas[0].isoformat(),
                'fim': datas[1].isoformat(),
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            {doacao.pk for doacao in resposta.context['doacoes']},
            {doacoes[0].pk, doacoes[1].pk},
        )
        self.assertContains(
            resposta,
            f'<input id="filtro-inicio" class="form-control" type="date" '
            f'name="inicio" value="{datas[0].isoformat()}">',
        )
        self.assertContains(
            resposta,
            f'<input id="filtro-fim" class="form-control" type="date" '
            f'name="fim" value="{datas[1].isoformat()}">',
        )

    def test_menu_lateral_marca_apenas_controle_de_doadores(self):
        resposta_doadores = self.client.get(reverse('doadores'))
        self.assertContains(
            resposta_doadores,
            'href="/doacao/doadores/" class="sidebar-link active"',
        )
        self.assertContains(
            resposta_doadores,
            'href="/doacao/" class="sidebar-link "',
        )

        resposta_doacoes = self.client.get(reverse('doacoes'))
        self.assertContains(
            resposta_doacoes,
            'href="/doacao/" class="sidebar-link active"',
        )
        self.assertContains(
            resposta_doacoes,
            'href="/doacao/doadores/" class="sidebar-link "',
        )

    def test_controle_de_doacoes_pagina_e_preserva_filtros(self):
        hoje = timezone.localdate()
        inicio = hoje - timedelta(days=10)
        fim = hoje - timedelta(days=1)
        for indice in range(23):
            Doacao.objects.create(
                tipo=Doacao.MATERIAL,
                doador=self.doador,
                data_recebimento=inicio + timedelta(days=indice % 10),
                status=Doacao.PENDENTE,
                finalidade=Doacao.FINALIDADE_GERAL,
                registrado_por=self.usuario,
                registrado_por_nome='Administrador',
                registrado_por_tipo='ADMIN',
            )
        Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            doador=self.doador,
            data_recebimento=inicio - timedelta(days=1),
            status=Doacao.PENDENTE,
            finalidade=Doacao.FINALIDADE_GERAL,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=self.doador,
            data_recebimento=fim + timedelta(days=1),
            status=Doacao.CONFIRMADA,
            finalidade=Doacao.FINALIDADE_ESPECIFICA,
            descricao_finalidade='Material escolar',
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        filtros = {
            'inicio': inicio.isoformat(),
            'fim': fim.isoformat(),
            'tipo': Doacao.MATERIAL,
            'status': Doacao.PENDENTE,
            'finalidade': Doacao.FINALIDADE_GERAL,
        }

        response = self.client.get(
            reverse('doacoes'),
            {**filtros, 'page': '1'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pagina'].number, 1)
        self.assertEqual(response.context['pagina'].paginator.count, 23)
        self.assertEqual(len(response.context['doacoes']), 20)
        self.assertEqual(
            response.context['filtros_query'],
            (
                f'inicio={inicio.isoformat()}&fim={fim.isoformat()}'
                f'&tipo={Doacao.MATERIAL}&status={Doacao.PENDENTE}'
                f'&finalidade={Doacao.FINALIDADE_GERAL}'
            ),
        )
        self.assertContains(
            response,
            f'inicio={inicio.isoformat()}&amp;fim={fim.isoformat()}'
            f'&amp;tipo={Doacao.MATERIAL}&amp;status={Doacao.PENDENTE}'
            f'&amp;finalidade={Doacao.FINALIDADE_GERAL}&amp;page=2',
        )
        self.assertContains(response, f'value="{inicio.isoformat()}"')
        self.assertContains(response, f'value="{fim.isoformat()}"')

        segunda_pagina = self.client.get(
            reverse('doacoes'),
            {**filtros, 'page': '2'},
        )

        self.assertEqual(segunda_pagina.status_code, 200)
        self.assertEqual(segunda_pagina.context['pagina'].number, 2)
        self.assertEqual(segunda_pagina.context['pagina'].paginator.count, 23)
        self.assertEqual(len(segunda_pagina.context['doacoes']), 3)
        self.assertEqual(segunda_pagina.context['inicio'], inicio.isoformat())
        self.assertEqual(segunda_pagina.context['fim'], fim.isoformat())
        self.assertEqual(segunda_pagina.context['tipo_selecionado'], Doacao.MATERIAL)
        self.assertEqual(segunda_pagina.context['status_selecionado'], Doacao.PENDENTE)
        self.assertEqual(
            segunda_pagina.context['finalidade_selecionada'],
            Doacao.FINALIDADE_GERAL,
        )

    def test_data_futura_e_rejeitada(self):
        form = DoacaoForm(data={
            'tipo': Doacao.MATERIAL,
            'doador': self.doador.pk,
            'data_recebimento': (timezone.localdate() + timedelta(days=1)).isoformat(),
            'status': Doacao.PENDENTE,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'praia': '',
            'acao': '',
            'descricao_finalidade': '',
            'observacoes': '',
            'referencia_comprovante': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('data_recebimento', form.errors)
        self.assertEqual(len(form.errors['data_recebimento']), 1)

    def test_cadastro_material_aceita_varios_itens(self):
        luvas = Material.objects.create(
            nome='Luvas',
            codigo='LUVAS',
            categoria='Proteção',
            unidade='UNIDADE',
        )
        sacos = Material.objects.create(
            nome='Sacos de lixo',
            codigo='SACOS',
            categoria='Limpeza',
            unidade='PACOTE',
        )
        response = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.MATERIAL,
            'doador': self.doador.pk,
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'financeira-valor': '',
            'financeira-forma_recebimento': '',
            'itens-TOTAL_FORMS': '2',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
            'itens-0-material': str(luvas.pk),
            'itens-0-nome': 'Luvas',
            'itens-0-categoria': 'Proteção',
            'itens-0-quantidade': '20',
            'itens-0-unidade': 'unidades',
            'itens-0-condicao': 'NOVO',
            'itens-0-observacoes': '',
            'itens-1-material': str(sacos.pk),
            'itens-1-nome': 'Sacos de lixo',
            'itens-1-categoria': 'Limpeza',
            'itens-1-quantidade': '5',
            'itens-1-unidade': 'pacotes',
            'itens-1-condicao': 'NOVO',
            'itens-1-observacoes': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ItemDoacaoMaterial.objects.count(), 2)
        movimentacoes = MovimentacaoEstoque.objects.order_by('material__nome')
        self.assertEqual(movimentacoes.count(), 2)
        self.assertEqual([mov.material_id for mov in movimentacoes], [luvas.pk, sacos.pk])
        self.assertTrue(all(mov.origem == 'DOACAO' for mov in movimentacoes))
        self.assertEqual(luvas.calcular_saldo(), 20)
        self.assertEqual(sacos.calcular_saldo(), 5)
        evento = EventoAuditoria.objects.get(
            entidade='DOACAO',
            id_registro=Doacao.objects.get().pk,
            acao='CRIACAO',
        )
        self.assertEqual(len(evento.valores_novos['itens_materiais']), 2)
        self.assertEqual(
            {item['nome'] for item in evento.valores_novos['itens_materiais']},
            {'Luvas', 'Sacos de lixo'},
        )

    def test_confirmar_doacao_material_cria_movimentacao_uma_unica_vez(self):
        material = Material.objects.create(
            nome='Cestas',
            codigo='CESTAS',
            categoria='Alimentos',
            unidade='UNIDADE',
        )
        doacao = Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=self.doador,
            data_recebimento=timezone.localdate(),
            status=Doacao.PENDENTE,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        item = ItemDoacaoMaterial.objects.create(
            doacao=doacao,
            material=material,
            nome='Cestas',
            categoria='Alimentos',
            quantidade=8,
            unidade='unidades',
            condicao=ItemDoacaoMaterial.CONDICAO_NOVO,
        )

        for _ in range(2):
            response = self.client.post(
                reverse('atualizar_status_doacao', args=[doacao.pk]),
                {'status': Doacao.CONFIRMADA},
            )
            self.assertEqual(response.status_code, 302)

        self.assertEqual(MovimentacaoEstoque.objects.filter(doacao=doacao).count(), 1)
        movimentacao = MovimentacaoEstoque.objects.get(doacao=doacao)
        self.assertEqual(movimentacao.item_doacao, item)
        self.assertEqual(material.calcular_saldo(), 8)
        self.assertContains(
            self.client.get(reverse('doacao_detalhe', args=[doacao.pk])),
            'Entrada aplicada',
        )
        self.assertContains(
            self.client.get(reverse('movimentacoes_estoque')),
            reverse('doacao_detalhe', args=[doacao.pk]),
        )

    def test_confirmacao_sem_correspondencia_no_estoque_e_bloqueada(self):
        doacao = Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=self.doador,
            data_recebimento=timezone.localdate(),
            status=Doacao.PENDENTE,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        ItemDoacaoMaterial.objects.create(
            doacao=doacao,
            nome='Item sem vínculo',
            categoria='Geral',
            quantidade=2,
            unidade='unidades',
            condicao=ItemDoacaoMaterial.CONDICAO_NOVO,
        )

        response = self.client.post(
            reverse('atualizar_status_doacao', args=[doacao.pk]),
            {'status': Doacao.CONFIRMADA},
            follow=True,
        )

        doacao.refresh_from_db()
        self.assertEqual(doacao.status, Doacao.PENDENTE)
        self.assertEqual(MovimentacaoEstoque.objects.count(), 0)
        self.assertContains(response, 'Selecione o material do estoque')

    def test_quantidade_fracionada_ou_material_danificado_nao_entra_no_estoque(self):
        material = Material.objects.create(
            nome='Ração',
            codigo='RACAO',
            categoria='Alimentos',
            unidade='KG',
        )
        for indice, quantidade, condicao in [
            (1, '2.5', ItemDoacaoMaterial.CONDICAO_NOVO),
            (2, '3', ItemDoacaoMaterial.CONDICAO_DANIFICADO),
        ]:
            doacao = Doacao.objects.create(
                tipo=Doacao.MATERIAL,
                doador=self.doador,
                data_recebimento=timezone.localdate(),
                status=Doacao.PENDENTE,
                registrado_por=self.usuario,
                registrado_por_nome='Administrador',
                registrado_por_tipo='ADMIN',
            )
            ItemDoacaoMaterial.objects.create(
                doacao=doacao,
                material=material,
                nome=f'Ração {indice}',
                categoria='Alimentos',
                quantidade=quantidade,
                unidade='kg',
                condicao=condicao,
            )

            response = self.client.post(
                reverse('atualizar_status_doacao', args=[doacao.pk]),
                {'status': Doacao.CONFIRMADA},
                follow=True,
            )

            doacao.refresh_from_db()
            self.assertEqual(doacao.status, Doacao.PENDENTE)
            self.assertContains(response, 'Não foi possível atualizar a situação da doação #')

        self.assertEqual(MovimentacaoEstoque.objects.count(), 0)
        self.assertEqual(material.calcular_saldo(), 0)

    def test_nao_permite_cancelar_doacao_que_ja_movimentou_estoque(self):
        material = Material.objects.create(
            nome='Cobertores',
            codigo='COBERT',
            categoria='Geral',
            unidade='UNIDADE',
        )
        doacao = Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=self.doador,
            data_recebimento=timezone.localdate(),
            status=Doacao.CONFIRMADA,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        item = ItemDoacaoMaterial.objects.create(
            doacao=doacao,
            material=material,
            nome='Cobertores',
            categoria='Geral',
            quantidade=3,
            unidade='unidades',
            condicao=ItemDoacaoMaterial.CONDICAO_NOVO,
        )
        self.client.post(
            reverse('atualizar_status_doacao', args=[doacao.pk]),
            {'status': Doacao.CONFIRMADA},
        )

        response = self.client.post(
            reverse('atualizar_status_doacao', args=[doacao.pk]),
            {'status': Doacao.CANCELADA},
            follow=True,
        )

        doacao.refresh_from_db()
        self.assertEqual(doacao.status, Doacao.CONFIRMADA)
        self.assertIn(
            f'A situação da doação #{doacao.pk} foi atualizada para Confirmada.',
            [str(mensagem) for mensagem in response.wsgi_request._messages],
        )
        self.assertEqual(MovimentacaoEstoque.objects.filter(item_doacao=item).count(), 1)
        self.assertContains(response, 'Não é possível retirar a confirmação')

    def test_doacao_cancelada_pode_ser_excluida_e_a_exclusao_e_auditada(self):
        doacao = Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            doador=self.doador,
            data_recebimento=timezone.localdate(),
            status=Doacao.CANCELADA,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        financeira = DoacaoFinanceira.objects.create(
            doacao=doacao,
            valor='25.00',
            forma_recebimento=DoacaoFinanceira.PIX,
        )

        listagem = self.client.get(reverse('doacoes'))
        self.assertContains(listagem, 'Excluir')
        self.assertContains(
            listagem,
            reverse('excluir_doacao', args=[doacao.pk]),
        )
        self.assertContains(listagem, f'doação cancelada #{doacao.pk}?')
        detalhe = self.client.get(reverse('doacao_detalhe', args=[doacao.pk]))
        self.assertContains(detalhe, 'Excluir')
        self.assertContains(
            detalhe,
            reverse('excluir_doacao', args=[doacao.pk]),
        )

        resposta = self.client.post(
            reverse('excluir_doacao', args=[doacao.pk]),
            follow=True,
        )

        self.assertRedirects(resposta, reverse('doacoes'))
        self.assertFalse(Doacao.objects.filter(pk=doacao.pk).exists())
        self.assertFalse(DoacaoFinanceira.objects.filter(pk=financeira.pk).exists())
        self.assertIn(
            f'A doação cancelada #{doacao.pk} foi excluída com sucesso.',
            [str(mensagem) for mensagem in resposta.wsgi_request._messages],
        )
        self.assertTrue(EventoAuditoria.objects.filter(
            entidade='DOACAO',
            id_registro=doacao.pk,
            acao='EXCLUSAO',
        ).exists())

    def test_nao_permite_excluir_doacao_que_nao_esteja_cancelada(self):
        doacao = Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            doador=self.doador,
            data_recebimento=timezone.localdate(),
            status=Doacao.PENDENTE,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )

        resposta = self.client.post(
            reverse('excluir_doacao', args=[doacao.pk]),
            follow=True,
        )

        self.assertRedirects(
            resposta,
            reverse('doacao_detalhe', args=[doacao.pk]),
        )
        self.assertTrue(Doacao.objects.filter(pk=doacao.pk).exists())
        self.assertContains(
            resposta,
            f'Não foi possível excluir a doação #{doacao.pk}. '
            'Somente doações canceladas podem ser excluídas.',
        )

    def test_nao_permite_excluir_doacao_cancelada_com_movimentacao_de_estoque(self):
        material = Material.objects.create(
            nome='Cestas protegidas',
            codigo='CESTAS-PROTEGIDAS',
            categoria='Alimentos',
            unidade='UNIDADE',
        )
        doacao = Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=self.doador,
            data_recebimento=timezone.localdate(),
            status=Doacao.CANCELADA,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        item = ItemDoacaoMaterial.objects.create(
            doacao=doacao,
            material=material,
            nome='Cestas protegidas',
            categoria='Alimentos',
            quantidade=2,
            unidade='unidades',
            condicao=ItemDoacaoMaterial.CONDICAO_NOVO,
        )
        movimentacao = MovimentacaoEstoque.objects.create(
            material=material,
            tipo='ENTRADA',
            quantidade=2,
            origem='DOACAO',
            doacao=doacao,
            item_doacao=item,
        )

        resposta = self.client.post(
            reverse('excluir_doacao', args=[doacao.pk]),
            follow=True,
        )

        self.assertRedirects(
            resposta,
            reverse('doacao_detalhe', args=[doacao.pk]),
        )
        self.assertTrue(Doacao.objects.filter(pk=doacao.pk).exists())
        self.assertTrue(MovimentacaoEstoque.objects.filter(pk=movimentacao.pk).exists())
        self.assertContains(
            resposta,
            f'Não foi possível excluir a doação cancelada #{doacao.pk}. '
            'Existem movimentações de estoque vinculadas que precisam ser preservadas.',
        )

    def test_coordenador_nao_pode_excluir_doacao_cancelada(self):
        doacao = Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            doador=self.doador,
            data_recebimento=timezone.localdate(),
            status=Doacao.CANCELADA,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        voluntario = Voluntario.objects.create(
            nome='Coordenador',
            dt_nascimento='1991-01-01',
            endereco='Rua B',
            telefone='11988888888',
            email='coordenador@example.com',
        )
        coordenador = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            senha='hash',
        )
        session = self.client.session
        session['usuario_id'] = coordenador.id_usuario
        session['usuario_tipo'] = coordenador.tipo
        session['usuario_nome'] = voluntario.nome
        session.save()
        self.client.cookies['sessionid'] = session.session_key

        resposta = self.client.post(
            reverse('excluir_doacao', args=[doacao.pk]),
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Doacao.objects.filter(pk=doacao.pk).exists())

    def test_coordenador_consulta_doacoes_mas_nao_pode_criar_editar_ou_cancelar(self):
        voluntario = Voluntario.objects.create(
            nome='Coordenador',
            dt_nascimento='1991-01-01',
            endereco='Rua B',
            telefone='11988888888',
            email='coordenador@example.com',
        )
        coordenador = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            senha='hash',
        )
        doacao = Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            doador=self.doador,
            data_recebimento=timezone.localdate(),
            status=Doacao.PENDENTE,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )

        session = self.client.session
        session['usuario_id'] = coordenador.id_usuario
        session['usuario_tipo'] = coordenador.tipo
        session['usuario_nome'] = voluntario.nome
        session.save()
        self.client.cookies['sessionid'] = session.session_key

        listagem = self.client.get(reverse('doacoes'))
        self.assertEqual(listagem.status_code, 200)
        self.assertContains(listagem, f'href="{reverse("doacao_detalhe", args=[doacao.pk])}"')
        self.assertNotContains(listagem, reverse('cadastro_doacao'))

        detalhe = self.client.get(reverse('doacao_detalhe', args=[doacao.pk]))
        self.assertEqual(detalhe.status_code, 200)
        self.assertContains(detalhe, f'Registro #{doacao.pk}')
        self.assertNotContains(detalhe, reverse('editar_doacao', args=[doacao.pk]))

        tentativas_bloqueadas = (
            self.client.get(reverse('cadastro_doacao')),
            self.client.post(reverse('cadastro_doacao'), {}),
            self.client.get(reverse('editar_doacao', args=[doacao.pk])),
            self.client.post(reverse('editar_doacao', args=[doacao.pk]), {}),
            self.client.post(
                reverse('atualizar_status_doacao', args=[doacao.pk]),
                {'status': Doacao.CANCELADA},
            ),
        )
        for resposta in tentativas_bloqueadas:
            with self.subTest(path=resposta.wsgi_request.path, method=resposta.wsgi_request.method):
                self.assertEqual(resposta.status_code, 403)

        doacao.refresh_from_db()
        self.assertEqual(doacao.status, Doacao.PENDENTE)
        self.assertEqual(Doacao.objects.count(), 1)

    def test_alterar_status_na_tela_de_detalhes_permanece_nela(self):
        doacao = Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            doador=self.doador,
            data_recebimento=timezone.localdate(),
            status=Doacao.PENDENTE,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )

        response = self.client.post(
            reverse('atualizar_status_doacao', args=[doacao.pk]),
            {'status': Doacao.CONFIRMADA, 'retorno': 'detalhe'},
        )

        self.assertRedirects(
            response,
            reverse('doacao_detalhe', args=[doacao.pk]),
        )
        doacao.refresh_from_db()
        self.assertEqual(doacao.status, Doacao.CONFIRMADA)
        self.assertIn(
            f'A situação da doação #{doacao.pk} foi atualizada para Confirmada.',
            [str(mensagem) for mensagem in response.wsgi_request._messages],
        )

    def test_detalhes_da_doacao_linkam_para_praia_e_acao_vinculadas(self):
        praia = Praia.objects.create(
            nome='Praia Teste',
            cidade='Santos',
            latitude='-23.9600',
            longitude='-46.3300',
        )
        acao = Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=timezone.localdate(),
            local='Orla',
            praia=praia,
        )
        doacao = Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=self.doador,
            data_recebimento=timezone.localdate(),
            status=Doacao.PENDENTE,
            praia=praia,
            acao=acao,
            registrado_por=self.usuario,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )

        response = self.client.get(reverse('doacao_detalhe', args=[doacao.pk]))

        self.assertContains(
            response,
            f'href="{reverse("praias")}?praia={praia.pk}#praia-{praia.pk}"',
        )
        self.assertContains(
            response,
            f'href="{reverse("acao_detalhe", args=[acao.pk])}"',
        )

    def test_alterar_status_na_tela_de_doador_permanece_nela(self):
        response = self.client.post(
            reverse('atualizar_status_doador', args=[self.doador.pk]),
            {'status': 'INATIVO', 'retorno': 'detalhe'},
        )

        self.assertRedirects(
            response,
            reverse('doador_detalhe', args=[self.doador.pk]),
        )
        self.doador.refresh_from_db()
        self.assertFalse(self.doador.ativo)
        self.assertIn(
            f'A situação do doador "{self.doador.nome}" foi atualizada para Inativo.',
            [str(mensagem) for mensagem in response.wsgi_request._messages],
        )

    def test_coordenador_nao_acessa_dados_pessoais_dos_doadores(self):
        self.doador.documento = '12345678901'
        self.doador.email = 'doador-privado@example.com'
        self.doador.telefone = '13988887777'
        self.doador.save()
        dados_pessoais = (
            self.doador.documento,
            self.doador.email,
            self.doador.telefone,
        )

        voluntario = Voluntario.objects.create(
            nome='Coordenador',
            dt_nascimento='1991-01-01',
            endereco='Rua B',
            telefone='11988888888',
            email='coordenador@example.com',
        )
        coordenador = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            senha='hash',
        )
        session = self.client.session
        session['usuario_id'] = coordenador.id_usuario
        session['usuario_tipo'] = coordenador.tipo
        session['usuario_nome'] = voluntario.nome
        session.save()
        self.client.cookies['sessionid'] = session.session_key

        requisicoes = (
            ('get', reverse('doadores'), None),
            ('get', reverse('doador_detalhe', args=[self.doador.pk]), None),
            ('get', reverse('cadastro_doador'), None),
            ('post', reverse('cadastro_doador'), {
                'tipo': Doador.PESSOA_FISICA,
                'nome': 'Doador não autorizado',
                'documento': '98765432100',
                'email': 'nao-autorizado@example.com',
                'telefone': '11977776666',
                'voluntario': '',
                'ativo': 'on',
            }),
            ('get', reverse('editar_doador', args=[self.doador.pk]), None),
            ('post', reverse('editar_doador', args=[self.doador.pk]), {
                'tipo': Doador.PESSOA_FISICA,
                'nome': 'Doador alterado sem permissão',
                'documento': '98765432100',
                'email': 'nao-autorizado@example.com',
                'telefone': '11977776666',
                'voluntario': '',
                'ativo': 'on',
            }),
            ('post', reverse('atualizar_status_doador', args=[self.doador.pk]), {
                'status': 'INATIVO',
            }),
        )

        for metodo, url, dados in requisicoes:
            with self.subTest(metodo=metodo, url=url):
                resposta = getattr(self.client, metodo)(url, dados or {})
                self.assertEqual(resposta.status_code, 403)
                conteudo = resposta.content.decode()
                for dado_pessoal in dados_pessoais:
                    self.assertNotIn(dado_pessoal, conteudo)

        self.doador.refresh_from_db()
        self.assertEqual(self.doador.documento, dados_pessoais[0])
        self.assertEqual(self.doador.email, dados_pessoais[1])
        self.assertEqual(self.doador.telefone, dados_pessoais[2])
        self.assertTrue(self.doador.ativo)
        self.assertEqual(Doador.objects.count(), 1)

    def test_detalhe_doador_exibe_breadcrumb_com_nome(self):
        response = self.client.get(
            reverse('doador_detalhe', args=[self.doador.pk])
        )

        self.assertContains(response, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            response,
            'href="/doacao/doadores/">Controle de Doadores</a>',
        )
        self.assertContains(
            response,
            '<span aria-current="page">Detalhes do Doador(a) - Doador Teste</span>',
        )

    def test_detalhe_doador_usa_cores_de_status_das_doacoes(self):
        for status in (
            Doacao.PENDENTE,
            Doacao.CONFIRMADA,
            Doacao.CANCELADA,
        ):
            Doacao.objects.create(
                tipo=Doacao.FINANCEIRA,
                doador=self.doador,
                data_recebimento=timezone.localdate(),
                status=status,
                registrado_por=self.usuario,
                registrado_por_nome='Administrador',
                registrado_por_tipo='ADMIN',
            )

        response = self.client.get(
            reverse('doador_detalhe', args=[self.doador.pk])
        )

        for status, rotulo in Doacao.STATUS_CHOICES:
            self.assertContains(
                response,
                f'class="status-badge status-{status.lower()}">{rotulo}</span>',
            )

    def test_lista_de_doadores_filtra_por_tipo_e_preserva_filtros_na_paginacao(self):
        Doador.objects.bulk_create([
            Doador(
                tipo=Doador.PESSOA_FISICA,
                nome=f'Doador de teste {indice:02d}',
                cadastrado_por_nome='Administrador',
            )
            for indice in range(21)
        ])
        Doador.objects.create(
            tipo=Doador.PESSOA_JURIDICA,
            nome='Doador de teste pessoa jurídica',
            cadastrado_por_nome='Administrador',
        )
        Doador.objects.create(
            tipo=Doador.PESSOA_FISICA,
            nome='Doador de teste inativo PF',
            ativo=False,
            cadastrado_por_nome='Administrador',
        )
        Doador.objects.create(
            tipo=Doador.PESSOA_JURIDICA,
            nome='Doador de teste inativo PJ',
            ativo=False,
            cadastrado_por_nome='Administrador',
        )
        filtros = {
            'busca': 'Doador de teste',
            'tipo': Doador.PESSOA_FISICA,
            'status': 'ATIVO',
        }

        primeira_pagina = self.client.get(reverse('doadores'), filtros)

        self.assertEqual(primeira_pagina.status_code, 200)
        self.assertEqual(primeira_pagina.context['pagina'].paginator.count, 21)
        self.assertEqual(primeira_pagina.context['pagina'].number, 1)
        self.assertEqual(len(primeira_pagina.context['doadores']), 20)
        self.assertEqual(
            {doador.tipo for doador in primeira_pagina.context['doadores']},
            {Doador.PESSOA_FISICA},
        )
        self.assertContains(
            primeira_pagina,
            '?busca=Doador+de+teste&amp;tipo=PF&amp;status=ATIVO&amp;page=2',
        )

        segunda_pagina = self.client.get(
            reverse('doadores'),
            {**filtros, 'page': '2'},
        )

        self.assertEqual(segunda_pagina.status_code, 200)
        self.assertEqual(segunda_pagina.context['pagina'].number, 2)
        self.assertEqual(segunda_pagina.context['pagina'].paginator.count, 21)
        self.assertEqual(len(segunda_pagina.context['doadores']), 1)
        self.assertEqual(
            segunda_pagina.context['doadores'][0].tipo,
            Doador.PESSOA_FISICA,
        )
        self.assertEqual(segunda_pagina.context['tipo_selecionado'], Doador.PESSOA_FISICA)
        self.assertEqual(segunda_pagina.context['status_selecionado'], 'ATIVO')
        self.assertContains(
            segunda_pagina,
            '?busca=Doador+de+teste&amp;tipo=PF&amp;status=ATIVO&amp;page=1',
        )

        juridicas = self.client.get(
            reverse('doadores'),
            {'tipo': Doador.PESSOA_JURIDICA},
        )
        self.assertEqual(juridicas.context['pagina'].paginator.count, 2)
        self.assertEqual(
            {doador.tipo for doador in juridicas.context['doadores']},
            {Doador.PESSOA_JURIDICA},
        )

        inativos = self.client.get(
            reverse('doadores'),
            {'busca': 'Doador de teste inativo', 'status': 'INATIVO'},
        )
        self.assertEqual(inativos.context['pagina'].paginator.count, 2)
        self.assertEqual(inativos.context['status_selecionado'], 'INATIVO')
        self.assertEqual(
            {doador.tipo for doador in inativos.context['doadores']},
            {Doador.PESSOA_FISICA, Doador.PESSOA_JURIDICA},
        )

    def test_cadastro_doador_exibe_breadcrumb_hierarquico(self):
        response = self.client.get(reverse('cadastro_doador'))

        self.assertContains(response, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            response,
            'href="/doacao/doadores/">Controle de Doadores</a>',
        )
        self.assertContains(
            response,
            '<span aria-current="page">Cadastro de Doador</span>',
        )

    def test_edicao_doador_exibe_breadcrumb_com_nome(self):
        response = self.client.get(
            reverse('editar_doador', args=[self.doador.pk])
        )

        self.assertContains(response, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            response,
            'href="/doacao/doadores/">Controle de Doadores</a>',
        )
        self.assertContains(
            response,
            '<span aria-current="page">Edição de Doador(a) - Doador Teste</span>',
        )

    def test_cadastro_cria_doador_na_mesma_tela(self):
        response = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.FINANCEIRA,
            'doador': '',
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'novo_doador-tipo': Doador.PESSOA_JURIDICA,
            'novo_doador-nome': 'Empresa Demonstrativa',
            'novo_doador-documento': '12345678000199',
            'novo_doador-email': 'empresa@example.com',
            'novo_doador-telefone': '13999990000',
            'financeira-valor': '75.00',
            'financeira-forma_recebimento': DoacaoFinanceira.PIX,
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Doador.objects.filter(nome='Empresa Demonstrativa').exists())
        self.assertEqual(Doacao.objects.get().doador.nome, 'Empresa Demonstrativa')

    def test_cadastro_inline_vincula_voluntario_ao_novo_doador(self):
        voluntario = Voluntario.objects.create(
            nome='Voluntário doador',
            dt_nascimento='1992-02-02',
            endereco='Rua C',
            telefone='13988887777',
            email='voluntario.doador@example.com',
        )
        response = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.FINANCEIRA,
            'doador': '',
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'novo_doador-tipo': Doador.PESSOA_FISICA,
            'novo_doador-nome': 'Doador voluntário',
            'novo_doador-documento': '',
            'novo_doador-email': 'VOLUNTARIO.DOADOR@EXAMPLE.COM',
            'novo_doador-telefone': '13988887777',
            'novo_doador-voluntario': voluntario.pk,
            'financeira-valor': '50.00',
            'financeira-forma_recebimento': DoacaoFinanceira.PIX,
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
        })

        self.assertEqual(response.status_code, 302)
        doador = Doador.objects.get(voluntario=voluntario)
        self.assertEqual(doador.email, 'voluntario.doador@example.com')
        self.assertEqual(doador.telefone, '13988887777')
        self.assertEqual(Doacao.objects.get().doador, doador)
        self.assertIn(
            f'O doador "{doador.nome}" foi cadastrado e vinculado à '
            f'doação #{Doacao.objects.get().pk} com sucesso.',
            [str(mensagem) for mensagem in response.wsgi_request._messages],
        )
        self.assertNotIn(
            voluntario,
            DoadorInlineForm().fields['voluntario'].queryset,
        )

    def test_formulario_invalido_exibe_erros_ao_usuario(self):
        response = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.FINANCEIRA,
            'doador': '',
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'financeira-valor': '',
            'financeira-forma_recebimento': '',
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['financeira_form'].errors)
        conteudo = response.content.decode()
        inicio_form = conteudo.index('<form method="post" class="form-card donation-form"')
        inicio_resumo = conteudo.index('class="form-error-summary"')
        self.assertLess(inicio_form, inicio_resumo)
        self.assertEqual(
            conteudo.count('Informe o doador ou marque a doação como anônima.'),
            1,
        )
        self.assertContains(response, 'Informe o valor da doação.')
        self.assertContains(response, 'Selecione a forma de recebimento.')
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(response.content.decode().count('data-toast'), 1)
        self.assertIn(
            'A doação financeira não foi cadastrada.',
            [str(mensagem) for mensagem in response.wsgi_request._messages],
        )

    def test_cadastro_de_doacao_material_invalido_exibe_feedback_unico(self):
        response = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.MATERIAL,
            'doador': self.doador.pk,
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.PENDENTE,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'financeira-valor': '',
            'financeira-forma_recebimento': '',
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
            'itens-0-material': '',
            'itens-0-nome': 'Arroz',
            'itens-0-categoria': 'Alimentos',
            'itens-0-unidade_nova': 'UNIDADE',
            'itens-0-quantidade': '0',
            'itens-0-condicao': ItemDoacaoMaterial.CONDICAO_NOVO,
            'itens-0-observacoes': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['itens_formset'].forms[0].errors)
        self.assertEqual(response.content.decode().count('data-toast'), 1)
        self.assertIn(
            'A doação material não foi cadastrada.',
            [str(mensagem) for mensagem in response.wsgi_request._messages],
        )
        self.assertEqual(Doacao.objects.count(), 0)

    def test_cadastro_inline_de_doador_mostra_cada_erro_uma_vez(self):
        response = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.FINANCEIRA,
            'doador': '',
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'novo_doador-tipo': Doador.PESSOA_FISICA,
            'novo_doador-nome': '',
            'novo_doador-documento': '',
            'novo_doador-email': '',
            'novo_doador-telefone': '',
            'novo_doador-voluntario': '',
            'financeira-valor': '25.00',
            'financeira-forma_recebimento': DoacaoFinanceira.PIX,
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
        })

        conteudo = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(conteudo.count('Informe o nome do doador.'), 1)
        self.assertEqual(
            conteudo.count('Informe o e-mail ou o telefone do doador.'),
            1,
        )
        self.assertEqual(conteudo.count('data-toast'), 1)

    def test_item_material_sem_nome_exibe_uma_orientacao_clara(self):
        response = self.client.post(reverse('cadastro_doacao'), {
            'tipo': Doacao.MATERIAL,
            'doador': self.doador.pk,
            'anonima': '',
            'data_recebimento': timezone.localdate().isoformat(),
            'status': Doacao.CONFIRMADA,
            'finalidade': Doacao.FINALIDADE_GERAL,
            'descricao_finalidade': '',
            'praia': '',
            'acao': '',
            'observacoes': '',
            'referencia_comprovante': '',
            'financeira-valor': '',
            'financeira-forma_recebimento': '',
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '1',
            'itens-MAX_NUM_FORMS': '1000',
            'itens-0-material': '',
            'itens-0-nome': '',
            'itens-0-categoria': 'Alimentos',
            'itens-0-unidade_nova': '',
            'itens-0-quantidade': '1',
            'itens-0-condicao': ItemDoacaoMaterial.CONDICAO_NOVO,
            'itens-0-observacoes': '',
        })

        mensagem_nome = 'Selecione um material existente ou informe o nome de um novo.'
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode().count(mensagem_nome), 1)
        self.assertEqual(Doacao.objects.count(), 0)

    def test_doador_exige_nome_e_email_ou_telefone(self):
        form = DoadorForm(data={
            'tipo': Doador.PESSOA_FISICA,
            'nome': '',
            'documento': '',
            'email': '',
            'telefone': '',
            'voluntario': '',
            'ativo': 'on',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('nome', form.errors)
        self.assertIn('email', form.errors)

    def test_doador_nao_aceita_documento_email_ou_telefone_repetido(self):
        self.doador.documento = '12345678901'
        self.doador.email = 'doador@example.com'
        self.doador.telefone = '11999999999'
        self.doador.save()

        for field, value in (
            ('documento', '123.456.789-01'),
            ('email', 'DOADOR@EXAMPLE.COM'),
            ('telefone', '(11) 99999-9999'),
        ):
            data = {
                'tipo': Doador.PESSOA_FISICA,
                'nome': 'Outro doador',
                'documento': '',
                'email': 'outro@example.com',
                'telefone': '',
                'voluntario': '',
                'ativo': 'on',
            }
            data[field] = value
            form = DoadorForm(data=data)
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)

    def test_doador_inline_nao_aceita_telefone_repetido_com_mascara(self):
        self.doador.telefone = '11999999999'
        self.doador.save()

        form = DoadorInlineForm(data={
            'tipo': Doador.PESSOA_FISICA,
            'nome': 'Outro doador',
            'documento': '',
            'email': 'outro@example.com',
            'telefone': '(11) 99999-9999',
            'voluntario': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('telefone', form.errors)
        self.assertEqual(
            str(form.errors['telefone'][0]),
            'Já existe um doador cadastrado com este telefone.',
        )

    def test_edicao_doador_nao_permite_repetir_email_ou_telefone(self):
        self.doador.email = 'doador@example.com'
        self.doador.telefone = '11999999999'
        self.doador.save()
        outro_doador = Doador.objects.create(
            tipo=Doador.PESSOA_JURIDICA,
            nome='Outro doador',
            email='outro@example.com',
            telefone='13988887777',
            cadastrado_por=self.usuario,
            cadastrado_por_nome='Administrador',
        )

        for campo, valor, mensagem in (
            (
                'email',
                ' OUTRO@example.com ',
                'Já existe um doador cadastrado com este e-mail.',
            ),
            (
                'telefone',
                '(13) 98888-7777',
                'Já existe um doador cadastrado com este telefone.',
            ),
        ):
            with self.subTest(campo=campo):
                dados = {
                    'tipo': Doador.PESSOA_FISICA,
                    'nome': 'Doador Teste editado',
                    'documento': '',
                    'email': 'doador@example.com',
                    'telefone': '(11) 99999-9999',
                    'voluntario': '',
                    'ativo': 'on',
                }
                dados[campo] = valor
                resposta = self.client.post(
                    reverse('editar_doador', args=[self.doador.pk]),
                    dados,
                )

                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, mensagem)
                self.assertIn(
                    'Não foi possível atualizar o cadastro do doador "Doador Teste editado". '
                    'Corrija os campos destacados no formulário e tente novamente.',
                    [str(mensagem) for mensagem in resposta.wsgi_request._messages],
                )
                self.doador.refresh_from_db()
                outro_doador.refresh_from_db()
                self.assertEqual(self.doador.nome, 'Doador Teste')
                self.assertEqual(self.doador.email, 'doador@example.com')
                self.assertEqual(self.doador.telefone, '11999999999')
                self.assertEqual(outro_doador.email, 'outro@example.com')
                self.assertEqual(outro_doador.telefone, '13988887777')

    def test_edicao_doador_permite_manter_proprio_email_e_telefone(self):
        self.doador.email = 'doador@example.com'
        self.doador.telefone = '11999999999'
        self.doador.save()

        resposta = self.client.post(
            reverse('editar_doador', args=[self.doador.pk]),
            {
                'tipo': Doador.PESSOA_FISICA,
                'nome': 'Doador Teste atualizado',
                'documento': '',
                'email': ' DOADOR@example.com ',
                'telefone': '(11) 99999-9999',
                'voluntario': '',
                'ativo': 'on',
            },
        )

        self.assertEqual(resposta.status_code, 302)
        self.doador.refresh_from_db()
        self.assertEqual(self.doador.nome, 'Doador Teste atualizado')
        self.assertEqual(self.doador.email, 'doador@example.com')
        self.assertEqual(self.doador.telefone, '11999999999')
        self.assertIn(
            'O doador "Doador Teste atualizado" foi atualizado com sucesso.',
            [str(mensagem) for mensagem in resposta.wsgi_request._messages],
        )

    def test_cadastro_doador_invalido_exibe_erros_e_toast_sem_repetir_mensagens(self):
        response = self.client.post(reverse('cadastro_doador'), {
            'tipo': Doador.PESSOA_FISICA,
            'nome': '',
            'documento': '',
            'email': '',
            'telefone': '',
            'voluntario': '',
            'ativo': 'on',
        })
        self.assertEqual(response.status_code, 200)
        conteudo = response.content.decode()
        self.assertEqual(conteudo.count('Informe o nome do doador.'), 1)
        self.assertEqual(
            conteudo.count('Informe o e-mail ou o telefone do doador.'),
            1,
        )
        self.assertEqual(
            conteudo.count(
                'Não foi possível cadastrar o doador. '
                'Corrija os campos destacados no formulário e tente novamente.'
            ),
            1,
        )
        self.assertEqual(conteudo.count('data-toast'), 1)

    def test_cadastro_doador_valido_exibe_toast_de_sucesso(self):
        response = self.client.post(
            reverse('cadastro_doador'),
            {
                'tipo': Doador.PESSOA_FISICA,
                'nome': 'Nova doadora',
                'documento': '',
                'email': 'nova-doadora@example.com',
                'telefone': '',
                'voluntario': '',
                'ativo': 'on',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('doadores'))
        self.assertContains(
            response,
            'O doador &quot;Nova doadora&quot; foi cadastrado com sucesso.',
        )
        self.assertEqual(response.content.decode().count('data-toast'), 1)
