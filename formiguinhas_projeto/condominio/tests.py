from datetime import date

from django.test import TestCase
from django.urls import reverse

from praia.models import Praia
from usuario.models import Usuario, Voluntario

from auditoria.models import EventoAuditoria
from .models import Bag, Condominio, MovimentacaoBag


class ControleCondominioPermissoesTests(TestCase):
    def setUp(self):
        self.admin = self.criar_usuario(
            nome='Administrador de Teste',
            email='admin.controle@teste.org',
            tipo='ADMIN',
        )
        self.coordenador = self.criar_usuario(
            nome='Coordenador de Teste',
            email='coordenador.controle@teste.org',
            tipo='COORDENADOR',
        )
        self.praia = Praia.objects.create(
            nome='Praia de Teste',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
        )
        self.condominio = Condominio.objects.create(
            nome='Condomínio Simulado',
            responsavel_nome='Responsável Simulado',
            responsavel_telefone='13999999999',
            responsavel_email='responsavel@teste.org',
            endereco='Rua das Formiguinhas',
            numero='100',
            bairro='Centro',
            cidade='Santos',
            estado='SP',
            cep='11000-000',
            praia=self.praia,
            porte='GRANDE',
            confiabilidade='ALTA',
            cadastrado_por=self.admin,
            cadastrado_por_nome=self.admin.id_voluntario.nome,
        )
        self.bag = Bag.objects.create(
            codigo='BAG-TESTE-001',
            condominio=self.condominio,
            status='EM_USO',
            peso_atual_kg='12.50',
            percentual_ocupacao=50,
            cadastrado_por=self.admin,
            cadastrado_por_nome=self.admin.id_voluntario.nome,
        )

    def criar_usuario(self, nome, email, tipo):
        voluntario = Voluntario.objects.create(
            nome=nome,
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua de Teste, 1',
            telefone='13999999999',
            email=email,
        )
        return Usuario.objects.create(
            id_voluntario=voluntario,
            tipo=tipo,
            senha='senha-de-teste',
        )

    def autenticar(self, usuario):
        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_tipo'] = usuario.tipo
        session['usuario_nome'] = usuario.id_voluntario.nome
        session.save()

    def dados_condominio(self, nome='Novo Condomínio'):
        return {
            'nome': nome,
            'responsavel_nome': 'Novo Responsável',
            'responsavel_telefone': '(13) 98888-7777',
            'responsavel_email': 'novo.responsavel@teste.org',
            'endereco': 'Avenida Nova',
            'numero': '200',
            'complemento': '',
            'bairro': 'Boqueirão',
            'cidade': 'Santos',
            'estado': 'SP',
            'cep': '11000-001',
            'praia': str(self.praia.id_praia),
            'porte': 'MEDIO',
            'confiabilidade': 'EM_AVALIACAO',
            'status': 'ATIVO',
            'observacoes': 'Cadastro simulado para teste.',
        }

    def test_admin_consegue_cadastrar_editar_e_movimentar(self):
        self.autenticar(self.admin)

        cadastro = self.client.post(
            reverse('cadastrar_condominio'),
            self.dados_condominio(),
        )
        self.assertEqual(cadastro.status_code, 302)
        novo_condominio = Condominio.objects.get(nome='Novo Condomínio')
        self.assertEqual(novo_condominio.cadastrado_por, self.admin)

        edicao = self.client.post(
            reverse('editar_condominio', args=[novo_condominio.id_condominio]),
            {**self.dados_condominio('Condomínio Editado'), 'status': 'INATIVO'},
        )
        self.assertEqual(edicao.status_code, 302)
        novo_condominio.refresh_from_db()
        self.assertEqual(novo_condominio.nome, 'Condomínio Editado')
        self.assertEqual(novo_condominio.ultimo_editado_por, self.admin)

        cadastro_bag = self.client.post(
            reverse('cadastrar_bag'),
            {
                'codigo': 'BAG-TESTE-002',
                'condominio': str(novo_condominio.id_condominio),
                'status': 'DISPONIVEL',
                'peso_atual_kg': '0',
                'percentual_ocupacao': '0',
                'observacoes': 'Bag simulada.',
            },
        )
        self.assertEqual(cadastro_bag.status_code, 302)
        nova_bag = Bag.objects.get(codigo='BAG-TESTE-002')
        self.assertEqual(nova_bag.cadastrado_por, self.admin)

        movimentacao = self.client.post(
            reverse('cadastrar_movimentacao_bag', args=[nova_bag.id_bag]),
            {
                'tipo': 'INICIO_USO',
                'status_novo': 'EM_USO',
                'data_movimentacao': '2026-09-21T21:00',
                'observacao': 'Início do uso simulado.',
            },
        )
        self.assertEqual(movimentacao.status_code, 302)
        nova_bag.refresh_from_db()
        self.assertEqual(nova_bag.status, 'EM_USO')
        self.assertEqual(
            MovimentacaoBag.objects.filter(bag=nova_bag).count(),
            1,
        )
        detalhe_condominio = self.client.get(
            reverse('detalhe_condominio', args=[novo_condominio.id_condominio]),
        )
        detalhe_bag = self.client.get(
            reverse('detalhe_bag', args=[nova_bag.id_bag]),
        )
        self.assertContains(detalhe_condominio, 'Movimentar')
        self.assertContains(detalhe_condominio, 'Ver auditoria completa')
        self.assertContains(detalhe_bag, 'Editar bag')
        self.assertContains(detalhe_bag, 'Registrar coleta')

    def test_coordenador_consegue_visualizar_dados(self):
        self.autenticar(self.coordenador)

        listagem = self.client.get(reverse('condominios'))
        detalhe_condominio = self.client.get(
            reverse('detalhe_condominio', args=[self.condominio.id_condominio]),
        )
        detalhe_bag = self.client.get(
            reverse('detalhe_bag', args=[self.bag.id_bag]),
        )

        self.assertEqual(listagem.status_code, 200)
        self.assertEqual(detalhe_condominio.status_code, 200)
        self.assertEqual(detalhe_bag.status_code, 200)
        self.assertContains(listagem, 'Condomínio Simulado')
        self.assertContains(detalhe_bag, 'BAG-TESTE-001')
        self.assertContains(detalhe_condominio, 'Bags cadastradas')
        self.assertContains(detalhe_condominio, 'Movimentações recentes')
        self.assertContains(detalhe_bag, 'Coletas de resíduos')
        self.assertContains(detalhe_bag, 'Histórico de movimentações')
        self.assertContains(detalhe_bag, 'Auditoria da bag')
        self.assertNotContains(
            detalhe_bag,
            reverse('editar_bag', args=[self.bag.id_bag]),
        )
        self.assertNotContains(
            detalhe_condominio,
            reverse('editar_condominio', args=[self.condominio.id_condominio]),
        )

    def test_admin_altera_status_direto_na_lista_com_movimentacao_e_auditoria(self):
        self.autenticar(self.admin)

        response = self.client.post(
            reverse('atualizar_status_bag', args=[self.bag.id_bag]),
            {
                'status': 'CHEIA',
                'busca': 'BAG-TESTE',
                'filtro_status': 'EM_USO',
            },
        )

        self.assertRedirects(
            response,
            reverse('bags') + '?busca=BAG-TESTE&status=EM_USO',
        )
        self.bag.refresh_from_db()
        self.assertEqual(self.bag.status, 'CHEIA')
        movimentacao = MovimentacaoBag.objects.get(bag=self.bag)
        self.assertEqual(movimentacao.tipo, 'OUTRO')
        self.assertEqual(movimentacao.status_anterior, 'EM_USO')
        self.assertEqual(movimentacao.status_novo, 'CHEIA')
        self.assertIn('diretamente pelo controle', movimentacao.observacao)
        self.assertTrue(EventoAuditoria.objects.filter(
            entidade='MOVIMENTACAO',
            id_registro=movimentacao.id_movimentacao,
            usuario=self.admin,
        ).exists())
        self.assertTrue(EventoAuditoria.objects.filter(
            entidade='BAG',
            id_registro=self.bag.id_bag,
            acao='MUDANCA_STATUS',
            usuario=self.admin,
        ).exists())

    def test_status_invalido_nao_altera_bag_nem_cria_movimentacao(self):
        self.autenticar(self.admin)

        response = self.client.post(
            reverse('atualizar_status_bag', args=[self.bag.id_bag]),
            {'status': 'INVALIDO'},
        )

        self.assertRedirects(response, reverse('bags'))
        self.bag.refresh_from_db()
        self.assertEqual(self.bag.status, 'EM_USO')
        self.assertFalse(MovimentacaoBag.objects.filter(bag=self.bag).exists())
        self.assertTrue(response.wsgi_request._messages)

    def test_coordenador_nao_altera_status_da_bag_pela_lista(self):
        self.autenticar(self.coordenador)

        response = self.client.post(
            reverse('atualizar_status_bag', args=[self.bag.id_bag]),
            {'status': 'CHEIA'},
        )

        self.assertRedirects(response, reverse('bags'))
        self.bag.refresh_from_db()
        self.assertEqual(self.bag.status, 'EM_USO')
        self.assertFalse(MovimentacaoBag.objects.filter(bag=self.bag).exists())

    def test_lista_exibe_seletor_de_status_somente_para_admin(self):
        self.autenticar(self.admin)
        resposta_admin = self.client.get(reverse('bags'))
        self.assertContains(resposta_admin, 'name="status"')
        self.assertContains(resposta_admin, 'Status da bag BAG-TESTE-001')

        self.autenticar(self.coordenador)
        resposta_coordenador = self.client.get(reverse('bags'))
        self.assertNotContains(resposta_coordenador, 'bag-status-select')
        self.assertContains(resposta_coordenador, 'Em uso')

    def test_controle_de_bags_pagina_resultados_e_preserva_filtro(self):
        for indice in range(2, 23):
            Bag.objects.create(
                codigo=f'BAG-TESTE-{indice:03d}',
                condominio=self.condominio,
                status='EM_USO',
            )
        self.autenticar(self.coordenador)

        response = self.client.get(
            reverse('bags'),
            {'status': 'EM_USO', 'page': '2'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pagina'].number, 2)
        self.assertEqual(response.context['pagina'].paginator.count, 22)
        self.assertEqual(response.context['filtros_query'], 'status=EM_USO')
        self.assertContains(response, 'BAG-TESTE-021')
        self.assertNotContains(response, 'BAG-TESTE-020')

    def test_usuario_consegue_consultar_tela_geral_de_auditoria(self):
        self.autenticar(self.admin)

        response = self.client.get(reverse('auditorias'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sistema/auditorias.html')

    def test_coordenador_nao_consegue_alterar_nenhum_fluxo(self):
        self.autenticar(self.coordenador)

        cadastro_condominio = self.client.post(
            reverse('cadastrar_condominio'),
            self.dados_condominio('Tentativa do Coordenador'),
        )
        edicao_condominio = self.client.post(
            reverse('editar_condominio', args=[self.condominio.id_condominio]),
            {**self.dados_condominio('Condomínio Alterado'), 'status': 'BLOQUEADO'},
        )
        cadastro_bag = self.client.post(
            reverse('cadastrar_bag'),
            {
                'codigo': 'BAG-COORD-001',
                'condominio': str(self.condominio.id_condominio),
                'status': 'DISPONIVEL',
                'peso_atual_kg': '0',
                'percentual_ocupacao': '0',
                'observacoes': '',
            },
        )
        movimentacao = self.client.post(
            reverse('cadastrar_movimentacao_bag', args=[self.bag.id_bag]),
            {
                'tipo': 'REGISTRO_CHEIA',
                'status_novo': 'CHEIA',
                'data_movimentacao': '2026-09-21T21:00',
                'observacao': 'Tentativa não autorizada.',
            },
        )

        self.assertRedirects(cadastro_condominio, reverse('condominios'))
        self.assertRedirects(edicao_condominio, reverse('condominios'))
        self.assertRedirects(cadastro_bag, reverse('condominios'))
        self.assertRedirects(
            movimentacao,
            reverse('detalhe_bag', args=[self.bag.id_bag]),
        )
        self.assertFalse(
            Condominio.objects.filter(nome='Tentativa do Coordenador').exists(),
        )
        self.assertFalse(Bag.objects.filter(codigo='BAG-COORD-001').exists())
        self.bag.refresh_from_db()
        self.assertEqual(self.bag.status, 'EM_USO')
        self.assertEqual(MovimentacaoBag.objects.filter(bag=self.bag).count(), 0)

    def test_admin_gera_auditoria_completa_do_fluxo(self):
        self.autenticar(self.admin)

        cadastro = self.client.post(
            reverse('cadastrar_condominio'),
            self.dados_condominio('Condomínio Auditado'),
        )
        condominio = Condominio.objects.get(nome='Condomínio Auditado')
        self.client.post(
            reverse('editar_condominio', args=[condominio.id_condominio]),
            {**self.dados_condominio('Condomínio Auditado Editado'), 'status': 'ATIVO'},
        )
        self.client.post(
            reverse('cadastrar_bag'),
            {
                'codigo': 'BAG-AUDIT-001',
                'condominio': str(condominio.id_condominio),
                'status': 'DISPONIVEL',
                'peso_atual_kg': '0',
                'percentual_ocupacao': '0',
                'observacoes': '',
            },
        )
        bag = Bag.objects.get(codigo='BAG-AUDIT-001')
        self.client.post(
            reverse('cadastrar_movimentacao_bag', args=[bag.id_bag]),
            {
                'tipo': 'INICIO_USO',
                'status_novo': 'EM_USO',
                'data_movimentacao': '21/09/2026 21:00',
                'observacao': 'Início auditado.',
            },
        )

        auditorias = EventoAuditoria.objects.filter(
            entidade__in=('CONDOMINIO', 'BAG', 'MOVIMENTACAO'),
        )
        self.assertEqual(
            set(auditorias.values_list('acao', flat=True)),
            {'CRIACAO', 'EDICAO', 'MUDANCA_STATUS', 'MOVIMENTACAO'},
        )
        self.assertTrue(
            auditorias.filter(entidade='CONDOMINIO', acao='CRIACAO').exists()
        )
        self.assertTrue(
            auditorias.filter(entidade='BAG', acao='CRIACAO').exists()
        )
        self.assertTrue(
            auditorias.filter(entidade='MOVIMENTACAO', acao='MOVIMENTACAO').exists()
        )
        self.assertTrue(
            auditorias.filter(entidade='BAG', acao='MUDANCA_STATUS').exists()
        )
        self.assertTrue(
            auditorias.filter(usuario=self.admin).count() >= 4
        )
