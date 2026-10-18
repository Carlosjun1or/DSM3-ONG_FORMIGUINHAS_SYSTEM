import csv
import io
from datetime import date

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from auditoria.models import EventoAuditoria
from doacao.models import Doador, Doacao, ItemDoacaoMaterial
from usuario.models import Usuario, Voluntario

from .forms import MaterialForm, MovimentacaoEstoqueForm
from .models import Material, MovimentacaoEstoque


def criar_usuario(nome, email, tipo):
    voluntario = Voluntario.objects.create(
        nome=nome,
        dt_nascimento=date(1990, 1, 1),
        endereco='Rua A, 1',
        telefone='13999999999',
        email=email,
    )
    # Os testes autenticam pela sessão; evitar o hash de senha mantém a suíte rápida.
    return Usuario.objects.create(id_voluntario=voluntario, tipo=tipo, senha='!')


def criar_material(**kw):
    codigo = kw.get('codigo', 'T1')
    nome = kw.get('nome', 'Tinta')
    categoria = kw.get('categoria')
    if categoria is None:
        categoria = f'Categoria-{codigo or nome}'
    dados = dict(
        nome=nome,
        codigo=codigo,
        categoria=categoria,
        unidade='LITRO',
        quantidade_inicial=10,
    )
    dados.update(kw)
    return Material.objects.create(**dados)


def dados_material(**kw):
    dados = dict(
        nome='Luva de Proteção M', codigo='L1', categoria='EPI', descricao='',
        quantidade_inicial=5, estoque_minimo=2, unidade='CAIXA',
    )
    dados.update(kw)
    return dados


class EstoqueTestCase(TestCase):
    def setUp(self):
        self.admin = criar_usuario('Administrador', 'admin@teste.org', 'ADMIN')
        self.coordenador = criar_usuario('Coordenador', 'coord@teste.org', 'COORDENADOR')

    def entrar(self, usuario):
        sessao = self.client.session
        sessao['usuario_id'] = usuario.id_usuario
        sessao['usuario_nome'] = usuario.id_voluntario.nome
        sessao['usuario_tipo'] = usuario.tipo
        sessao.save()


class SimularEstoqueCommandTests(TestCase):
    def setUp(self):
        criar_usuario('Administrador', 'admin-simulacao@teste.org', 'ADMIN')

    def test_cria_dados_integrados_e_pode_ser_executado_mais_de_uma_vez(self):
        call_command('simular_estoque', stdout=io.StringIO())
        call_command('simular_estoque', stdout=io.StringIO())

        self.assertEqual(Material.objects.count(), 4)
        self.assertEqual(MovimentacaoEstoque.objects.count(), 5)
        self.assertEqual(
            Doacao.objects.filter(observacoes__startswith='DADO DEMONSTRATIVO - estoque').count(),
            1,
        )
        doacao = Doacao.objects.get(observacoes__startswith='DADO DEMONSTRATIVO - estoque')
        movimentacao = MovimentacaoEstoque.objects.get(doacao=doacao)
        self.assertEqual(movimentacao.item_doacao.material, movimentacao.material)
        self.assertEqual(movimentacao.quantidade, 6)
        self.assertEqual(
            Material.objects.get(codigo='DEMO-EPI-001').calcular_saldo(),
            32,
        )


class FormulariosEstoqueTests(TestCase):
    def test_formulario_material_tem_placeholders_e_orientacoes(self):
        form = MaterialForm()

        self.assertEqual(form.fields['nome'].widget.attrs['placeholder'], 'Ex.: Luvas de proteção tamanho M')
        self.assertEqual(form.fields['codigo'].widget.attrs['placeholder'], 'Ex.: MAT-0001')
        self.assertEqual(form.fields['quantidade_inicial'].widget.attrs['placeholder'], 'Ex.: 20')
        self.assertEqual(form.fields['estoque_minimo'].widget.attrs['placeholder'], 'Ex.: 5')
        self.assertIn('opcional', form.fields['descricao'].widget.attrs['placeholder'])

    def test_formulario_movimentacao_orienta_os_campos(self):
        form = MovimentacaoEstoqueForm()

        self.assertEqual(form.fields['quantidade'].widget.attrs['placeholder'], 'Ex.: 10')
        self.assertIn('mutirão', form.fields['justificativa'].widget.attrs['placeholder'])
        self.assertIn('Obrigatória para entradas', form.fields['origem'].help_text)
        self.assertIn('saída', form.fields['justificativa'].help_text)
        material = criar_material(nome='Luvas', codigo='LUV-01', quantidade_inicial=8, unidade='CAIXA')
        escolha = form.fields['material'].label_from_instance(
            Material.objects.com_saldo().get(pk=material.pk)
        )
        self.assertIn('saldo: 8 Caixa', escolha)

    def test_tela_de_movimentacao_permite_pesquisar_material(self):
        admin = criar_usuario('Administrador', 'admin-busca@teste.org', 'ADMIN')
        sessao = self.client.session
        sessao['usuario_id'] = admin.id_usuario
        sessao['usuario_nome'] = admin.id_voluntario.nome
        sessao['usuario_tipo'] = admin.tipo
        sessao.save()
        resposta = self.client.get(reverse('cadastrar_movimentacao_estoque'))

        self.assertContains(resposta, 'id="material-search"')
        self.assertContains(resposta, 'Digite o nome ou código do material')
        self.assertContains(resposta, 'aria-controls="material-options"')
        self.assertContains(resposta, 'name="material"')

    def test_tela_de_movimentacao_preseleciona_material_da_url(self):
        admin = criar_usuario('Administrador', 'admin-material-url@teste.org', 'ADMIN')
        sessao = self.client.session
        sessao['usuario_id'] = admin.id_usuario
        sessao['usuario_nome'] = admin.id_voluntario.nome
        sessao['usuario_tipo'] = admin.tipo
        sessao.save()
        material = criar_material(nome='Luvas', codigo='LUV-URL')

        resposta = self.client.get(
            reverse('cadastrar_movimentacao_estoque'),
            {'material': material.pk},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['form'].initial['material'], material)
        self.assertContains(resposta, f'value="{material.pk}" selected')
        self.assertContains(resposta, 'Luvas — saldo: 10 Litro')


class AcessoTests(EstoqueTestCase):
    URLS = [
        'materiais', 'cadastrar_material', 'movimentacoes_estoque',
        'cadastrar_movimentacao_estoque', 'exportar_movimentacoes_estoque',
        'relatorio_estoque',
    ]

    def test_anonimo_vai_para_login(self):
        for nome in self.URLS:
            r = self.client.get(reverse(nome))
            self.assertRedirects(r, reverse('login'), fetch_redirect_response=False, msg_prefix=nome)

    def test_coordenador_e_bloqueado_no_estoque_e_relatorio(self):
        self.entrar(self.coordenador)
        for nome in ('materiais', 'relatorio_estoque'):
            resposta = self.client.get(reverse(nome))
            self.assertEqual(resposta.status_code, 403, nome)
            self.assertContains(resposta, 'Você não tem permissão', status_code=403)

    def test_coordenador_bloqueado_nas_telas_de_administrador(self):
        self.entrar(self.coordenador)
        restritas = [
            n for n in self.URLS
            if n not in ('materiais', 'relatorio_estoque')
        ]
        for nome in restritas:
            r = self.client.get(reverse(nome))
            self.assertEqual(r.status_code, 403, nome)
            self.assertContains(r, 'Você não tem permissão', status_code=403, msg_prefix=nome)

    def test_coordenador_nao_cria_material_nem_movimenta(self):
        self.entrar(self.coordenador)
        self.client.post(reverse('cadastrar_material'), dados_material())
        material = criar_material()
        self.client.post(reverse('cadastrar_movimentacao_estoque'), {
            'material': material.pk, 'tipo': 'SAIDA', 'quantidade': 1, 'justificativa': 'x',
        })
        self.assertEqual(Material.objects.filter(codigo='L1').count(), 0)
        self.assertEqual(MovimentacaoEstoque.objects.count(), 0)

    def test_admin_acessa_todas_as_telas(self):
        self.entrar(self.admin)
        for nome in self.URLS:
            self.assertEqual(self.client.get(reverse(nome)).status_code, 200, nome)

    def test_sessao_de_usuario_removido_e_invalidada(self):
        self.entrar(self.admin)
        self.admin.delete()
        r = self.client.get(reverse('materiais'))
        self.assertRedirects(r, reverse('login'), fetch_redirect_response=False)

    def test_menu_lateral_tem_links_do_estoque_apenas_para_admin(self):
        self.entrar(self.admin)
        resposta = self.client.get(reverse('materiais'))
        self.assertContains(resposta, 'Controle de Estoque')
        self.assertContains(resposta, 'Controle de Movimentações')


class MaterialTests(EstoqueTestCase):
    def test_cadastro_ok_registra_responsavel_e_auditoria(self):
        self.entrar(self.admin)
        r = self.client.post(reverse('cadastrar_material'), dados_material(), follow=True)
        self.assertRedirects(r, reverse('materiais'))
        self.assertContains(r, 'cadastrado com sucesso')
        material = Material.objects.get(codigo='L1')
        self.assertEqual(material.cadastrado_por, self.admin)
        self.assertEqual(material.cadastrado_por_nome, 'Administrador')
        evento = EventoAuditoria.objects.get(entidade='MATERIAL', acao='CRIACAO')
        self.assertEqual(evento.id_registro, material.pk)
        self.assertEqual(evento.usuario, self.admin)

    def test_campos_obrigatorios(self):
        self.entrar(self.admin)
        r = self.client.post(reverse('cadastrar_material'), dados_material(nome='', unidade=''))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Material.objects.count(), 0)
        self.assertContains(r, 'field-error')

    def test_categoria_obrigatoria(self):
        self.assertIn('categoria', MaterialForm(data=dados_material(categoria='')).errors)

    def test_nome_duplicado_sem_distinguir_maiusculas(self):
        criar_material(nome='Luva de Proteção M', codigo='A')
        form = MaterialForm(data=dados_material(nome='luva de proteção m', codigo='B'))
        self.assertFalse(form.is_valid())
        self.assertIn('já existe', str(form.errors))

    def test_cadastro_exibe_nomes_existentes_para_alerta_em_tempo_real(self):
        self.entrar(self.admin)
        criar_material(nome='Álcool em gel', codigo='ALC-1')
        resposta = self.client.get(reverse('cadastrar_material'))

        self.assertContains(resposta, 'materiais-existentes')
        self.assertContains(resposta, 'data-material-name-options')
        self.assertContains(resposta, 'materiais-nome-resultados')
        self.assertEqual(resposta.context['materiais_existentes'][0]['nome'], 'Álcool em gel')
        self.assertEqual(resposta.context['materiais_existentes'][0]['codigo'], 'ALC-1')

    def test_busca_de_material_existente_inclui_categoria_para_consulta(self):
        criar_material(
            nome='Álcool em gel',
            codigo='ALC-1',
            categoria='Higiene',
        )
        self.entrar(self.admin)

        resposta = self.client.get(reverse('cadastrar_material'))

        self.assertEqual(resposta.context['materiais_existentes'][0]['categoria'], 'Higiene')
        self.assertContains(resposta, 'data-material-edit-url')
        self.assertContains(resposta, 'data-categoria-empty')
        self.assertContains(resposta, 'data-value="Higiene"')
        self.assertContains(resposta, 'aria-haspopup="listbox"')

    def test_edicao_nao_exibe_seletor_de_busca_de_material(self):
        self.entrar(self.admin)
        material = criar_material(nome='Luvas', codigo='LUV-EDIT')

        resposta = self.client.get(reverse('editar_material', args=[material.pk]))

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, 'id="materiais-nome-resultados"')
        self.assertNotContains(resposta, 'id="materiais-existentes"')
        self.assertContains(
            resposta,
            f'href="{reverse("cadastrar_movimentacao_estoque")}?material={material.pk}"',
        )
        self.assertContains(resposta, 'Registrar movimentação deste material')

    def test_nome_duplicado_ignorando_espacos(self):
        criar_material(nome='Álcool em gel', codigo='A')
        form = MaterialForm(data=dados_material(nome='  álcool em gel  ', codigo='B'))
        self.assertFalse(form.is_valid())
        self.assertIn('já existe', str(form.errors))

    def test_codigo_duplicado(self):
        criar_material(codigo='L1', nome='Outro')
        self.assertIn('codigo', MaterialForm(data=dados_material()).errors)

    def test_unidades_predefinidas(self):
        rotulos = [r for _, r in Material.UNIDADE_CHOICES]
        for esperado in ('Unidade', 'Caixa', 'Pacote', 'Kg', 'Litro'):
            self.assertIn(esperado, rotulos)
        self.assertFalse(MaterialForm(data=dados_material(unidade='xyz')).is_valid())

    def test_categoria_aceita_espacos_e_normaliza(self):
        form = MaterialForm(data=dados_material(categoria='  Pintura  '))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['categoria'], 'Pintura')

    def test_categoria_existente_e_reutilizada_sem_variacao_de_caixa(self):
        criar_material(categoria='Equipamentos')
        form = MaterialForm(data=dados_material(categoria='  equipamentos  '))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['categoria'], 'Equipamentos')

    def test_formulario_nao_exibe_origem_removida_do_material(self):
        self.entrar(self.admin)
        resposta = self.client.get(reverse('cadastrar_material'))

        self.assertNotContains(resposta, 'id_donativo')
        self.assertNotContains(resposta, 'id_doador')

    def test_edicao_registra_editor_e_valores_anteriores(self):
        material = criar_material(nome='Tinta', codigo='T1')
        self.entrar(self.admin)
        r = self.client.post(
            reverse('editar_material', args=[material.pk]),
            dados_material(nome='Tinta Branca', codigo='T1', unidade='LITRO'),
        )
        self.assertRedirects(r, reverse('materiais'))
        material.refresh_from_db()
        self.assertEqual(material.nome, 'Tinta Branca')
        self.assertEqual(material.ultimo_editado_por, self.admin)
        self.assertIsNotNone(material.dt_ultima_edicao)
        evento = EventoAuditoria.objects.get(entidade='MATERIAL', acao='EDICAO')
        self.assertEqual(evento.valores_anteriores['nome'], 'Tinta')
        self.assertEqual(evento.valores_novos['nome'], 'Tinta Branca')

    def test_edicao_permite_manter_o_proprio_nome(self):
        material = criar_material(nome='Tinta', codigo='T1')
        form = MaterialForm(data=dados_material(nome='Tinta', codigo='T1', unidade='LITRO'), instance=material)
        self.assertTrue(form.is_valid(), form.errors)

    def test_edicao_de_material_inexistente(self):
        self.entrar(self.admin)
        self.assertEqual(self.client.get(reverse('editar_material', args=[999])).status_code, 404)


class SaldoTests(EstoqueTestCase):
    def setUp(self):
        super().setUp()
        self.material = criar_material(quantidade_inicial=10, estoque_minimo=5)

    def movimentar(self, tipo, quantidade, **kw):
        dados = dict(material=self.material, tipo=tipo, quantidade=quantidade)
        if tipo == 'ENTRADA':
            dados.setdefault('origem', 'COMPRA')
        dados.setdefault('registrado_por', self.admin)
        dados.update(kw)
        return MovimentacaoEstoque.objects.create(**dados)

    def test_saldo_considera_inicial_entradas_e_saidas(self):
        self.movimentar('ENTRADA', 5)
        self.movimentar('SAIDA', 3, justificativa='Uso')
        self.assertEqual(self.material.calcular_saldo(), 12)
        self.assertEqual(Material.objects.com_saldo().get(pk=self.material.pk).saldo, 12)

    def test_saida_maior_que_saldo_e_recusada(self):
        with self.assertRaises(ValidationError):
            self.movimentar('SAIDA', 11, justificativa='Uso')
        self.assertEqual(MovimentacaoEstoque.objects.count(), 0)

    def test_saida_exige_justificativa_na_validacao(self):
        mov = MovimentacaoEstoque(material=self.material, tipo='SAIDA', quantidade=1)
        with self.assertRaises(ValidationError):
            mov.clean()

    def test_entrada_exige_origem_na_validacao(self):
        mov = MovimentacaoEstoque(material=self.material, tipo='ENTRADA', quantidade=1)
        with self.assertRaises(ValidationError):
            mov.clean()

    def test_quantidade_zero_recusada(self):
        with self.assertRaises(ValidationError):
            self.movimentar('ENTRADA', 0)

    def test_entrada_de_doacao_so_pelo_registro_de_doacao(self):
        with self.assertRaises(ValidationError):
            self.movimentar('ENTRADA', 1, origem='DOACAO')

    def test_baixo_estoque(self):
        self.assertFalse(self.material.baixo_estoque)
        self.movimentar('SAIDA', 6, justificativa='Uso')
        material = Material.objects.com_saldo().get(pk=self.material.pk)
        self.assertEqual(material.saldo, 4)
        self.assertTrue(material.baixo_estoque)
        self.assertFalse(material.sem_estoque)
        self.movimentar('SAIDA', 4, justificativa='Uso')
        self.assertTrue(Material.objects.com_saldo().get(pk=self.material.pk).sem_estoque)

    def test_material_com_movimentacao_nao_pode_ser_excluido(self):
        from django.db.models import ProtectedError
        self.movimentar('ENTRADA', 1)
        with self.assertRaises(ProtectedError):
            self.material.delete()

    def test_remover_usuario_preserva_nome_do_responsavel(self):
        mov = self.movimentar('ENTRADA', 1, registrado_por_nome='Administrador')
        self.admin.delete()
        mov.refresh_from_db()
        self.assertIsNone(mov.registrado_por)
        self.assertEqual(mov.registrado_por_nome, 'Administrador')


class MovimentacaoViewTests(EstoqueTestCase):
    def setUp(self):
        super().setUp()
        self.material = criar_material(quantidade_inicial=10)
        self.entrar(self.admin)
        self.url = reverse('cadastrar_movimentacao_estoque')

    def test_entrada_registrada_com_responsavel_e_auditoria(self):
        r = self.client.post(self.url, {
            'material': self.material.pk, 'tipo': 'ENTRADA', 'quantidade': 5, 'origem': 'COMPRA',
        }, follow=True)
        self.assertRedirects(r, reverse('movimentacoes_estoque'))
        self.assertContains(r, 'Movimentação registrada')
        mov = MovimentacaoEstoque.objects.get()
        self.assertEqual(mov.registrado_por, self.admin)
        self.assertEqual(mov.registrado_por_nome, 'Administrador')
        self.assertEqual(self.material.calcular_saldo(), 15)
        evento = EventoAuditoria.objects.get(entidade='MOVIMENTACAO_ESTOQUE')
        self.assertEqual(evento.acao, 'MOVIMENTACAO')
        self.assertEqual(evento.id_registro, mov.pk)

    def test_saida_registrada(self):
        self.client.post(self.url, {
            'material': self.material.pk, 'tipo': 'SAIDA', 'quantidade': 4,
            'justificativa': 'Mutirão', 'origem': 'COMPRA',
        })
        mov = MovimentacaoEstoque.objects.get()
        self.assertEqual(mov.origem, '')
        self.assertEqual(self.material.calcular_saldo(), 6)

    def test_saldo_insuficiente_mostra_erro_e_nao_grava(self):
        r = self.client.post(self.url, {
            'material': self.material.pk, 'tipo': 'SAIDA', 'quantidade': 11, 'justificativa': 'x',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'saldo insuficiente')
        self.assertEqual(MovimentacaoEstoque.objects.count(), 0)
        self.assertEqual(EventoAuditoria.objects.filter(entidade='MOVIMENTACAO_ESTOQUE').count(), 0)

    def test_saida_sem_justificativa(self):
        r = self.client.post(self.url, {
            'material': self.material.pk, 'tipo': 'SAIDA', 'quantidade': 1,
        })
        self.assertContains(r, 'justificativa')
        self.assertEqual(MovimentacaoEstoque.objects.count(), 0)

    def test_entrada_sem_origem(self):
        r = self.client.post(self.url, {
            'material': self.material.pk, 'tipo': 'ENTRADA', 'quantidade': 1,
        })
        self.assertContains(r, 'origem da entrada')
        self.assertEqual(MovimentacaoEstoque.objects.count(), 0)

    def test_origem_doacao_nao_e_aceita_no_formulario(self):
        r = self.client.post(self.url, {
            'material': self.material.pk, 'tipo': 'ENTRADA', 'quantidade': 1, 'origem': 'DOACAO',
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(MovimentacaoEstoque.objects.count(), 0)

    def test_material_obrigatorio(self):
        r = self.client.post(self.url, {'tipo': 'ENTRADA', 'quantidade': 1, 'origem': 'COMPRA'})
        self.assertContains(r, 'Selecione um item do catálogo')


class DoacaoTests(EstoqueTestCase):
    def setUp(self):
        super().setUp()
        self.material = criar_material(quantidade_inicial=0)
        self.entrar(self.admin)

    def test_doacao_gera_entrada_e_auditoria(self):
        response = self.client.get(reverse('doacoes_estoque'))
        self.assertRedirects(response, reverse('doacoes'), fetch_redirect_response=False)
        response = self.client.get(reverse('cadastrar_doacao_estoque'))
        self.assertRedirects(response, reverse('cadastro_doacao'), fetch_redirect_response=False)

    def test_lista_materiais_mostra_origem_derivada_da_doacao(self):
        doador = Doador.objects.create(
            tipo=Doador.PESSOA_FISICA,
            nome='Maria',
            cadastrado_por=self.admin,
            cadastrado_por_nome='Administrador',
        )
        doacao = Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=doador,
            status=Doacao.CONFIRMADA,
            registrado_por=self.admin,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        item = ItemDoacaoMaterial.objects.create(
            doacao=doacao,
            material=self.material,
            nome=self.material.nome,
            categoria=self.material.categoria,
            quantidade=2,
            unidade=self.material.get_unidade_display(),
            condicao=ItemDoacaoMaterial.CONDICAO_NOVO,
        )
        MovimentacaoEstoque.objects.create(
            material=self.material,
            tipo='ENTRADA',
            quantidade=2,
            origem='DOACAO',
            doacao=doacao,
            item_doacao=item,
            registrado_por=self.admin,
            registrado_por_nome='Administrador',
        )

        resposta = self.client.get(reverse('materiais'))

        self.assertContains(resposta, 'Donativo (Maria)')

    def test_gravacao_direta_nao_substitui_fluxo_de_confirmacao(self):
        doador = Doador.objects.create(
            tipo=Doador.PESSOA_FISICA,
            nome='Maria',
            cadastrado_por=self.admin,
            cadastrado_por_nome='Administrador',
        )
        doacao = Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=doador,
            status=Doacao.CONFIRMADA,
            registrado_por=self.admin,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        ItemDoacaoMaterial.objects.create(
            doacao=doacao,
            nome='Luvas',
            categoria='EPI',
            quantidade=7,
            unidade='caixas',
            condicao=ItemDoacaoMaterial.CONDICAO_NOVO,
        )

        self.assertEqual(self.material.calcular_saldo(), 0)
        self.assertEqual(MovimentacaoEstoque.objects.count(), 0)
        self.assertContains(self.client.get(reverse('doacoes')), 'Maria')


class ConsultaTests(EstoqueTestCase):
    def setUp(self):
        super().setUp()
        self.tinta = criar_material(nome='Tinta', codigo='T1', categoria='Pintura', estoque_minimo=20)
        self.luva = criar_material(nome='Luva', codigo='L1', categoria='EPI', estoque_minimo=1)
        self.entrar(self.coordenador)

    def test_lista_todos_com_saldo(self):
        r = self.client.get(reverse('materiais'))
        self.assertContains(r, 'Tinta')
        self.assertContains(r, 'Luva')

    def test_busca_por_nome_e_codigo(self):
        self.assertNotContains(self.client.get(reverse('materiais'), {'busca': 'tinta'}), 'Luva')
        self.assertNotContains(self.client.get(reverse('materiais'), {'busca': 'L1'}), 'Tinta')

    def test_filtro_por_categoria(self):
        r = self.client.get(reverse('materiais'), {'categoria': 'epi'})
        self.assertContains(r, 'Luva')
        self.assertNotContains(r, '<strong>Tinta</strong>')

    def test_filtro_estoque_baixo(self):
        r = self.client.get(reverse('materiais'), {'situacao': 'BAIXO'})
        self.assertContains(r, '<strong>Tinta</strong>')
        self.assertNotContains(r, '<strong>Luva</strong>')
        self.assertEqual(r.context['total_baixo_estoque'], 1)

    def test_total_doado_no_periodo(self):
        doador = Doador.objects.create(
            tipo=Doador.PESSOA_FISICA,
            nome='Maria',
            cadastrado_por=self.admin,
            cadastrado_por_nome='Administrador',
        )
        doacao = Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=doador,
            status=Doacao.CONFIRMADA,
            registrado_por=self.admin,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        ItemDoacaoMaterial.objects.create(
            doacao=doacao,
            nome='Tinta',
            categoria='Pintura',
            quantidade=4,
            unidade='litros',
            condicao=ItemDoacaoMaterial.CONDICAO_NOVO,
        )
        r = self.client.get(reverse('materiais'))
        self.assertEqual(r.context['doado_total'], 4)
        r = self.client.get(reverse('materiais'), {'data_inicio': '2000-01-01', 'data_fim': '2000-12-31'})
        self.assertEqual(r.context['doado_total'], 0)

    def test_consulta_sem_n_mais_um(self):
        for i in range(5):
            criar_material(nome=f'Item {i}', codigo=f'I{i}')
        with self.assertNumQueries(8):
            self.client.get(reverse('materiais'))

    def test_relatorio_por_origem(self):
        material_doado = criar_material(nome='Doado', codigo='D1', quantidade_inicial=3)
        doador = Doador.objects.create(
            tipo=Doador.PESSOA_FISICA,
            nome='Maria',
            cadastrado_por=self.admin,
            cadastrado_por_nome='Administrador',
        )
        doacao = Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=doador,
            status=Doacao.CONFIRMADA,
            registrado_por=self.admin,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        ItemDoacaoMaterial.objects.create(
            doacao=doacao,
            material=material_doado,
            nome='Doado',
            categoria='Pintura',
            quantidade=3,
            unidade='unidades',
            condicao=ItemDoacaoMaterial.CONDICAO_NOVO,
        )
        MovimentacaoEstoque.objects.create(
            material=material_doado,
            tipo='ENTRADA',
            quantidade=3,
            origem='DOACAO',
            doacao=doacao,
            item_doacao=ItemDoacaoMaterial.objects.get(material=material_doado),
            registrado_por=self.admin,
            registrado_por_nome='Administrador',
        )
        r = self.client.get(reverse('relatorio_estoque'))
        self.assertEqual(r.context['total_donativos'], 1)
        self.assertEqual(r.context['quantidade_donativos'], 3)
        self.assertEqual(r.context['total_comprados'], 2)
        self.assertEqual(r.context['total_materiais'], 3)
        self.assertEqual(r.context['quantidade_total'], 23)


class HistoricoTests(EstoqueTestCase):
    def setUp(self):
        super().setUp()
        self.material = criar_material(nome='Tinta', codigo='T1', quantidade_inicial=100)
        self.outro = criar_material(nome='Luva', codigo='L1', quantidade_inicial=100)
        for i in range(12):
            MovimentacaoEstoque.objects.create(
                material=self.material, tipo='ENTRADA', quantidade=1, origem='COMPRA',
                registrado_por=self.admin, registrado_por_nome='Administrador',
            )
        MovimentacaoEstoque.objects.create(
            material=self.outro, tipo='SAIDA', quantidade=1, justificativa='=cmd()',
            registrado_por_nome='Administrador',
        )
        self.entrar(self.admin)

    def test_paginacao_de_dez_itens(self):
        r = self.client.get(reverse('movimentacoes_estoque'))
        self.assertEqual(len(r.context['page_obj']), 13)
        self.assertEqual(r.context['page_obj'].paginator.per_page, 20)
        self.assertEqual(r.context['page_obj'].paginator.num_pages, 1)

    def test_resumo_mostra_contagem_de_movimentacoes_filtradas(self):
        r = self.client.get(reverse('movimentacoes_estoque'), {'tipo': 'ENTRADA'})
        self.assertEqual(r.context['total_movimentacoes'], 12)
        self.assertEqual(r.context['total_entradas'], 12)
        self.assertEqual(r.context['total_saidas'], 0)

    def test_paginacao_preserva_filtros(self):
        for i in range(9):
            MovimentacaoEstoque.objects.create(
                material=self.material, tipo='ENTRADA', quantidade=1, origem='COMPRA',
                registrado_por=self.admin, registrado_por_nome='Administrador',
            )
        r = self.client.get(reverse('movimentacoes_estoque'), {'busca': 'Tinta'})
        self.assertContains(r, 'busca=Tinta&amp;page=2')

    def test_filtros(self):
        r = self.client.get(reverse('movimentacoes_estoque'), {'tipo': 'SAIDA'})
        self.assertEqual(r.context['page_obj'].paginator.count, 1)
        r = self.client.get(reverse('movimentacoes_estoque'), {'busca': 'L1'})
        self.assertEqual(r.context['page_obj'].paginator.count, 1)
        r = self.client.get(reverse('movimentacoes_estoque'), {'data_inicio': '2999-01-01'})
        self.assertEqual(r.context['page_obj'].paginator.count, 0)

    def test_filtro_de_data_invalido_e_ignorado(self):
        r = self.client.get(reverse('movimentacoes_estoque'), {'data_inicio': 'abc', 'tipo': 'xx'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['page_obj'].paginator.count, 13)

    def test_exportacao_csv(self):
        r = self.client.get(reverse('exportar_movimentacoes_estoque'), {'tipo': 'SAIDA'})
        self.assertEqual(r['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment', r['Content-Disposition'])
        linhas = list(csv.reader(io.StringIO(r.content.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(linhas[0][:3], ['Data/hora', 'Tipo', 'Material'])
        self.assertEqual(len(linhas), 2)
        self.assertEqual(linhas[1][1], 'Saída')

    def test_exportacao_neutraliza_formulas(self):
        r = self.client.get(reverse('exportar_movimentacoes_estoque'), {'tipo': 'SAIDA'})
        linhas = list(csv.reader(io.StringIO(r.content.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(linhas[1][7], "'=cmd()")


class AuditoriaEventosTests(EstoqueTestCase):
    def test_cadastro_registra_evento_com_rotulo(self):
        self.entrar(self.admin)
        self.client.post(reverse('cadastrar_material'), dados_material())
        evento = EventoAuditoria.objects.get(entidade='MATERIAL', acao='CRIACAO')
        self.assertEqual(evento.get_entidade_display(), 'Material')
        self.assertEqual(EventoAuditoria(entidade='MOVIMENTACAO_ESTOQUE').get_entidade_display(), 'Movimentação de estoque')
        self.assertEqual(EventoAuditoria(entidade='DOACAO').get_entidade_display(), 'Doação')


class CoordenadorInicialTests(TestCase):
    def test_login_do_coordenador_inicial_leva_ao_home(self):
        r = self.client.post(reverse('login'), {'email': 'coordenador@gmail.com', 'senha': 'coordenador'})
        self.assertRedirects(r, reverse('home'))
        self.assertEqual(self.client.session['usuario_tipo'], 'COORDENADOR')
        self.assertEqual(self.client.get(reverse('materiais')).status_code, 403)

    def test_raiz_redireciona_para_estoque(self):
        self.assertRedirects(self.client.get('/'), reverse('materiais'), fetch_redirect_response=False)


class FiltroOrigemELiveTests(EstoqueTestCase):
    def setUp(self):
        super().setUp()
        self.entrar(self.admin)
        self.doado = criar_material(nome='Doado', codigo='D1')
        doador = Doador.objects.create(
            tipo=Doador.PESSOA_FISICA,
            nome='Ana',
            cadastrado_por=self.admin,
            cadastrado_por_nome='Administrador',
        )
        doacao = Doacao.objects.create(
            tipo=Doacao.MATERIAL,
            doador=doador,
            status=Doacao.CONFIRMADA,
            registrado_por=self.admin,
            registrado_por_nome='Administrador',
            registrado_por_tipo='ADMIN',
        )
        item = ItemDoacaoMaterial.objects.create(
            doacao=doacao,
            material=self.doado,
            nome='Doado',
            categoria='Pintura',
            quantidade=1,
            unidade='unidades',
            condicao=ItemDoacaoMaterial.CONDICAO_NOVO,
        )
        MovimentacaoEstoque.objects.create(
            material=self.doado,
            tipo='ENTRADA',
            quantidade=1,
            origem='DOACAO',
            doacao=doacao,
            item_doacao=item,
            registrado_por=self.admin,
            registrado_por_nome='Administrador',
        )
        self.comprado = criar_material(nome='Comprado', codigo='C1')
        MovimentacaoEstoque.objects.create(
            material=self.comprado, tipo='ENTRADA', quantidade=1, origem='COMPRA')
        MovimentacaoEstoque.objects.create(
            material=self.comprado, tipo='ENTRADA', quantidade=1, origem='AJUSTE')

    def test_consulta_filtra_por_origem(self):
        r = self.client.get(reverse('materiais'), {'origem': 'DONATIVO'})
        self.assertEqual([m.nome for m in r.context['materiais']], ['Doado'])
        r = self.client.get(reverse('materiais'), {'origem': 'COMPRADO'})
        self.assertEqual([m.nome for m in r.context['materiais']], ['Comprado'])

    def test_historico_filtra_por_origem(self):
        r = self.client.get(reverse('movimentacoes_estoque'), {'origem': 'AJUSTE'})
        self.assertEqual([m.origem for m in r.context['page_obj']], ['AJUSTE'])
        self.assertEqual(r.context['filtros']['origem'], 'AJUSTE')

    def test_historico_ignora_origem_invalida(self):
        r = self.client.get(reverse('movimentacoes_estoque'), {'origem': 'XYZ'})
        self.assertEqual(len(r.context['page_obj']), 2)
        self.assertEqual(r.context['filtros']['origem'], '')

    def test_exportacao_respeita_origem(self):
        r = self.client.get(reverse('exportar_movimentacoes_estoque'), {'origem': 'COMPRA'})
        linhas = list(csv.reader(io.StringIO(r.content.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(len(linhas), 2)
        self.assertEqual(linhas[1][8], 'Compra')

    def test_paginas_expoem_regioes_para_atualizacao_em_tempo_real(self):
        for nome, regioes in [
            ('materiais', ['metricas', 'acoes', 'resultado']),
            ('movimentacoes_estoque', ['exportar', 'acoes', 'resultado']),
        ]:
            html = self.client.get(reverse(nome)).content.decode()
            self.assertIn('data-filtro-vivo', html)
            for regiao in regioes:
                self.assertIn(f'data-live="{regiao}"', html)

    def test_cadastro_de_material_exibe_confirmacao(self):
        r = self.client.post(reverse('cadastrar_material'), dados_material(), follow=True)
        self.assertContains(r, 'Material cadastrado com sucesso.')
        self.assertContains(r, 'data-toast')

    def test_material_e_movimentacao_exibem_links_de_navegacao_relacionada(self):
        materiais = self.client.get(reverse('materiais'))
        self.assertContains(
            materiais,
            f'href="{reverse("movimentacoes_estoque")}?busca=C1"',
            html=False,
        )
        historico = self.client.get(reverse('movimentacoes_estoque'))
        self.assertContains(
            historico,
            f'href="{reverse("materiais")}?busca=C1"',
            html=False,
        )

    def test_menu_lateral_destaca_movimentacoes_sem_destacar_estoque(self):
        for url in (
            reverse('movimentacoes_estoque'),
            reverse('cadastrar_movimentacao_estoque'),
        ):
            resposta = self.client.get(url)
            self.assertEqual(resposta.status_code, 200)
            self.assertContains(
                resposta,
                '<a href="/estoque/movimentacoes/" class="sidebar-link active">Controle de Movimentações</a>',
                html=True,
            )
            self.assertContains(
                resposta,
                '<a href="/estoque/" class="sidebar-link ">Controle de Estoque</a>',
                html=True,
            )


class CriteriosAceiteTests(EstoqueTestCase):
    def test_visitante_e_redirecionado_ao_login_com_aviso_de_acesso_restrito(self):
        r = self.client.get(reverse('materiais'), follow=True)
        self.assertRedirects(r, reverse('login'))
        self.assertContains(r, 'Acesso restrito')

    def test_visitante_no_historico_ve_aviso_de_restricao_a_administradores(self):
        r = self.client.get(reverse('movimentacoes_estoque'), follow=True)
        self.assertRedirects(r, reverse('login'))
        self.assertContains(r, 'restrita a administradores')

    def test_campos_obrigatorios_em_portugues_e_destacados(self):
        self.entrar(self.admin)
        r = self.client.post(reverse('cadastrar_material'), {})
        self.assertContains(r, 'Este campo é obrigatório.')
        self.assertContains(r, 'campo-invalido')
        self.assertContains(r, 'destacados em vermelho')
        self.assertEqual(Material.objects.count(), 0)

    def test_material_duplicado_destaca_o_campo_nome(self):
        self.entrar(self.admin)
        criar_material(nome='Luva de Proteção M', codigo='L1')
        r = self.client.post(reverse('cadastrar_material'), dados_material(nome='luva de proteção m', codigo='L2'))
        self.assertContains(r, 'Este material já existe no estoque.')
        self.assertContains(r, 'campo-invalido')

    def test_codigo_duplicado_em_portugues(self):
        self.entrar(self.admin)
        criar_material(nome='Outro', codigo='L1')
        r = self.client.post(reverse('cadastrar_material'), dados_material(codigo='L1'))
        self.assertContains(r, 'Já existe um material com este código.')
