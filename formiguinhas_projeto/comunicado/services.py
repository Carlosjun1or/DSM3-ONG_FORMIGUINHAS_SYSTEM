import calendar
from datetime import timedelta

from django.utils import timezone
from auditoria.services import registrar_evento, snapshot
from .models import Comunicado
from .mongo_services import salvar_comunicado_mongo


def calcular_expiracao(inicio, quantidade, unidade):
    if unidade == 'DIAS':
        return inicio + timedelta(days=quantidade)
    if unidade == 'SEMANAS':
        return inicio + timedelta(weeks=quantidade)
    if unidade == 'MESES':
        total_meses = inicio.month - 1 + quantidade
        ano = inicio.year + total_meses // 12
        mes = total_meses % 12 + 1
        dia = min(inicio.day, calendar.monthrange(ano, mes)[1])
        return inicio.replace(year=ano, month=mes, day=dia)
    if unidade == 'ANOS':
        try:
            return inicio.replace(year=inicio.year + quantidade)
        except ValueError:
            return inicio.replace(year=inicio.year + quantidade, day=28)
    return None


def publicar(comunicado, usuario):
    anterior = snapshot(comunicado)
    comunicado.status = Comunicado.PUBLICADO
    comunicado.dt_publicacao = timezone.now()
    if comunicado.duracao_expiracao and comunicado.unidade_duracao_expiracao:
        comunicado.dt_expiracao = calcular_expiracao(
            comunicado.dt_publicacao,
            comunicado.duracao_expiracao,
            comunicado.unidade_duracao_expiracao,
        )
    else:
        comunicado.dt_expiracao = None
    comunicado.ultimo_editado_por = usuario
    comunicado.dt_ultima_edicao = timezone.now()
    comunicado.full_clean()
    comunicado.save()
    salvar_comunicado_mongo(comunicado)
    registrar_evento(entidade='COMUNICADO', instancia=comunicado, acao='MUDANCA_STATUS',
                     usuario=usuario, resumo='Comunicado publicado',
                     valores_anteriores=anterior)


def despublicar(comunicado, usuario):
    anterior = snapshot(comunicado)
    comunicado.status = Comunicado.RASCUNHO
    comunicado.ultimo_editado_por = usuario
    comunicado.dt_ultima_edicao = timezone.now()
    comunicado.save(update_fields=('status', 'ultimo_editado_por', 'dt_ultima_edicao', 'atualizado_em'))
    salvar_comunicado_mongo(comunicado)
    registrar_evento(entidade='COMUNICADO', instancia=comunicado, acao='MUDANCA_STATUS',
                     usuario=usuario, resumo='Comunicado despublicado',
                     valores_anteriores=anterior)


def arquivar(comunicado, usuario):
    anterior = snapshot(comunicado)
    comunicado.status = Comunicado.ARQUIVADO
    comunicado.ultimo_editado_por = usuario
    comunicado.dt_ultima_edicao = timezone.now()
    comunicado.save(update_fields=('status', 'ultimo_editado_por', 'dt_ultima_edicao', 'atualizado_em'))
    salvar_comunicado_mongo(comunicado)
    registrar_evento(entidade='COMUNICADO', instancia=comunicado, acao='MUDANCA_STATUS',
                     usuario=usuario, resumo='Comunicado arquivado',
                     valores_anteriores=anterior)


def desarquivar(comunicado, usuario):
    anterior = snapshot(comunicado)
    comunicado.status = Comunicado.RASCUNHO
    comunicado.ultimo_editado_por = usuario
    comunicado.dt_ultima_edicao = timezone.now()
    comunicado.save(update_fields=('status', 'ultimo_editado_por', 'dt_ultima_edicao', 'atualizado_em'))
    salvar_comunicado_mongo(comunicado)
    registrar_evento(entidade='COMUNICADO', instancia=comunicado, acao='MUDANCA_STATUS',
                     usuario=usuario, resumo='Comunicado desarquivado',
                     valores_anteriores=anterior)
