from datetime import datetime, time
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date
from usuario.paginacao import paginar_queryset
from usuario.models import Usuario
from usuario.views import render_acesso_bloqueado
from config.mongodb import test_mongo_connection
from .models import EstadoLeituraAuditoria, EventoAuditoria
from .mongo_services import (
    consultar_eventos_mongo,
    obter_entidades_mongo,
    obter_estatisticas_mongo,
)


class MongoEventoAdapter:
    """Adapta documentos BSON do MongoDB Atlas para a interface esperada pelos templates Django."""
    def __init__(self, doc):
        self.doc = doc
        self.id = str(doc.get('_id', ''))
        self.id_mongo = str(doc.get('_id', ''))
        self.id_registro = doc.get('id_registro') or doc.get('id_sql', '')
        self.data_evento = doc.get('data_evento')
        self.entidade = doc.get('entidade', '')
        self.acao = doc.get('acao', '')
        self.resumo = doc.get('resumo', '')
        self.usuario_nome = doc.get('usuario_nome') or (doc.get('usuario') or {}).get('nome', '')
        self.valores_anteriores = doc.get('valores_anteriores', {})
        self.valores_novos = doc.get('valores_novos', {})
        self._entidade_display = doc.get('entidade_display', '')
        self._acao_display = doc.get('acao_display', '')
        self.origem = doc.get('origem', 'MONGODB_ATLAS')

    def get_entidade_display(self):
        return self._entidade_display or self.entidade.replace('_', ' ').title()

    def get_acao_display(self):
        return self._acao_display or self.acao.replace('_', ' ').title()


def global_auditoria(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')
    usuario = Usuario.objects.filter(id_usuario=usuario_id).first()
    if not usuario:
        request.session.flush()
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    # Fonte primária exclusiva: MongoDB Atlas
    mongo_ok, mongo_msg, mongo_info = test_mongo_connection()
    mongo_stats = obter_estatisticas_mongo() if mongo_ok else {'disponivel': False, 'total': 0}

    # Atualiza notificação de leitura
    try:
        ultimo_evento_id = EventoAuditoria.objects.order_by('-id').values_list('id', flat=True).first() or 0
    except Exception:
        ultimo_evento_id = mongo_stats.get('total', 0) if mongo_ok else 0

    estado_leitura, _ = EstadoLeituraAuditoria.objects.get_or_create(
        usuario=usuario,
        defaults={'ultimo_evento_id': ultimo_evento_id},
    )
    if estado_leitura.ultimo_evento_id < ultimo_evento_id:
        estado_leitura.ultimo_evento_id = ultimo_evento_id
        estado_leitura.save(update_fields=['ultimo_evento_id'])

    entidade = request.GET.get('entidade', '').strip()
    acao = request.GET.get('acao', '').strip()
    usuario_filtro = request.GET.get('usuario', '').strip()
    inicio_str = request.GET.get('inicio', '').strip()
    fim_str = request.GET.get('fim', '').strip()
    inicio, fim = parse_date(inicio_str), parse_date(fim_str)

    filtros_mql = {
        'entidade': entidade,
        'acao': acao,
        'usuario': usuario_filtro,
        'inicio': inicio,
        'fim': fim,
    }

    if mongo_ok:
        # Consulta 100% orientada a documentos no MongoDB Atlas
        docs, total_docs = consultar_eventos_mongo(filtros_mql, pagina=1, por_pagina=1000)
        lista_adaptada = [MongoEventoAdapter(d) for d in docs]
        pagina, filtros_query = paginar_queryset(request, lista_adaptada, por_pagina=20)
        entidades_nomes = sorted(set(obter_entidades_mongo() or list(EventoAuditoria.ENTIDADE_LABELS.keys())))
        fonte = 'mongo'
    else:
        # Fallback apenas se o cluster Atlas estiver offline
        fonte = 'sql'
        try:
            eventos = EventoAuditoria.objects.select_related('usuario').order_by('-data_evento', '-id')
        except Exception:
            eventos = []
        pagina, filtros_query = paginar_queryset(request, eventos, por_pagina=20)
        entidades_nomes = list(EventoAuditoria.ENTIDADE_LABELS.keys())

    return render(request, 'sistema/auditorias.html', {
        'usuario': usuario,
        'auditorias': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'entidades': entidades_nomes,
        'entidade_selecionada': entidade,
        'acao_selecionada': acao,
        'usuario_selecionado': usuario_filtro,
        'inicio': inicio_str,
        'fim': fim_str,
        'entidade_choices': [(e, EventoAuditoria.ENTIDADE_LABELS.get(e, e.replace('_', ' ').title())) for e in entidades_nomes],
        'acao_choices': EventoAuditoria.ACAO_CHOICES,
        'usuarios_filtro': Usuario.objects.select_related('id_voluntario').order_by('id_voluntario__nome'),
        # Informações da persistência poliglota / MongoDB Atlas
        'fonte_atual': fonte,
        'mongo_conectado': mongo_ok,
        'mongo_info': mongo_info,
        'mongo_stats': mongo_stats,
    })
