from datetime import date, time, timedelta
from decimal import Decimal
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core import mail
from django.db.models import Sum
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from acao.models import Acao
from config.settings import load_local_environment
from doacao.models import Doacao, DoacaoFinanceira
from praia.models import Praia
from .paginacao import paginar_queryset
from .models import Usuario, Voluntario
from .tokens import password_reset_token


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
        self.assertContains(resposta, 'css/template.css')
        self.assertNotContains(resposta, inativo.nome)


class LoginPageTests(TestCase):
    def test_login_nao_exibe_cabecalho_do_dashboard(self):
        resposta = self.client.get(reverse('login'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Entrar no sistema')
        self.assertNotContains(resposta, 'Painel administrativo')
        self.assertNotContains(resposta, '> Dashboard <')


class PermissoesStatusVoluntarioTests(TestCase):
    def setUp(self):
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

    def test_menu_lateral_usa_identidade_visual_e_preserva_permissoes(self):
        resposta = self.client.get(reverse('voluntarios'))

        self.assertContains(resposta, 'DA PRAIA')
        self.assertContains(resposta, 'href="/usuario/voluntarios/" class="sidebar-link active"')
        self.assertContains(
            resposta,
            'href="/static/usuario/icons/sidebar-icons.svg#volunteers"',
        )
        self.assertContains(resposta, '<span>Resíduos</span>')
        self.assertNotContains(resposta, 'href="/usuario/usuarios/"')
        self.assertNotContains(resposta, 'href="/auditoria/"')


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

        self.assertContains(resposta, 'Se o e-mail estiver cadastrado')
        self.assertEqual(len(mail.outbox), 1)
        token = password_reset_token.make_token(self.usuario)
        self.assertIn(
            reverse('redefinir_senha', args=[self.usuario.id_usuario, token]),
            mail.outbox[0].body,
        )

    def test_solicitacao_nao_revela_email_inexistente(self):
        resposta = self.client.post(
            reverse('recuperar_senha'),
            {'email': 'inexistente@teste.org'},
        )

        self.assertContains(resposta, 'Se o e-mail estiver cadastrado')
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
            'o link aparecerá no terminal onde o servidor Django está rodando',
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

        self.assertContains(resposta, 'class="auth-password-error" role="alert"')
        self.assertContains(resposta, 'muito comum')

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
