from django.db import transaction
from django.core.exceptions import ValidationError

from auditoria.services import registrar_evento
from doacao.models import Doacao, ItemDoacaoMaterial

from .models import MovimentacaoEstoque


def _nome_usuario(usuario):
    return usuario.id_voluntario.nome


@transaction.atomic
def registrar_movimentacao(movimentacao, usuario):
    """Salva a movimentação validando saldo e registra o evento de auditoria."""
    movimentacao.registrado_por = usuario
    movimentacao.registrado_por_nome = _nome_usuario(usuario)
    movimentacao.save()
    registrar_evento(
        entidade='MOVIMENTACAO_ESTOQUE',
        instancia=movimentacao,
        acao='MOVIMENTACAO',
        usuario=usuario,
        resumo=(
            f'{movimentacao.get_tipo_display()} de {movimentacao.quantidade} '
            f'{movimentacao.material.get_unidade_display()} de "{movimentacao.material.nome}".'
        ),
    )
    return movimentacao


@transaction.atomic
def registrar_entradas_doacao(doacao, usuario):
    """Cria uma entrada auditada para cada item válido de uma doação confirmada."""
    if doacao.tipo != Doacao.MATERIAL or doacao.status != Doacao.CONFIRMADA:
        raise ValidationError('Somente doações de materiais confirmadas movimentam o estoque.')

    itens = list(doacao.itens_materiais.select_related('material').order_by('pk'))
    if not itens:
        raise ValidationError('A doação não possui materiais para lançar no estoque.')

    if doacao.movimentacoes_estoque.filter(item_doacao__isnull=True).exists():
        raise ValidationError(
            'Esta doação já possui movimentações históricas sem vínculo com os itens. '
            'Revise o histórico antes de gerar novas entradas.'
        )

    for item in itens:
        if item.material_id is None:
            raise ValidationError(
                f'Selecione o material do estoque para o item "{item.nome}".'
            )
        if item.quantidade != item.quantidade.to_integral_value():
            raise ValidationError(
                f'A quantidade de "{item.nome}" precisa ser inteira para movimentar o estoque.'
            )
        if item.condicao == ItemDoacaoMaterial.CONDICAO_DANIFICADO:
            raise ValidationError(
                f'O material "{item.nome}" está danificado e não pode entrar no estoque.'
            )
    for item in itens:
        if MovimentacaoEstoque.objects.filter(item_doacao=item).exists():
            continue
        movimentacao = MovimentacaoEstoque(
            material=item.material,
            tipo='ENTRADA',
            quantidade=int(item.quantidade),
            origem='DOACAO',
            doacao=doacao,
            item_doacao=item,
        )
        registrar_movimentacao(movimentacao, usuario)
