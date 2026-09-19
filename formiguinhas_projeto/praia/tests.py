from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from usuario.models import Usuario, Voluntario

from .forms import PraiaForm
from .models import Praia


class PraiaModelTests(TestCase):
    def test_str_retorna_nome_da_praia(self):
        praia = Praia(
            nome='Praia Central',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
        )

        self.assertEqual(str(praia), 'Praia Central')

    def test_coordenadas_fora_dos_limites_sao_invalidas(self):
        praia = Praia(
            nome='Praia Inválida',
            cidade='Santos',
            latitude=91,
            longitude=-46.328,
        )

        with self.assertRaises(ValidationError):
            praia.full_clean()


class PraiaViewsTests(TestCase):
    def setUp(self):
        voluntario = Voluntario.objects.create(
            nome='Administrador',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua A, 1',
            telefone='13999999999',
            email='admin@formiguinhas.org',
        )
        self.usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        session = self.client.session
        session['usuario_id'] = self.usuario.id_usuario
        session['usuario_tipo'] = self.usuario.tipo
        session.save()

    def test_usuario_autenticado_acessa_listagem(self):
        response = self.client.get(reverse('praias'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sistema/praias.html')

    def test_usuario_autenticado_cadastra_praia(self):
        response = self.client.post(reverse('cadastrar_praia'), {
            'nome': 'Praia Central',
            'cidade': 'Santos',
            'latitude': '-23.967000',
            'longitude': '-46.328000',
            'praia_ativa': 'on',
            'descricao': 'Área de atuação.',
        })

        self.assertRedirects(response, reverse('praias'))
        praia = Praia.objects.get(nome='Praia Central')
        self.assertEqual(praia.cadastrado_por, self.usuario)

    def test_coordenador_nao_pode_cadastrar_praia(self):
        voluntario = Voluntario.objects.create(
            nome='Coordenador',
            dt_nascimento=date(1991, 1, 1),
            endereco='Rua B, 2',
            telefone='13988888888',
            email='coordenador@formiguinhas.org',
        )
        coordenador = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )
        session = self.client.session
        session['usuario_id'] = coordenador.id_usuario
        session['usuario_tipo'] = coordenador.tipo
        session.save()

        response = self.client.get(reverse('cadastrar_praia'))

        self.assertRedirects(response, reverse('praias'))
        self.assertFalse(Praia.objects.filter(nome='Praia do Coordenador').exists())

    def test_formulario_rejeita_latitude_invalida(self):
        form = PraiaForm(data={
            'nome': 'Praia Central',
            'cidade': 'Santos',
            'latitude': '91',
            'longitude': '-46.328000',
            'praia_ativa': True,
            'descricao': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('latitude', form.errors)
