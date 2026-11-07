from datetime import date, time, timedelta
from decimal import Decimal
import os
from pathlib import Path
from smtplib import SMTPServerDisconnected
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.base import Message
from django.core import mail
from django.db.models import Sum
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from acao.models import Acao
from config.settings import load_local_environment
from doacao.models import Doacao, DoacaoFinanceira
from equipe.models import Equipe, EquipeMembro
from estoque.models import Material
from praia.models import Praia
from residuo.models import ColetaResiduo, ItemColetaResiduo, ResiduoColetado
from .paginacao import paginar_queryset
from .models import Usuario, Voluntario
from .tokens import password_reset_token


class FeedbackTemplateTests(SimpleTestCase):
    def test_template_base_nao_repete_mensagem_identica(self):
        request = RequestFactory().get('/usuario/home/')
        request.session = {}
        request.user = AnonymousUser()
        request.resolver_match = resolve('/usuario/home/')
        mensagem_repetida = 'Feedback duplicado de teste'
        mensagem_distinta = 'Feedback independente de teste'

        html = render_to_string(
            'sistema/template-sistema.html',
            {
                'mensagem': mensagem_repetida,
                'messages': [
                    Message(25, mensagem_repetida),
                    Message(25, mensagem_distinta),
                ],
            },
            request=request,
        )

        self.assertEqual(html.count(mensagem_repetida), 1)
        self.assertEqual(html.count(mensagem_distinta), 1)
        self.assertIn('class="system-feedback-stack"', html)
        self.assertIn('data-system-feedback-toast', html)
        self.assertIn('aria-label="Fechar notificação"', html)


class LocalEnvironmentSettingsTests(SimpleTestCase):
    def test_carrega_variaveis_do_arquivo_env_sem_substituir_ambiente(self):
        with TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / '.env'
            env_path.write_text(
                '# Configuracao local\nEMAIL_HOST=smtp.gmail.com\n'
                'EMAIL_PORT="587"\nEMAIL_HOST_USER=arquivo@gmail.com\n',
                encoding='utf-8',
            )
            with patch.dict(os.environ, {'EMAIL_HOST_USER': 'ambiente@gmail.com'}):
                load_local_environment(env_path)

                self.assertEqual(os.environ['EMAIL_HOST'], 'smtp.gmail.com')
                self.assertEqual(os.environ['EMAIL_PORT'], '587')
                self.assertEqual(os.environ['EMAIL_HOST_USER'], 'ambiente@gmail.com')

    def test_arquivo_env_com_linha_invalida_gera_erro_explicito(self):
        with TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / '.env'
            env_path.write_text('CONFIGURACAO_INVALIDA\n', encoding='utf-8')

            with self.assertRaisesRegex(ValueError, 'linha 1'):
                load_local_environment(env_path)


class PaginacaoTests(SimpleTestCase):
    def test_paginacao_preserva_filtros_e_remove_pagina_anterior(self):
        request = RequestFactory().get(
            '/controle/',
            {'busca': 'Praia Central', 'status': 'ATIVA', 'page': '2'},
        )

        pagina, filtros_query = paginar_queryset(request, list(range(23)))

        self.assertEqual(pagina.number, 2)
        self.assertEqual(pagina.object_list, list(range(20, 23)))
        self.assertEqual(filtros_query, 'busca=Praia+Central&status=ATIVA')

    def test_pagina_invalida_vai_para_ultima_pagina(self):
        request = RequestFactory().get('/controle/', {'page': '999'})

        pagina, _ = paginar_queryset(request, list(range(22)))

        self.assertEqual(pagina.number, 2)
        self.assertEqual(pagina.object_list, [20, 21])


class HomeDashboardTests(TestCase):
    def test_home_exibe_metricas_reais_e_proximas_acoes(self):
        hoje = timezone.localdate()
        voluntarios_ativos_antes = Voluntario.objects.filter(status='ATIVO').count()
        atividades_hoje_antes = Acao.objects.filter(
            data=hoje,
        ).exclude(
            status=Acao.STATUS_CANCELADA,
        ).count()
        doacoes_confirmadas_antes = DoacaoFinanceira.objects.filter(
            doacao__status=Doacao.CONFIRMADA,
        ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua A',
            telefone='11999999999',
            email='administradora@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        inativo = Voluntario.objects.create(
            nome='Voluntário inativo',
            dt_nascimento=date(1992, 1, 1),
            endereco='Rua B',
            telefone='11988888888',
            email='inativo@teste.org',
            status='INATIVO',
        )
        praia = Praia.objects.create(
            nome='Praia Central',
            cidade='Santos',
            latitude='-23.9600',
            longitude='-46.3300',
        )
        acao_de_hoje = Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=hoje,
            horario=time(9, 0),
            local='Ponto de encontro',
            praia=praia,
        )
        acao_futura = Acao.objects.create(
            tipo=Acao.TIPO_COLETA_VOLUNTARIA,
            data=hoje + timedelta(days=1),
            horario=time(14, 30),
            praia=praia,
        )
        Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=hoje,
            horario=time(8, 0),
            praia=praia,
            status=Acao.STATUS_CANCELADA,
        )
        doacao_confirmada = Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            status=Doacao.CONFIRMADA,
            registrado_por_nome='Administradora',
            registrado_por_tipo='ADMIN',
        )
        DoacaoFinanceira.objects.create(
            doacao=doacao_confirmada,
            valor=Decimal('125.50'),
            forma_recebimento=DoacaoFinanceira.PIX,
        )
        doacao_pendente = Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            registrado_por_nome='Administradora',
            registrado_por_tipo='ADMIN',
        )
        DoacaoFinanceira.objects.create(
            doacao=doacao_pendente,
            valor=Decimal('200.00'),
            forma_recebimento=DoacaoFinanceira.PIX,
        )

        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_tipo'] = usuario.tipo
        session.save()

        with patch('acao.mongo_services.get_acoes_collection', return_value=None):
            resposta = self.client.get(reverse('home'))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.context['total_voluntarios_ativos'],
            voluntarios_ativos_antes + 1,
        )
        self.assertEqual(
            resposta.context['atividades_hoje'],
            atividades_hoje_antes + 1,
        )
        self.assertEqual(
            resposta.context['total_doacoes_confirmadas'],
            doacoes_confirmadas_antes + Decimal('125.50'),
        )
        acoes_proximas_ids = [
            acao.id_acao for acao in resposta.context['acoes_proximas']
        ]
        self.assertIn(acao_de_hoje.id_acao, acoes_proximas_ids)
        self.assertIn(acao_futura.id_acao, acoes_proximas_ids)
        self.assertLess(
            acoes_proximas_ids.index(acao_de_hoje.id_acao),
            acoes_proximas_ids.index(acao_futura.id_acao),
        )
        self.assertContains(resposta, 'Bem-vindo, Administradora!')
        self.assertContains(resposta, 'css/style.css')
        self.assertNotContains(resposta, inativo.nome)

    def test_home_exibe_indicadores_de_residuos_e_alertas_com_links_validos(self):
        voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua A',
            telefone='11999999999',
            email='dashboard@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        ResiduoColetado.objects.create(
            unidade='KG',
            quantidade=Decimal('3.25'),
            registrado_por=usuario,
            registrado_por_nome=voluntario.nome,
            registrado_por_tipo=usuario.tipo,
        )
        ResiduoColetado.objects.create(
            unidade='LITRO',
            quantidade=Decimal('11.00'),
            registrado_por=usuario,
            registrado_por_nome=voluntario.nome,
            registrado_por_tipo=usuario.tipo,
        )
        coleta = ColetaResiduo.objects.create(
            origem='BAG',
            registrado_por=usuario,
            registrado_por_nome=voluntario.nome,
            registrado_por_tipo=usuario.tipo,
        )
        ItemColetaResiduo.objects.create(
            coleta=coleta,
            unidade='KG',
            quantidade=Decimal('2.50'),
            registrado_por=usuario,
            registrado_por_nome=voluntario.nome,
            registrado_por_tipo=usuario.tipo,
        )
        ItemColetaResiduo.objects.create(
            coleta=coleta,
            unidade='UNIDADE',
            quantidade=Decimal('7.00'),
            registrado_por=usuario,
            registrado_por_nome=voluntario.nome,
            registrado_por_tipo=usuario.tipo,
        )
        Material.objects.create(
            nome='Material abaixo do mínimo',
            codigo='DASH-LOW',
            categoria='Teste',
            unidade='UNIDADE',
            quantidade_inicial=1,
            estoque_minimo=3,
        )
        Material.objects.create(
            nome='Material suficiente',
            codigo='DASH-OK',
            categoria='Teste',
            unidade='UNIDADE',
            quantidade_inicial=5,
            estoque_minimo=3,
        )
        Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            status=Doacao.PENDENTE,
            registrado_por_nome=voluntario.nome,
            registrado_por_tipo=usuario.tipo,
        )

        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_tipo'] = usuario.tipo
        session['usuario_nome'] = voluntario.nome
        session.save()

        with patch('acao.mongo_services.get_acoes_collection', return_value=None):
            resposta = self.client.get(reverse('home'))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['residuos_kg_mes'], Decimal('5.75'))
        self.assertEqual(resposta.context['total_materiais_baixo_estoque'], 1)
        self.assertEqual(resposta.context['total_doacoes_pendentes'], 1)
        self.assertContains(resposta, '5,8 kg')
        self.assertContains(resposta, 'materiais abaixo do estoque mínimo')
        self.assertContains(resposta, 'doações pendentes de confirmação')
        self.assertContains(resposta, f'href="{reverse("materiais")}"')
        self.assertContains(resposta, f'href="{reverse("doacoes")}"')
        self.assertContains(resposta, f'href="{reverse("cadastro_acao")}"')
        self.assertContains(resposta, f'href="{reverse("cadastro_doacao")}"')
        self.assertContains(
            resposta,
            f'href="{reverse("cadastrar_movimentacao_estoque")}"',
        )

    def test_home_oculta_atalhos_administrativos_de_coordenador(self):
        voluntario = Voluntario.objects.create(
            nome='Coordenadora',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua B',
            telefone='11988888888',
            email='coordenadora-dashboard@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )
        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_tipo'] = usuario.tipo
        session['usuario_nome'] = voluntario.nome
        session.save()

        with patch('acao.mongo_services.get_acoes_collection', return_value=None):
            resposta = self.client.get(reverse('home'))

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.context['is_admin'])
        self.assertTrue(resposta.context['is_coordinator'])
        self.assertContains(resposta, 'Acompanhe suas equipes')
        self.assertContains(resposta, 'Minhas equipes')
        self.assertContains(
            resposta,
            f'href="{reverse("equipes")}?participacao=MINHAS"',
        )
        self.assertContains(
            resposta,
            f'href="{reverse("cadastro_voluntario")}"',
        )
        self.assertNotContains(
            resposta,
            f'href="{reverse("cadastro_acao")}"',
        )
        self.assertNotContains(
            resposta,
            f'href="{reverse("cadastro_doacao")}"',
        )
        self.assertContains(
            resposta,
            f'href="{reverse("doacoes")}"',
        )
        self.assertNotContains(
            resposta,
            f'href="{reverse("cadastrar_movimentacao_estoque")}"',
        )
        self.assertNotContains(
            resposta,
            f'href="{reverse("relatorios")}"',
        )


class LoginPageTests(TestCase):
    def test_login_nao_exibe_cabecalho_do_dashboard(self):
        resposta = self.client.get(reverse('login'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Entrar no sistema')
        self.assertNotContains(resposta, 'Painel administrativo')
        self.assertNotContains(resposta, '> Dashboard <')

    def test_login_valido_cria_sessao_e_redireciona_para_home(self):
        voluntario = Voluntario.objects.create(
            nome='Voluntário de teste',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua de teste',
            telefone='11999999999',
            email='login@teste.org',
        )
        usuario = Usuario(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='',
        )
        usuario.set_password('senha-segura')
        usuario.save()

        resposta = self.client.post(reverse('login'), {
            'email': voluntario.email,
            'senha': 'senha-segura',
        })

        self.assertRedirects(resposta, reverse('home'))
        self.assertEqual(self.client.session['usuario_id'], usuario.id_usuario)
        self.assertEqual(self.client.session['usuario_nome'], voluntario.nome)
        self.assertEqual(self.client.session['usuario_tipo'], usuario.tipo)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PermissoesStatusVoluntarioTests(TestCase):
    def setUp(self):
        mail.outbox.clear()
        self.coordenador_voluntario = Voluntario.objects.create(
            nome='Coordenador',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua A',
            telefone='11999999999',
            email='coordenador@teste.org',
        )
        self.coordenador = Usuario.objects.create(
            id_voluntario=self.coordenador_voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )
        self.voluntario = Voluntario.objects.create(
            nome='Voluntário',
            dt_nascimento=date(1992, 1, 1),
            endereco='Rua B',
            telefone='11988888888',
            email='voluntario@teste.org',
            status='ATIVO',
        )
        session = self.client.session
        session['usuario_id'] = self.coordenador.id_usuario
        session['usuario_tipo'] = self.coordenador.tipo
        session.save()

    def autenticar_como_admin(self):
        self.coordenador.tipo = 'ADMIN'
        self.coordenador.save(update_fields=['tipo'])
        session = self.client.session
        session['usuario_tipo'] = 'ADMIN'
        session.save()

    def test_coordenador_nao_altera_status_pelo_endpoint(self):
        resposta = self.client.post(
            reverse(
                'atualizar_status_voluntario',
                args=[self.voluntario.id_voluntario],
            ),
            {'status': 'INATIVO'},
        )

        self.assertRedirects(resposta, reverse('voluntarios'))
        self.voluntario.refresh_from_db()
        self.assertEqual(self.voluntario.status, 'ATIVO')

    def test_admin_altera_status_e_recebe_feedback(self):
        self.autenticar_como_admin()
        resposta = self.client.post(
            reverse(
                'atualizar_status_voluntario',
                args=[self.voluntario.id_voluntario],
            ),
            {'status': 'INATIVO'},
            follow=True,
        )

        self.assertContains(
            resposta,
            f'O status do voluntário &quot;{self.voluntario.nome}&quot; foi atualizado para Inativo.',
        )
        self.voluntario.refresh_from_db()
        self.assertEqual(self.voluntario.status, 'INATIVO')

    def test_admin_recebe_feedback_ao_excluir_voluntario_com_vinculo_protegido(self):
        equipe = Equipe.objects.create(nome='Equipe com histórico')
        EquipeMembro.objects.create(equipe=equipe, voluntario=self.voluntario)
        self.autenticar_como_admin()

        resposta = self.client.post(
            reverse('excluir_voluntario', args=[self.voluntario.id_voluntario]),
            follow=True,
        )

        self.assertContains(
            resposta,
            'existem vínculos ou registros históricos protegidos',
        )
        self.assertTrue(
            Voluntario.objects.filter(pk=self.voluntario.pk).exists(),
        )
        self.assertTrue(
            EquipeMembro.objects.filter(voluntario=self.voluntario).exists(),
        )

    def test_admin_nao_pode_excluir_o_proprio_voluntario(self):
        self.autenticar_como_admin()

        resposta = self.client.post(
            reverse(
                'excluir_voluntario',
                args=[self.coordenador_voluntario.id_voluntario],
            ),
            follow=True,
        )

        self.assertContains(
            resposta,
            f'Não é possível excluir o voluntário &quot;{self.coordenador_voluntario.nome}&quot;, '
            'pois ele está vinculado à sua própria conta de acesso.',
        )
        self.assertTrue(
            Voluntario.objects.filter(pk=self.coordenador_voluntario.pk).exists(),
        )
        self.assertTrue(
            Usuario.objects.filter(pk=self.coordenador.pk).exists(),
        )

    def test_admin_exclui_voluntario_e_usuario_vinculado(self):
        usuario_vinculado = Usuario.objects.create(
            id_voluntario=self.voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )
        self.autenticar_como_admin()

        resposta = self.client.post(
            reverse('excluir_voluntario', args=[self.voluntario.id_voluntario]),
            follow=True,
        )

        self.assertContains(resposta, 'excluído com sucesso')
        self.assertFalse(
            Voluntario.objects.filter(pk=self.voluntario.pk).exists(),
        )
        self.assertFalse(
            Usuario.objects.filter(pk=usuario_vinculado.pk).exists(),
        )

    def test_coordenador_nao_altera_status_pela_edicao(self):
        resposta = self.client.post(
            reverse('editar_voluntario', args=[self.voluntario.id_voluntario]),
            {
                'nome': self.voluntario.nome,
                'dt_nascimento': '01/01/1992',
                'endereco': self.voluntario.endereco,
                'telefone': self.voluntario.telefone,
                'email': self.voluntario.email,
                'status': 'INATIVO',
            },
        )

        self.assertRedirects(resposta, reverse('voluntarios'))
        self.voluntario.refresh_from_db()
        self.assertEqual(self.voluntario.status, 'ATIVO')

    def test_coordenador_visualiza_status_sem_seletor_na_lista(self):
        resposta = self.client.get(reverse('voluntarios'))

        self.assertContains(resposta, 'Ativo')
        self.assertNotContains(
            resposta,
            f'/voluntarios/{self.voluntario.id_voluntario}/status/',
        )

    def test_usuario_coordenador_nao_aparece_vinculado_a_praia_de_equipe_inativa(self):
        praia = Praia.objects.create(
            nome='Praia de equipe inativa',
            cidade='Santos',
            latitude=-23.9,
            longitude=-46.3,
        )
        equipe = Equipe.objects.create(
            nome='Equipe inativa',
            praia=praia,
            status='INATIVA',
        )
        coordenador_voluntario = Voluntario.objects.create(
            nome='Coordenador de equipe inativa',
            dt_nascimento=date(1991, 1, 1),
            endereco='Rua C',
            telefone='11977777777',
            email='coord-equipe-inativa@teste.org',
        )
        Usuario.objects.create(
            id_voluntario=coordenador_voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )
        EquipeMembro.objects.create(
            equipe=equipe,
            voluntario=coordenador_voluntario,
            papel=EquipeMembro.PAPEL_COORDENADOR,
            status='ATIVO',
        )
        self.autenticar_como_admin()

        resposta = self.client.get(reverse('usuarios'))

        self.assertEqual(resposta.status_code, 200)
        coordenador_exibido = next(
            usuario_item
            for usuario_item in resposta.context['usuarios']
            if usuario_item.id_voluntario_id == coordenador_voluntario.id_voluntario
        )
        self.assertEqual(coordenador_exibido.praias_coordenador, [])
        self.assertContains(resposta, 'Sem equipe ativa')
        self.assertNotContains(resposta, praia.nome)

    def test_menu_lateral_usa_identidade_visual_e_preserva_permissoes(self):
        resposta = self.client.get(reverse('voluntarios'))

        self.assertContains(resposta, 'DA PRAIA')
        self.assertContains(
            resposta,
            'href="/usuario/home/" class="sidebar-brand" aria-label="Ir para a página inicial do sistema"',
        )
        self.assertContains(resposta, 'href="/usuario/voluntarios/" class="sidebar-link active"')
        self.assertContains(
            resposta,
            'href="/static/usuario/icons/sidebar-icons.svg#volunteers"',
        )
        self.assertContains(resposta, 'aria-label="Navegação estrutural"')
        self.assertContains(resposta, 'class="sidebar-toggle"')
        self.assertContains(resposta, 'aria-controls="system-sidebar"')
        self.assertContains(resposta, 'class="sidebar-backdrop"')
        self.assertContains(resposta, 'class="sidebar-link logout-link"')
        self.assertContains(resposta, 'class="sidebar-footer"')
        self.assertContains(resposta, 'sidebar-icons.svg?v=6#logout')
        self.assertLess(
            resposta.content.index(b'</nav>'),
            resposta.content.index(b'<div class="sidebar-footer">'),
        )
        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            '<span aria-current="page">Controle de Voluntários</span>',
        )
        self.assertContains(resposta, 'href="/comunicado/central/" class="notification-link"'        )
        self.assertContains(resposta, 'sidebar-icons.svg?v=5#topbar-bell')
        self.assertContains(resposta, 'class="topbar-user" href="/usuario/perfil/"')
        self.assertContains(resposta, '<span class="topbar-user-initial" aria-hidden="true">V</span>')
        self.assertLess(
            resposta.content.index(b'<aside class="sidebar" id="system-sidebar">'),
            resposta.content.index(b'<header class="topbar">'),
        )
        self.assertContains(resposta, '<span>Resíduos</span>')
        self.assertNotContains(resposta, 'href="/usuario/usuarios/"')
        self.assertNotContains(resposta, 'href="/auditoria/"')

    def test_cadastro_voluntario_exibe_breadcrumb_hierarquico(self):
        resposta = self.client.get(reverse('cadastro_voluntario'))

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/usuario/voluntarios/">Controle de Voluntários</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Cadastro de voluntário</span>',
        )

    def test_edicao_voluntario_exibe_breadcrumb_com_nome(self):
        resposta = self.client.get(
            reverse('editar_voluntario', args=[self.voluntario.id_voluntario])
        )

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/usuario/voluntarios/">Controle de Voluntários</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Edição de Voluntário - Voluntário</span>',
        )

    def test_edicao_usuario_exibe_breadcrumb_com_nome(self):
        self.autenticar_como_admin()
        usuario_editado = Usuario.objects.create(
            id_voluntario=self.voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )

        resposta = self.client.get(
            reverse('editar_usuario', args=[usuario_editado.id_usuario])
        )

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/usuario/usuarios/">Controle de Usuários</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Edição de Usuário - Voluntário</span>',
        )

    def test_cadastro_completo_exibe_breadcrumb_hierarquico(self):
        self.autenticar_como_admin()

        resposta = self.client.get(reverse('cadastro'))

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/usuario/usuarios/">Controle de Usuários</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Cadastro completo</span>',
        )

    def test_cadastro_usuario_exibe_breadcrumb_hierarquico(self):
        self.autenticar_como_admin()

        resposta = self.client.get(reverse('cadastro_usuario'))

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/usuario/usuarios/">Controle de Usuários</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Cadastro de usuário</span>',
        )

    def test_cadastro_usuario_envia_credenciais_por_email(self):
        self.autenticar_como_admin()
        senha = 'SenhaInicialSegura2026!'

        resposta = self.client.post(
            reverse('cadastro_usuario'),
            {
                'voluntario': self.voluntario.pk,
                'tipo': 'COORDENADOR',
                'senha': senha,
                'confirmar_senha': senha,
            },
            follow=True,
        )

        usuario = Usuario.objects.get(id_voluntario=self.voluntario)
        self.assertTrue(usuario.check_password(senha))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.voluntario.email])
        self.assertIn(f'E-mail de acesso: {self.voluntario.email}', mail.outbox[0].body)
        self.assertIn(f'Senha temporária: {senha}', mail.outbox[0].body)
        self.assertIn('Perfil > Alterar senha', mail.outbox[0].body)
        self.assertContains(resposta, 'os dados de acesso foram enviados para')

    def test_cadastro_completo_envia_credenciais_por_email(self):
        self.autenticar_como_admin()
        senha = 'SenhaInicialSegura2026!'
        email = 'novo-voluntario@teste.org'

        resposta = self.client.post(
            reverse('cadastro'),
            {
                'nome': 'Novo Voluntário',
                'dt_nascimento': '01/01/1994',
                'endereco': 'Rua Nova',
                'telefone': '11977776666',
                'email': email,
                'tipo': 'COORDENADOR',
                'senha': senha,
                'confirmar_senha': senha,
            },
            follow=True,
        )

        voluntario = Voluntario.objects.get(email=email)
        usuario = Usuario.objects.get(id_voluntario=voluntario)
        self.assertTrue(usuario.check_password(senha))
        self.assertFalse(usuario.primeiro_acesso_concluido)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [email])
        self.assertIn(f'Senha temporária: {senha}', mail.outbox[0].body)
        self.assertIn('Perfil > Alterar senha', mail.outbox[0].body)
        self.assertContains(resposta, 'os dados de acesso foram enviados para')

    def test_cadastro_completo_rejeita_email_ja_utilizado(self):
        self.autenticar_como_admin()
        quantidade_voluntarios_antes = Voluntario.objects.count()
        email_existente = self.voluntario.email.upper()
        dados = {
            'nome': 'Outro Voluntário',
            'dt_nascimento': '01/01/1994',
            'endereco': 'Rua Nova',
            'telefone': '11977776666',
            'email': email_existente,
            'tipo': 'COORDENADOR',
            'senha': 'SenhaInicialSegura2026!',
            'confirmar_senha': 'SenhaInicialSegura2026!',
        }
        request = RequestFactory().post(reverse('cadastro'), dados)
        request.session = {'usuario_id': self.coordenador.id_usuario}

        with patch('usuario.views.render') as render:
            resposta = resolve(reverse('cadastro')).func(request)

        form = render.call_args.args[2]['form']
        self.assertIs(resposta, render.return_value)
        self.assertIn('email', form.errors)
        self.assertIn(
            'já existe um voluntário',
            str(form.errors['email']).casefold(),
        )
        self.assertEqual(
            Voluntario.objects.count(),
            quantidade_voluntarios_antes,
        )
        self.assertFalse(Usuario.objects.filter(id_voluntario=self.voluntario).exists())
        self.assertEqual(mail.outbox, [])

    @patch('usuario.views.send_mail', side_effect=SMTPServerDisconnected('SMTP indisponível'))
    def test_cadastro_usuario_e_cancelado_se_email_nao_puder_ser_enviado(
        self,
        send_mail_mock,
    ):
        self.autenticar_como_admin()
        senha = 'SenhaInicialSegura2026!'

        resposta = self.client.post(
            reverse('cadastro_usuario'),
            {
                'voluntario': self.voluntario.pk,
                'tipo': 'COORDENADOR',
                'senha': senha,
                'confirmar_senha': senha,
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Usuario.objects.filter(id_voluntario=self.voluntario).exists())
        self.assertContains(resposta, 'o cadastro não foi concluído')
        send_mail_mock.assert_called_once()

    def test_perfil_usa_identidade_visual_e_preserva_acoes(self):
        resposta = self.client.get(reverse('perfil'))

        self.assertContains(resposta, '<body class="system-page profile-page-body">')
        self.assertContains(resposta, '<section class="profile-page">')
        self.assertContains(resposta, '<h2>Meu Perfil</h2>')
        self.assertContains(resposta, 'profile-button profile-button--save')
        self.assertContains(resposta, 'href="/usuario/alterar-senha/" class="btn profile-button profile-button--password"')
        self.assertContains(resposta, 'href="/usuario/home/" class="btn profile-button profile-button--cancel"')
        self.assertContains(resposta, '<span aria-current="page">Perfil</span>')
        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(resposta, 'class="breadcrumb-separator"')

    def test_alterar_nome_no_perfil_atualiza_nome_do_botao_de_perfil(self):
        session = self.client.session
        session['usuario_nome'] = self.coordenador_voluntario.nome
        session.save()

        resposta = self.client.post(reverse('perfil'), {
            'nome': 'Novo Coordenador',
            'dt_nascimento': '01/01/1990',
            'endereco': 'Rua A',
            'telefone': '11999999999',
            'email': 'coordenador@teste.org',
        })

        self.assertEqual(resposta.status_code, 200)
        self.coordenador_voluntario.refresh_from_db()
        self.assertEqual(self.coordenador_voluntario.nome, 'Novo Coordenador')
        self.assertEqual(
            self.client.session['usuario_nome'],
            'Novo Coordenador',
        )
        self.assertContains(
            resposta,
            '<span class="topbar-user-name">Novo Coordenador</span>',
        )
        self.assertContains(
            resposta,
            '<span class="topbar-user-initial" aria-hidden="true">N</span>',
        )

    def test_perfil_rejeita_data_de_nascimento_que_resulta_em_menos_de_18_anos(self):
        data_menor_de_18 = timezone.localdate().replace(
            year=timezone.localdate().year - 17,
        )

        resposta = self.client.post(reverse('perfil'), {
            'nome': self.coordenador_voluntario.nome,
            'dt_nascimento': data_menor_de_18.strftime('%d/%m/%Y'),
            'endereco': 'Rua A',
            'telefone': '11999999999',
            'email': 'coordenador@teste.org',
        })

        self.assertEqual(resposta.status_code, 200)
        self.coordenador_voluntario.refresh_from_db()
        self.assertEqual(
            self.coordenador_voluntario.dt_nascimento,
            date(1990, 1, 1),
        )
        self.assertContains(
            resposta,
            'O voluntário precisa ter 18 anos ou mais para ser responsável.',
        )

    def test_alteracao_senha_usa_identidade_visual_e_preserva_controles(self):
        resposta = self.client.get(reverse('alterar_senha'))

        self.assertContains(resposta, 'class="system-page password-page-body"')
        self.assertContains(resposta, '<section class="password-page">')
        self.assertContains(resposta, 'class="password-eyebrow">Segurança da conta</span>')
        self.assertContains(resposta, 'name="senha_atual"')
        self.assertContains(resposta, 'name="nova_senha"')
        self.assertContains(resposta, 'name="confirmar_nova_senha"')
        self.assertContains(resposta, 'class="btn profile-button profile-button--save"')
        self.assertContains(resposta, 'href="/usuario/perfil/" class="btn profile-button profile-button--cancel"')
        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(resposta, 'href="/usuario/perfil/">Perfil</a>')
        self.assertContains(resposta, '<span aria-current="page">Alterar senha</span>')

    def test_alteracao_senha_exibe_erro_com_estilo_de_alerta(self):
        self.coordenador.set_password('SenhaAtualSegura2026!')
        self.coordenador.save()

        resposta = self.client.post(reverse('alterar_senha'), {
            'senha_atual': 'SenhaErrada2026!',
            'nova_senha': 'NovaSenhaSegura2026!',
            'confirmar_nova_senha': 'NovaSenhaSegura2026!',
        })

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'class="alert-box alert-error system-feedback-toast" role="alert"')
        self.assertContains(
            resposta,
            'Não foi possível alterar a senha porque a senha atual está incorreta.',
        )

    def test_alteracao_senha_exibe_sucesso_na_mesma_tela(self):
        self.coordenador.set_password('SenhaAtualSegura2026!')
        self.coordenador.save()

        resposta = self.client.post(reverse('alterar_senha'), {
            'senha_atual': 'SenhaAtualSegura2026!',
            'nova_senha': 'NovaSenhaSegura2026!',
            'confirmar_nova_senha': 'NovaSenhaSegura2026!',
        }, follow=True)

        self.coordenador.refresh_from_db()
        self.assertTrue(self.coordenador.check_password('NovaSenhaSegura2026!'))
        self.assertEqual(resposta.redirect_chain, [(reverse('alterar_senha'), 302)])
        self.assertContains(
            resposta,
            'class="alert-box alert-success system-feedback-toast" role="status"',
        )
        self.assertContains(resposta, 'A senha da sua conta foi alterada com sucesso.')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RecuperacaoSenhaTests(TestCase):
    def setUp(self):
        self.voluntario = Voluntario.objects.create(
            nome='Voluntária',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua A',
            telefone='11999999999',
            email='voluntaria@teste.org',
        )
        self.usuario = Usuario.objects.create(
            id_voluntario=self.voluntario,
            tipo='COORDENADOR',
        )
        self.usuario.set_password('SenhaAntigaSegura2026!')
        self.usuario.save()

    def test_tela_de_login_exibe_link_de_recuperacao(self):
        resposta = self.client.get(reverse('login'))

        self.assertContains(resposta, reverse('recuperar_senha'))
        self.assertContains(resposta, 'Recuperar senha')

    def test_solicitacao_envia_link_com_token(self):
        resposta = self.client.post(
            reverse('recuperar_senha'),
            {'email': self.voluntario.email},
        )

        self.assertContains(resposta, 'Este e-mail está cadastrado.')
        self.assertContains(resposta, 'Enviamos as instruções')
        self.assertEqual(len(mail.outbox), 1)
        token = password_reset_token.make_token(self.usuario)
        self.assertIn(
            reverse('redefinir_senha', args=[self.usuario.id_usuario, token]),
            mail.outbox[0].body,
        )

    @patch('usuario.views.send_mail')
    @patch('usuario.views.get_connection')
    def test_solicitacao_tenta_ssl_apos_desconexao_smtp_em_starttls(
        self,
        get_connection,
        send_mail,
    ):
        primeira_conexao = Mock()
        segunda_conexao = Mock()
        primeira_conexao.open.side_effect = SMTPServerDisconnected(
            'Connection unexpectedly closed'
        )
        get_connection.side_effect = [primeira_conexao, segunda_conexao]
        send_mail.return_value = 1

        resposta = self.client.post(
            reverse('recuperar_senha'),
            {'email': self.voluntario.email},
        )

        self.assertContains(resposta, 'Este e-mail está cadastrado.')
        self.assertEqual(get_connection.call_count, 2)
        primeira_conexao.open.assert_called_once()
        segunda_conexao.open.assert_called_once()
        self.assertEqual(
            get_connection.call_args_list[1].kwargs,
            {
                'fail_silently': False,
                'port': 465,
                'use_tls': False,
                'use_ssl': True,
            },
        )
        send_mail.assert_called_once()
        self.assertIs(send_mail.call_args.kwargs['connection'], segunda_conexao)

    @patch(
        'usuario.views.send_mail',
        side_effect=SMTPServerDisconnected('Connection unexpectedly closed'),
    )
    def test_solicitacao_informa_conta_cadastrada_se_envio_falhar(self, send_mail):
        resposta = self.client.post(
            reverse('recuperar_senha'),
            {'email': self.voluntario.email},
        )

        self.assertContains(resposta, 'Este e-mail está cadastrado, mas não foi possível enviar')
        self.assertContains(resposta, 'class="auth-feedback auth-feedback--error" role="alert"')
        self.assertEqual(
            resposta.content.decode().count(
                'Este e-mail está cadastrado, mas não foi possível enviar'
            ),
            1,
        )
        self.assertNotContains(resposta, 'Não foi possível enviar o e-mail agora.')
        send_mail.assert_called_once()

    def test_solicitacao_nao_revela_email_inexistente(self):
        resposta = self.client.post(
            reverse('recuperar_senha'),
            {'email': 'inexistente@teste.org'},
        )

        self.assertContains(resposta, 'E-mail não cadastrado')
        self.assertContains(
            resposta,
            'class="auth-feedback auth-feedback--info" role="status"',
        )
        self.assertContains(resposta, 'Nenhum e-mail foi enviado')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        DEBUG=True,
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
    )
    def test_modo_console_indica_onde_encontrar_link(self):
        resposta = self.client.post(
            reverse('recuperar_senha'),
            {'email': self.voluntario.email},
        )

        self.assertContains(
            resposta,
            'Este e-mail está cadastrado. O link de redefinição aparecerá no terminal',
        )

    def test_link_redefine_senha_e_fica_invalido_apos_uso(self):
        token = password_reset_token.make_token(self.usuario)
        url = reverse('redefinir_senha', args=[self.usuario.id_usuario, token])

        resposta = self.client.post(url, {
            'senha': 'NovaSenhaSegura2026!',
            'confirmar_senha': 'NovaSenhaSegura2026!',
        }, follow=True)

        self.assertRedirects(resposta, reverse('login'))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('NovaSenhaSegura2026!'))
        self.assertFalse(password_reset_token.check_token(self.usuario, token))
        self.assertContains(resposta, 'auth-feedback auth-feedback--success')
        self.assertContains(resposta, 'Sua senha foi redefinida.')
        self.assertNotContains(resposta, 'data-toast')

    def test_tela_de_redefinicao_permite_mostrar_senhas_e_explica_regras(self):
        token = password_reset_token.make_token(self.usuario)
        resposta = self.client.get(
            reverse('redefinir_senha', args=[self.usuario.id_usuario, token]),
        )

        self.assertContains(resposta, 'class="password-toggle"')
        self.assertContains(resposta, 'class="password-hint"')
        self.assertContains(resposta, 'Senhas comuns ou formadas apenas por números')

    def test_erro_de_senha_usa_alerta_com_identidade_visual(self):
        token = password_reset_token.make_token(self.usuario)
        resposta = self.client.post(
            reverse('redefinir_senha', args=[self.usuario.id_usuario, token]),
            {'senha': 'password', 'confirmar_senha': 'password'},
        )

        self.assertContains(
            resposta,
            'class="auth-feedback auth-feedback--error" role="alert"',
        )
        self.assertContains(resposta, 'muito comum')

    def test_erro_de_confirmacao_usa_feedback_padrao(self):
        token = password_reset_token.make_token(self.usuario)
        resposta = self.client.post(
            reverse('redefinir_senha', args=[self.usuario.id_usuario, token]),
            {
                'senha': 'Trilha!DoMar2026',
                'confirmar_senha': 'Outra!Senha2026',
            },
        )

        self.assertContains(
            resposta,
            'class="auth-feedback auth-feedback--error" role="alert"',
        )
        self.assertContains(resposta, 'As senhas não coincidem.')

    def test_redefinicao_rejeita_senha_comum_com_mensagem_de_validacao(self):
        token = password_reset_token.make_token(self.usuario)
        resposta = self.client.post(
            reverse('redefinir_senha', args=[self.usuario.id_usuario, token]),
            {'senha': 'password', 'confirmar_senha': 'password'},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'muito comum')
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('SenhaAntigaSegura2026!'))


class LogoutTests(TestCase):
    def test_logout_limpa_sessao_e_exibe_opcoes_de_retorno(self):
        session = self.client.session
        session['usuario_id'] = 123
        session['usuario_tipo'] = 'ADMIN'
        session.save()

        resposta = self.client.get(reverse('logout'))

        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('usuario_id', self.client.session)
        self.assertContains(resposta, 'Você saiu do sistema')
        self.assertContains(resposta, reverse('login'))
        self.assertContains(resposta, reverse('index'))
        self.assertNotContains(resposta, 'Logout realizado com sucesso!')
