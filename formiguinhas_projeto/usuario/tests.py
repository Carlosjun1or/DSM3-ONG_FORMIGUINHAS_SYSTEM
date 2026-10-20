from datetime import date

from django.core import mail
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .paginacao import paginar_queryset
from .models import Usuario, Voluntario
from .tokens import password_reset_token


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

    def test_link_redefine_senha_e_fica_invalido_apos_uso(self):
        token = password_reset_token.make_token(self.usuario)
        url = reverse('redefinir_senha', args=[self.usuario.id_usuario, token])

        resposta = self.client.post(url, {
            'senha': 'NovaSenhaSegura2026!',
            'confirmar_senha': 'NovaSenhaSegura2026!',
        })

        self.assertRedirects(resposta, reverse('login'))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('NovaSenhaSegura2026!'))
        self.assertFalse(password_reset_token.check_token(self.usuario, token))


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
