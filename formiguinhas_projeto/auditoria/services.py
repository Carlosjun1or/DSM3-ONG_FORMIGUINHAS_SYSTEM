"""Registro de auditoria sem expor credenciais, arquivos ou dados sensíveis."""
from datetime import date, datetime, time
from decimal import Decimal
from django.db.models.fields.files import FieldFile
from django.utils import timezone

# Campos que nunca devem aparecer no snapshot (segurança: não logar senhas/tokens)
SENSITIVE = {'senha', 'password', 'senha_hash', 'token', 'secret', 'hash'}


def snapshot(instance):
    """Captura os valores atuais da instância como dict, filtrando campos sensíveis.
    
    Regras:
    - Campos com 'senha', 'password', 'token', 'secret' no nome são omitidos.
    - FieldFile (imagens) é omitido (não faz sentido logar o caminho do arquivo).
    - Choices são resolvidas para o display label (ex: 'ATIVO' -> 'Ativo').
    - FKs são convertidas para str(instancia) (legível, não o ID cru).
    """
    result = {}
    for field in instance._meta.concrete_fields:
        name = field.name.lower()
        if name in SENSITIVE or any(part in name for part in ('senha', 'password', 'token', 'secret')):
            continue
        value = getattr(instance, field.name, None)
        if isinstance(value, FieldFile):
            continue
        if field.is_relation:
            value = str(value) if value is not None else None
        elif isinstance(value, (datetime, date, time)):
            value = value.isoformat() if value else None
        elif isinstance(value, Decimal):
            value = str(value)
        elif not isinstance(value, (str, int, float, bool, type(None))):
            value = str(value)
        choices = getattr(field, 'choices', None)
        if choices and value is not None:
            value = dict(choices).get(value, value)
        result[field.name] = value
    return result


def registrar_evento(*, entidade, instancia=None, acao, usuario=None, resumo,
                     valores_anteriores=None, valores_novos=None, id_registro=None,
                     usuario_nome=None):
    """
    Registra um evento de auditoria em duas camadas:
    1. MongoDB Atlas (primária) — falha silenciosa se offline.
    2. SQLite (fallback) — só persiste se a tabela existir (testes locais).
    
    Ambas as escritas são best-effort: se falharem, o evento é perdido mas a
    aplicação não quebra (auditoria não pode bloquear a operação principal).
    """
    nome = usuario_nome or ''
    if not nome and usuario is not None:
        nome = getattr(getattr(usuario, 'id_voluntario', None), 'nome', '') or str(usuario)

    registro_id = id_registro if id_registro is not None else getattr(instancia, 'pk', None)
    anteriores = valores_anteriores or {}
    novos = valores_novos if valores_novos is not None else (snapshot(instancia) if instancia else {})
    momento = timezone.now()

    # 1. Persistência Primária no MongoDB Atlas (NoSQL)
    try:
        from .mongo_services import registrar_evento_mongo
        registrar_evento_mongo(
            entidade=entidade,
            id_registro=registro_id,
            acao=acao,
            usuario=usuario,
            usuario_nome=nome,
            resumo=resumo,
            valores_anteriores=anteriores,
            valores_novos=novos,
            data_evento=momento,
            origem='SISTEMA_WEB',
        )
    except Exception:
        pass

    # 2. Tolerância para testes locais se a tabela ainda existir em banco temporário de teste
    try:
        from .models import EventoAuditoria
        EventoAuditoria.objects.create(
            entidade=entidade,
            id_registro=registro_id,
            acao=acao,
            usuario=usuario,
            usuario_nome=nome[:150],
            resumo=resumo[:255],
            valores_anteriores=anteriores,
            valores_novos=novos,
        )
    except Exception:
        # Tabela removida do SQLite em produção/desenvolvimento
        pass

    return None
