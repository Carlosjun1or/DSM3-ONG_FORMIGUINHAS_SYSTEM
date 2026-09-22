from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from acao.models import Acao
from auditoria.models import EventoAuditoria
from auditoria.services import registrar_evento, snapshot
from condominio.models import Bag, Condominio, MovimentacaoBag
from equipe.models import Equipe, EquipeMembro
from praia.models import Praia
from usuario.models import Usuario, Voluntario


MARCADOR = 'SIM-AUDITORIA-GLOBAL'


class Command(BaseCommand):
    help = 'Cria dados demonstrativos e eventos para testar a auditoria global.'

    @transaction.atomic
    def handle(self, *args, **options):
        usuario = Usuario.objects.filter(tipo='ADMIN').select_related('id_voluntario').first()
        if not usuario:
            self.stderr.write(self.style.ERROR('É necessário ter um usuário ADMIN cadastrado.'))
            return

        if EventoAuditoria.objects.filter(resumo__startswith=MARCADOR).exists():
            self.stdout.write(self.style.WARNING(
                'Os dados demonstrativos da auditoria já foram criados. Nenhuma duplicação foi feita.'
            ))
            return

        voluntario = Voluntario.objects.create(
            nome='Voluntário Demonstração - Auditoria',
            dt_nascimento=date(1990, 5, 20),
            endereco='Rua da Demonstração, 100',
            telefone='(13) 99999-0000',
            email='sim-auditoria-voluntario@example.com',
            cadastrado_por=usuario,
            cadastrado_por_nome=usuario.id_voluntario.nome,
            cadastrado_por_tipo=usuario.tipo,
        )
        registrar_evento(
            entidade='VOLUNTARIO',
            instancia=voluntario,
            acao='CRIACAO',
            usuario=usuario,
            resumo=f'{MARCADOR}: voluntário criado.',
        )

        voluntario_anterior = snapshot(voluntario)
        voluntario.status = 'PAUSADO'
        voluntario.ultimo_editado_por = usuario
        voluntario.ultimo_editado_por_nome = usuario.id_voluntario.nome
        voluntario.ultimo_editado_por_tipo = usuario.tipo
        voluntario.dt_ultima_edicao = timezone.now()
        voluntario.save()
        registrar_evento(
            entidade='VOLUNTARIO',
            instancia=voluntario,
            acao='MUDANCA_STATUS',
            usuario=usuario,
            resumo=f'{MARCADOR}: status do voluntário alterado.',
            valores_anteriores=voluntario_anterior,
        )

        usuario_demo = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            cadastrado_por=usuario,
            cadastrado_por_nome=usuario.id_voluntario.nome,
            cadastrado_por_tipo=usuario.tipo,
        )
        usuario_demo.set_password('Auditoria@123')
        usuario_demo.save(update_fields=['senha'])
        registrar_evento(
            entidade='USUARIO',
            instancia=usuario_demo,
            acao='CRIACAO',
            usuario=usuario,
            resumo=f'{MARCADOR}: usuário criado.',
        )

        praia = Praia.objects.create(
            nome='Praia Demonstração da Auditoria',
            cidade='Santos',
            latitude=Decimal('-23.967000'),
            longitude=Decimal('-46.328000'),
            descricao='Registro criado para testar a auditoria global.',
            cadastrado_por=usuario,
            cadastrado_por_nome=usuario.id_voluntario.nome,
            cadastrado_por_tipo=usuario.tipo,
        )
        registrar_evento(
            entidade='PRAIA',
            instancia=praia,
            acao='CRIACAO',
            usuario=usuario,
            resumo=f'{MARCADOR}: praia criada.',
        )

        praia_anterior = snapshot(praia)
        praia.praia_ativa = 'INATIVA'
        praia.ultimo_editado_por = usuario
        praia.ultimo_editado_por_nome = usuario.id_voluntario.nome
        praia.ultimo_editado_por_tipo = usuario.tipo
        praia.dt_ultima_edicao = timezone.now()
        praia.save()
        registrar_evento(
            entidade='PRAIA',
            instancia=praia,
            acao='MUDANCA_STATUS',
            usuario=usuario,
            resumo=f'{MARCADOR}: status da praia alterado.',
            valores_anteriores=praia_anterior,
        )

        equipe = Equipe.objects.create(
            nome='Equipe Demonstração da Auditoria',
            praia=praia,
            descricao='Equipe criada para testar vínculos na auditoria global.',
            cadastrado_por=usuario,
            cadastrado_por_nome=usuario.id_voluntario.nome,
            cadastrado_por_tipo=usuario.tipo,
        )
        registrar_evento(
            entidade='EQUIPE',
            instancia=equipe,
            acao='CRIACAO',
            usuario=usuario,
            resumo=f'{MARCADOR}: equipe criada.',
        )

        membro = EquipeMembro.objects.create(
            equipe=equipe,
            voluntario=voluntario,
            cadastrado_por=usuario,
            cadastrado_por_nome=usuario.id_voluntario.nome,
            cadastrado_por_tipo=usuario.tipo,
        )
        registrar_evento(
            entidade='EQUIPE_MEMBRO',
            instancia=membro,
            acao='VINCULO',
            usuario=usuario,
            resumo=f'{MARCADOR}: voluntário vinculado à equipe.',
        )

        acao = Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=date.today(),
            horario=timezone.localtime().time().replace(second=0, microsecond=0),
            local='Orla da praia de demonstração',
            descricao='Ação criada para testar a auditoria global.',
            praia=praia,
            cadastrado_por=usuario,
            cadastrado_por_nome=usuario.id_voluntario.nome,
            cadastrado_por_tipo=usuario.tipo,
        )
        registrar_evento(
            entidade='ACAO',
            instancia=acao,
            acao='CRIACAO',
            usuario=usuario,
            resumo=f'{MARCADOR}: ação criada.',
        )

        acao_anterior = snapshot(acao)
        acao.status = Acao.STATUS_EM_ANDAMENTO
        acao.ultimo_editado_por = usuario
        acao.ultimo_editado_por_nome = usuario.id_voluntario.nome
        acao.ultimo_editado_por_tipo = usuario.tipo
        acao.dt_ultima_edicao = timezone.now()
        acao.save()
        registrar_evento(
            entidade='ACAO',
            instancia=acao,
            acao='MUDANCA_STATUS',
            usuario=usuario,
            resumo=f'{MARCADOR}: status da ação alterado.',
            valores_anteriores=acao_anterior,
        )

        condominio = Condominio.objects.create(
            nome='Condomínio Demonstração da Auditoria',
            responsavel_nome='Responsável Demonstração',
            responsavel_telefone='(13) 98888-0000',
            responsavel_email='sim-auditoria-condominio@example.com',
            endereco='Avenida da Auditoria',
            numero='200',
            bairro='Gonzaga',
            cidade='Santos',
            estado='SP',
            cep='11000-000',
            praia=praia,
            cadastrado_por=usuario,
            cadastrado_por_nome=usuario.id_voluntario.nome,
        )
        registrar_evento(
            entidade='CONDOMINIO',
            instancia=condominio,
            acao='CRIACAO',
            usuario=usuario,
            resumo=f'{MARCADOR}: condomínio criado.',
        )

        bag = Bag.objects.create(
            codigo='SIM-AUD-001',
            condominio=condominio,
            status='EM_USO',
            percentual_ocupacao=35,
            peso_atual_kg=Decimal('12.50'),
            cadastrado_por=usuario,
            cadastrado_por_nome=usuario.id_voluntario.nome,
        )
        registrar_evento(
            entidade='BAG',
            instancia=bag,
            acao='CRIACAO',
            usuario=usuario,
            resumo=f'{MARCADOR}: bag criada.',
        )

        movimentacao = MovimentacaoBag.objects.create(
            bag=bag,
            tipo='REGISTRO_CHEIA',
            status_anterior='EM_USO',
            status_novo='CHEIA',
            observacao='Movimentação demonstrativa.',
            registrado_por=usuario,
            registrado_por_nome=usuario.id_voluntario.nome,
        )
        bag_anterior = snapshot(bag)
        bag.status = 'CHEIA'
        bag.percentual_ocupacao = 100
        bag.peso_atual_kg = Decimal('38.75')
        bag.save(update_fields=['status', 'percentual_ocupacao', 'peso_atual_kg'])
        registrar_evento(
            entidade='MOVIMENTACAO',
            instancia=movimentacao,
            acao='MOVIMENTACAO',
            usuario=usuario,
            resumo=f'{MARCADOR}: movimentação de bag registrada.',
        )
        registrar_evento(
            entidade='BAG',
            instancia=bag,
            acao='MUDANCA_STATUS',
            usuario=usuario,
            resumo=f'{MARCADOR}: status da bag alterado.',
            valores_anteriores=bag_anterior,
        )

        praia_exclusao = Praia.objects.create(
            nome='Praia Temporária para Exclusão',
            cidade='Santos',
            latitude=Decimal('-23.968000'),
            longitude=Decimal('-46.329000'),
            cadastrado_por=usuario,
        )
        praia_exclusao_anterior = snapshot(praia_exclusao)
        praia_exclusao.delete()
        registrar_evento(
            entidade='PRAIA',
            id_registro=praia_exclusao.pk,
            acao='EXCLUSAO',
            usuario=usuario,
            resumo=f'{MARCADOR}: praia excluída.',
            valores_anteriores=praia_exclusao_anterior,
        )

        self.stdout.write(self.style.SUCCESS(
            'Dados demonstrativos criados com eventos de criação, edição, status, vínculo, movimentação e exclusão.'
        ))
