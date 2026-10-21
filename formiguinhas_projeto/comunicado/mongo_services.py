"""
Serviços de persistência documental e consultas no MongoDB Atlas para o módulo de Comunicados (Persistência Poliglota).
Modela Comunicados como documentos agregados ricos contendo Tema, Leituras e Relacionamentos (Praias, Equipes, Ações, Doações).
"""
import logging
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from config.mongodb import get_mongo_collection

logger = logging.getLogger(__name__)

COLECAO_COMUNICADOS = getattr(settings, 'MONGODB_COMUNICADOS_COLECAO', 'comunicados')
_indices_configurados = False


def get_comunicados_collection():
    """Retorna a coleção de comunicados no MongoDB Atlas garantindo índices."""
    global _indices_configurados
    col = get_mongo_collection(COLECAO_COMUNICADOS)
    if col is None:
        return None

    if not _indices_configurados:
        try:
            col.create_index([('id_sql', 1)], unique=True)
            col.create_index([('status', 1), ('publico', 1), ('dt_publicacao', DESCENDING)])
            col.create_index([('tipo', 1), ('status', 1)])
            col.create_index([('tema.id', 1)])
            col.create_index([('praias.id', 1)])
            col.create_index([('equipes.id', 1)])
            col.create_index([('acoes.id', 1)])
            col.create_index([('leituras.usuario_id', 1)])
            _indices_configurados = True
        except Exception as erro:
            logger.warning(f'Falha ao criar índices da coleção comunicados no MongoDB Atlas: {erro}')
    return col


def formatar_comunicado_documento(comunicado):
    """
    Transforma a instância relacional de Comunicado e seus relacionamentos
    (Tema, Praias, Equipes, Ações, Doações e Leituras) em um documento BSON rico.
    """
    # 1. Tema
    tema_info = None
    if comunicado.tema_id and comunicado.tema:
        tema_info = {
            'id': comunicado.tema.pk,
            'nome': comunicado.tema.nome,
            'descricao': comunicado.tema.descricao or '',
            'ativo': bool(comunicado.tema.ativo),
        }

    # 2. Praias relacionadas
    praias_lista = []
    for cp in comunicado.praias.select_related('praia').all():
        p = cp.praia
        praias_lista.append({
            'id': p.pk,
            'nome': p.nome,
            'cidade': p.cidade,
        })

    # 3. Equipes relacionadas
    equipes_lista = []
    for ce in comunicado.equipes.select_related('equipe').all():
        eq = ce.equipe
        equipes_lista.append({
            'id': eq.pk,
            'nome': eq.nome,
            'status': eq.status,
        })

    # 4. Ações relacionadas
    acoes_lista = []
    for ca in comunicado.acoes.select_related('acao__praia').all():
        ac = ca.acao
        acoes_lista.append({
            'id': ac.pk,
            'tipo': ac.tipo,
            'tipo_display': ac.get_tipo_display(),
            'praia_nome': ac.praia.nome if ac.praia else '',
            'data': ac.data.isoformat() if ac.data else None,
            'status': ac.status,
            'status_display': ac.get_status_display(),
        })

    # 5. Doações relacionadas
    doacoes_lista = []
    for cd in comunicado.doacoes.select_related('doacao__doador').all():
        d = cd.doacao
        doacoes_lista.append({
            'id': d.pk,
            'tipo': d.tipo,
            'tipo_display': d.get_tipo_display(),
            'anonima': bool(d.anonima),
            'doador_nome': d.doador.nome if (d.doador and not d.anonima) else 'Anônima',
            'data_recebimento': d.data_recebimento.isoformat() if d.data_recebimento else None,
        })

    # 6. Leituras registradas
    leituras_lista = []
    for cl in comunicado.leituras.select_related('usuario__id_voluntario').all():
        u = cl.usuario
        nome = u.id_voluntario.nome if (u and u.id_voluntario) else str(u)
        leituras_lista.append({
            'usuario_id': u.pk if u else None,
            'usuario_nome': nome,
            'lido_em': cl.lido_em.isoformat() if cl.lido_em else None,
        })

    # Autor e Edição
    autor_nome = ''
    if comunicado.autor:
        autor_nome = (
            comunicado.autor.id_voluntario.nome
            if comunicado.autor.id_voluntario
            else str(comunicado.autor)
        )

    ultimo_editado_por_nome = ''
    if comunicado.ultimo_editado_por:
        ultimo_editado_por_nome = (
            comunicado.ultimo_editado_por.id_voluntario.nome
            if comunicado.ultimo_editado_por.id_voluntario
            else str(comunicado.ultimo_editado_por)
        )

    return {
        'id_sql': comunicado.pk,
        'tipo': comunicado.tipo,
        'tipo_display': comunicado.get_tipo_display(),
        'titulo': comunicado.titulo,
        'resumo': comunicado.resumo or '',
        'conteudo': comunicado.conteudo or '',
        'publico': comunicado.publico,
        'publico_display': comunicado.get_publico_display(),
        'status': comunicado.status,
        'status_display': comunicado.get_status_display(),
        'tema': tema_info,
        'dt_publicacao': comunicado.dt_publicacao,
        'dt_expiracao': comunicado.dt_expiracao,
        'duracao_expiracao': comunicado.duracao_expiracao,
        'unidade_duracao_expiracao': comunicado.unidade_duracao_expiracao or '',
        'autor': {
            'id': comunicado.autor_id,
            'nome': autor_nome,
            'perfil': comunicado.perfil_autor or '',
        },
        'ultimo_editado_por_nome': ultimo_editado_por_nome,
        'dt_ultima_edicao': comunicado.dt_ultima_edicao,
        'criado_em': comunicado.criado_em,
        'atualizado_em': comunicado.atualizado_em,
        'praias': praias_lista,
        'equipes': equipes_lista,
        'acoes': acoes_lista,
        'doacoes': doacoes_lista,
        'leituras': leituras_lista,
        'total_leituras': len(leituras_lista),
        'metadados': {
            'versao_schema': 1,
            'armazenamento': 'mongodb_atlas',
            'sincronizado_em': timezone.now().isoformat(),
        },
    }


def salvar_comunicado_mongo(comunicado):
    """Persiste ou atualiza (upsert) o documento completo de comunicado no MongoDB Atlas."""
    col = get_comunicados_collection()
    if col is None:
        return False

    try:
        doc = formatar_comunicado_documento(comunicado)
        col.replace_one({'id_sql': comunicado.pk}, doc, upsert=True)
        return True
    except PyMongoError as erro:
        logger.warning(f'Erro ao salvar comunicado #{comunicado.pk} no MongoDB Atlas: {erro}')
        return False
    except Exception as erro:
        logger.error(f'Erro inesperado ao salvar comunicado #{comunicado.pk} no MongoDB Atlas: {erro}')
        return False


def remover_comunicado_mongo(comunicado_id):
    """Remove o documento de comunicado do MongoDB Atlas."""
    col = get_comunicados_collection()
    if col is None:
        return False

    try:
        col.delete_one({'id_sql': int(comunicado_id)})
        return True
    except Exception as erro:
        logger.warning(f'Erro ao remover comunicado #{comunicado_id} no MongoDB Atlas: {erro}')
        return False


def registrar_leitura_comunicado_mongo(comunicado_id, usuario):
    """Adiciona a leitura do usuário diretamente no array de leituras do documento no Atlas."""
    col = get_comunicados_collection()
    if col is None:
        return False

    try:
        nome = (
            usuario.id_voluntario.nome
            if getattr(usuario, 'id_voluntario', None)
            else str(usuario)
        )
        col.update_one(
            {
                'id_sql': int(comunicado_id),
                'leituras.usuario_id': {'$ne': usuario.pk},
            },
            {
                '$push': {
                    'leituras': {
                        'usuario_id': usuario.pk,
                        'usuario_nome': nome,
                        'lido_em': timezone.now().isoformat(),
                    }
                },
                '$inc': {'total_leituras': 1},
            }
        )
        return True
    except Exception as erro:
        logger.warning(f'Erro ao registrar leitura no MongoDB Atlas para comunicado #{comunicado_id}: {erro}')
        return False


def consultar_comunicados_mongo(filtros=None, pagina=1, por_pagina=20):
    """
    Realiza busca paginada com filtros MQL no MongoDB Atlas.
    Retorna (itens: list, total: int).
    """
    col = get_comunicados_collection()
    if col is None:
        return [], 0

    filtros = filtros or {}
    query = {}

    busca = filtros.get('busca')
    if busca:
        query['$or'] = [
            {'titulo': {'$regex': busca, '$options': 'i'}},
            {'resumo': {'$regex': busca, '$options': 'i'}},
            {'conteudo': {'$regex': busca, '$options': 'i'}},
        ]

    tipo = filtros.get('tipo')
    if tipo:
        query['tipo'] = tipo

    status = filtros.get('status')
    if status:
        query['status'] = status

    publico = filtros.get('publico')
    if publico:
        query['publico'] = publico

    tema_id = filtros.get('tema_id')
    if tema_id:
        try:
            query['tema.id'] = int(tema_id)
        except (ValueError, TypeError):
            pass

    pagina = max(1, int(pagina or 1))
    por_pagina = max(1, int(por_pagina or 20))
    skip = (pagina - 1) * por_pagina

    try:
        total = col.count_documents(query)
        cursor = (
            col.find(query)
            .sort([('dt_publicacao', DESCENDING), ('criado_em', DESCENDING), ('id_sql', DESCENDING)])
            .skip(skip)
            .limit(por_pagina)
        )
        return list(cursor), total
    except Exception as erro:
        logger.error(f'Erro ao consultar comunicados no MongoDB Atlas: {erro}')
        return [], 0


def obter_comunicado_mongo(comunicado_id):
    """Busca um documento de comunicado no Atlas pelo seu id_sql."""
    col = get_comunicados_collection()
    if col is None:
        return None

    try:
        return col.find_one({'id_sql': int(comunicado_id)})
    except Exception as erro:
        logger.warning(f'Erro ao obter comunicado #{comunicado_id} no MongoDB Atlas: {erro}')
        return None


def obter_metricas_comunicados_mongo():
    """Calcula estatísticas de comunicados agregadas nativamente no MongoDB."""
    col = get_comunicados_collection()
    if col is None:
        return {'total': 0, 'publicados': 0, 'rascunhos': 0, 'arquivados': 0}

    try:
        total = col.count_documents({})
        publicados = col.count_documents({'status': 'PUBLICADO'})
        rascunhos = col.count_documents({'status': 'RASCUNHO'})
        arquivados = col.count_documents({'status': 'ARQUIVADO'})

        return {
            'total': total,
            'publicados': publicados,
            'rascunhos': rascunhos,
            'arquivados': arquivados,
        }
    except Exception as erro:
        logger.warning(f'Erro ao calcular métricas de comunicados no MongoDB: {erro}')
        return {'total': 0, 'publicados': 0, 'rascunhos': 0, 'arquivados': 0}

