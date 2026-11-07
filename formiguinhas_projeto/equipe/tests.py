from datetime import date

from django.test import TestCase
from django.urls import reverse

from praia.models import Praia
from usuario.models import Usuario, Voluntario

from .models import Equipe, EquipeMembro


class BreadcrumbDetalheEquipeTests(TestCase):
    def test_cadastro_de_equipe_exibe_feedback(self):
        voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua de teste',
            telefone='11999999999',
            email='admin-cadastro-equipe@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        praia = Praia.objects.create(
            nome='Praia de teste',
            cidade='Santos',
            latitude=-23.9,
            longitude=-46.3,
        )
        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_tipo'] = usuario.tipo
        session.save()

        resposta = self.client.post(
            reverse('cadastro_equipe'),
            {
                'nome': 'Equipe Nova',
                'praia': praia.id_praia,
                'descricao': '',
                'status': 'ATIVA',
            },
            follow=True,
        )

        self.assertContains(resposta, 'A equipe &quot;Equipe Nova&quot; foi cadastrada com sucesso.')
        self.assertTrue(Equipe.objects.filter(nome='Equipe Nova').exists())

    def test_alterar_status_exibe_feedback(self):
        voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua de teste',
            telefone='11999999999',
            email='admin-equipe@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        equipe = Equipe.objects.create(nome='Areia Viva')
        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_tipo'] = usuario.tipo
        session.save()

        resposta = self.client.post(
            reverse('atualizar_status_equipe', args=[equipe.id_equipe]),
            {'status': 'INATIVA'},
            follow=True,
        )

        self.assertContains(
            resposta,
            'O status da equipe &quot;Areia Viva&quot; foi atualizado para Inativa.',
        )
        equipe.refresh_from_db()
        self.assertEqual(equipe.status, 'INATIVA')

    def test_excluir_equipe_identifica_qual_equipe_foi_excluida(self):
        voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua de teste',
            telefone='11999999999',
            email='admin-excluir-equipe@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        equipe = Equipe.objects.create(nome='Equipe Areia Limpa')
        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_tipo'] = usuario.tipo
        session.save()

        resposta = self.client.post(
            reverse('excluir_equipe', args=[equipe.id_equipe]),
            follow=True,
        )

        self.assertContains(
            resposta,
            'A equipe &quot;Equipe Areia Limpa&quot; foi excluída com sucesso.',
        )
        self.assertFalse(Equipe.objects.filter(pk=equipe.pk).exists())

    def test_detalhe_exibe_breadcrumb_com_nome_da_equipe(self):
        voluntario = Voluntario.objects.create(
            nome='Coordenadora',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua A',
            telefone='11999999999',
            email='coordenadora@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )
        equipe = Equipe.objects.create(nome='Areia Viva')
        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_tipo'] = usuario.tipo
        session.save()

        resposta = self.client.get(
            reverse('equipe_detalhe', args=[equipe.id_equipe])
        )

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/equipe/">Controle de Equipes</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Areia Viva</span>',
        )

    def test_edicao_exibe_breadcrumb_com_nome_da_equipe(self):
        voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua B',
            telefone='11888888888',
            email='administradora@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        equipe = Equipe.objects.create(nome='Areia Viva')
        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_tipo'] = usuario.tipo
        session.save()

        resposta = self.client.get(
            reverse('editar_equipe', args=[equipe.id_equipe])
        )

        self.assertContains(resposta, 'href="/usuario/home/">Início</a>')
        self.assertContains(
            resposta,
            'href="/equipe/">Controle de Equipes</a>',
        )
        self.assertContains(
            resposta,
            '<span aria-current="page">Edição de Equipe - Areia Viva</span>',
        )


class AcoesCoordenadoresEquipeTests(TestCase):
    def setUp(self):
        self.coordenador_voluntario = Voluntario.objects.create(
            nome='Coordenador atual',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua C',
            telefone='11777777777',
            email='coordenador-atual@teste.org',
        )
        self.coordenador = Usuario.objects.create(
            id_voluntario=self.coordenador_voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )
        self.outro_coordenador_voluntario = Voluntario.objects.create(
            nome='Outro coordenador',
            dt_nascimento=date(1991, 1, 1),
            endereco='Rua D',
            telefone='11666666666',
            email='outro-coordenador@teste.org',
        )
        self.voluntario = Voluntario.objects.create(
            nome='Voluntário',
            dt_nascimento=date(1992, 1, 1),
            endereco='Rua E',
            telefone='11555555555',
            email='voluntario-equipe@teste.org',
        )
        self.equipe = Equipe.objects.create(nome='Equipe Teste')
        self.membro_coordenador = EquipeMembro.objects.create(
            equipe=self.equipe,
            voluntario=self.coordenador_voluntario,
            papel=EquipeMembro.PAPEL_COORDENADOR,
        )
        self.outro_membro_coordenador = EquipeMembro.objects.create(
            equipe=self.equipe,
            voluntario=self.outro_coordenador_voluntario,
            papel=EquipeMembro.PAPEL_COORDENADOR,
        )
        self.membro_voluntario = EquipeMembro.objects.create(
            equipe=self.equipe,
            voluntario=self.voluntario,
            papel=EquipeMembro.PAPEL_VOLUNTARIO,
        )
        session = self.client.session
        session['usuario_id'] = self.coordenador.id_usuario
        session['usuario_tipo'] = self.coordenador.tipo
        session.save()

    def test_coordenadores_sao_realçados_e_proprio_perfil_tem_acao_sair(self):
        resposta = self.client.get(
            reverse('equipe_detalhe', args=[self.equipe.id_equipe])
        )

        self.assertContains(resposta, 'equipe-membro--coordenador')
        self.assertContains(resposta, 'equipe-membro--atual-coordenador')
        self.assertContains(resposta, 'Coordenador · Você')
        self.assertContains(resposta, '>Sair</button>')
        self.assertContains(resposta, '>Outro coordenador</span>')

    def test_coordenador_nao_remove_outro_coordenador(self):
        resposta = self.client.post(
            reverse(
                'remover_membro_equipe',
                args=[self.equipe.id_equipe, self.outro_membro_coordenador.id_equipe_membro],
            ),
            follow=True,
        )

        self.outro_membro_coordenador.refresh_from_db()
        self.assertEqual(self.outro_membro_coordenador.status, 'ATIVO')
        self.assertContains(
            resposta,
            f'Você não pode remover outro coordenador da equipe &quot;{self.equipe.nome}&quot;.',
        )

    def test_coordenador_pode_sair_da_equipe(self):
        resposta = self.client.post(
            reverse(
                'remover_membro_equipe',
                args=[self.equipe.id_equipe, self.membro_coordenador.id_equipe_membro],
            ),
            follow=True,
        )

        self.membro_coordenador.refresh_from_db()
        self.assertEqual(self.membro_coordenador.status, 'INATIVO')
        self.assertContains(resposta, f'Você saiu da equipe &quot;{self.equipe.nome}&quot;.')

    def test_coordenador_pode_remover_voluntario(self):
        self.client.post(
            reverse(
                'remover_membro_equipe',
                args=[self.equipe.id_equipe, self.membro_voluntario.id_equipe_membro],
            ),
        )

        self.membro_voluntario.refresh_from_db()
        self.assertEqual(self.membro_voluntario.status, 'INATIVO')

    def test_coordenador_nao_adiciona_voluntario_que_ja_e_membro_ativo(self):
        total_membros_ativos = EquipeMembro.objects.filter(
            equipe=self.equipe,
            voluntario=self.voluntario,
            status='ATIVO',
        ).count()

        resposta = self.client.post(
            reverse('adicionar_membro_equipe', args=[self.equipe.id_equipe]),
            {'voluntario': self.voluntario.id_voluntario},
            follow=True,
        )

        self.assertEqual(
            EquipeMembro.objects.filter(
                equipe=self.equipe,
                voluntario=self.voluntario,
                status='ATIVO',
            ).count(),
            total_membros_ativos,
        )
        self.assertContains(
            resposta,
            f'&quot;{self.voluntario.nome}&quot; já possui vínculo ativo '
            f'com a equipe &quot;{self.equipe.nome}&quot;.',
        )

    def test_coordenador_nao_duplica_vinculo_ativo_de_outro_coordenador(self):
        total_membros_ativos = EquipeMembro.objects.filter(
            equipe=self.equipe,
            voluntario=self.outro_coordenador_voluntario,
            status='ATIVO',
        ).count()

        resposta = self.client.post(
            reverse('adicionar_membro_equipe', args=[self.equipe.id_equipe]),
            {'voluntario': self.outro_coordenador_voluntario.id_voluntario},
            follow=True,
        )

        self.assertEqual(
            EquipeMembro.objects.filter(
                equipe=self.equipe,
                voluntario=self.outro_coordenador_voluntario,
                status='ATIVO',
            ).count(),
            total_membros_ativos,
        )
        self.assertContains(
            resposta,
            f'&quot;{self.outro_coordenador_voluntario.nome}&quot; já possui vínculo ativo '
            f'com a equipe &quot;{self.equipe.nome}&quot;.',
        )

    def test_coordenador_nao_adiciona_voluntario_inativo(self):
        voluntario_inativo = Voluntario.objects.create(
            nome='Voluntário inativo',
            dt_nascimento=date(1993, 1, 1),
            endereco='Rua F',
            telefone='11444444444',
            email='voluntario-inativo@teste.org',
            status='INATIVO',
        )

        resposta_formulario = self.client.get(
            reverse('equipe_detalhe', args=[self.equipe.id_equipe])
        )
        self.assertNotContains(
            resposta_formulario,
            f'<option value="{voluntario_inativo.id_voluntario}">',
        )

        resposta = self.client.post(
            reverse('adicionar_membro_equipe', args=[self.equipe.id_equipe]),
            {'voluntario': voluntario_inativo.id_voluntario},
            follow=True,
        )

        self.assertFalse(
            EquipeMembro.objects.filter(
                equipe=self.equipe,
                voluntario=voluntario_inativo,
            ).exists()
        )
        self.assertContains(
            resposta,
            f'Não foi possível adicionar &quot;{voluntario_inativo.nome}&quot; à equipe '
            f'&quot;{self.equipe.nome}&quot;, pois o cadastro do voluntário não está ativo.',
        )

    def test_coordenador_nao_adiciona_membro_a_equipe_inativa(self):
        voluntario_novo = Voluntario.objects.create(
            nome='Novo voluntário',
            dt_nascimento=date(1993, 1, 1),
            endereco='Rua F',
            telefone='11444444444',
            email='novo-voluntario@teste.org',
        )
        self.equipe.status = 'INATIVA'
        self.equipe.save(update_fields=['status'])

        resposta = self.client.post(
            reverse('adicionar_membro_equipe', args=[self.equipe.id_equipe]),
            {'voluntario': voluntario_novo.id_voluntario},
            follow=True,
        )

        self.assertFalse(
            EquipeMembro.objects.filter(
                equipe=self.equipe,
                voluntario=voluntario_novo,
                status='ATIVO',
            ).exists()
        )
        self.assertContains(
            resposta,
            f'Você não tem permissão para adicionar membros à equipe &quot;{self.equipe.nome}&quot;.',
        )

    def test_equipe_inativa_bloqueia_remocao_de_voluntario_e_coordenador(self):
        self.equipe.status = 'INATIVA'
        self.equipe.save(update_fields=['status'])

        for membro in (
            self.membro_voluntario,
            self.outro_membro_coordenador,
            self.membro_coordenador,
        ):
            with self.subTest(papel=membro.papel, proprio=membro == self.membro_coordenador):
                resposta = self.client.post(
                    reverse(
                        'remover_membro_equipe',
                        args=[self.equipe.id_equipe, membro.id_equipe_membro],
                    ),
                    follow=True,
                )

                membro.refresh_from_db()
                self.assertEqual(membro.status, 'ATIVO')
                self.assertIsNone(membro.dt_saida)
                self.assertContains(
                    resposta,
                    f'Você não tem permissão para remover membros da equipe '
                    f'&quot;{self.equipe.nome}&quot;.',
                )

    def test_equipe_inativa_bloqueia_alteracao_de_funcao_de_membro(self):
        administrador_voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1988, 1, 1),
            endereco='Rua G',
            telefone='11333333333',
            email='admin-equipe-inativa@teste.org',
        )
        administrador = Usuario.objects.create(
            id_voluntario=administrador_voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        session = self.client.session
        session['usuario_id'] = administrador.id_usuario
        session['usuario_tipo'] = administrador.tipo
        session.save()
        self.equipe.status = 'INATIVA'
        self.equipe.save(update_fields=['status'])

        resposta = self.client.post(
            reverse(
                'atualizar_funcao_membro',
                args=[self.equipe.id_equipe, self.membro_voluntario.id_equipe_membro],
            ),
            {'papel': EquipeMembro.PAPEL_COORDENADOR},
            follow=True,
        )

        self.membro_voluntario.refresh_from_db()
        self.assertEqual(self.membro_voluntario.papel, EquipeMembro.PAPEL_VOLUNTARIO)
        self.assertContains(
            resposta,
            f'Não é possível alterar funções de membros na equipe inativa '
            f'&quot;{self.equipe.nome}&quot;.',
        )

    def test_equipe_inativa_bloqueia_adicao_de_coordenador(self):
        administrador_voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1988, 1, 1),
            endereco='Rua G',
            telefone='11333333334',
            email='admin-adicao-coord-inativa@teste.org',
        )
        administrador = Usuario.objects.create(
            id_voluntario=administrador_voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        voluntario_novo = Voluntario.objects.create(
            nome='Novo coordenador',
            dt_nascimento=date(1993, 1, 1),
            endereco='Rua H',
            telefone='11333333335',
            email='novo-coordenador-inativo@teste.org',
        )
        session = self.client.session
        session['usuario_id'] = administrador.id_usuario
        session['usuario_tipo'] = administrador.tipo
        session.save()
        self.equipe.status = 'INATIVA'
        self.equipe.save(update_fields=['status'])

        resposta = self.client.post(
            reverse('adicionar_membro_equipe', args=[self.equipe.id_equipe]),
            {
                'voluntario': voluntario_novo.id_voluntario,
                'papel': EquipeMembro.PAPEL_COORDENADOR,
            },
            follow=True,
        )

        self.assertFalse(
            EquipeMembro.objects.filter(
                equipe=self.equipe,
                voluntario=voluntario_novo,
                status='ATIVO',
            ).exists()
        )
        self.assertContains(
            resposta,
            f'Você não tem permissão para adicionar membros à equipe &quot;{self.equipe.nome}&quot;.',
        )

    def test_equipe_inativa_bloqueia_exclusao_de_historico_de_membro(self):
        administrador_voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1988, 1, 1),
            endereco='Rua I',
            telefone='11333333336',
            email='admin-historico-inativo@teste.org',
        )
        administrador = Usuario.objects.create(
            id_voluntario=administrador_voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        session = self.client.session
        session['usuario_id'] = administrador.id_usuario
        session['usuario_tipo'] = administrador.tipo
        session.save()
        self.equipe.status = 'INATIVA'
        self.equipe.save(update_fields=['status'])
        self.membro_voluntario.status = 'INATIVO'
        self.membro_voluntario.save(update_fields=['status'])

        resposta = self.client.post(
            reverse(
                'excluir_historico_membro',
                args=[self.equipe.id_equipe, self.membro_voluntario.id_equipe_membro],
            ),
            follow=True,
        )

        self.assertTrue(
            EquipeMembro.objects.filter(pk=self.membro_voluntario.pk).exists()
        )
        self.assertContains(
            resposta,
            f'Não é possível excluir registros de membros da equipe inativa '
            f'&quot;{self.equipe.nome}&quot;.',
        )

    def test_coordenador_nao_gerencia_equipe_por_urls_diretas(self):
        equipe_vazia = Equipe.objects.create(nome='Equipe sem membros')
        urls_e_dados = (
            (
                reverse('cadastro_equipe'),
                {
                    'nome': 'Equipe não autorizada',
                    'descricao': '',
                    'status': 'ATIVA',
                },
            ),
            (
                reverse('editar_equipe', args=[self.equipe.id_equipe]),
                {
                    'nome': 'Nome alterado sem autorização',
                    'descricao': '',
                    'status': 'ATIVA',
                },
            ),
            (
                reverse('atualizar_status_equipe', args=[self.equipe.id_equipe]),
                {'status': 'INATIVA'},
            ),
            (
                reverse('excluir_equipe', args=[equipe_vazia.id_equipe]),
                {},
            ),
        )

        for url, dados in urls_e_dados:
            with self.subTest(url=url):
                resposta = self.client.post(url, dados)
                self.assertEqual(resposta.status_code, 403)

        self.assertFalse(Equipe.objects.filter(nome='Equipe não autorizada').exists())
        self.equipe.refresh_from_db()
        equipe_vazia.refresh_from_db()
        self.assertEqual(self.equipe.nome, 'Equipe Teste')
        self.assertEqual(self.equipe.status, 'ATIVA')
        self.assertTrue(Equipe.objects.filter(pk=equipe_vazia.pk).exists())

    def test_paginacao_preserva_filtros_de_busca_status_e_participacao(self):
        equipes_filtradas = [
            Equipe(nome=f'Projeto de praia {indice:02d}', status='ATIVA')
            for indice in range(23)
        ]
        Equipe.objects.bulk_create(equipes_filtradas)
        equipes_filtradas = list(
            Equipe.objects.filter(nome__startswith='Projeto de praia').order_by('nome')
        )
        EquipeMembro.objects.bulk_create([
            EquipeMembro(
                equipe=equipe,
                voluntario=self.coordenador_voluntario,
                papel=EquipeMembro.PAPEL_COORDENADOR,
            )
            for equipe in equipes_filtradas
        ])
        equipe_inativa = Equipe.objects.create(
            nome='Projeto de praia inativo',
            status='INATIVA',
        )
        EquipeMembro.objects.create(
            equipe=equipe_inativa,
            voluntario=self.coordenador_voluntario,
            papel=EquipeMembro.PAPEL_COORDENADOR,
        )
        equipe_com_outro_papel = Equipe.objects.create(
            nome='Projeto de praia outro papel',
            status='ATIVA',
        )
        EquipeMembro.objects.create(
            equipe=equipe_com_outro_papel,
            voluntario=self.coordenador_voluntario,
            papel=EquipeMembro.PAPEL_VOLUNTARIO,
        )
        filtros = {
            'busca': 'Projeto de praia',
            'status': 'ATIVA',
            'participacao': 'MINHAS',
            'papel_equipe': EquipeMembro.PAPEL_COORDENADOR,
        }

        primeira_pagina = self.client.get(reverse('equipes'), filtros)

        self.assertEqual(primeira_pagina.status_code, 200)
        self.assertEqual(primeira_pagina.context['pagina'].number, 1)
        self.assertEqual(primeira_pagina.context['pagina'].paginator.count, 23)
        self.assertEqual(len(primeira_pagina.context['equipes']), 20)
        self.assertContains(
            primeira_pagina,
            '?busca=Projeto+de+praia&amp;status=ATIVA&amp;participacao=MINHAS'
            '&amp;papel_equipe=COORDENADOR&amp;page=2',
        )

        segunda_pagina = self.client.get(
            reverse('equipes'),
            {**filtros, 'page': '2'},
        )

        self.assertEqual(segunda_pagina.status_code, 200)
        self.assertEqual(segunda_pagina.context['pagina'].number, 2)
        self.assertEqual(segunda_pagina.context['pagina'].paginator.count, 23)
        self.assertEqual(len(segunda_pagina.context['equipes']), 3)
        self.assertEqual(segunda_pagina.context['busca'], filtros['busca'])
        self.assertEqual(segunda_pagina.context['status_selecionado'], filtros['status'])
        self.assertEqual(
            segunda_pagina.context['participacao_selecionada'],
            filtros['participacao'],
        )
        self.assertEqual(
            segunda_pagina.context['papel_equipe_selecionado'],
            filtros['papel_equipe'],
        )
        self.assertContains(
            segunda_pagina,
            '?busca=Projeto+de+praia&amp;status=ATIVA&amp;participacao=MINHAS'
            '&amp;papel_equipe=COORDENADOR&amp;page=1',
        )

    def test_coordenador_nao_altera_membro_de_outra_equipe_por_id(self):
        outra_equipe = Equipe.objects.create(nome='Outra Equipe')
        membro_de_outra_equipe = EquipeMembro.objects.create(
            equipe=outra_equipe,
            voluntario=self.voluntario,
            papel=EquipeMembro.PAPEL_VOLUNTARIO,
        )

        resposta = self.client.post(
            reverse(
                'remover_membro_equipe',
                args=[self.equipe.id_equipe, membro_de_outra_equipe.id_equipe_membro],
            ),
        )

        membro_de_outra_equipe.refresh_from_db()
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(membro_de_outra_equipe.status, 'ATIVO')
        self.assertEqual(membro_de_outra_equipe.equipe_id, outra_equipe.id_equipe)
