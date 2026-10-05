from django.db.models import Q
from django.utils import timezone

from usuario.models import Usuario

from .models import Comunicado, ComunicadoLeitura


def notificacoes_comunicados(request):
    usuario_id = request.session.get('usuario_id')
    usuario_tipo = request.session.get('usuario_tipo')
    if not usuario_id or usuario_tipo not in ('ADMIN', 'COORDENADOR'):
        return {'comunicados_vigentes_count': 0}

    try:
        usuario = Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        return {'comunicados_nao_lidos_count': 0, 'comunicados_vigentes_count': 0}

    agora = timezone.now()
    vigentes = Comunicado.objects.filter(
        status=Comunicado.PUBLICADO,
        dt_publicacao__isnull=False,
        dt_publicacao__lte=agora,
    ).filter(Q(dt_expiracao__isnull=True) | Q(dt_expiracao__gt=agora))
    if usuario.tipo != 'ADMIN':
        vigentes = vigentes.filter(
            Q(publico=Comunicado.TODOS) | Q(publico=Comunicado.COORDENADORES)
        )
    nao_lidos = vigentes.exclude(leituras__usuario=usuario)
    return {
        'comunicados_nao_lidos_count': nao_lidos.count(),
        # Kept for compatibility with existing templates.
        'comunicados_vigentes_count': vigentes.count(),
    }
