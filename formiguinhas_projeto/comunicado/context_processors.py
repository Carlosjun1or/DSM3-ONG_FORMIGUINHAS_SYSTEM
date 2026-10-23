from django.utils import timezone
from config.mongodb import test_mongo_connection


def notificacoes_comunicados(request):
    """Context processor: conta comunicados não lidos pelo usuário logado.
    
    Fonte primária: MongoDB (campo 'leituras' embutido no documento do comunicado).
    Fallback: SQLite via ComunicadoLeitura. Injetado em todos os templates.
    """
    usuario_id = request.session.get('usuario_id')
    usuario_tipo = request.session.get('usuario_tipo')
    if not usuario_id or usuario_tipo not in ('ADMIN', 'COORDENADOR'):
        return {'comunicados_nao_lidos_count': 0, 'comunicados_vigentes_count': 0}

    # 1. Consulta prioritaria no MongoDB Atlas
    mongo_ok, _, _ = test_mongo_connection()
    if mongo_ok:
        try:
            from comunicado.mongo_services import get_comunicados_collection
            col = get_comunicados_collection()
            if col is not None:
                query = {'status': 'PUBLICADO'}
                if usuario_tipo != 'ADMIN':
                    query['publico'] = {'$in': ['TODOS', 'COORDENADORES']}
                total_vigentes = col.count_documents(query)
                query_nao_lidos = dict(query)
                query_nao_lidos['leituras.usuario_id'] = {'$ne': int(usuario_id)}
                nao_lidos = col.count_documents(query_nao_lidos)
                return {
                    'comunicados_nao_lidos_count': nao_lidos,
                    'comunicados_vigentes_count': total_vigentes,
                }
        except Exception:
            pass

    # 2. Fallback caso a tabela SQLite exista (modo de testes)
    try:
        from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, When
        from .models import Comunicado, ComunicadoLeitura

        agora = timezone.now()
        vigentes = Comunicado.objects.filter(
            status=Comunicado.PUBLICADO,
            dt_publicacao__isnull=False,
            dt_publicacao__lte=agora,
        ).filter(Q(dt_expiracao__isnull=True) | Q(dt_expiracao__gt=agora))
        if usuario_tipo != 'ADMIN':
            vigentes = vigentes.filter(
                Q(publico=Comunicado.TODOS) | Q(publico=Comunicado.COORDENADORES)
            )

        vigentes = vigentes.annotate(
            ja_lido=Exists(
                ComunicadoLeitura.objects.filter(
                    comunicado_id=OuterRef('pk'),
                    usuario_id=usuario_id,
                )
            )
        )
        totais = vigentes.aggregate(
            comunicados_vigentes_count=Count('id_comunicado'),
            comunicados_nao_lidos_count=Count(
                Case(
                    When(ja_lido=False, then=1),
                    output_field=IntegerField(),
                )
            ),
        )
        return {
            'comunicados_nao_lidos_count': totais['comunicados_nao_lidos_count'] or 0,
            'comunicados_vigentes_count': totais['comunicados_vigentes_count'] or 0,
        }
    except Exception:
        return {'comunicados_nao_lidos_count': 0, 'comunicados_vigentes_count': 0}
