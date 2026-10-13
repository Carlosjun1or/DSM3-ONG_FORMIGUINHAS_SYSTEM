from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from usuario.models import Usuario

from auditoria.services import registrar_evento
from doacao.models import Doador, Doacao, DoacaoFinanceira, ItemDoacaoMaterial
from praia.models import Praia
from acao.models import Acao


class Command(BaseCommand):
    help = 'Cria doadores e doações demonstrativas sem duplicar registros.'

    def handle(self, *args, **options):
        usuario = Usuario.objects.order_by('id_usuario').first()
        if not usuario:
            raise CommandError('Cadastre pelo menos um usuário antes de criar dados demonstrativos.')
        praia = Praia.objects.order_by('id_praia').first()
        acao = Acao.objects.order_by('id_acao').first()
        nome_usuario = usuario.id_voluntario.nome

        doador_pf, doador_pf_criado = Doador.objects.get_or_create(
            nome='Doador demonstrativo - Ana Silva',
            defaults={
                'tipo': Doador.PESSOA_FISICA,
                'documento': '123.456.789-00',
                'email': 'ana.demonstrativa@example.com',
                'telefone': '(13) 99999-0001',
                'cadastrado_por': usuario,
                'cadastrado_por_nome': nome_usuario,
            },
        )
        doador_pj, doador_pj_criado = Doador.objects.get_or_create(
            nome='Empresa demonstrativa - Mar Azul',
            defaults={
                'tipo': Doador.PESSOA_JURIDICA,
                'documento': '12.345.678/0001-90',
                'email': 'marazul.demonstrativa@example.com',
                'telefone': '(13) 99999-0002',
                'cadastrado_por': usuario,
                'cadastrado_por_nome': nome_usuario,
            },
        )
        for doador, criado in (
            (doador_pf, doador_pf_criado),
            (doador_pj, doador_pj_criado),
        ):
            if criado:
                registrar_evento(
                    entidade='DOADOR',
                    instancia=doador,
                    acao='CRIACAO',
                    usuario=usuario,
                    resumo=f'Doador demonstrativo #{doador.pk} cadastrado.',
                )

        financeira, criada = Doacao.objects.get_or_create(
            observacoes='DADO DEMONSTRATIVO - pode ser removido após a apresentação.',
            defaults={
                'tipo': Doacao.FINANCEIRA,
                'doador': doador_pf,
                'data_recebimento': timezone.localdate(),
                'status': Doacao.CONFIRMADA,
                'finalidade': Doacao.FINALIDADE_GERAL,
                'praia': praia,
                'acao': acao,
                'registrado_por': usuario,
                'registrado_por_nome': nome_usuario,
                'registrado_por_tipo': usuario.tipo,
            },
        )
        if criada:
            DoacaoFinanceira.objects.create(
                doacao=financeira,
                valor=Decimal('250.00'),
                forma_recebimento=DoacaoFinanceira.PIX,
            )
            registrar_evento(
                entidade='DOACAO',
                instancia=financeira,
                acao='CRIACAO',
                usuario=usuario,
                resumo=f'Doação demonstrativa #{financeira.pk} cadastrada.',
            )

        material, criada = Doacao.objects.get_or_create(
            observacoes='DADO DEMONSTRATIVO - materiais pendentes de confirmação e entrada no estoque.',
            defaults={
                'tipo': Doacao.MATERIAL,
                'doador': doador_pj,
                'data_recebimento': timezone.localdate(),
                'status': Doacao.PENDENTE,
                'finalidade': Doacao.FINALIDADE_ESPECIFICA,
                'descricao_finalidade': 'Apoio aos próximos mutirões',
                'praia': praia,
                'acao': acao,
                'registrado_por': usuario,
                'registrado_por_nome': nome_usuario,
                'registrado_por_tipo': usuario.tipo,
            },
        )
        if criada:
            ItemDoacaoMaterial.objects.bulk_create([
                ItemDoacaoMaterial(
                    doacao=material,
                    nome='Luvas de proteção',
                    categoria='Equipamentos de proteção',
                    quantidade=Decimal('50'),
                    unidade='unidades',
                    condicao=ItemDoacaoMaterial.CONDICAO_NOVO,
                ),
                ItemDoacaoMaterial(
                    doacao=material,
                    nome='Sacos para coleta',
                    categoria='Materiais de limpeza',
                    quantidade=Decimal('10'),
                    unidade='pacotes',
                    condicao=ItemDoacaoMaterial.CONDICAO_NOVO,
                ),
            ])
            registrar_evento(
                entidade='DOACAO',
                instancia=material,
                acao='CRIACAO',
                usuario=usuario,
                resumo=f'Doação demonstrativa #{material.pk} cadastrada.',
            )

        self.stdout.write(self.style.SUCCESS(
            'Dados demonstrativos disponíveis: 2 doadores e 2 doações.'
        ))
