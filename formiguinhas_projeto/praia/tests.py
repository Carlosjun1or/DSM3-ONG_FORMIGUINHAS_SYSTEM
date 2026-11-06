from datetime import date
from urllib.error import URLError
from unittest.mock import MagicMock, patch

from django import forms
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acao.models import Acao
from equipe.models import Equipe
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

    def test_excluir_praia_sem_vinculos_exibe_sucesso(self):
        praia = Praia.objects.create(
            nome='Praia para excluir',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
        )

        response = self.client.post(
            reverse('excluir_praia', args=[praia.id_praia]),
            follow=True,
        )

        self.assertRedirects(response, reverse('praias'))
        self.assertFalse(Praia.objects.filter(pk=praia.pk).exists())
        self.assertContains(response, 'Praia para excluir excluída com sucesso.')

    def test_nao_exclui_praia_vinculada_a_acao(self):
        praia = Praia.objects.create(
            nome='Praia com ação',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
        )
        Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=date(2026, 1, 1),
            praia=praia,
        )

        response = self.client.post(
            reverse('excluir_praia', args=[praia.id_praia]),
            follow=True,
        )

        self.assertRedirects(response, reverse('praias'))
        self.assertTrue(Praia.objects.filter(pk=praia.pk).exists())
        self.assertContains(
            response,
            'Não é possível excluir Praia com ação: ela está vinculada a ações ou equipes.',
        )

    def test_nao_exclui_praia_vinculada_a_equipe(self):
        praia = Praia.objects.create(
            nome='Praia com equipe',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
        )
        Equipe.objects.create(nome='Equipe de teste', praia=praia)

        response = self.client.post(
            reverse('excluir_praia', args=[praia.id_praia]),
            follow=True,
        )

        self.assertRedirects(response, reverse('praias'))
        self.assertTrue(Praia.objects.filter(pk=praia.pk).exists())
        self.assertContains(
            response,
            'Não é possível excluir Praia com equipe: ela está vinculada a ações ou equipes.',
        )

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
            [praia.nome for praia in response.context['praias']],
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

    def test_listagem_sem_resultados_exibe_estado_vazio(self):
        response = self.client.get(reverse('praias'), {'busca': 'Praia inexistente'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['praias']), [])
        self.assertContains(response, 'Nenhuma praia encontrada')
        self.assertContains(response, 'Ajuste os filtros ou cadastre uma nova praia.')
        self.assertNotContains(response, 'record-pagination')

    def test_paginacao_preserva_filtros_ao_navegar_entre_paginas(self):
        Praia.objects.bulk_create([
            Praia(
                nome=f'Praia Filtrada {indice:02d}',
                cidade='Santos',
                latitude=-23.967,
                longitude=-46.328,
                praia_ativa='ATIVA',
            )
            for indice in range(23)
        ])
        Praia.objects.create(
            nome='Praia Filtrada de outra cidade',
            cidade='Guarujá',
            latitude=-23.967,
            longitude=-46.328,
            praia_ativa='ATIVA',
        )
        Praia.objects.create(
            nome='Praia Filtrada inativa',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
            praia_ativa='INATIVA',
        )
        filtros = {
            'busca': 'Filtrada',
            'cidade': 'Santos',
            'status': 'ATIVA',
        }

        primeira_pagina = self.client.get(reverse('praias'), filtros)

        self.assertEqual(primeira_pagina.status_code, 200)
        self.assertEqual(primeira_pagina.context['pagina'].number, 1)
        self.assertEqual(primeira_pagina.context['pagina'].paginator.count, 23)
        self.assertEqual(len(primeira_pagina.context['praias']), 20)
        self.assertContains(
            primeira_pagina,
            '?busca=Filtrada&amp;cidade=Santos&amp;status=ATIVA&amp;page=2',
        )

        segunda_pagina = self.client.get(
            reverse('praias'),
            {**filtros, 'page': '2'},
        )

        self.assertEqual(segunda_pagina.status_code, 200)
        self.assertEqual(segunda_pagina.context['pagina'].number, 2)
        self.assertEqual(segunda_pagina.context['pagina'].paginator.count, 23)
        self.assertEqual(len(segunda_pagina.context['praias']), 3)
        self.assertEqual(segunda_pagina.context['busca'], 'Filtrada')
        self.assertEqual(segunda_pagina.context['cidade_selecionada'], 'Santos')
        self.assertEqual(segunda_pagina.context['status_selecionado'], 'ATIVA')
        self.assertContains(
            segunda_pagina,
            '?busca=Filtrada&amp;cidade=Santos&amp;status=ATIVA&amp;page=1',
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

        self.assertEqual(response.status_code, 302)
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
        self.assertContains(
            response,
            'Praia não cadastrada. Já existe uma praia cadastrada com esse nome e cidade.',
            count=1,
        )
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
            follow=True,
        )

        self.assertContains(response, 'Praia Atualizada atualizada com sucesso.')
        self.assertEqual(Praia.objects.count(), 1)
        praia.refresh_from_db()
        self.assertEqual(praia.nome, 'Praia Atualizada')
        self.assertEqual(praia.praia_ativa, 'INATIVA')

    def test_editar_praia_rejeita_nome_e_cidade_duplicados_ignorando_case(self):
        praia_original = Praia.objects.create(
            nome='Praia Original',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
            praia_ativa='ATIVA',
        )
        Praia.objects.create(
            nome='Praia Central',
            cidade='Santos',
            latitude=-23.968,
            longitude=-46.327,
            praia_ativa='ATIVA',
        )

        response = self.client.post(
            reverse('editar_praia', args=[praia_original.id_praia]),
            {
                'nome': 'praia central',
                'cidade': 'SANTOS',
                'latitude': '-23.967000',
                'longitude': '-46.328000',
                'praia_ativa': 'ATIVA',
                'descricao': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Praia não atualizada. Já existe uma praia cadastrada com esse nome e cidade.',
            count=1,
        )
        self.assertEqual(Praia.objects.count(), 2)
        praia_original.refresh_from_db()
        self.assertEqual(praia_original.nome, 'Praia Original')

    def test_alterar_status_exibe_feedback(self):
        praia = Praia.objects.create(
            nome='Praia Central',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
            praia_ativa='ATIVA',
        )

        resposta = self.client.post(
            reverse('atualizar_status_praia', args=[praia.id_praia]),
            {'praia_ativa': 'INATIVA'},
            follow=True,
        )

        self.assertContains(
            resposta,
            'Status de Praia Central atualizado para Inativa.',
        )
        praia.refresh_from_db()
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

        self.assertEqual(response.status_code, 403)
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
        self.assertEqual(response.status_code, 403)

        response = self.client.post(reverse('excluir_praia', args=[praia.id_praia]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Praia.objects.filter(pk=praia.pk).exists())

        response = self.client.post(
            reverse('atualizar_status_praia', args=[praia.id_praia]),
            {'praia_ativa': 'INATIVA'}
        )
        self.assertEqual(response.status_code, 403)
        praia.refresh_from_db()
        self.assertEqual(praia.praia_ativa, 'ATIVA')

    def test_edicao_exibe_breadcrumb_com_nome_da_praia(self):
        praia = Praia.objects.create(
            nome='Praia Central',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
            praia_ativa='ATIVA',
            descricao='Praia de teste',
        )

        response = self.client.get(
            reverse('editar_praia', args=[praia.id_praia])
        )

        self.assertContains(response, 'href="/usuario/home/">Início</a>')
        self.assertContains(response, 'href="/praia/praias/">Controle de Praias</a>')
        self.assertContains(
            response,
            '<span aria-current="page">Edição de Praia - Praia Central</span>',
        )

    def test_cadastro_exibe_breadcrumb_hierarquico(self):
        response = self.client.get(reverse('cadastrar_praia'))

        self.assertContains(response, 'href="/usuario/home/">Início</a>')
        self.assertContains(response, 'href="/praia/praias/">Controle de Praias</a>')
        self.assertContains(
            response,
            '<span aria-current="page">Cadastro de Praia</span>',
        )

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

    def test_localizacao_rejeita_metodo_diferente_de_get(self):
        response = self.client.post(reverse('localizar_praia'), {
            'nome': 'Praia Central',
            'cidade': 'Santos',
        })

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json(), {'erro': 'Método não permitido.'})

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

    @patch('praia.views.urlopen', side_effect=URLError('serviço indisponível'))
    def test_localizacao_retorna_502_quando_servico_esta_indisponivel(
        self,
        mock_urlopen,
    ):
        response = self.client.get(reverse('localizar_praia'), {
            'nome': 'Praia Central',
            'cidade': 'Santos',
        })

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(),
            {'erro': 'Não foi possível consultar o serviço de localização agora.'},
        )
        self.assertTrue(mock_urlopen.called)
