"""
Serviços de persistência e consulta no MongoDB Atlas para a Auditoria (Persistência Poliglota).
"""
import logging
from datetime import datetime, time
from django.conf import settings
from django.utils import timezone
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from config.mongodb import get_mongo_collection

logger = logging.getLogger(__name__)

COLECAO_AUDITORIA = getattr(settings, 'MONGODB_AUDITORIA_COLECAO', 'auditoria_eventos')
_indices_configurados = False


def get_auditoria_collection():
    """Retorna a coleção de eventos de auditoria com índices garantidos."""
    global _indices_configurados
    col = get_mongo_collection(COLECAO_AUDITORIA)
    if col is None:
        return None

    if not _indices_configurados:
        try:
            col.create_index([('data_evento', DESCENDING)])
            col.create_index([('entidade', 1), ('acao', 1)])
            col.create_index([('usuario.id', 1)])
            _indices_configurados = True
        except Exception as erro:
            logger.warning(f'Falha ao criar índices no MongoDB Atlas: {erro}')
    return col


def formatar_documento_auditoria(
    *,
    entidade,
    id_registro=None,
    acao,
    usuario=None,
    usuario_nome=None,
    resumo,
    valores_anteriores=None,
    valores_novos=None,
    data_evento=None,
    origem='SISTEMA_WEB',
):
    """
    Estrutura um documento BSON rico e auto-contido para o MongoDB Atlas.
    """
    from .models import EventoAuditoria

    # Resolução de labels amigáveis
    entidade_display = EventoAuditoria.ENTIDADE_LABELS.get(
        entidade,
        entidade.replace('_', ' ').title() if isinstance(entidade, str) else str(entidade),
    )
    acao_dict = dict(EventoAuditoria.ACAO_CHOICES)
    acao_display = acao_dict.get(acao, acao)

    # Dados do usuário ator
    usuario_info = None
    nome_ator = usuario_nome or ''
    if usuario is not None:
        nome_ator = (
            getattr(getattr(usuario, 'id_voluntario', None), 'nome', '')
            or nome_ator
            or str(usuario)
        )
        usuario_info = {
            'id': getattr(usuario, 'pk', None),
            'nome': nome_ator[:150],
            'tipo': getattr(usuario, 'tipo', ''),
        }
    elif nome_ator:
        usuario_info = {
            'id': None,
            'nome': nome_ator[:150],
            'tipo': '',
        }

    # Data do evento
    momento = data_evento or timezone.now()
    if isinstance(momento, str):
        try:
            momento = datetime.fromisoformat(momento)
        except Exception:
            momento = timezone.now()

    return {
        'entidade': str(entidade),
        'entidade_display': entidade_display,
        'id_registro': id_registro,
        'acao': str(acao),
        'acao_display': acao_display,
        'resumo': (resumo or '')[:255],
        'usuario': usuario_info,
        'usuario_nome': nome_ator[:150],
        'data_evento': momento,
        'valores_anteriores': valores_anteriores or {},
        'valores_novos': valores_novos or {},
        'origem': origem,
        'metadados': {
            'armazenamento': 'mongodb_atlas',
            'versao_schema': 1,
        },
    }


def registrar_evento_mongo(
    *,
    entidade,
    id_registro=None,
    acao,
    usuario=None,
    usuario_nome=None,
    resumo,
    valores_anteriores=None,
    valores_novos=None,
    data_evento=None,
    origem='SISTEMA_WEB',
):
    """
    Insere um documento de auditoria no MongoDB Atlas de forma segura.
    Retorna a string do ObjectId gerado ou None se houver falha.
    """
    try:
        col = get_auditoria_collection()
        if col is None:
            return None

        doc = formatar_documento_auditoria(
            entidade=entidade,
            id_registro=id_registro,
            acao=acao,
            usuario=usuario,
            usuario_nome=usuario_nome,
            resumo=resumo,
            valores_anteriores=valores_anteriores,
            valores_novos=valores_novos,
            data_evento=data_evento,
            origem=origem,
        )

        resultado = col.insert_one(doc)
        return str(resultado.inserted_id)
    except PyMongoError as erro:
        logger.error(f'Falha ao registrar auditoria no MongoDB Atlas: {erro}')
        return None
    except Exception as erro:
        logger.error(f'Erro inesperado ao salvar auditoria no MongoDB: {erro}')
        return None


def construir_query_mongo(filtros=None):
    """Monta o dicionário de filtros MQL (MongoDB Query Language)."""
    filtros = filtros or {}
    query = {}

    entidade = filtros.get('entidade')
    if entidade:
        query['entidade'] = entidade

    acao = filtros.get('acao')
    if acao:
        query['acao'] = acao

    usuario_id = filtros.get('usuario')
    if usuario_id:
        try:
            query['usuario.id'] = int(usuario_id)
        except (ValueError, TypeError):
            pass

    inicio = filtros.get('inicio')
    fim = filtros.get('fim')
    filtro_data = {}
    if inicio:
        if isinstance(inicio, str):
            from django.utils.dateparse import parse_date
            data_obj = parse_date(inicio)
            if data_obj:
                filtro_data['$gte'] = datetime.combine(data_obj, time.min)
        elif hasattr(inicio, 'year'):
            filtro_data['$gte'] = datetime.combine(inicio, time.min)

    if fim:
        if isinstance(fim, str):
            from django.utils.dateparse import parse_date
            data_obj = parse_date(fim)
            if data_obj:
                filtro_data['$lte'] = datetime.combine(data_obj, time.max)
        elif hasattr(fim, 'year'):
            filtro_data['$lte'] = datetime.combine(fim, time.max)

    if filtro_data:
        query['data_evento'] = filtro_data

    busca = filtros.get('busca')
    if busca:
        query['$or'] = [
            {'resumo': {'$regex': busca, '$options': 'i'}},
            {'usuario_nome': {'$regex': busca, '$options': 'i'}},
        ]

    return query


def consultar_eventos_mongo(filtros=None, pagina=1, por_pagina=20):
    """
    Consulta os eventos de auditoria paginados a partir do MongoDB Atlas.
    Retorna (itens: list, total: int).
    """
    col = get_auditoria_collection()
    if col is None:
        return [], 0

    query = construir_query_mongo(filtros)
    pagina = max(1, int(pagina or 1))
    por_pagina = max(1, int(por_pagina or 20))
    skip = (pagina - 1) * por_pagina

    try:
        total = col.count_documents(query)
        cursor = (
            col.find(query)
            .sort('data_evento', DESCENDING)
            .skip(skip)
            .limit(por_pagina)
        )

        eventos = []
        for doc in cursor:
            doc['id_mongo'] = str(doc.get('_id'))
            eventos.append(doc)
        return eventos, total
    except Exception as erro:
        logger.error(f'Erro ao consultar auditoria no MongoDB Atlas: {erro}')
        return [], 0


def obter_entidades_mongo():
    """Retorna a lista de entidades distintas existentes no MongoDB."""
    col = get_auditoria_collection()
    if col is None:
        return []
    try:
        return sorted(col.distinct('entidade'))
    except Exception as erro:
        logger.warning(f'Erro ao obter entidades distintas do MongoDB: {erro}')
        return []


def obter_estatisticas_mongo():
    """
    Calcula agregações analíticas nativas usando o Aggregation Framework do MongoDB.
    """
    col = get_auditoria_collection()
    if col is None:
        return {
            'disponivel': False,
            'total': 0,
            'por_acao': {},
            'por_entidade': {},
            'total_usuarios_distintos': 0,
        }

    try:
        total = col.count_documents({})
        if total == 0:
            return {
                'disponivel': True,
                'total': 0,
                'por_acao': {},
                'por_entidade': {},
                'total_usuarios_distintos': 0,
            }

        # Agregação por Ação
        pipe_acao = [{'$group': {'_id': '$acao', 'total': {'$sum': 1}}}]
        acoes = {item['_id']: item['total'] for item in col.aggregate(pipe_acao) if item['_id']}

        # Agregação por Entidade
        pipe_entidade = [{'$group': {'_id': '$entidade', 'total': {'$sum': 1}}}, {'$sort': {'total': -1}}]
        entidades = {item['_id']: item['total'] for item in col.aggregate(pipe_entidade) if item['_id']}

        # Usuários distintos
        usuarios_distintos = len([u for u in col.distinct('usuario.id') if u is not None])

        return {
            'disponivel': True,
            'total': total,
            'por_acao': acoes,
            'por_entidade': entidades,
            'total_usuarios_distintos': usuarios_distintos,
        }
    except Exception as erro:
        logger.error(f'Erro ao calcular métricas de auditoria no MongoDB: {erro}')
        return {
            'disponivel': False,
            'erro': str(erro),
            'total': 0,
            'por_acao': {},
            'por_entidade': {},
            'total_usuarios_distintos': 0,
        }

