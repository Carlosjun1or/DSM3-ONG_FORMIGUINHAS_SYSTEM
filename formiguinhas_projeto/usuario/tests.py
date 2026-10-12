from datetime import date

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from .paginacao import paginar_queryset
from .models import Usuario, Voluntario


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
