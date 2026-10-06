from django.db import migrations


def migrar_residuos(apps, schema_editor):
    ResiduoColetado = apps.get_model('residuo', 'ResiduoColetado')
    ColetaResiduo = apps.get_model('residuo', 'ColetaResiduo')
    ItemColetaResiduo = apps.get_model('residuo', 'ItemColetaResiduo')
    DestinacaoResiduo = apps.get_model('residuo', 'DestinacaoResiduo')

    for residuo in ResiduoColetado.objects.all():
        coleta = ColetaResiduo.objects.create(
            origem='ACAO',
            acao_id=residuo.acao_id,
            data_coleta=residuo.dt_registro,
            observacao=residuo.observacao,
            registrado_por_id=residuo.registrado_por_id,
            registrado_por_nome=residuo.registrado_por_nome,
            registrado_por_tipo=residuo.registrado_por_tipo,
        )
        item = ItemColetaResiduo.objects.create(
            coleta_id=coleta.pk,
            tipo=residuo.tipo,
            categoria=residuo.categoria,
            quantidade=residuo.quantidade,
            unidade=residuo.unidade,
            observacao=residuo.observacao,
            registrado_por_id=residuo.registrado_por_id,
            registrado_por_nome=residuo.registrado_por_nome,
            registrado_por_tipo=residuo.registrado_por_tipo,
        )
        DestinacaoResiduo.objects.filter(residuo_id=residuo.pk).update(item_coleta_id=item.pk)


def reverter_migracao(apps, schema_editor):
    ColetaResiduo = apps.get_model('residuo', 'ColetaResiduo')
    ColetaResiduo.objects.filter(origem='ACAO').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('residuo', '0005_alter_destinacaoresiduo_residuo_coletaresiduo_and_more'),
    ]

    operations = [
        migrations.RunPython(migrar_residuos, reverter_migracao),
    ]
