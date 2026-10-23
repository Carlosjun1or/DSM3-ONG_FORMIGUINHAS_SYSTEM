"""
Serviços de persistência documental e consultas no MongoDB Atlas para o módulo de Condomínios.

Fluxo de escrita (dual-write): a view salva no SQLite via Django ORM (gera id_condominio),
depois chama salvar_condominio_mongo(condominio) que faz upsert no MongoDB usando id_sql = id_condominio.

Fluxo de leitura: consultar_condominios_mongo() é a fonte primária das telas.
Se o MongoDB estiver offline, a view faz fallback para Condominio.objects (SQLite).
"""
import logging
from django.conf import settings
from config.mongodb import get_mongo_collection

logger = logging.getLogger(__name__)

COLECAO_CONDOMINIOS = getattr(settings, 'MONGODB_CONDOMINIOS_COLECAO', 'condominios')
_indices_configurados = False


def get_condominios_collection():
    """Retorna a coleção de condomínios no MongoDB Atlas garantindo índices."""
    global _indices_configurados
    col = get_mongo_collection(COLECAO_CONDOMINIOS)
    if col is None:
        return None

    if not _indices_configurados:
        try:
            col.create_index([('id_sql', 1)], unique=True)
            col.create_index([('nome', 1)])
            col.create_index([('status', 1)])
            col.create_index([('confiabilidade', 1)])
            _indices_configurados = True
        except Exception as erro:
            logger.warning(f'Falha ao criar índices da coleção condomínios no MongoDB: {erro}')
    return col


def formatar_condominio_documento(condominio_obj):
    """
    Estrutura um documento BSON rico de Condomínio com suas Bags.
    
    O MongoDB recebe um documento 'desnormalizado': além dos campos do condomínio,
    embute a praia vinculada e todas as bags associadas. Isso permite que a tela
    de listagem faça uma única query no MongoDB em vez de joins.
    O campo id_sql guarda o ID do SQLite para sincronização (upsert por id_sql).
    """
    doc = {
        'id_sql': condominio_obj.id_condominio,
        'nome': condominio_obj.nome,
        'responsavel': {
            'nome': condominio_obj.responsavel_nome or '',
            'telefone': condominio_obj.responsavel_telefone or '',
            'email': condominio_obj.responsavel_email or '',
        },
        'endereco': {
            'logradouro': condominio_obj.endereco or '',
            'numero': condominio_obj.numero or '',
            'complemento': condominio_obj.complemento or '',
            'bairro': condominio_obj.bairro or '',
            'cidade': condominio_obj.cidade or '',
            'estado': condominio_obj.estado or '',
            'cep': condominio_obj.cep or '',
        },
        'porte': condominio_obj.porte or '',
        'porte_display': condominio_obj.get_porte_display() if hasattr(condominio_obj, 'get_porte_display') else condominio_obj.porte,
        'confiabilidade': condominio_obj.confiabilidade or '',
        'confiabilidade_display': condominio_obj.get_confiabilidade_display() if hasattr(condominio_obj, 'get_confiabilidade_display') else condominio_obj.confiabilidade,
        'status': condominio_obj.status or '',
        'status_display': condominio_obj.get_status_display() if hasattr(condominio_obj, 'get_status_display') else condominio_obj.status,
        'observacoes': condominio_obj.observacoes or '',
        'dt_cadastro': condominio_obj.dt_cadastro,
        'dt_ultima_edicao': condominio_obj.dt_ultima_edicao,
        'cadastrado_por_nome': condominio_obj.cadastrado_por_nome or '',
        'ultimo_editado_por_nome': condominio_obj.ultimo_editado_por_nome or '',
    }

    if hasattr(condominio_obj, 'praia') and getattr(condominio_obj, 'praia_id', None):
        doc['praia'] = {
            'id': condominio_obj.praia_id,
            'nome': condominio_obj.praia.nome if condominio_obj.praia else '',
            'cidade': condominio_obj.praia.cidade if condominio_obj.praia else '',
        }
    else:
        doc['praia'] = None

    # Incorpora Bags vinculadas ao condomínio
    bags_lista = []
    if hasattr(condominio_obj, 'bags'):
        for bag in condominio_obj.bags.all():
            bags_lista.append({
                'id': bag.pk,
                'codigo': bag.codigo,
                'status': bag.status,
                'status_display': bag.get_status_display(),
                'peso_atual_kg': float(bag.peso_atual_kg) if getattr(bag, 'peso_atual_kg', None) is not None else 0.0,
                'percentual_ocupacao': float(bag.percentual_ocupacao) if getattr(bag, 'percentual_ocupacao', None) is not None else 0.0,
            })
    doc['bags'] = bags_lista

    return doc


def salvar_condominio_mongo(condominio_obj):
    """Cria ou atualiza um documento de condomínio no MongoDB (upsert por id_sql)."""
    try:
        col = get_condominios_collection()
        if col is None:
            # MongoDB offline: falha silenciosa, o dado já está salvo no SQLite
            return None
        doc = formatar_condominio_documento(condominio_obj)
        col.replace_one({'id_sql': condominio_obj.id_condominio}, doc, upsert=True)
        return str(doc.get('_id'))
    except Exception as erro:
        logger.warning(f'Erro ao salvar condomínio no MongoDB: {erro}')
        return None


def salvar_condominio_por_bag(bag_obj):
    """Atualiza o condomínio correspondente no MongoDB quando uma Bag é alterada.
    
    Como as bags estão embutidas no documento do condomínio no MongoDB,
    qualquer alteração de bag exige re-escrever o documento inteiro do condomínio
    para que os dados da bag fiquem atualizados na leitura.
    """
    if bag_obj and getattr(bag_obj, 'condominio', None):
        return salvar_condominio_mongo(bag_obj.condominio)
    return None


def remover_condominio_mongo(id_sql):
    """Remove o condomínio identificado por id_sql do MongoDB."""
    try:
        col = get_condominios_collection()
        if col is not None:
            col.delete_one({'id_sql': int(id_sql)})
    except Exception as erro:
        logger.warning(f'Erro ao remover condomínio do MongoDB: {erro}')


def obter_condominio_mongo(id_sql):
    """Retorna o documento de condomínio com o id_sql solicitado."""
    try:
        col = get_condominios_collection()
        if col is not None:
            return col.find_one({'id_sql': int(id_sql)})
    except Exception as erro:
        logger.warning(f'Erro ao obter condomínio no MongoDB: {erro}')
    return None


def consultar_condominios_mongo(filtros=None, pagina=1, por_pagina=100):
    """Busca condomínios com paginação e filtros opcionais."""
    try:
        col = get_condominios_collection()
        if col is None:
            return [], 0

        filtros = filtros or {}
        query = {}

        busca = filtros.get('busca')
        if busca:
            query['$or'] = [
                {'nome': {'$regex': busca, '$options': 'i'}},
                {'endereco.logradouro': {'$regex': busca, '$options': 'i'}},
                {'endereco.bairro': {'$regex': busca, '$options': 'i'}},
                {'endereco.cidade': {'$regex': busca, '$options': 'i'}},
                {'responsavel.nome': {'$regex': busca, '$options': 'i'}},
            ]

        status = filtros.get('status')
        if status:
            query['status'] = status

        pagina = max(1, int(pagina or 1))
        por_pagina = max(1, int(por_pagina or 100))
        cursor = col.find(query).sort('nome', 1).skip((pagina - 1) * por_pagina).limit(por_pagina)
        total = col.count_documents(query)
        return list(cursor), total
    except Exception as erro:
        logger.warning(f'Erro ao consultar condomínios no MongoDB: {erro}')
        return [], 0


def obter_metricas_condominios_mongo():
    """Retorna métricas agregadas usadas nas views."""
    try:
        col = get_condominios_collection()
        if col is None:
            return {'total': 0, 'ativos': 0, 'em_avaliacao': 0}
        pipeline = [{
            '$group': {
                '_id': None,
                'total': {'$sum': 1},
                'ativos': {'$sum': {'$cond': [{'$eq': ['$status', 'ATIVO']}, 1, 0]}},
                'em_avaliacao': {'$sum': {'$cond': [{'$eq': ['$confiabilidade', 'EM_AVALIACAO']}, 1, 0]}},
            }
        }]
        result = list(col.aggregate(pipeline))
        if result:
            return result[0]
    except Exception as erro:
        logger.warning(f'Erro ao obter métricas de condomínios no MongoDB: {erro}')
    return {'total': 0, 'ativos': 0, 'em_avaliacao': 0}


def obter_bag_mongo(bag_id):
    """
    Busca os dados de uma Bag no MongoDB Atlas, pesquisando dentro da lista
    de bags embutida em cada documento de Condomínio.
    """
    try:
        col = get_condominios_collection()
        if col is None:
            return None
        doc = col.find_one(
            {'bags.id': int(bag_id)},
            {'bags.$': 1, 'nome': 1, 'id_sql': 1, 'praia': 1}
        )
        if doc and doc.get('bags'):
            bag_data = doc['bags'][0]
            bag_data['condominio_nome'] = doc.get('nome')
            bag_data['condominio_id'] = doc.get('id_sql')
            bag_data['condominio_praia'] = doc.get('praia')
            return bag_data
    except Exception as erro:
        logger.warning(f'Erro ao buscar bag #{bag_id} no MongoDB: {erro}')
    return None

