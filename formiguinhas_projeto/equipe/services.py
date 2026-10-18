from django.db import transaction
from django.utils import timezone

from auditoria.services import registrar_evento, snapshot
from .models import Equipe, EquipeMembro


@transaction.atomic
def encerrar_vinculos_voluntario(voluntario, usuario):
    agora = timezone.now()
    membros = list(
        EquipeMembro.objects.select_related('equipe').filter(
            voluntario=voluntario,
            status='ATIVO',
        )
    )

    if not membros:
        return 0

    equipes_ids = {membro.equipe_id for membro in membros}
    for membro in membros:
        valores_anteriores = snapshot(membro)
        membro.status = 'INATIVO'
        membro.dt_saida = agora
        membro.ultimo_editado_por = usuario
        membro.ultimo_editado_por_nome = usuario.id_voluntario.nome
        membro.ultimo_editado_por_tipo = usuario.tipo
        membro.dt_ultima_edicao = agora
        membro.save(update_fields=[
            'status',
            'dt_saida',
            'ultimo_editado_por',
            'ultimo_editado_por_nome',
            'ultimo_editado_por_tipo',
            'dt_ultima_edicao',
        ])
        registrar_evento(
            entidade='EQUIPE_MEMBRO',
            instancia=membro,
            acao='MUDANCA_STATUS',
            usuario=usuario,
            resumo=f'{voluntario.nome} removido da equipe "{membro.equipe.nome}" por inativação do voluntário.',
            valores_anteriores=valores_anteriores,
        )

    Equipe.objects.filter(id_equipe__in=equipes_ids).update(
        ultimo_editado_por=usuario,
        ultimo_editado_por_nome=usuario.id_voluntario.nome,
        ultimo_editado_por_tipo=usuario.tipo,
        dt_ultima_edicao=agora,
    )
    return len(membros)
