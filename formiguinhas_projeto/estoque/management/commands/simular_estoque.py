from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from auditoria.services import registrar_evento
from doacao.models import Doador, Doacao, ItemDoacaoMaterial
from estoque.models import Material, MovimentacaoEstoque
from estoque.services import registrar_entradas_doacao, registrar_movimentacao
from usuario.models import Usuario


MARCADOR = 'DADO DEMONSTRATIVO - estoque'


class Command(BaseCommand):
    help = 'Cria materiais e movimentações demonstrativas sem duplicar dados.'

    @transaction.atomic
    def handle(self, *args, **options):
        usuario = (
            Usuario.objects.filter(tipo='ADMIN')
            .select_related('id_voluntario')
            .order_by('id_usuario')
            .first()
        )
        if not usuario:
            raise CommandError('Cadastre pelo menos um usuário ADMIN antes de simular o estoque.')

        nome_usuario = usuario.id_voluntario.nome
        materiais = {}
        criados = []
        for dados in (
            {
                'codigo': 'DEMO-EPI-001',
                'nome': 'Luvas de proteção demonstrativas',
                'categoria': 'Equipamentos de proteção',
                'descricao': f'{MARCADOR}: material para demonstrar entradas e saídas.',
                'quantidade_inicial': 24,
                'estoque_minimo': 10,
                'unidade': 'CAIXA',
            },
            {
                'codigo': 'DEMO-LIM-001',
                'nome': 'Sacos para coleta demonstrativos',
                'categoria': 'Limpeza',
                'descricao': f'{MARCADOR}: exemplo de estoque baixo.',
                'quantidade_inicial': 5,
                'estoque_minimo': 10,
                'unidade': 'PACOTE',
            },
            {
                'codigo': 'DEMO-KIT-001',
                'nome': 'Kit de primeiros socorros demonstrativo',
                'categoria': 'Primeiros socorros',
                'descricao': f'{MARCADOR}: exemplo de entrada por doação confirmada.',
                'quantidade_inicial': 0,
                'estoque_minimo': 2,
                'unidade': 'UNIDADE',
            },
            {
                'codigo': 'DEMO-HIG-001',
                'nome': 'Água sanitária demonstrativa',
                'categoria': 'Limpeza',
                'descricao': f'{MARCADOR}: exemplo de compra e saída.',
                'quantidade_inicial': 3,
                'estoque_minimo': 2,
                'unidade': 'LITRO',
            },
        ):
            defaults = {
                **dados,
                'cadastrado_por': usuario,
                'cadastrado_por_nome': nome_usuario,
            }
            material, criado = Material.objects.get_or_create(
                codigo=dados['codigo'],
                defaults=defaults,
            )
            if material.nome != dados['nome']:
                raise CommandError(
                    f'O código demonstrativo {dados["codigo"]} já está vinculado a outro material.'
                )
            materiais[dados['codigo']] = material
            if criado:
                criados.append(material)
                registrar_evento(
                    entidade='MATERIAL',
                    instancia=material,
                    acao='CRIACAO',
                    usuario=usuario,
                    resumo=f'{MARCADOR}: material "{material.nome}" criado.',
                )

        doador, _ = Doador.objects.get_or_create(
            email='estoque.demonstrativo@example.org',
            defaults={
                'tipo': Doador.PESSOA_JURIDICA,
                'nome': 'Doador demonstrativo do estoque',
                'telefone': '(13) 99999-0000',
                'cadastrado_por': usuario,
                'cadastrado_por_nome': nome_usuario,
            },
        )
        doacao, doacao_criada = Doacao.objects.get_or_create(
            observacoes=f'{MARCADOR}: doação confirmada para demonstrar a integração.',
            defaults={
                'tipo': Doacao.MATERIAL,
                'doador': doador,
                'data_recebimento': timezone.localdate(),
                'status': Doacao.CONFIRMADA,
                'finalidade': Doacao.FINALIDADE_GERAL,
                'registrado_por': usuario,
                'registrado_por_nome': nome_usuario,
                'registrado_por_tipo': usuario.tipo,
            },
        )
        if doacao.tipo != Doacao.MATERIAL or doacao.status != Doacao.CONFIRMADA:
            raise CommandError('O registro demonstrativo existente não está em um estado válido.')
        if doacao_criada:
            registrar_evento(
                entidade='DOACAO',
                instancia=doacao,
                acao='CRIACAO',
                usuario=usuario,
                resumo=f'{MARCADOR}: doação material confirmada criada.',
            )

        material_doado = materiais['DEMO-KIT-001']
        item, _ = ItemDoacaoMaterial.objects.get_or_create(
            doacao=doacao,
            nome='Kit de primeiros socorros demonstrativo',
            defaults={
                'material': material_doado,
                'categoria': material_doado.categoria,
                'quantidade': Decimal('6'),
                'unidade': material_doado.get_unidade_display(),
                'condicao': ItemDoacaoMaterial.CONDICAO_NOVO,
                'observacoes': MARCADOR,
            },
        )
        if item.material_id != material_doado.pk or item.quantidade != Decimal('6'):
            raise CommandError('O item demonstrativo existente não corresponde ao material esperado.')
        if not doacao.movimentacoes_estoque.exists():
            registrar_entradas_doacao(doacao, usuario)

        self._registrar_entrada(
            materiais['DEMO-EPI-001'],
            usuario,
            quantidade=12,
            origem='COMPRA',
            justificativa=f'{MARCADOR}: compra simulada de luvas.',
        )
        self._registrar_saida(
            materiais['DEMO-EPI-001'],
            usuario,
            quantidade=4,
            justificativa=f'{MARCADOR}: saída simulada para ação de limpeza.',
        )
        self._registrar_entrada(
            materiais['DEMO-HIG-001'],
            usuario,
            quantidade=8,
            origem='COMPRA',
            justificativa=f'{MARCADOR}: compra simulada de material de limpeza.',
        )
        self._registrar_saida(
            materiais['DEMO-HIG-001'],
            usuario,
            quantidade=2,
            justificativa=f'{MARCADOR}: saída simulada para ação de limpeza.',
        )

        movimentacoes_demo = MovimentacaoEstoque.objects.filter(
            Q(justificativa__startswith=MARCADOR) | Q(doacao=doacao)
        ).distinct().count()
        self.stdout.write(self.style.SUCCESS(
            'Dados demonstrativos prontos: '
            f'{len(criados)} material(is) novo(s), '
            f'{movimentacoes_demo} '
            'movimentação(ões) simulada(s), incluindo uma doação integrada. '
            'Executar novamente não duplica os registros.'
        ))
        for material in materiais.values():
            material.refresh_from_db()
            self.stdout.write(
                f'- {material.nome}: saldo {material.calcular_saldo()} '
                f'{material.get_unidade_display()} (mínimo {material.estoque_minimo})'
            )

    @staticmethod
    def _registrar_entrada(material, usuario, quantidade, origem, justificativa):
        if MovimentacaoEstoque.objects.filter(
            material=material,
            tipo='ENTRADA',
            origem=origem,
            justificativa=justificativa,
        ).exists():
            return
        registrar_movimentacao(MovimentacaoEstoque(
            material=material,
            tipo='ENTRADA',
            quantidade=quantidade,
            origem=origem,
            justificativa=justificativa,
        ), usuario)

    @staticmethod
    def _registrar_saida(material, usuario, quantidade, justificativa):
        if MovimentacaoEstoque.objects.filter(
            material=material,
            tipo='SAIDA',
            justificativa=justificativa,
        ).exists():
            return
        registrar_movimentacao(MovimentacaoEstoque(
            material=material,
            tipo='SAIDA',
            quantidade=quantidade,
            justificativa=justificativa,
        ), usuario)
