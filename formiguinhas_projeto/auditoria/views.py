from datetime import datetime, time
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date
from usuario.models import Usuario
from .models import EventoAuditoria


def global_auditoria(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')
    usuario = Usuario.objects.filter(id_usuario=usuario_id).first()
    if not usuario:
        request.session.flush()
        return redirect('login')
    eventos = EventoAuditoria.objects.select_related('usuario')
    entidade = request.GET.get('entidade', '').strip()
    acao = request.GET.get('acao', '').strip()
    usuario_filtro = request.GET.get('usuario', '').strip()
    inicio, fim = parse_date(request.GET.get('inicio', '')), parse_date(request.GET.get('fim', ''))
    if entidade:
        eventos = eventos.filter(entidade=entidade)
    if acao in dict(EventoAuditoria.ACAO_CHOICES):
        eventos = eventos.filter(acao=acao)
    if usuario_filtro.isdigit():
        eventos = eventos.filter(usuario_id=usuario_filtro)
    if inicio:
        eventos = eventos.filter(data_evento__gte=datetime.combine(inicio, time.min))
    if fim:
        eventos = eventos.filter(data_evento__lte=datetime.combine(fim, time.max))
    entidades = EventoAuditoria.objects.values_list('entidade', flat=True).distinct().order_by('entidade')
    return render(request, 'sistema/auditorias.html', {
        'usuario': usuario, 'auditorias': eventos[:300],
        'entidades': entidades, 'entidade_selecionada': entidade,
        'acao_selecionada': acao, 'usuario_selecionado': usuario_filtro,
        'inicio': request.GET.get('inicio', ''), 'fim': request.GET.get('fim', ''),
        'entidade_choices': [(e, e.replace('_', ' ').title()) for e in entidades],
        'acao_choices': EventoAuditoria.ACAO_CHOICES,
        'usuarios_filtro': Usuario.objects.select_related('id_voluntario').order_by('id_voluntario__nome'),
    })
