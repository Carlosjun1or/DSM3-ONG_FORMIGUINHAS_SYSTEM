"""
Serviços de persistência documental e consultas no MongoDB Atlas para o módulo de Ações (Cenário C).
Permite modelar Ações de Limpeza de Praia como documentos ricos (DDD Aggregate Root),
incluindo equipes, participantes, imagens, coordenadas GeoJSON e resíduos coletados.
"""
import logging
from datetime import date, datetime, time
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from config.mongodb import get_mongo_collection

logger = logging.getLogger(__name__)

COLECAO_ACOES = getattr(settings, 'MONGODB_ACOES_COLECAO', 'acoes')
_indices_acoes_configurados = False


def get_acoes_collection():
    """Retorna a coleção de ações no MongoDB Atlas garantindo índices e suporte geoespacial."""
    global _indices_acoes_configurados
    col = get_mongo_collection(COLECAO_ACOES)
    if col is None:
        return None

    if not _indices_acoes_configurados:
        try:
            col.create_index([('id_sql', 1)], unique=True)
            col.create_index([('data', DESCENDING), ('id_sql', DESCENDING)])
            col.create_index([('status', 1)])
            col.create_index([('tipo', 1)])
            col.create_index([('praia.id', 1)])
            col.create_index([('participantes.voluntario_id', 1)])
            # Índice geoespacial 2dsphere para buscar ações próximas via coordenadas
            col.create_index([('praia.localizacao_geo', '2dsphere')])
            _indices_acoes_configurados = True
        except Exception as erro:
            logger.warning(f'Falha ao criar índices da coleção acoes no MongoDB Atlas: {erro}')
    return col


def formatar_acao_documento(acao):
    """
    Transforma a instância relacional de Ação e seus relacionamentos (Equipes,
    Participantes, Responsáveis, Fotos, Resíduos e Coordenadas) em um documento BSON rico.
    """
    # 1. Dados da Praia com GeoJSON (Point: [longitude, latitude])
    praia_info = None
    if acao.praia_id and acao.praia:
        praia_obj = acao.praia
        lat = float(praia_obj.latitude) if praia_obj.latitude is not None else 0.0
        lng = float(praia_obj.longitude) if praia_obj.longitude is not None else 0.0
        praia_info = {
            'id': praia_obj.pk,
            'id_praia': praia_obj.pk,
            'nome': praia_obj.nome,
            'cidade': praia_obj.cidade,
            'latitude': lat,
            'longitude': lng,
            'localizacao_geo': {
                'type': 'Point',
                'coordinates': [lng, lat],
            },
        }

    # 2. Equipes Vinculadas
    equipes_lista = []
    for vinculada in acao.equipes_vinculadas.select_related('equipe__praia').all():
        eq = vinculada.equipe
        equipes_lista.append({
            'id': eq.pk,
            'nome': eq.nome,
            'status': eq.status,
            'praia_nome': eq.praia.nome if eq.praia else '',
        })

    # 3. Responsáveis
    responsaveis_lista = []
    for resp in acao.responsaveis.select_related('voluntario').all():
        vol = resp.voluntario
        responsaveis_lista.append({
            'voluntario_id': vol.pk,
            'nome': vol.nome,
            'papel': resp.papel,
            'papel_display': resp.get_papel_display(),
        })

    # 4. Participantes Inscritos
    participantes_lista = []
    for part in acao.participantes.select_related('voluntario').all():
        vol = part.voluntario
        participantes_lista.append({
            'id': part.pk,
            'voluntario_id': vol.pk,
            'nome': vol.nome,
            'email': vol.email,
            'telefone': vol.telefone,
            'status': part.status,
            'status_display': part.get_status_display(),
            'compareceu': bool(part.compareceu),
            'observacao': part.observacao or '',
            'dt_confirmacao': part.dt_confirmacao.isoformat() if part.dt_confirmacao else None,
        })

    # 5. Histórico de Participantes Removidos
    historico_lista = []
    for hist in acao.historico_participantes.select_related('voluntario').filter(restaurado=False).all():
        historico_lista.append({
            'id': hist.pk,
            'voluntario_id': hist.voluntario_id,
            'nome': hist.voluntario.nome,
            'status': hist.status,
            'compareceu': hist.compareceu,
            'observacao': hist.observacao or '',
            'dt_movimentacao': hist.dt_movimentacao.isoformat() if hist.dt_movimentacao else None,
            'movido_por_nome': hist.movido_por_nome or '',
        })

    # 6. Imagens
    imagens_lista = []
    for img in acao.imagens_acao.all():
        imagens_lista.append({
            'id': img.pk,
            'url': img.imagem.url if img.imagem else '',
            'descricao': img.descricao or '',
            'dt_cadastro': img.dt_cadastro.isoformat() if img.dt_cadastro else None,
        })

    # 7. Resíduos Coletados (Consolidação com módulo de resíduo)
    residuos_lista = []
    total_kg = Decimal('0.0')
    if hasattr(acao, 'residuos_coletados'):
        for res in acao.residuos_coletados.prefetch_related('destinacoes').all():
            destinacoes_lista = []
            for dest in res.destinacoes.all():
                destinacoes_lista.append({
                    'id': dest.pk,
                    'tipo': dest.tipo,
                    'tipo_display': dest.get_tipo_display(),
                    'quantidade': float(dest.quantidade) if dest.quantidade else 0.0,
                    'unidade': dest.unidade,
                })
            qtd = float(res.quantidade) if res.quantidade else 0.0
            if res.unidade == 'KG' and res.quantidade:
                total_kg += res.quantidade
            residuos_lista.append({
                'id': res.pk,
                'tipo': res.tipo,
                'tipo_display': res.get_tipo_display(),
                'categoria': res.categoria,
                'categoria_display': res.get_categoria_display(),
                'quantidade': qtd,
                'unidade': res.unidade,
                'unidade_display': res.get_unidade_display(),
                'observacao': res.observacao or '',
                'destinacoes': destinacoes_lista,
            })

    # Datas formatadas
    data_str = acao.data.isoformat() if acao.data else None
    data_date = acao.data
    if isinstance(data_date, datetime):
        data_date = data_date.date()

    horario_str = acao.horario.strftime('%H:%M:%S') if acao.horario else None

    return {
        'id_sql': acao.pk,
        'tipo': acao.tipo,
        'tipo_display': acao.get_tipo_display(),
        'data': data_str,
        'data_evento': datetime.combine(data_date or date.today(), acao.horario or time.min) if data_date else timezone.now(),
        'horario': horario_str,
        'local': acao.local or '',
        'descricao': acao.descricao or '',
        'status': acao.status,
        'status_display': acao.get_status_display(),
        'praia': praia_info,
        'equipes': equipes_lista,
        'responsaveis': responsaveis_lista,
        'participantes': participantes_lista,
        'historico_participantes': historico_lista,
        'imagens': imagens_lista,
        'residuos_coletados': residuos_lista,
        'total_residuos_kg': float(total_kg),
        'total_participantes': len(participantes_lista),
        'cadastrado_por': {
            'id': acao.cadastrado_por_id,
            'nome': acao.cadastrado_por_nome or '',
            'tipo': acao.cadastrado_por_tipo or '',
        },
        'cadastrado_por_nome': acao.cadastrado_por_nome or '',
        'ultimo_editado_por_nome': acao.ultimo_editado_por_nome or '',
        'dt_cadastro': acao.dt_cadastro if acao.dt_cadastro else timezone.now(),
        'dt_ultima_edicao': acao.dt_ultima_edicao,
        'metadados': {
            'versao_schema': 1,
            'armazenamento': 'mongodb_atlas',
            'sincronizado_em': timezone.now().isoformat(),
        },
    }


def salvar_acao_mongo(acao):
    """
    Persiste ou atualiza (upsert) o documento completo da ação no MongoDB Atlas.
    """
    col = get_acoes_collection()
    if col is None:
        return False

    try:
        doc = formatar_acao_documento(acao)
        col.replace_one({'id_sql': acao.pk}, doc, upsert=True)
        return True
    except PyMongoError as erro:
        logger.warning(f'Erro ao salvar ação #{acao.pk} no MongoDB Atlas: {erro}')
        return False
    except Exception as erro:
        logger.error(f'Erro inesperado ao salvar ação #{acao.pk} no MongoDB Atlas: {erro}')
        return False


def remover_acao_mongo(acao_id):
    """Remove o documento da ação da coleção no MongoDB Atlas."""
    col = get_acoes_collection()
    if col is None:
        return False

    try:
        col.delete_one({'id_sql': int(acao_id)})
        return True
    except Exception as erro:
        logger.warning(f'Erro ao remover ação #{acao_id} no MongoDB Atlas: {erro}')
        return False


def consultar_acoes_mongo(filtros=None, pagina=1, por_pagina=20):
    """
    Realiza busca paginada com filtros MQL no MongoDB Atlas.
    Retorna (itens: list, total: int).
    """
    col = get_acoes_collection()
    if col is None:
        return [], 0

    filtros = filtros or {}
    query = {}

    busca = filtros.get('busca')
    if busca:
        query['$or'] = [
            {'local': {'$regex': busca, '$options': 'i'}},
            {'descricao': {'$regex': busca, '$options': 'i'}},
            {'praia.nome': {'$regex': busca, '$options': 'i'}},
            {'praia.cidade': {'$regex': busca, '$options': 'i'}},
        ]

    tipo = filtros.get('tipo')
    if tipo:
        query['tipo'] = tipo

    status = filtros.get('status')
    if status:
        query['status'] = status

    praia_id = filtros.get('praia')
    if praia_id:
        try:
            query['praia.id'] = int(praia_id)
        except (ValueError, TypeError):
            pass

    voluntario_id = filtros.get('voluntario_id')
    if voluntario_id:
        try:
            query['participantes.voluntario_id'] = int(voluntario_id)
        except (ValueError, TypeError):
            pass

    pagina = max(1, int(pagina or 1))
    por_pagina = max(1, int(por_pagina or 20))
    skip = (pagina - 1) * por_pagina

    try:
        total = col.count_documents(query)
        cursor = (
            col.find(query)
            .sort([('data', DESCENDING), ('id_sql', DESCENDING)])
            .skip(skip)
            .limit(por_pagina)
        )
        documentos = list(cursor)
        return documentos, total
    except Exception as erro:
        logger.error(f'Erro ao consultar ações no MongoDB Atlas: {erro}')
        return [], 0


def obter_acao_mongo(acao_id):
    """Obtém um único documento de ação a partir de seu id_sql."""
    col = get_acoes_collection()
    if col is None:
        return None

    try:
        return col.find_one({'id_sql': int(acao_id)})
    except Exception as erro:
        logger.warning(f'Erro ao buscar ação #{acao_id} no MongoDB Atlas: {erro}')
        return None


def buscar_acoes_proximas_mongo(latitude, longitude, raio_km=10):
    """
    Busca ações próximas a uma coordenada geográfica usando a consulta $near nativa do MongoDB.
    """
    col = get_acoes_collection()
    if col is None:
        return []

    raio_metros = raio_km * 1000
    try:
        query = {
            'praia.localizacao_geo': {
                '$near': {
                    '$geometry': {
                        'type': 'Point',
                        'coordinates': [float(longitude), float(latitude)],
                    },
                    '$maxDistance': raio_metros,
                }
            }
        }
        return list(col.find(query).limit(50))
    except Exception as erro:
        logger.warning(f'Erro na consulta geoespacial de ações no MongoDB: {erro}')
        return []


def obter_metricas_acoes_mongo():
    """
    Calcula métricas agregadas sobre ações via Aggregation Pipeline no MongoDB.
    """
    col = get_acoes_collection()
    if col is None:
        return {'total': 0, 'planejadas': 0, 'concluidas': 0, 'por_tipo': {}}

    try:
        total = col.count_documents({})
        planejadas = col.count_documents({'status': 'PLANEJADA'})
        concluidas = col.count_documents({'status': 'CONCLUIDA'})

        pipe_tipo = [{'$group': {'_id': '$tipo', 'total': {'$sum': 1}}}]
        por_tipo = {item['_id']: item['total'] for item in col.aggregate(pipe_tipo) if item['_id']}

        return {
            'total': total,
            'planejadas': planejadas,
            'concluidas': concluidas,
            'por_tipo': por_tipo,
        }
    except Exception as erro:
        logger.warning(f'Erro ao calcular métricas de ações no MongoDB: {erro}')
        return {'total': 0, 'planejadas': 0, 'concluidas': 0, 'por_tipo': {}}

