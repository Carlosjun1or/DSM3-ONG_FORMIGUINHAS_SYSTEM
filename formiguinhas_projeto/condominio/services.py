from django.forms.models import model_to_dict

from .models import Bag, Condominio, MovimentacaoBag


def _label(instance, field_name, value):
    field = instance._meta.get_field(field_name)
    choices = dict(field.choices or [])
    return choices.get(value, value)


def snapshot(instance):
    if isinstance(instance, Condominio):
        return {
            'nome': instance.nome,
            'responsavel_nome': instance.responsavel_nome,
            'responsavel_telefone': instance.responsavel_telefone,
            'responsavel_email': instance.responsavel_email,
            'endereco': instance.endereco,
            'numero': instance.numero,
            'complemento': instance.complemento,
            'bairro': instance.bairro,
            'cidade': instance.cidade,
            'estado': instance.estado,
            'cep': instance.cep,
            'praia': instance.praia.nome if instance.praia else None,
            'porte': instance.get_porte_display(),
            'confiabilidade': instance.get_confiabilidade_display(),
            'status': instance.get_status_display(),
            'observacoes': instance.observacoes,
        }
    if isinstance(instance, Bag):
        return {
            'codigo': instance.codigo,
            'condominio': instance.condominio.nome,
            'status': instance.get_status_display(),
            'peso_atual_kg': str(instance.peso_atual_kg),
            'percentual_ocupacao': instance.percentual_ocupacao,
            'observacoes': instance.observacoes,
        }
    if isinstance(instance, MovimentacaoBag):
        return {
            'bag': instance.bag.codigo,
            'tipo': instance.get_tipo_display(),
            'status_anterior': _label(instance, 'status_anterior', instance.status_anterior),
            'status_novo': _label(instance, 'status_novo', instance.status_novo),
            'data_movimentacao': instance.data_movimentacao.isoformat(),
            'observacao': instance.observacao,
        }
    return model_to_dict(instance)


def registrar_auditoria(
    *,
    entidade,
    instancia,
    acao,
    usuario,
    resumo,
    valores_anteriores=None,
    valores_novos=None,
):
    from auditoria.services import registrar_evento
    return registrar_evento(
        entidade=entidade, instancia=instancia, acao=acao, usuario=usuario,
        resumo=resumo, valores_anteriores=valores_anteriores,
        valores_novos=valores_novos or snapshot(instancia),
    )
