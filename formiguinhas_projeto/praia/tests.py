from datetime import date
from unittest.mock import MagicMock, patch

from django import forms
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
    def test_praia_usa_status_em_select_com_ativas_e_inativas(self):
        form = PraiaForm()

        self.assertEqual(form.fields['praia_ativa'].widget.__class__, forms.Select)
        self.assertEqual(form.fields['praia_ativa'].choices, [
            ('ATIVA', 'Ativa'),
            ('INATIVA', 'Inativa'),
        ])

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

    def test_filtro_de_cidade_ignora_case_e_nao_repete_opcoes(self):
        Praia.objects.create(
            nome='Praia Central', cidade='Santos', latitude=-23.967,
            longitude=-46.328, praia_ativa='ATIVA',
        )
        Praia.objects.create(
            nome='Praia do Gonzaga', cidade='santos', latitude=-23.968,
            longitude=-46.327, praia_ativa='ATIVA',
        )
        Praia.objects.create(
            nome='Praia Grande', cidade='Praia Grande', latitude=-24.005,
            longitude=-46.402, praia_ativa='ATIVA',
        )

        response = self.client.get(reverse('praias'), {'cidade': 'SANTOS'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['praias'].values_list('nome', flat=True)),
            ['Praia Central', 'Praia do Gonzaga'],
        )
        self.assertEqual(response.context['cidades'], ['Praia Grande', 'Santos'])

    def test_busca_livre_consulta_apenas_nome_da_praia(self):
        Praia.objects.create(
            nome='Praia Central', cidade='Santos', latitude=-23.967,
            longitude=-46.328, praia_ativa='ATIVA',
        )
        Praia.objects.create(
            nome='Praia do Gonzaga', cidade='Central', latitude=-23.968,
            longitude=-46.327, praia_ativa='ATIVA',
        )

        response = self.client.get(reverse('praias'), {'busca': 'Central'})

        self.assertEqual(
            list(response.context['praias'].values_list('nome', flat=True)),
            ['Praia Central'],
        )

    def test_usuario_autenticado_cadastra_praia(self):
        response = self.client.post(reverse('cadastrar_praia'), {
            'nome': 'Praia Central',
            'cidade': 'Santos',
            'latitude': '-23.967000',
            'longitude': '-46.328000',
            'praia_ativa': 'ATIVA',
            'descricao': 'Área de atuação.',
        })

        self.assertRedirects(response, reverse('praias'))
        praia = Praia.objects.get(nome='Praia Central')
        self.assertEqual(praia.cadastrado_por, self.usuario)
        self.assertEqual(praia.cadastrado_por_nome, self.usuario.id_voluntario.nome)
        self.assertEqual(praia.cadastrado_por_tipo, self.usuario.tipo)

    def test_nao_permite_cadastro_repetido_de_mesma_praia_na_mesma_cidade_ignorando_case(self):
        Praia.objects.create(
            nome='Praia Central',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
            praia_ativa='ATIVA',
            descricao='Praia existente',
        )

        response = self.client.post(reverse('cadastrar_praia'), {
            'nome': 'praia central',
            'cidade': 'SANTOS',
            'latitude': '-23.967000',
            'longitude': '-46.328000',
            'praia_ativa': 'ATIVA',
            'descricao': 'Tentativa de duplicar.',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Já existe uma praia cadastrada com esse nome e cidade')
        self.assertEqual(Praia.objects.filter(nome='Praia Central', cidade='Santos').count(), 1)

    def test_praia_exibe_auditoria_na_listagem(self):
        Praia.objects.create(
            nome='Praia Auditada',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
            praia_ativa='ATIVA',
            cadastrado_por=self.usuario,
            cadastrado_por_nome=self.usuario.id_voluntario.nome,
            cadastrado_por_tipo=self.usuario.tipo,
            ultimo_editado_por=self.usuario,
            ultimo_editado_por_nome=self.usuario.id_voluntario.nome,
            ultimo_editado_por_tipo=self.usuario.tipo,
            dt_ultima_edicao=timezone.now(),
        )

        response = self.client.get(reverse('praias'))

        self.assertContains(response, 'Cadastrado por')
        self.assertContains(response, 'Editado por')
        self.assertContains(response, 'Administrador')

    def test_editar_praia_nao_cria_nova_praia(self):
        praia = Praia.objects.create(
            nome='Praia Original',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
            praia_ativa='ATIVA',
            descricao='Praia original',
        )

        response = self.client.post(
            reverse('editar_praia', args=[praia.id_praia]),
            {
                'nome': 'Praia Atualizada',
                'cidade': 'Santos',
                'latitude': '-23.967000',
                'longitude': '-46.328000',
                'praia_ativa': 'INATIVA',
                'descricao': 'Praia atualizada',
            },
        )

        self.assertRedirects(response, reverse('praias'))
        self.assertEqual(Praia.objects.count(), 1)
        praia.refresh_from_db()
        self.assertEqual(praia.nome, 'Praia Atualizada')
        self.assertEqual(praia.praia_ativa, 'INATIVA')

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

    def test_coordenador_nao_pode_editar_ou_excluir_praia(self):
        praia = Praia.objects.create(
            nome='Praia do Coordenador',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
            praia_ativa='ATIVA',
            descricao='Praia de teste',
        )
        voluntario = Voluntario.objects.create(
            nome='Coordenador 2',
            dt_nascimento=date(1991, 2, 2),
            endereco='Rua C, 3',
            telefone='13977777777',
            email='coordenador2@formiguinhas.org',
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

        response = self.client.get(reverse('editar_praia', args=[praia.id_praia]))
        self.assertRedirects(response, reverse('praias'))

        response = self.client.post(reverse('excluir_praia', args=[praia.id_praia]))
        self.assertRedirects(response, reverse('praias'))
        self.assertTrue(Praia.objects.filter(pk=praia.pk).exists())

        response = self.client.post(
            reverse('atualizar_status_praia', args=[praia.id_praia]),
            {'praia_ativa': 'INATIVA'}
        )
        self.assertRedirects(response, reverse('praias'))
        praia.refresh_from_db()
        self.assertEqual(praia.praia_ativa, 'ATIVA')

    def test_formulario_rejeita_latitude_invalida(self):
        form = PraiaForm(data={
            'nome': 'Praia Central',
            'cidade': 'Santos',
            'latitude': '91',
            'longitude': '-46.328000',
            'praia_ativa': 'ATIVA',
            'descricao': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('latitude', form.errors)

    def test_localizacao_exige_nome_e_cidade(self):
        response = self.client.get(reverse('localizar_praia'))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()['erro'],
            'Informe o nome da praia e a cidade para localizar.',
        )

    @patch('praia.views.urlopen')
    def test_localizacao_retorna_coordenadas_do_nominatim(self, mock_urlopen):
        resposta_nominatim = MagicMock()
        resposta_nominatim.read.return_value = b'[{"lat": "-23.967", "lon": "-46.328", "display_name": "interno"}]'
        mock_urlopen.return_value.__enter__.return_value = resposta_nominatim

        response = self.client.get(reverse('localizar_praia'), {
            'nome': 'Praia Central',
            'cidade': 'Santos',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'latitude': -23.967,
            'longitude': -46.328,
        })
        requisicao = mock_urlopen.call_args.args[0]
        self.assertEqual(requisicao.headers['User-agent'], 'Formiguinhas-ONG/1.0')

    @patch('praia.views.urlopen')
    def test_localizacao_informa_quando_nominatim_nao_encontra_resultado(self, mock_urlopen):
        resposta_nominatim = MagicMock()
        resposta_nominatim.read.return_value = b'[]'
        mock_urlopen.return_value.__enter__.return_value = resposta_nominatim

        response = self.client.get(reverse('localizar_praia'), {
            'nome': 'Praia Inexistente',
            'cidade': 'Santos',
        })

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()['erro'],
            'Localização não encontrada para essa praia e cidade.',
        )
