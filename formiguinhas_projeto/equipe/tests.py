from datetime import date

from django.test import TestCase
from django.urls import reverse

from usuario.models import Usuario, Voluntario

from .models import Equipe


class BreadcrumbDetalheEquipeTests(TestCase):
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
