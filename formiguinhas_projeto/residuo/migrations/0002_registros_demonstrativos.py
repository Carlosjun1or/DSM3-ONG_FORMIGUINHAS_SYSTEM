from decimal import Decimal

from django.db import migrations


def criar_registros_demonstrativos(apps, schema_editor):
    Acao = apps.get_model('acao', 'Acao')
    Usuario = apps.get_model('usuario', 'Usuario')
    ResiduoColetado = apps.get_model('residuo', 'ResiduoColetado')

    usuario = Usuario.objects.order_by('id_usuario').first()
    if not usuario:
        return
    nome = getattr(getattr(usuario, 'id_voluntario', None), 'nome', '') or 'Sistema'
    for acao in Acao.objects.all():
        ResiduoColetado.objects.get_or_create(
            acao_id=acao.pk,
            tipo='OUTRO',
            categoria='OUTROS',
            defaults={
                'quantidade': Decimal('0.01'),
                'unidade': 'KG',
                'observacao': 'Registro demonstrativo inicial; substituir pelos dados reais da coleta.',
                'registrado_por_id': usuario.pk,
                'registrado_por_nome': nome[:150],
                'registrado_por_tipo': usuario.tipo,
            },
        )


def remover_registros_demonstrativos(apps, schema_editor):
    ResiduoColetado = apps.get_model('residuo', 'ResiduoColetado')
    ResiduoColetado.objects.filter(
        observacao='Registro demonstrativo inicial; substituir pelos dados reais da coleta.'
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('residuo', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(criar_registros_demonstrativos, remover_registros_demonstrativos),
    ]
