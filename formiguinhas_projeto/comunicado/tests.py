from datetime import date

from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from acao.models import Acao
from doacao.models import Doacao, DoacaoFinanceira
from praia.models import Praia
from residuo.models import ResiduoColetado
from usuario.models import Usuario, Voluntario

from .context_processors import notificacoes_comunicados
from .models import (
    Comunicado,
    ComunicadoAcao,
    ComunicadoDoacao,
    ComunicadoLeitura,
    Tema,
)
from .services import desarquivar
from .views import interno_detalhe


class ComunicadoLeituraTests(TestCase):
    def setUp(self):
        voluntario = Voluntario.objects.create(
            nome='Coordenador de teste',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua de teste',
            telefone='11999999999',
            email='coordenador-teste@example.com',
        )
        self.usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )
        self.session = self.client.session
        self.session['usuario_id'] = self.usuario.id_usuario
        self.session['usuario_tipo'] = self.usuario.tipo
        self.session['usuario_nome'] = voluntario.nome
        self.session.save()
        self.client.cookies['sessionid'] = self.session.session_key

    def criar_comunicado(self, titulo):
        return Comunicado.objects.create(
            tipo=Comunicado.AVISO,
            titulo=titulo,
            conteudo='Conteúdo de teste',
            publico=Comunicado.TODOS,
            status=Comunicado.PUBLICADO,
            dt_publicacao=timezone.now(),
        )

    def test_sino_conta_apenas_comunicados_nao_lidos(self):
        self.criar_comunicado('Aviso não lido')
        outro = self.criar_comunicado('Aviso lido')
        ComunicadoLeitura.objects.create(comunicado=outro, usuario=self.usuario)

        request = RequestFactory().get('/')
        request.session = self.session
        contexto = notificacoes_comunicados(request)

        self.assertEqual(contexto['comunicados_nao_lidos_count'], 1)
        self.assertEqual(contexto['comunicados_vigentes_count'], 2)

    def test_abrir_central_mantem_comunicados_nao_lidos(self):
        self.criar_comunicado('Primeiro aviso')
        self.criar_comunicado('Segundo aviso')

        response = self.client.get(reverse('central_comunicados'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ComunicadoLeitura.objects.filter(usuario=self.usuario).count(),
            0,
        )
        self.assertEqual(response.context['total_nao_lidos'], 2)
        self.assertEqual(response.context['total_lidos'], 0)
        self.assertFalse(response.context['comunicados'][0].foi_lido)

    def test_central_filtra_nao_lidos_e_lidos(self):
        nao_lido = self.criar_comunicado('Aviso não lido')
        lido = self.criar_comunicado('Aviso lido')
        ComunicadoLeitura.objects.create(comunicado=lido, usuario=self.usuario)

        resposta_nao_lidos = self.client.get(
            reverse('central_comunicados'),
            {'leitura': 'nao_lidos'},
        )
        resposta_lidos = self.client.get(
            reverse('central_comunicados'),
            {'leitura': 'lidos'},
        )

        self.assertEqual(resposta_nao_lidos.status_code, 200)
        self.assertContains(resposta_nao_lidos, nao_lido.titulo)
        self.assertNotContains(resposta_nao_lidos, lido.titulo)
        self.assertContains(resposta_nao_lidos, 'communication-item is-unread')
        self.assertContains(resposta_nao_lidos, 'Não lido')
        self.assertEqual(resposta_lidos.status_code, 200)
        self.assertContains(resposta_lidos, lido.titulo)
        self.assertNotContains(resposta_lidos, nao_lido.titulo)
        self.assertNotContains(resposta_lidos, 'communication-item is-unread')

    def test_central_filtra_comunicados_por_busca(self):
        self.criar_comunicado('Mutirão deste sábado')
        self.criar_comunicado('Reunião da equipe')

        response = self.client.get(
            reverse('central_comunicados'),
            {'busca': 'Mutirão'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mutirão deste sábado')
        self.assertNotContains(response, 'Reunião da equipe')

    def test_central_filtra_comunicados_por_tipo(self):
        self.criar_comunicado('Aviso importante')
        tema = Tema.objects.create(nome='Tema de teste')
        Comunicado.objects.create(
            tipo=Comunicado.NOTICIA,
            titulo='Notícia da ONG',
            conteudo='Conteúdo de teste',
            resumo='Resumo da notícia',
            tema=tema,
            publico=Comunicado.TODOS,
            status=Comunicado.PUBLICADO,
            dt_publicacao=timezone.now(),
        )

        response = self.client.get(
            reverse('central_comunicados'),
            {'tipo': Comunicado.NOTICIA},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notícia da ONG')
        self.assertNotContains(response, 'Aviso importante')

    def test_central_pagina_resultados_e_preserva_filtros(self):
        for indice in range(21):
            self.criar_comunicado(f'Aviso adicional {indice}')

        response = self.client.get(
            reverse('central_comunicados'),
            {'leitura': 'nao_lidos', 'page': '2'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pagina'].number, 2)
        self.assertEqual(response.context['pagina'].paginator.count, 21)
        self.assertEqual(response.context['filtros_query'], 'leitura=nao_lidos')
        self.assertContains(response, 'leitura=nao_lidos&amp;page=1')

    def test_abrir_detalhe_marca_apenas_o_comunicado(self):
        comunicado = self.criar_comunicado('Aviso detalhado')
        outro = self.criar_comunicado('Outro aviso')

        request = RequestFactory().get(
            reverse('comunicado_interno_detalhe', args=[comunicado.id_comunicado])
        )
        request.session = self.session
        response = interno_detalhe(request, comunicado.id_comunicado)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'communication-read-label">Lido')
        self.assertTrue(
            ComunicadoLeitura.objects.filter(
                usuario=self.usuario,
                comunicado=comunicado,
            ).exists()
        )
        self.assertFalse(
            ComunicadoLeitura.objects.filter(
                usuario=self.usuario,
                comunicado=outro,
            ).exists()
        )
        request = RequestFactory().get('/')
        request.session = self.session
        self.assertEqual(
            notificacoes_comunicados(request)['comunicados_nao_lidos_count'],
            1,
        )

    def test_desarquivar_retorna_comunicado_para_rascunho(self):
        comunicado = self.criar_comunicado('Aviso arquivado')
        comunicado.status = Comunicado.ARQUIVADO
        comunicado.save(update_fields=('status',))

        desarquivar(comunicado, self.usuario)

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.status, Comunicado.RASCUNHO)


class ComunicadoStatusAdminTests(TestCase):
    def setUp(self):
        voluntario = Voluntario.objects.create(
            nome='Administrador de teste',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua de teste',
            telefone='11999999999',
            email='administrador-teste@example.com',
        )
        self.usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        session = self.client.session
        session['usuario_id'] = self.usuario.id_usuario
        session['usuario_tipo'] = self.usuario.tipo
        session['usuario_nome'] = voluntario.nome
        session.save()
        self.client.cookies['sessionid'] = session.session_key
        self.comunicado = Comunicado.objects.create(
            tipo=Comunicado.AVISO,
            titulo='Aviso para alterar status',
            conteudo='Conteúdo de teste',
            publico=Comunicado.TODOS,
            status=Comunicado.RASCUNHO,
            autor=self.usuario,
            duracao_expiracao=3,
            unidade_duracao_expiracao='DIAS',
        )

    def alterar_status(self, status, **filtros):
        return self.client.post(
            reverse(
                'comunicado_status',
                args=[self.comunicado.id_comunicado, 'alterar_status'],
            ),
            {'status': status, **filtros},
        )

    def test_alterar_status_publica_comunicado_e_preserva_filtros(self):
        response = self.alterar_status(
            Comunicado.PUBLICADO,
            busca='aviso',
            tipo=Comunicado.AVISO,
            filtro_status=Comunicado.RASCUNHO,
        )

        self.comunicado.refresh_from_db()
        self.assertEqual(
            self.comunicado.status,
            Comunicado.PUBLICADO,
            [str(mensagem) for mensagem in response.wsgi_request._messages],
        )
        self.assertIsNotNone(self.comunicado.dt_publicacao)
        self.assertIsNotNone(self.comunicado.dt_expiracao)
        self.assertEqual(
            response.url,
            reverse('comunicados_admin')
            + '?busca=aviso&tipo=AVISO&status=RASCUNHO',
        )

    def test_alterar_status_arquiva_e_restaura_comunicado(self):
        response = self.alterar_status(Comunicado.ARQUIVADO)
        self.assertEqual(response.status_code, 302)
        self.comunicado.refresh_from_db()
        self.assertEqual(self.comunicado.status, Comunicado.ARQUIVADO)

        response = self.alterar_status(Comunicado.RASCUNHO)
        self.assertEqual(response.status_code, 302)
        self.comunicado.refresh_from_db()
        self.assertEqual(self.comunicado.status, Comunicado.RASCUNHO)

    def test_status_invalido_nao_altera_comunicado(self):
        response = self.alterar_status('INVALIDO')

        self.comunicado.refresh_from_db()
        self.assertEqual(self.comunicado.status, Comunicado.RASCUNHO)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(list(response.wsgi_request._messages)), 1)

    def test_status_atual_nao_registra_nova_edicao(self):
        response = self.alterar_status(Comunicado.RASCUNHO)

        self.comunicado.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.comunicado.dt_ultima_edicao)

    def test_controle_exibe_seletor_de_status_e_mantem_edicao(self):
        response = self.client.get(reverse('comunicados_admin'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="status"')
        self.assertContains(response, 'Rascunho')
        self.assertContains(response, 'name="filtro_status"')
        self.assertContains(response, 'Editar')
        self.assertNotContains(response, '>Publicar</button>')
        self.assertContains(response, 'Até 20 por página')
        self.assertContains(response, 'aria-label="Paginação de registros"')
        self.assertContains(response, 'Página 1 de 1')
        self.assertContains(response, 'Exibindo 1–1 de 1')

    def test_controle_pagina_resultados_e_mantem_filtros(self):
        for indice in range(20):
            Comunicado.objects.create(
                tipo=Comunicado.AVISO,
                titulo=f'Aviso adicional {indice}',
                conteudo='Conteúdo de teste',
                publico=Comunicado.TODOS,
                status=Comunicado.RASCUNHO,
                autor=self.usuario,
            )

        response = self.client.get(
            reverse('comunicados_admin'),
            {'page': 2, 'tipo': Comunicado.AVISO},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pagina'].number, 2)
        self.assertEqual(response.context['pagina'].start_index(), 21)
        self.assertContains(response, 'Página 2 de 2')
        self.assertContains(response, 'Exibindo 21–21 de 21')
        self.assertContains(response, 'name="page" value="2"')
        self.assertContains(response, 'Aviso para alterar status')

    def test_atualizar_status_preserva_pagina_atual(self):
        for indice in range(20):
            Comunicado.objects.create(
                tipo=Comunicado.AVISO,
                titulo=f'Aviso adicional {indice}',
                conteudo='Conteúdo de teste',
                publico=Comunicado.TODOS,
                status=Comunicado.RASCUNHO,
                autor=self.usuario,
            )

        response = self.alterar_status(Comunicado.ARQUIVADO, page='2')

        self.assertEqual(response.url, reverse('comunicados_admin') + '?page=2')

    def test_paginacao_publica_exibe_limite_total_e_preserva_filtro(self):
        for indice in range(21):
            Comunicado.objects.create(
                tipo=Comunicado.AVISO,
                titulo=f'Aviso público {indice}',
                conteudo='Conteúdo de teste',
                publico=Comunicado.TODOS,
                status=Comunicado.PUBLICADO,
                dt_publicacao=timezone.now(),
            )

        response = self.client.get(
            reverse('comunicados_publicos'),
            {'tipo': Comunicado.AVISO, 'page': '2'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pagina'].number, 2)
        self.assertEqual(response.context['pagina'].paginator.count, 21)
        self.assertEqual(response.context['filtros_query'], 'tipo=AVISO')
        self.assertContains(response, 'Exibindo 21–21 de 21')
        self.assertContains(response, 'Até 20 por página')
        self.assertContains(response, 'Página 2 de 2')
        self.assertContains(response, 'tipo=AVISO&amp;page=1')


class ComunicadoResiduoRelacionamentoTests(TestCase):
    def setUp(self):
        voluntario = Voluntario.objects.create(
            nome='Administrador de resíduos',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua de teste',
            telefone='11999999999',
            email='administrador-residuos@example.com',
        )
        self.usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        session = self.client.session
        session['usuario_id'] = self.usuario.id_usuario
        session['usuario_tipo'] = self.usuario.tipo
        session['usuario_nome'] = voluntario.nome
        session.save()
        self.client.cookies['sessionid'] = session.session_key

        praia = Praia.objects.create(
            nome='Praia de teste',
            cidade='Santos',
            latitude=-23.96,
            longitude=-46.33,
            cadastrado_por=self.usuario,
        )
        self.acao = Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=timezone.localdate(),
            local='Trecho norte',
            status=Acao.STATUS_CONCLUIDA,
            praia=praia,
        )
        self.residuo = ResiduoColetado.objects.create(
            acao=self.acao,
            tipo='PLASTICO',
            categoria='RECICLAVEL',
            quantidade='2.50',
            unidade='KG',
            registrado_por=self.usuario,
            registrado_por_nome=voluntario.nome,
            registrado_por_tipo=self.usuario.tipo,
        )

    def test_selecionar_acao_disponibiliza_residuos_existentes(self):
        response = self.client.get(
            reverse('comunicado_relacionamentos'),
            {'acao': self.acao.id_acao},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['residuos'], [{
            'id': self.residuo.id_residuo,
            'acao_id': self.acao.id_acao,
            'acao': f'Mutirão - {self.acao.data:%d/%m/%Y}',
            'tipo': 'Plástico',
            'categoria': 'Reciclável',
            'quantidade': '2.50',
            'unidade': 'Quilograma (kg)',
        }])

    def test_detalhe_do_comunicado_apresenta_residuo_da_acao_relacionada(self):
        comunicado = Comunicado.objects.create(
            tipo=Comunicado.AVISO,
            titulo='Aviso sobre a coleta',
            conteudo='Mensagem de teste',
            publico=Comunicado.TODOS,
            status=Comunicado.PUBLICADO,
            dt_publicacao=timezone.now(),
            autor=self.usuario,
        )
        ComunicadoAcao.objects.create(comunicado=comunicado, acao=self.acao)

        response = self.client.get(
            reverse('comunicado_interno_detalhe', args=[comunicado.id_comunicado])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Resíduo: Plástico')
        self.assertContains(response, 'Reciclável')
        self.assertContains(response, '2.50 Quilograma (kg)')


class ComunicadoDoacaoRelacionamentoTests(TestCase):
    def setUp(self):
        voluntario = Voluntario.objects.create(
            nome='Administrador de doações',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua de teste',
            telefone='11999999999',
            email='administrador-doacoes@example.com',
        )
        self.usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        session = self.client.session
        session['usuario_id'] = self.usuario.id_usuario
        session['usuario_tipo'] = self.usuario.tipo
        session['usuario_nome'] = voluntario.nome
        session.save()
        self.client.cookies['sessionid'] = session.session_key
        self.doacao = Doacao.objects.create(
            tipo=Doacao.FINANCEIRA,
            anonima=True,
            data_recebimento=timezone.localdate(),
            status=Doacao.CONFIRMADA,
            registrado_por=self.usuario,
            registrado_por_nome=voluntario.nome,
            registrado_por_tipo=self.usuario.tipo,
        )
        DoacaoFinanceira.objects.create(
            doacao=self.doacao,
            valor='125.50',
            forma_recebimento=DoacaoFinanceira.PIX,
        )

    def test_formulario_lista_doacoes_para_relacionamento(self):
        response = self.client.get(reverse('comunicado_cadastrar'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id_doacoes')
        self.assertContains(response, f'Doação #{self.doacao.id_doacao}')
        self.assertContains(response, 'Financeira - Anônima')
        self.assertNotContains(response, '125.50')

    def test_endpoint_retorna_dados_da_doacao_selecionada(self):
        response = self.client.get(
            reverse('comunicado_relacionamentos'),
            {'doacao': self.doacao.id_doacao},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['doacoes'], [{
            'id': self.doacao.id_doacao,
            'tipo': 'Financeira',
            'data': self.doacao.data_recebimento.strftime('%d/%m/%Y'),
            'doador': 'Anônima',
        }])

    def test_salvar_comunicado_persiste_doacao_relacionada(self):
        response = self.client.post(
            reverse('comunicado_cadastrar'),
            {
                'tipo': Comunicado.AVISO,
                'titulo': 'Comunicado sobre doação',
                'resumo': '',
                'conteudo': 'Agradecemos a doação recebida.',
                'publico': Comunicado.TODOS,
                'tema': '',
                'duracao_expiracao': '',
                'unidade_duracao_expiracao': '',
                'praias': [],
                'equipes': [],
                'acoes': [],
                'doacoes': [str(self.doacao.id_doacao)],
            },
        )

        self.assertEqual(response.status_code, 302)
        comunicado = Comunicado.objects.get(titulo='Comunicado sobre doação')
        self.assertTrue(
            ComunicadoDoacao.objects.filter(
                comunicado=comunicado,
                doacao=self.doacao,
            ).exists()
        )

    def test_detalhe_interno_apresenta_link_da_doacao(self):
        comunicado = Comunicado.objects.create(
            tipo=Comunicado.AVISO,
            titulo='Aviso sobre doação',
            conteudo='Mensagem de teste',
            publico=Comunicado.TODOS,
            status=Comunicado.PUBLICADO,
            dt_publicacao=timezone.now(),
            autor=self.usuario,
        )
        ComunicadoDoacao.objects.create(comunicado=comunicado, doacao=self.doacao)

        response = self.client.get(
            reverse('comunicado_interno_detalhe', args=[comunicado.id_comunicado])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Doação #{self.doacao.id_doacao}')
        self.assertContains(response, reverse('doacao_detalhe', args=[self.doacao.id_doacao]))
        self.assertContains(response, 'R$ 125.50')

    def test_coordenador_acessa_doacao_relacionada(self):
        comunicado = Comunicado.objects.create(
            tipo=Comunicado.AVISO,
            titulo='Aviso sobre doação privada',
            conteudo='Mensagem de teste',
            publico=Comunicado.TODOS,
            status=Comunicado.PUBLICADO,
            dt_publicacao=timezone.now(),
            autor=self.usuario,
        )
        ComunicadoDoacao.objects.create(comunicado=comunicado, doacao=self.doacao)
        self.usuario.tipo = 'COORDENADOR'
        self.usuario.save(update_fields=('tipo',))
        session = self.client.session
        session['usuario_tipo'] = self.usuario.tipo
        session.save()

        response = self.client.get(
            reverse('comunicado_interno_detalhe', args=[comunicado.id_comunicado])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Doação #{self.doacao.id_doacao}')
        self.assertContains(
            response,
            reverse('doacao_detalhe', args=[self.doacao.id_doacao]),
        )
        self.assertContains(response, 'R$ 125.50')
