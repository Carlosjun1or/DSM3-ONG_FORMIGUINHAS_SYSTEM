from .models import EstadoLeituraAuditoria, EventoAuditoria


def notificacoes_auditoria(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id or request.session.get('usuario_tipo') != 'ADMIN':
        return {'auditoria_nao_lida_count': 0}

    estado = EstadoLeituraAuditoria.objects.filter(usuario_id=usuario_id).first()
    if estado is None:
        ultimo_evento_id = EventoAuditoria.objects.order_by('-id').values_list('id', flat=True).first() or 0
        EstadoLeituraAuditoria.objects.get_or_create(
            usuario_id=usuario_id,
            defaults={'ultimo_evento_id': ultimo_evento_id},
        )
        return {'auditoria_nao_lida_count': 0}

    total = EventoAuditoria.objects.filter(id__gt=estado.ultimo_evento_id).count()
    return {'auditoria_nao_lida_count': total}
