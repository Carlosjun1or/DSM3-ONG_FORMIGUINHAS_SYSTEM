from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from praia.models import Praia
from usuario.models import Usuario, Voluntario

from .models import Acao


class AcaoDetalheBreadcrumbTests(TestCase):
    def setUp(self):
        voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua A',
            telefone='11999999999',
            email='admin-acoes@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        praia = Praia.objects.create(
            nome='Praia Central',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
        )
        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_tipo'] = usuario.tipo
        session.save()
        self.praia = praia

    def test_breadcrumb_inclui_tipo_e_praia_da_acao(self):
        tipos_e_titulos = (
            (Acao.TIPO_MUTIRAO, 'Mutirão - Praia Central - 25/10/2026'),
            (
                Acao.TIPO_COLETA_VOLUNTARIA,
                'Coleta voluntária - Praia Central - 25/10/2026',
            ),
        )

        for tipo, titulo in tipos_e_titulos:
            with self.subTest(tipo=tipo):
                acao = Acao.objects.create(
                    tipo=tipo,
                    data=date(2026, 10, 25),
                    local='Praia Central',
                    praia=self.praia,
                )

                resposta = self.client.get(
                    reverse('acao_detalhe', args=[acao.id_acao])
                )

                self.assertContains(
                    resposta,
                    'href="/usuario/home/">Início</a>',
                )
                self.assertContains(
                    resposta,
                    'href="/acao/">Controle de Ações</a>',
                )
                self.assertContains(
                    resposta,
                    f'<span aria-current="page">{titulo}</span>',
                )

    def test_botoes_expansiveis_do_detalhe_seguem_estilo_dos_outros_detalhes(self):
        acao = Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=date(2026, 10, 25),
            local='Praia Central',
            praia=self.praia,
        )

        resposta = self.client.get(
            reverse('acao_detalhe', args=[acao.id_acao]),
        )

        self.assertEqual(resposta.status_code, 200)
        for painel in (
            'painel-residuo',
            'painel-material',
            'painel-imagens',
            'painel-responsavel',
            'painel-participante',
        ):
            with self.subTest(painel=painel):
                self.assertContains(
                    resposta,
                    f'class="btn btn-outline btn-small detail-panel-toggle" data-abrir-painel="{painel}"',
                )
                self.assertContains(
                    resposta,
                    f'<span aria-hidden="true"><svg class="acao-icone"><use href="#i-mais"></use></svg></span>',
                )

    def test_breadcrumb_edicao_inclui_tipo_e_praia_da_acao(self):
        tipos_e_titulos = (
            (
                Acao.TIPO_MUTIRAO,
                'Edição da Ação - Mutirão - Praia Central - 25/10/2026',
            ),
            (
                Acao.TIPO_COLETA_VOLUNTARIA,
                'Edição da Ação - Coleta voluntária - Praia Central - 25/10/2026',
            ),
        )

        for tipo, titulo in tipos_e_titulos:
            with self.subTest(tipo=tipo):
                acao = Acao.objects.create(
                    tipo=tipo,
                    data=date(2026, 10, 25),
                    local='Praia Central',
                    praia=self.praia,
                )

                resposta = self.client.get(
                    reverse('editar_acao', args=[acao.id_acao])
                )

                self.assertContains(
                    resposta,
                    'href="/usuario/home/">Início</a>',
                )
                self.assertContains(
                    resposta,
                    'href="/acao/">Controle de Ações</a>',
                )
                self.assertContains(
                    resposta,
                    f'<span aria-current="page">{titulo}</span>',
                )

    @patch('acao.views.salvar_acao_mongo')
    def test_alterar_status_exibe_feedback(self, _salvar_acao_mongo):
        acao = Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=date(2026, 10, 25),
            local='Praia Central',
            praia=self.praia,
        )

        resposta = self.client.post(
            reverse('atualizar_status_acao', args=[acao.id_acao]),
            {'status': Acao.STATUS_CANCELADA},
            follow=True,
        )

        self.assertContains(
            resposta,
            'Status da ação atualizado de Planejada para Cancelada.',
        )
        acao.refresh_from_db()
        self.assertEqual(acao.status, Acao.STATUS_CANCELADA)
