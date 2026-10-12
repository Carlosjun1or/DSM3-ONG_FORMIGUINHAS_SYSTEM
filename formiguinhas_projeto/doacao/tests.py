from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acao.models import Acao
from praia.models import Praia
from usuario.models import Usuario, Voluntario

from .forms import DoadorForm, DoadorInlineForm, DoacaoForm
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

    def test_menu_lateral_marca_apenas_controle_de_doadores(self):
        resposta_doadores = self.client.get(reverse('doadores'))
        self.assertContains(
            resposta_doadores,
            '<a href="/doacao/doadores/" class="sidebar-link active">Controle de Doadores</a>',
            html=True,
        )
        self.assertContains(
            resposta_doadores,
            '<a href="/doacao/" class="sidebar-link ">Controle de Doações</a>',
            html=True,
        )

        resposta_doacoes = self.client.get(reverse('doacoes'))
        self.assertContains(
            resposta_doacoes,
            '<a href="/doacao/" class="sidebar-link active">Controle de Doações</a>',
            html=True,
        )
        self.assertContains(
            resposta_doacoes,
            '<a href="/doacao/doadores/" class="sidebar-link ">Controle de Doadores</a>',
            html=True,
        )

    def test_controle_de_doacoes_pagina_e_preserva_filtros(self):
        for indice in range(21):
            Doacao.objects.create(
                tipo=Doacao.MATERIAL,
                doador=self.doador,
                data_recebimento=timezone.localdate(),
                status=Doacao.PENDENTE,
                registrado_por=self.usuario,
                registrado_por_nome='Administrador',
                registrado_por_tipo='ADMIN',
            )

        response = self.client.get(
            reverse('doacoes'),
            {'tipo': Doacao.MATERIAL, 'status': Doacao.PENDENTE, 'page': '2'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pagina'].number, 2)
        self.assertEqual(response.context['pagina'].paginator.count, 21)
        self.assertEqual(
            response.context['filtros_query'],
            'tipo=MATERIAL&status=PENDENTE',
        )
        self.assertContains(response, 'tipo=MATERIAL&amp;status=PENDENTE&amp;page=1')

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

    def test_cadastro_material_aceita_varios_itens(self):
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
            'itens-0-nome': 'Luvas',
            'itens-0-categoria': 'Proteção',
            'itens-0-quantidade': '20',
            'itens-0-unidade': 'unidades',
            'itens-0-condicao': 'NOVO',
            'itens-0-observacoes': '',
            'itens-1-nome': 'Sacos de lixo',
            'itens-1-categoria': 'Limpeza',
            'itens-1-quantidade': '5',
            'itens-1-unidade': 'pacotes',
            'itens-1-condicao': 'NOVO',
            'itens-1-observacoes': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ItemDoacaoMaterial.objects.count(), 2)

    def test_coordenador_nao_pode_cancelar_doacao(self):
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

        response = self.client.post(
            reverse('atualizar_status_doacao', args=[doacao.pk]),
            {'status': Doacao.CANCELADA},
        )
        self.assertEqual(response.status_code, 302)
        doacao.refresh_from_db()
        self.assertEqual(doacao.status, Doacao.PENDENTE)

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
        self.assertContains(response, 'Não foi possível salvar a doação.')
        self.assertContains(response, 'Informe o doador ou marque a doação como anônima.')

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

    def test_doador_nao_aceita_documento_ou_email_repetido(self):
        self.doador.documento = '12345678901'
        self.doador.email = 'doador@example.com'
        self.doador.telefone = '11999999999'
        self.doador.save()

        for field, value in (
            ('documento', '123.456.789-01'),
            ('email', 'DOADOR@EXAMPLE.COM'),
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

    def test_cadastro_doador_invalido_exibe_mensagem(self):
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
        self.assertContains(
            response,
            'Não foi possível cadastrar o doador. Verifique os erros informados.',
        )
