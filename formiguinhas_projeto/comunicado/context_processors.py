from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, When
from django.utils import timezone

from .models import Comunicado, ComunicadoLeitura


def notificacoes_comunicados(request):
    usuario_id = request.session.get('usuario_id')
    usuario_tipo = request.session.get('usuario_tipo')
    if not usuario_id or usuario_tipo not in ('ADMIN', 'COORDENADOR'):
        return {'comunicados_nao_lidos_count': 0, 'comunicados_vigentes_count': 0}

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
