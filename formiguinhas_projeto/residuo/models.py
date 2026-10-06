from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

TIPO_RESIDUO_CHOICES = [
    ('PLASTICO', 'Plástico'), ('PAPEL', 'Papel'), ('VIDRO', 'Vidro'),
    ('METAL', 'Metal'), ('ORGANICO', 'Orgânico'), ('ELETRONICO', 'Eletrônico'),
    ('PERIGOSO', 'Perigoso'), ('OUTRO', 'Outro'),
]
CATEGORIA_RESIDUO_CHOICES = [
    ('RECICLAVEL', 'Reciclável'), ('ORGANICO', 'Orgânico'),
    ('REJEITO', 'Rejeito'), ('PERIGOSO', 'Perigoso'), ('OUTROS', 'Outros'),
]
UNIDADE_RESIDUO_CHOICES = [
    ('KG', 'Quilograma (kg)'), ('LITRO', 'Litro (L)'), ('UNIDADE', 'Unidade'),
]


class ColetaResiduo(models.Model):
    ORIGEM_CHOICES = [
        ('ACAO', 'Ação'),
        ('BAG', 'Bag'),
    ]

    id_coleta = models.AutoField(primary_key=True)
    origem = models.CharField(max_length=10, choices=ORIGEM_CHOICES)
    acao = models.ForeignKey(
        'acao.Acao',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='coletas_residuos',
    )
    bag = models.ForeignKey(
        'condominio.Bag',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='coletas_residuos',
    )
    data_coleta = models.DateTimeField(default=timezone.now)
    observacao = models.TextField(blank=True, default='')
    registrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.PROTECT,
        related_name='coletas_residuos_registradas',
    )
    registrado_por_nome = models.CharField(max_length=150)
    registrado_por_tipo = models.CharField(max_length=20)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coletas_residuos_editadas',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, blank=True, default='')
    ultimo_editado_por_tipo = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        db_table = 'coleta_residuo'
        ordering = ('-data_coleta', '-id_coleta')

    def __str__(self):
        if self.origem == 'BAG' and self.bag_id:
            return f'Coleta #{self.pk} - {self.bag}'
        return f'Coleta #{self.pk} - ação {self.acao_id}'


class ItemColetaResiduo(models.Model):
    id_item = models.AutoField(primary_key=True)
    coleta = models.ForeignKey(ColetaResiduo, on_delete=models.CASCADE, related_name='itens')
    tipo = models.CharField(max_length=20, choices=TIPO_RESIDUO_CHOICES, blank=True, default='')
    categoria = models.CharField(max_length=20, choices=CATEGORIA_RESIDUO_CHOICES, blank=True, default='')
    quantidade = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unidade = models.CharField(max_length=10, choices=UNIDADE_RESIDUO_CHOICES, blank=True, default='')
    observacao = models.TextField(blank=True, default='')
    registrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.PROTECT,
        related_name='itens_coleta_residuos_registrados',
    )
    registrado_por_nome = models.CharField(max_length=150)
    registrado_por_tipo = models.CharField(max_length=20)
    dt_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'item_coleta_residuo'
        ordering = ('id_item',)


class ResiduoColetado(models.Model):
    TIPO_CHOICES = [
        ('PLASTICO', 'Plástico'),
        ('PAPEL', 'Papel'),
        ('VIDRO', 'Vidro'),
        ('METAL', 'Metal'),
        ('ORGANICO', 'Orgânico'),
        ('ELETRONICO', 'Eletrônico'),
        ('PERIGOSO', 'Perigoso'),
        ('OUTRO', 'Outro'),
    ]
    CATEGORIA_CHOICES = [
        ('RECICLAVEL', 'Reciclável'),
        ('ORGANICO', 'Orgânico'),
        ('REJEITO', 'Rejeito'),
        ('PERIGOSO', 'Perigoso'),
        ('OUTROS', 'Outros'),
    ]
    UNIDADE_CHOICES = [
        ('KG', 'Quilograma (kg)'),
        ('LITRO', 'Litro (L)'),
        ('UNIDADE', 'Unidade'),
    ]

    id_residuo = models.AutoField(primary_key=True)
    acao = models.ForeignKey(
        'acao.Acao',
        on_delete=models.CASCADE,
        related_name='residuos_coletados',
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, blank=True, default='')
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, blank=True, default='')
    quantidade = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        null=True,
        blank=True,
    )
    unidade = models.CharField(max_length=10, choices=UNIDADE_CHOICES, blank=True, default='')
    observacao = models.TextField(blank=True, default='')
    dt_registro = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.PROTECT,
        related_name='residuos_registrados',
    )
    registrado_por_nome = models.CharField(max_length=150)
    registrado_por_tipo = models.CharField(max_length=20)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='residuos_editados',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, blank=True, default='')
    ultimo_editado_por_tipo = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        db_table = 'residuo_coletado'
        ordering = ('-dt_registro', '-id_residuo')

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.quantidade} {self.get_unidade_display()}'


class DestinacaoResiduo(models.Model):
    TIPO_CHOICES = [
        ('RECICLAGEM', 'Reciclagem'),
        ('REUTILIZACAO', 'Reutilização'),
        ('COMPOSTAGEM', 'Compostagem'),
        ('ATERRO', 'Aterro/Descarte'),
        ('DOACAO', 'Doação'),
        ('OUTRA', 'Outra'),
    ]
    UNIDADE_CHOICES = ResiduoColetado.UNIDADE_CHOICES

    id_destinacao = models.AutoField(primary_key=True)
    residuo = models.ForeignKey(
        ResiduoColetado,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='destinacoes',
    )
    item_coleta = models.ForeignKey(
        ItemColetaResiduo,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='destinacoes',
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, blank=True, default='')
    quantidade = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        null=True,
        blank=True,
    )
    unidade = models.CharField(max_length=10, choices=UNIDADE_CHOICES, blank=True, default='')
    observacao = models.TextField(blank=True, default='')
    dt_registro = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.PROTECT,
        related_name='destinacoes_residuo_registradas',
    )
    registrado_por_nome = models.CharField(max_length=150)
    registrado_por_tipo = models.CharField(max_length=20)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='destinacoes_residuo_editadas',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, blank=True, default='')
    ultimo_editado_por_tipo = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        db_table = 'destinacao_residuo'
        ordering = ('-dt_registro', '-id_destinacao')

    def __str__(self):
        return f'{self.residuo} - {self.get_tipo_display()}'
