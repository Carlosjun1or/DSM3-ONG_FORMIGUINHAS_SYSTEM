from django.db import transaction

from auditoria.services import registrar_evento


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
def registrar_doacao(doacao, usuario):
    """Salva a doação (que gera a entrada no estoque) e audita as duas operações."""
    doacao.registrado_por = usuario
    doacao.registrado_por_nome = _nome_usuario(usuario)
    doacao.save()
    registrar_evento(
        entidade='DOACAO',
        instancia=doacao,
        acao='CRIACAO',
        usuario=usuario,
        resumo=f'Doação de {doacao.quantidade} de "{doacao.material.nome}" por {doacao.doador}.',
    )
    entrada = doacao.movimentacoes.get()
    registrar_evento(
        entidade='MOVIMENTACAO_ESTOQUE',
        instancia=entrada,
        acao='MOVIMENTACAO',
        usuario=usuario,
        resumo=f'Entrada por doação de {entrada.quantidade} de "{doacao.material.nome}".',
    )
    return doacao
