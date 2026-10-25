from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acao.models import Acao
from praia.models import Praia
from usuario.models import Usuario, Voluntario

from .forms import ItemColetaResiduoForm, ResiduoColetadoForm
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

    def test_formularios_de_acao_e_bag_compartilham_campos_e_opcoes(self):
        form_acao = ResiduoColetadoForm(require_type_and_category=True)
        form_bag = ItemColetaResiduoForm(require_type_and_category=True)

        for campo in ('tipo', 'categoria', 'quantidade', 'unidade', 'observacao'):
            with self.subTest(campo=campo):
                self.assertEqual(
                    form_acao.fields[campo].label,
                    form_bag.fields[campo].label,
                )
                self.assertEqual(
                    form_acao.fields[campo].help_text,
                    form_bag.fields[campo].help_text,
                )
                self.assertEqual(
                    form_acao.fields[campo].widget.attrs,
                    form_bag.fields[campo].widget.attrs,
                )
                if campo in ('tipo', 'categoria', 'unidade'):
                    self.assertEqual(
                        list(form_acao.fields[campo].choices),
                        list(form_bag.fields[campo].choices),
                    )
        self.assertTrue(form_acao.fields['tipo'].required)
        self.assertTrue(form_acao.fields['categoria'].required)
        self.assertTrue(form_bag.fields['tipo'].required)
        self.assertTrue(form_bag.fields['categoria'].required)
        self.assertFalse(form_acao.fields['quantidade'].required)
        self.assertFalse(form_bag.fields['quantidade'].required)

    def test_formularios_de_acao_e_bag_rejeitam_tipo_ou_categoria_vazios(self):
        dados = {'tipo': '', 'categoria': '', 'quantidade': '', 'unidade': ''}

        for form_class in (ResiduoColetadoForm, ItemColetaResiduoForm):
            with self.subTest(form=form_class.__name__):
                form = form_class(dados, require_type_and_category=True)
                self.assertFalse(form.is_valid())
                self.assertIn('tipo', form.errors)
                self.assertIn('categoria', form.errors)

    def test_formularios_de_acao_e_bag_aceitam_dados_equivalentes(self):
        dados = {
            'tipo': 'PLASTICO',
            'categoria': 'RECICLAVEL',
            'quantidade': '2.50',
            'unidade': 'KG',
            'observacao': 'Garrafas plásticas.',
        }

        for form_class in (ResiduoColetadoForm, ItemColetaResiduoForm):
            with self.subTest(form=form_class.__name__):
                form = form_class(dados, require_type_and_category=True)
                self.assertTrue(form.is_valid(), form.errors)

    def test_admin_visualiza_itens_e_pode_adicionar_outro(self):
        self.autenticar(self.admin)
        self.assertEqual(self.coleta.acao_id, self.acao.id_acao)

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

    def test_coletas_sem_vinculo_nao_exibem_acao_none_nem_quebram_detalhe(self):
        self.autenticar(self.admin)
        coleta_sem_acao = ColetaResiduo.objects.create(
            origem='ACAO',
            registrado_por=self.admin,
            registrado_por_nome='Admin',
            registrado_por_tipo='ADMIN',
        )
        ColetaResiduo.objects.create(
            origem='BAG',
            registrado_por=self.admin,
            registrado_por_nome='Admin',
            registrado_por_tipo='ADMIN',
        )

        lista = self.client.get(reverse('residuos'))
        detalhe = self.client.get(
            reverse('detalhe_coleta_residuo', args=[coleta_sem_acao.id_coleta]),
        )

        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, 'Ação sem vínculo')
        self.assertContains(lista, 'Bag sem vínculo')
        self.assertNotContains(lista, 'Ação #None')
        self.assertEqual(detalhe.status_code, 200)
        self.assertContains(detalhe, 'Coleta de ação sem vínculo')
        self.assertNotContains(detalhe, '/acao/None/')

    def test_coordenador_consulta_coleta_sem_formulario_administrativo(self):
        self.autenticar(self.coordenador)

        response = self.client.get(
            reverse('detalhe_coleta_residuo', args=[self.coleta.id_coleta]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Praia de Teste')
        self.assertContains(response, 'Plástico')
        self.assertNotContains(response, 'Adicionar item à coleta')
