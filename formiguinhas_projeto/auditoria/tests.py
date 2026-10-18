from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from acao.models import Acao, AcaoParticipante
from equipe.models import Equipe, EquipeMembro
from praia.models import Praia
from usuario.models import Usuario, Voluntario

from .context_processors import notificacoes_auditoria
from .models import EstadoLeituraAuditoria, EventoAuditoria


class AuditoriaUsuariosTests(TestCase):
    def setUp(self):
        self.admin_voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1985, 1, 1),
            endereco='Rua Admin, 1',
            telefone='11999990000',
            email='admin@teste.org',
        )
        self.admin = Usuario.objects.create(
            id_voluntario=self.admin_voluntario,
            tipo='ADMIN',
        )
        self.admin.set_password('senha')
        self.admin.save()
        session = self.client.session
        session['usuario_id'] = self.admin.pk
        session['usuario_tipo'] = self.admin.tipo
        session.save()

    def test_notificacao_mostra_novos_eventos_e_limpa_ao_abrir_auditoria(self):
        request = type('Request', (), {'session': self.client.session})()
        self.assertEqual(notificacoes_auditoria(request)['auditoria_nao_lida_count'], 0)
        estado = EstadoLeituraAuditoria.objects.get(usuario=self.admin)

        evento = EventoAuditoria.objects.create(
            entidade='MATERIAL',
            id_registro=1,
            acao='CRIACAO',
            usuario=self.admin,
            resumo='Material cadastrado.',
        )
        self.assertEqual(notificacoes_auditoria(request)['auditoria_nao_lida_count'], 1)
        resposta_home = self.client.get(reverse('home'))
        self.assertContains(
            resposta_home,
            '<span class="notification-badge" aria-hidden="true">!</span>',
            html=True,
        )

        resposta = self.client.get(reverse('auditoria_global'))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(
            resposta,
            '<span class="notification-badge" aria-hidden="true">!</span>',
            html=True,
        )
        estado.refresh_from_db()
        self.assertEqual(estado.ultimo_evento_id, evento.pk)
        self.assertEqual(
            resposta.context['auditoria_nao_lida_count'],
            0,
        )

        novo_evento = EventoAuditoria.objects.create(
            entidade='MATERIAL',
            id_registro=2,
            acao='CRIACAO',
            usuario=self.admin,
            resumo='Outro material cadastrado.',
        )
        self.assertEqual(notificacoes_auditoria(request)['auditoria_nao_lida_count'], 1)
        self.assertGreater(novo_evento.pk, evento.pk)

    def test_cadastros_de_voluntario_e_usuario_sao_auditados(self):
        self.client.post(reverse('cadastro_voluntario'), {
            'nome': 'Novo voluntário',
            'dt_nascimento': '01/01/1990',
            'endereco': 'Rua Nova, 2',
            'telefone': '11999990001',
            'email': 'novo@teste.org',
        })
        voluntario = Voluntario.objects.get(email='novo@teste.org')
        evento_voluntario = EventoAuditoria.objects.get(
            entidade='VOLUNTARIO',
            id_registro=voluntario.pk,
            acao='CRIACAO',
        )
        self.assertEqual(evento_voluntario.usuario, self.admin)

        self.client.post(reverse('cadastro_usuario'), {
            'voluntario': voluntario.pk,
            'tipo': 'COORDENADOR',
            'senha': 'senha-segura',
            'confirmar_senha': 'senha-segura',
        })
        usuario = Usuario.objects.get(id_voluntario=voluntario)
        evento_usuario = EventoAuditoria.objects.get(
            entidade='USUARIO',
            id_registro=usuario.pk,
            acao='CRIACAO',
        )
        self.assertEqual(evento_usuario.usuario, self.admin)
        self.assertNotIn('senha', evento_usuario.valores_novos)

        resposta = self.client.get(reverse('auditoria_global'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Novo voluntário')

    def test_edicao_de_tipo_e_exclusao_de_usuario_sao_auditadas(self):
        voluntario = Voluntario.objects.create(
            nome='Usuário alvo',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua Alvo, 3',
            telefone='11999990002',
            email='alvo@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )

        self.client.post(
            reverse('atualizar_tipo_usuario', args=[usuario.pk]),
            {'tipo': 'ADMIN'},
        )
        usuario.refresh_from_db()
        self.assertEqual(usuario.tipo, 'ADMIN')
        evento_edicao = EventoAuditoria.objects.get(
            entidade='USUARIO',
            id_registro=usuario.pk,
            acao='EDICAO',
        )
        self.assertEqual(evento_edicao.valores_anteriores['tipo'], 'Coordenador')
        self.assertEqual(evento_edicao.valores_novos['tipo'], 'Administrador')

        self.client.post(reverse('excluir_usuario', args=[usuario.pk]))
        self.assertTrue(EventoAuditoria.objects.filter(
            entidade='USUARIO',
            id_registro=usuario.pk,
            acao='EXCLUSAO',
        ).exists())
        self.assertTrue(EventoAuditoria.objects.filter(
            entidade='VOLUNTARIO',
            id_registro=voluntario.pk,
            acao='EXCLUSAO',
        ).exists())

    def test_exclusao_de_voluntario_audita_tambem_usuario_em_cascata(self):
        voluntario = Voluntario.objects.create(
            nome='Voluntário removido',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua Removida, 5',
            telefone='11999990004',
            email='removido@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )

        self.client.post(
            reverse('excluir_voluntario', args=[voluntario.pk]),
        )

        self.assertFalse(Voluntario.objects.filter(pk=voluntario.pk).exists())
        self.assertTrue(EventoAuditoria.objects.filter(
            entidade='USUARIO',
            id_registro=usuario.pk,
            acao='EXCLUSAO',
        ).exists())

    def test_edicao_de_usuario_e_troca_de_senha_sao_auditadas_sem_credenciais(self):
        voluntario = Voluntario.objects.create(
            nome='Usuário editado',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua Original, 4',
            telefone='11999990003',
            email='editado@teste.org',
        )
        usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )
        self.client.post(reverse('editar_usuario', args=[usuario.pk]), {
            'tipo': 'ADMIN',
            'nome': 'Usuário editado',
            'dt_nascimento': '01/01/1990',
            'endereco': 'Rua Atualizada, 4',
            'telefone': '11999990003',
            'email': 'editado@teste.org',
            'status': 'ATIVO',
        })
        voluntario.refresh_from_db()
        usuario.refresh_from_db()
        self.assertEqual(voluntario.endereco, 'Rua Atualizada, 4')
        self.assertEqual(usuario.tipo, 'ADMIN')
        self.assertTrue(EventoAuditoria.objects.filter(
            entidade='VOLUNTARIO',
            id_registro=voluntario.pk,
            acao='EDICAO',
        ).exists())
        self.assertTrue(EventoAuditoria.objects.filter(
            entidade='USUARIO',
            id_registro=usuario.pk,
            acao='EDICAO',
        ).exists())

        self.client.post(reverse('alterar_senha'), {
            'senha_atual': 'senha',
            'nova_senha': 'nova-senha-secreta',
            'confirmar_nova_senha': 'nova-senha-secreta',
        })
        evento_senha = EventoAuditoria.objects.filter(
            entidade='USUARIO',
            id_registro=self.admin.pk,
            resumo__icontains='Senha',
        ).latest('id')
        self.assertEqual(evento_senha.valores_novos, {'senha_alterada': True})
        self.assertNotIn('senha', evento_senha.valores_anteriores)


class AuditoriaControlesTests(TestCase):
    def setUp(self):
        self.admin_voluntario = Voluntario.objects.create(
            nome='Administradora',
            dt_nascimento=date(1985, 1, 1),
            endereco='Rua Admin, 1',
            telefone='11999990000',
            email='admin@teste.org',
        )
        self.admin = Usuario.objects.create(
            id_voluntario=self.admin_voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        session = self.client.session
        session['usuario_id'] = self.admin.pk
        session.save()
        self.voluntario = Voluntario.objects.create(
            nome='Voluntário',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua Voluntário, 2',
            telefone='11999990001',
            email='voluntario@teste.org',
        )
        self.praia = Praia.objects.create(
            nome='Praia Teste',
            cidade='Santos',
            latitude=-23.9,
            longitude=-46.3,
        )

    def test_alteracoes_de_equipe_sao_auditadas(self):
        equipe = Equipe.objects.create(nome='Equipe Teste')
        membro = EquipeMembro.objects.create(
            equipe=equipe,
            voluntario=self.voluntario,
            papel=EquipeMembro.PAPEL_VOLUNTARIO,
        )

        self.client.post(
            reverse('atualizar_funcao_membro', args=[equipe.pk, membro.pk]),
            {'papel': EquipeMembro.PAPEL_COORDENADOR},
        )
        evento_funcao = EventoAuditoria.objects.get(
            entidade='EQUIPE_MEMBRO',
            id_registro=membro.pk,
            acao='EDICAO',
        )
        self.assertEqual(evento_funcao.valores_anteriores['papel'], 'Voluntário')
        self.assertEqual(evento_funcao.valores_novos['papel'], 'Coordenador')

        self.client.post(
            reverse('remover_membro_equipe', args=[equipe.pk, membro.pk]),
        )
        evento_remocao = EventoAuditoria.objects.get(
            entidade='EQUIPE_MEMBRO',
            id_registro=membro.pk,
            acao='MUDANCA_STATUS',
        )
        self.assertEqual(evento_remocao.valores_anteriores['status'], 'Ativo')
        self.assertEqual(evento_remocao.valores_novos['status'], 'Inativo')

        self.client.post(
            reverse('atualizar_status_equipe', args=[equipe.pk]),
            {'status': 'INATIVA'},
        )
        self.assertTrue(EventoAuditoria.objects.filter(
            entidade='EQUIPE',
            id_registro=equipe.pk,
            acao='MUDANCA_STATUS',
        ).exists())

    def test_vinculo_de_participante_e_alteracao_de_status_sao_auditados(self):
        acao = Acao.objects.create(
            tipo=Acao.TIPO_COLETA_VOLUNTARIA,
            data=date(2030, 1, 1),
            praia=self.praia,
        )
        self.client.post(
            reverse('adicionar_participante_acao', args=[acao.pk]),
            {'voluntario': self.voluntario.pk, 'observacao': 'Presença confirmada'},
        )
        participante = AcaoParticipante.objects.get(acao=acao, voluntario=self.voluntario)
        self.assertTrue(EventoAuditoria.objects.filter(
            entidade='ACAO_PARTICIPANTE',
            id_registro=participante.pk,
            acao='VINCULO',
        ).exists())

        self.client.post(
            reverse('confirmar_participacao_acao', args=[acao.pk, participante.pk]),
            {'status': AcaoParticipante.STATUS_CONFIRMADO},
        )
        evento_status = EventoAuditoria.objects.filter(
            entidade='ACAO_PARTICIPANTE',
            id_registro=participante.pk,
            acao='EDICAO',
        ).latest('id')
        self.assertEqual(evento_status.valores_anteriores['status'], 'Pendente')
        self.assertEqual(evento_status.valores_novos['status'], 'Confirmado')


class AuditoriaDjangoAdminTests(TestCase):
    def setUp(self):
        voluntario = Voluntario.objects.create(
            nome='Administração do sistema',
            dt_nascimento=date(1985, 1, 1),
            endereco='Rua Admin, 1',
            telefone='11999990000',
            email='admin-sistema@teste.org',
        )
        self.usuario_aplicacao = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='ADMIN',
            senha='senha',
        )
        self.usuario_django = get_user_model().objects.create_superuser(
            username='admin-sistema',
            email=voluntario.email,
            password='senha',
        )
        self.client.force_login(self.usuario_django)

    def test_criacao_por_django_admin_fica_na_auditoria_global(self):
        resposta = self.client.post(reverse('admin:estoque_material_add'), {
            'nome': 'Material pelo admin',
            'codigo': 'ADM-001',
            'categoria': 'Limpeza',
            'descricao': '',
            'quantidade_inicial': '0',
            'estoque_minimo': '0',
            'unidade': 'UNIDADE',
        })

        self.assertEqual(resposta.status_code, 302)
        evento = EventoAuditoria.objects.get(
            entidade='MATERIAL',
            acao='CRIACAO',
            valores_novos__nome='Material pelo admin',
        )
        self.assertEqual(evento.usuario, self.usuario_aplicacao)
        self.assertEqual(evento.usuario_nome, 'Administração do sistema')

        from estoque.models import Material

        material = Material.objects.get(codigo='ADM-001')
        resposta_edicao = self.client.post(
            reverse('admin:estoque_material_change', args=[material.pk]),
            {
                'nome': material.nome,
                'codigo': material.codigo,
                'categoria': 'Higiene',
                'descricao': material.descricao,
                'quantidade_inicial': material.quantidade_inicial,
                'estoque_minimo': material.estoque_minimo,
                'unidade': material.unidade,
                '_save': 'Salvar',
            },
        )
        self.assertEqual(resposta_edicao.status_code, 302)
        evento_edicao = EventoAuditoria.objects.get(
            entidade='MATERIAL',
            id_registro=material.pk,
            acao='EDICAO',
        )
        self.assertEqual(evento_edicao.valores_anteriores['categoria'], 'Limpeza')
        self.assertEqual(evento_edicao.valores_novos['categoria'], 'Higiene')

        resposta_exclusao = self.client.post(
            reverse('admin:estoque_material_delete', args=[material.pk]),
            {'post': 'yes'},
        )
        self.assertEqual(resposta_exclusao.status_code, 302)
        self.assertTrue(EventoAuditoria.objects.filter(
            entidade='MATERIAL',
            id_registro=material.pk,
            acao='EXCLUSAO',
        ).exists())
