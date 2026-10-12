from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acao.models import Acao
from praia.models import Praia
from usuario.models import Usuario, Voluntario

from .models import ColetaResiduo, ItemColetaResiduo


class DetalheColetaResiduoTests(TestCase):
    def setUp(self):
        self.admin = self.criar_usuario('Admin', 'admin-coleta@example.org', 'ADMIN')
        self.coordenador = self.criar_usuario(
            'Coordenador',
            'coord-coleta@example.org',
            'COORDENADOR',
        )
        self.praia = Praia.objects.create(
            nome='Praia de Teste',
            cidade='Santos',
            latitude=-23.967,
            longitude=-46.328,
        )
        self.acao = Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=timezone.localdate(),
            local='Orla',
            praia=self.praia,
        )
        self.coleta = ColetaResiduo.objects.create(
            origem='ACAO',
            acao=self.acao,
            registrado_por=self.admin,
            registrado_por_nome='Admin',
            registrado_por_tipo='ADMIN',
        )
        ItemColetaResiduo.objects.create(
            coleta=self.coleta,
            tipo='PLASTICO',
            categoria='RECICLAVEL',
            quantidade='2.00',
            unidade='KG',
            registrado_por=self.admin,
            registrado_por_nome='Admin',
            registrado_por_tipo='ADMIN',
        )

    def criar_usuario(self, nome, email, tipo):
        voluntario = Voluntario.objects.create(
            nome=nome,
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua de Teste, 1',
            telefone='13999999999',
            email=email,
        )
        return Usuario.objects.create(
            id_voluntario=voluntario,
            tipo=tipo,
            senha='senha-de-teste',
        )

    def autenticar(self, usuario):
        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_tipo'] = usuario.tipo
        session['usuario_nome'] = usuario.id_voluntario.nome
        session.save()

    def test_admin_visualiza_itens_e_pode_adicionar_outro(self):
        self.autenticar(self.admin)

        detalhe = self.client.get(
            reverse('detalhe_coleta_residuo', args=[self.coleta.id_coleta]),
        )

        self.assertEqual(detalhe.status_code, 200)
        self.assertContains(detalhe, 'Itens da coleta')
        self.assertContains(detalhe, 'Plástico')
        self.assertContains(detalhe, 'Adicionar item à coleta')
        self.assertContains(
            detalhe,
            reverse('acao_detalhe', args=[self.acao.id_acao]),
        )

        resposta = self.client.post(
            reverse('adicionar_item_coleta', args=[self.coleta.id_coleta]),
            {
                'tipo': 'PAPEL',
                'categoria': 'RECICLAVEL',
                'quantidade': '1.50',
                'unidade': 'KG',
                'observacao': 'Papel separado',
            },
        )

        self.assertRedirects(
            resposta,
            reverse('detalhe_coleta_residuo', args=[self.coleta.id_coleta]),
        )
        self.assertTrue(
            ItemColetaResiduo.objects.filter(
                coleta=self.coleta,
                tipo='PAPEL',
                quantidade='1.50',
            ).exists(),
        )

    def test_coordenador_consulta_coleta_sem_formulario_administrativo(self):
        self.autenticar(self.coordenador)

        response = self.client.get(
            reverse('detalhe_coleta_residuo', args=[self.coleta.id_coleta]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Praia de Teste')
        self.assertContains(response, 'Plástico')
        self.assertNotContains(response, 'Adicionar item à coleta')
