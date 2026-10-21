from .models import EstadoLeituraAuditoria
from config.mongodb import test_mongo_connection
from .mongo_services import get_auditoria_collection


def notificacoes_auditoria(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id or request.session.get('usuario_tipo') != 'ADMIN':
        return {'auditoria_nao_lida_count': 0}

    estado = EstadoLeituraAuditoria.objects.filter(usuario_id=usuario_id).first()
    if estado is None:
        EstadoLeituraAuditoria.objects.get_or_create(
            usuario_id=usuario_id,
            defaults={'ultimo_evento_id': 0},
        )
        return {'auditoria_nao_lida_count': 0}

    mongo_ok, _, _ = test_mongo_connection()
    if mongo_ok:
        try:
            col = get_auditoria_collection()
            if col is not None:
                total = col.count_documents({})
                nao_lidas = max(0, total - estado.ultimo_evento_id)
                return {'auditoria_nao_lida_count': nao_lidas}
        except Exception:
            pass

    # Fallback para banco de testes se a tabela existir no SQLite
    try:
        from .models import EventoAuditoria
        total = EventoAuditoria.objects.filter(id__gt=estado.ultimo_evento_id).count()
        return {'auditoria_nao_lida_count': total}
    except Exception:
        pass

    return {'auditoria_nao_lida_count': 0}
