from decimal import Decimal

from django.db import migrations


REGISTROS = [
    ('PLASTICO', 'RECICLAVEL', '18.40', 'KG', 'Garrafas e embalagens plásticas recolhidas na faixa de areia.'),
    ('PAPEL', 'RECICLAVEL', '7.25', 'KG', 'Copos, caixas e papéis encontrados próximos aos quiosques.'),
    ('VIDRO', 'RECICLAVEL', '11.00', 'KG', 'Fragmentos e garrafas de vidro recolhidos com cuidado.'),
    ('METAL', 'RECICLAVEL', '9.80', 'KG', 'Latas e tampas metálicas separadas durante a triagem.'),
    ('ORGANICO', 'ORGANICO', '24.50', 'KG', 'Restos orgânicos e folhas recolhidos na área de acesso.'),
    ('ELETRONICO', 'PERIGOSO', '3.00', 'UNIDADE', 'Pilhas e pequenos componentes eletrônicos encontrados.'),
    ('PERIGOSO', 'PERIGOSO', '2.35', 'KG', 'Material perigoso acondicionado e separado para encaminhamento.'),
    ('OUTRO', 'REJEITO', '15.60', 'KG', 'Materiais sem possibilidade de reaproveitamento identificados na coleta.'),
    ('PLASTICO', 'RECICLAVEL', '32.75', 'KG', 'Embalagens plásticas recolhidas em grande concentração.'),
    ('PAPEL', 'RECICLAVEL', '5.50', 'KG', 'Papéis úmidos e secos separados durante a limpeza.'),
    ('ORGANICO', 'ORGANICO', '12.00', 'LITRO', 'Resíduos orgânicos acondicionados em recipientes próprios.'),
    ('METAL', 'RECICLAVEL', '16.20', 'KG', 'Latas de alumínio e outros metais enviados para triagem.'),
]

DESTINACOES = [
    ('RECICLAGEM', '18.40', 'KG', 'Encaminhado para cooperativa de reciclagem.'),
    ('REUTILIZACAO', '7.25', 'KG', 'Materiais separados para reaproveitamento em oficinas.'),
    ('RECICLAGEM', '11.00', 'KG', 'Vidros separados para reciclagem especializada.'),
    ('RECICLAGEM', '9.80', 'KG', 'Metais encaminhados para triagem.'),
    ('COMPOSTAGEM', '24.50', 'KG', 'Resíduo orgânico destinado à compostagem.'),
    ('OUTRA', '3.00', 'UNIDADE', 'Encaminhado a ponto de coleta de eletrônicos.'),
    ('ATERRO', '2.35', 'KG', 'Destinação controlada para material perigoso.'),
    ('ATERRO', '15.60', 'KG', 'Descarte em local apropriado para rejeitos.'),
    ('RECICLAGEM', '32.75', 'KG', 'Encaminhado para cooperativa parceira.'),
    ('REUTILIZACAO', '5.50', 'KG', 'Separado para reutilização em ações educativas.'),
    ('COMPOSTAGEM', '12.00', 'LITRO', 'Destinado à compostagem comunitária.'),
    ('RECICLAGEM', '16.20', 'KG', 'Metais destinados à reciclagem.'),
]

OBSERVACAO_INICIAL = 'Registro demonstrativo inicial; substituir pelos dados reais da coleta.'


def variar_registros(apps, schema_editor):
    ResiduoColetado = apps.get_model('residuo', 'ResiduoColetado')
    DestinacaoResiduo = apps.get_model('residuo', 'DestinacaoResiduo')

    registros = list(
        ResiduoColetado.objects.filter(observacao=OBSERVACAO_INICIAL).order_by('acao_id')
    )
    for residuo, dados, destinacao in zip(registros, REGISTROS, DESTINACOES):
        tipo, categoria, quantidade, unidade, observacao = dados
        residuo.tipo = tipo
        residuo.categoria = categoria
        residuo.quantidade = Decimal(quantidade)
        residuo.unidade = unidade
        residuo.observacao = observacao
        residuo.save(update_fields=['tipo', 'categoria', 'quantidade', 'unidade', 'observacao'])
        DestinacaoResiduo.objects.create(
            residuo_id=residuo.pk,
            tipo=destinacao[0],
            quantidade=Decimal(destinacao[1]),
            unidade=destinacao[2],
            observacao=destinacao[3],
            registrado_por_id=residuo.registrado_por_id,
            registrado_por_nome=residuo.registrado_por_nome,
            registrado_por_tipo=residuo.registrado_por_tipo,
        )


def reverter_registros(apps, schema_editor):
    ResiduoColetado = apps.get_model('residuo', 'ResiduoColetado')
    DestinacaoResiduo = apps.get_model('residuo', 'DestinacaoResiduo')

    destinacoes = DestinacaoResiduo.objects.filter(
        observacao__in=[item[3] for item in DESTINACOES]
    )
    residuo_ids = list(destinacoes.values_list('residuo_id', flat=True))
    destinacoes.delete()
    ResiduoColetado.objects.filter(id_residuo__in=residuo_ids).update(
        tipo='OUTRO',
        categoria='OUTROS',
        quantidade=Decimal('0.01'),
        unidade='KG',
        observacao=OBSERVACAO_INICIAL,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('residuo', '0002_registros_demonstrativos'),
    ]

    operations = [
        migrations.RunPython(variar_registros, reverter_registros),
    ]
