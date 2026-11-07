from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from praia.models import Praia
from usuario.models import Usuario, Voluntario

from auditoria.models import EventoAuditoria
from residuo.models import ColetaResiduo, ItemColetaResiduo
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

    def test_listagem_condominios_exibe_breadcrumb_simplificado(self):
        self.autenticar(self.admin)

        resposta = self.client.get(reverse('condominios'))

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            '<span aria-current="page">Controle de Condomínios</span>',
        )

    def test_cadastro_condominio_exibe_breadcrumb_hierarquico(self):
        self.autenticar(self.admin)

        resposta = self.client.get(reverse('cadastrar_condominio'))

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/condominio/">Controle de Condomínios</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Cadastro de Condomínio</span>',
        )

    def test_detalhe_condominio_exibe_breadcrumb_hierarquico(self):
        self.autenticar(self.admin)

        resposta = self.client.get(
            reverse('detalhe_condominio', args=[self.condominio.id_condominio]),
        )

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/condominio/">Controle de Condomínios</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Detalhes de Condomínio - Condomínio Simulado</span>',
        )

    def test_cadastro_bag_exibe_breadcrumb_hierarquico(self):
        self.autenticar(self.admin)

        resposta = self.client.get(reverse('cadastrar_bag'))

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/condominio/bags/">Controle de Bags</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Cadastro de Bag</span>',
        )

    def test_edicao_bag_exibe_breadcrumb_hierarquico(self):
        self.autenticar(self.admin)

        resposta = self.client.get(
            reverse('editar_bag', args=[self.bag.id_bag]),
        )

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/condominio/bags/">Controle de Bags</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Edição de Bag - BAG-TESTE-001</span>',
        )

    def test_detalhe_bag_exibe_breadcrumb_hierarquico(self):
        self.autenticar(self.admin)

        resposta = self.client.get(
            reverse('detalhe_bag', args=[self.bag.id_bag]),
        )

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/condominio/bags/">Controle de Bags</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Detalhes da Bag BAG-TESTE-001 - Condomínio Simulado</span>',
        )

    def test_detalhe_bag_exibe_formulario_inline_e_registra_coleta(self):
        self.autenticar(self.admin)
        url_detalhe = reverse('detalhe_bag', args=[self.bag.id_bag])

        detalhe = self.client.get(url_detalhe)

        self.assertContains(detalhe, 'id="registrar-coleta"')
        self.assertContains(
            detalhe,
            'data-detail-panel-toggle="registrar-coleta"',
        )
        self.assertContains(
            detalhe,
            'aria-expanded="false" aria-controls="registrar-coleta"',
        )
        self.assertContains(detalhe, 'id="registrar-coleta" hidden')
        self.assertContains(detalhe, 'name="formulario" value="registrar-coleta"')
        self.assertContains(detalhe, 'Tipo de resíduo')

        resposta = self.client.post(
            url_detalhe,
            {
                'formulario': 'registrar-coleta',
                'data_coleta': '2026-10-25T18:00',
                'observacao': 'Coleta realizada no condomínio.',
                'tipo': 'PLASTICO',
                'categoria': 'RECICLAVEL',
                'quantidade': '3.50',
                'unidade': 'KG',
                'observacao': 'Garrafas e embalagens.',
            },
        )

        self.assertRedirects(resposta, f'{url_detalhe}#coletas', fetch_redirect_response=False)
        coleta = ColetaResiduo.objects.get(bag_id=self.bag.id_bag)
        item = ItemColetaResiduo.objects.get(coleta=coleta)
        self.assertEqual(coleta.origem, 'BAG')
        self.assertEqual(coleta.observacao, 'Garrafas e embalagens.')
        self.assertEqual(item.tipo, 'PLASTICO')
        self.assertEqual(item.quantidade, 3.5)

    def test_detalhe_bag_nao_registra_coleta_sem_tipo_e_categoria(self):
        self.autenticar(self.admin)
        url_detalhe = reverse('detalhe_bag', args=[self.bag.id_bag])

        resposta = self.client.post(
            url_detalhe,
            {
                'formulario': 'registrar-coleta',
                'data_coleta': '2026-10-25T18:00',
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Este campo é obrigatório.')
        self.assertContains(
            resposta,
            'aria-expanded="true" aria-controls="registrar-coleta"',
        )
        self.assertContains(resposta, 'id="registrar-coleta">')
        self.assertFalse(ColetaResiduo.objects.filter(bag_id=self.bag.id_bag).exists())
        self.assertFalse(
            resposta.content.decode().count('href="#registrar-coleta"'),
        )

    def test_detalhe_bag_exibe_formulario_inline_de_movimentacao(self):
        self.autenticar(self.admin)
        url_detalhe = reverse('detalhe_bag', args=[self.bag.id_bag])

        resposta = self.client.get(url_detalhe)

        self.assertContains(resposta, 'id="movimentacoes"')
        self.assertContains(
            resposta,
            'name="formulario" value="registrar-movimentacao"',
        )
        self.assertContains(
            resposta,
            'data-detail-panel-toggle="registrar-movimentacao"',
        )
        self.assertContains(
            resposta,
            'data-detail-panel-fragment="movimentacoes"',
        )
        self.assertContains(resposta, 'id="registrar-movimentacao" hidden')
        self.assertContains(
            resposta,
            '<progress class="bag-occupancy-progress" value="50" max="100"',
        )
        self.assertContains(resposta, 'Tipo de movimentação')
        self.assertContains(resposta, 'Novo status')

    def test_botao_movimentar_abre_detalhes_da_bag_no_formulario(self):
        self.autenticar(self.admin)
        url_detalhe = reverse('detalhe_bag', args=[self.bag.id_bag])

        lista_bags = self.client.get(reverse('bags'))
        detalhe_condominio = self.client.get(
            reverse('detalhe_condominio', args=[self.condominio.id_condominio]),
        )

        self.assertContains(
            lista_bags,
            f'href="{url_detalhe}#movimentacoes">Movimentar</a>',
        )
        self.assertContains(
            detalhe_condominio,
            f'href="{url_detalhe}#movimentacoes" class="btn btn-outline btn-small">Movimentar</a>',
        )
        destino = self.client.get(f'{url_detalhe}#movimentacoes')
        self.assertEqual(destino.status_code, 200)
        self.assertContains(destino, 'name="formulario" value="registrar-movimentacao"')
        self.assertContains(destino, 'data-detail-panel-fragment="movimentacoes"')

    def test_rotas_externas_de_coleta_e_movimentacao_de_bag_foram_removidas(self):
        self.autenticar(self.admin)

        coleta_externa = self.client.get(
            f'/residuo/bag/{self.bag.id_bag}/cadastrar/',
        )
        movimentacao_externa = self.client.get(
            f'/condominio/bags/{self.bag.id_bag}/movimentar/',
        )

        self.assertEqual(coleta_externa.status_code, 404)
        self.assertEqual(movimentacao_externa.status_code, 404)

    def test_detalhe_bag_registra_movimentacao_inline_e_atualiza_status(self):
        self.autenticar(self.admin)
        url_detalhe = reverse('detalhe_bag', args=[self.bag.id_bag])

        resposta = self.client.post(
            url_detalhe,
            {
                'formulario': 'registrar-movimentacao',
                'tipo': 'RETIRADA',
                'status_novo': 'RETIRADA',
                'data_movimentacao': '2026-10-25T18:00',
                'observacao': 'Bag retirada para transporte.',
            },
        )

        self.assertRedirects(
            resposta,
            f'{url_detalhe}#movimentacoes',
            fetch_redirect_response=False,
        )
        self.bag.refresh_from_db()
        self.assertEqual(self.bag.status, 'RETIRADA')
        movimentacao = MovimentacaoBag.objects.get(bag=self.bag)
        self.assertEqual(movimentacao.status_anterior, 'EM_USO')
        self.assertEqual(movimentacao.status_novo, 'RETIRADA')
        self.assertEqual(movimentacao.registrado_por, self.admin)

    def test_detalhe_bag_nao_registra_movimentacao_incompleta(self):
        self.autenticar(self.admin)
        url_detalhe = reverse('detalhe_bag', args=[self.bag.id_bag])

        resposta = self.client.post(
            url_detalhe,
            {'formulario': 'registrar-movimentacao'},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Este campo é obrigatório.')
        self.assertContains(
            resposta,
            'aria-expanded="true" aria-controls="registrar-movimentacao"',
        )
        self.assertContains(resposta, 'id="registrar-movimentacao">')
        self.bag.refresh_from_db()
        self.assertEqual(self.bag.status, 'EM_USO')
        self.assertFalse(MovimentacaoBag.objects.filter(bag=self.bag).exists())

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
            reverse('detalhe_bag', args=[nova_bag.id_bag]),
            {
                'formulario': 'registrar-movimentacao',
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
        self.assertContains(
            detalhe_condominio,
            f'href="{reverse("detalhe_bag", args=[nova_bag.id_bag])}#movimentacoes" class="btn btn-outline btn-small">Movimentar</a>',
        )

    def test_coordenador_nao_visualiza_controles_restritos(self):
        self.autenticar(self.coordenador)

        home = self.client.get(reverse('home'))
        listagem = self.client.get(reverse('condominios'))
        detalhe_condominio = self.client.get(
            reverse('detalhe_condominio', args=[self.condominio.id_condominio]),
        )
        detalhe_bag = self.client.get(
            reverse('detalhe_bag', args=[self.bag.id_bag]),
        )

        self.assertNotContains(home, 'Controle de Condomínios')
        self.assertNotContains(home, 'Controle de Bags')
        self.assertNotContains(home, 'Auditoria global')
        for resposta in (listagem, detalhe_condominio, detalhe_bag):
            self.assertEqual(resposta.status_code, 403)
            self.assertIn(
                'Você não tem permissão para acessar esta tela'.encode(),
                resposta.content,
            )

    def test_menu_lateral_destaca_bags_sem_destacar_condominios(self):
        self.autenticar(self.admin)

        for url in (
            reverse('bags'),
            reverse('cadastrar_bag'),
            reverse('detalhe_bag', args=[self.bag.id_bag]),
            reverse('editar_bag', args=[self.bag.id_bag]),
        ):
            resposta = self.client.get(url)
            self.assertEqual(resposta.status_code, 200)
            self.assertContains(
                resposta,
                'href="/condominio/bags/" class="sidebar-link active"',
            )
            self.assertContains(
                resposta,
                '<span>Bags</span>',
            )
            self.assertContains(
                resposta,
                'href="/condominio/" class="sidebar-link "',
            )
            self.assertContains(
                resposta,
                '<span>Condomínios</span>',
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

        self.assertIn(
            'O status da bag "BAG-TESTE-001" foi atualizado para Cheia, '
            'e a movimentação foi registrada.',
            [str(mensagem) for mensagem in response.wsgi_request._messages],
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

        self.assertEqual(response.status_code, 403)
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
        self.assertEqual(resposta_coordenador.status_code, 403)

    def test_lista_de_bags_destaca_codigo_e_exibe_condominio_como_contexto(self):
        self.autenticar(self.admin)

        resposta = self.client.get(reverse('bags'))

        self.assertContains(
            resposta,
            '<span class="record-card-eyebrow">Condomínio Simulado</span>',
        )
        self.assertContains(
            resposta,
            f'<h3><a href="{reverse("detalhe_bag", args=[self.bag.id_bag])}">Bag - BAG-TESTE-001</a></h3>',
        )

    def test_controle_de_bags_pagina_resultados_e_preserva_filtro(self):
        for indice in range(2, 23):
            Bag.objects.create(
                codigo=f'BAG-TESTE-{indice:03d}',
                condominio=self.condominio,
                status='EM_USO',
            )
        self.autenticar(self.admin)

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

    @patch('condominio.views.test_mongo_connection', return_value=(False, 'offline', {}))
    def test_controle_de_bags_filtra_por_condominio(self, _mongo_connection):
        outro_condominio = Condominio.objects.create(
            nome='Condomínio de Outra Praia',
            responsavel_nome='Outro Responsável',
            responsavel_telefone='13988887777',
            responsavel_email='outro@teste.org',
            endereco='Rua Diferente',
            numero='200',
            bairro='Gonzaga',
            cidade='Santos',
            estado='SP',
            praia=self.praia,
            porte='MEDIO',
            confiabilidade='MEDIA',
            cadastrado_por=self.admin,
            cadastrado_por_nome=self.admin.id_voluntario.nome,
        )
        Bag.objects.create(
            codigo='BAG-OUTRO-COND',
            condominio=outro_condominio,
            status='DISPONIVEL',
        )
        self.autenticar(self.admin)

        response = self.client.get(
            reverse('bags'),
            {'condominio': str(self.condominio.id_condominio)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pagina'].paginator.count, 1)
        self.assertEqual(
            response.context['filtros_query'],
            f'condominio={self.condominio.id_condominio}',
        )
        self.assertContains(response, 'BAG-TESTE-001')
        self.assertNotContains(response, 'BAG-OUTRO-COND')
        self.assertContains(response, 'Todos os condomínios')
        self.assertContains(response, 'Condomínio de Outra Praia')

    @patch('condominio.views.test_mongo_connection', return_value=(False, 'offline', {}))
    def test_alteracao_de_status_preserva_filtro_de_condominio(self, _mongo_connection):
        self.autenticar(self.admin)

        response = self.client.post(
            reverse('atualizar_status_bag', args=[self.bag.id_bag]),
            {
                'status': 'CHEIA',
                'filtro_condominio': str(self.condominio.id_condominio),
            },
        )

        self.assertRedirects(
            response,
            f'{reverse("bags")}?condominio={self.condominio.id_condominio}',
            fetch_redirect_response=False,
        )

    def test_usuario_consegue_consultar_tela_geral_de_auditoria(self):
        self.autenticar(self.admin)

        response = self.client.get(reverse('auditorias'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auditoria/auditorias.html')

    def test_coordenador_nao_visualiza_auditoria_global_nas_rotas(self):
        self.autenticar(self.coordenador)

        auditoria_global = self.client.get(reverse('auditoria_global'))
        auditoria_legada = self.client.get(reverse('auditorias'))

        for resposta in (auditoria_global, auditoria_legada):
            self.assertEqual(resposta.status_code, 403)
            self.assertIn(b'Acesso bloqueado', resposta.content)

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
            reverse('detalhe_bag', args=[self.bag.id_bag]),
            {
                'formulario': 'registrar-movimentacao',
                'tipo': 'REGISTRO_CHEIA',
                'status_novo': 'CHEIA',
                'data_movimentacao': '2026-09-21T21:00',
                'observacao': 'Tentativa não autorizada.',
            },
        )

        for resposta in (
            cadastro_condominio,
            edicao_condominio,
            cadastro_bag,
            movimentacao,
        ):
            self.assertEqual(resposta.status_code, 403)
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
            reverse('detalhe_bag', args=[bag.id_bag]),
            {
                'formulario': 'registrar-movimentacao',
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
