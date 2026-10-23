

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class SoftRefQuerySet(models.QuerySet):
    """
    QuerySet customizado que aceita instâncias de objeto ou IDs crus como filtros.

    Por que existe: acao_id e bag_id são PositiveIntegerField (não FKs reais) para
    evitar constraint FK no banco — os modelos Acao e Bag têm managed=False ou
    são lidos do MongoDB. Sem FK real, o ORM não aceita filter(acao=instance);
    este QuerySet intercepta e converte para filter(acao_id=instance.pk).
    """

    def filter(self, *args, **kwargs):
        if 'acao' in kwargs:
            val = kwargs.pop('acao')
            kwargs['acao_id'] = val.pk if hasattr(val, 'pk') else val
        if 'bag' in kwargs:
            val = kwargs.pop('bag')
            kwargs['bag_id'] = val.pk if hasattr(val, 'pk') else val
        return super().filter(*args, **kwargs)

    def get(self, *args, **kwargs):
        if 'acao' in kwargs:
            val = kwargs.pop('acao')
            kwargs['acao_id'] = val.pk if hasattr(val, 'pk') else val
        if 'bag' in kwargs:
            val = kwargs.pop('bag')
            kwargs['bag_id'] = val.pk if hasattr(val, 'pk') else val
        return super().get(*args, **kwargs)


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
    """
    Coleta de resíduos vinculada a uma Ação ou a uma Bag de condomínio.

    Usa acao_id e bag_id como campos inteiros simples (sem FK real) para
    evitar constraint com tabelas managed=False. As properties acao e bag
    resolvem o objeto correspondente consultando primeiro o MongoDB, depois
    o SQLite como fallback. O SoftRefQuerySet permite usar filter(acao=obj).
    """
    objects = SoftRefQuerySet.as_manager()

    def __init__(self, *args, **kwargs):
        acao_val = kwargs.pop('acao', None)
        bag_val = kwargs.pop('bag', None)
        super().__init__(*args, **kwargs)
        if acao_val is not None:
            self.acao = acao_val
        if bag_val is not None:
            self.bag = bag_val

    ORIGEM_CHOICES = [
        ('ACAO', 'Ação'),
        ('BAG', 'Bag'),
    ]

    id_coleta = models.AutoField(primary_key=True)
    origem = models.CharField(max_length=10, choices=ORIGEM_CHOICES)
    acao_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_column='acao_id',
        verbose_name='Ação (ID)',
    )
    bag_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_column='bag_id',
        verbose_name='Bag (ID)',
    )

    @property
    def acao(self):
        """Resolve a Ação: tenta MongoDB primeiro, SQLite como fallback, proxy mínimo se tudo falhar."""
        if not self.acao_id:
            return None
        from config.mongodb import MongoAcaoProxy
        try:
            from acao.mongo_services import obter_acao_mongo
            doc = obter_acao_mongo(self.acao_id)
            if doc:
                return MongoAcaoProxy(doc)
        except Exception:
            pass
        try:
            from acao.models import Acao
            return Acao.objects.filter(pk=self.acao_id).first()
        except Exception:
            return MongoAcaoProxy({'id_sql': self.acao_id, 'tipo': f'Ação #{self.acao_id}'})

    @acao.setter
    def acao(self, value):
        if value is None:
            self.acao_id = None
        elif isinstance(value, int):
            self.acao_id = value
        elif hasattr(value, 'pk'):
            self.acao_id = value.pk
        elif isinstance(value, dict):
            self.acao_id = value.get('id_sql') or value.get('id') or value.get('id_acao')
        else:
            try:
                self.acao_id = int(value)
            except (ValueError, TypeError):
                self.acao_id = None

    @property
    def bag(self):
        """Resolve a Bag: tenta MongoDB primeiro, SQLite como fallback, proxy mínimo se tudo falhar."""
        if not self.bag_id:
            return None
        from config.mongodb import MongoBagProxy
        try:
            from condominio.mongo_services import obter_bag_mongo
            doc = obter_bag_mongo(self.bag_id)
            if doc:
                return MongoBagProxy(doc)
        except Exception:
            pass
        try:
            from condominio.models import Bag
            return Bag.objects.filter(pk=self.bag_id).first()
        except Exception:
            return MongoBagProxy({'id': self.bag_id, 'codigo': f'#{self.bag_id}'})

    @bag.setter
    def bag(self, value):
        if value is None:
            self.bag_id = None
        elif isinstance(value, int):
            self.bag_id = value
        elif hasattr(value, 'pk'):
            self.bag_id = value.pk
        elif isinstance(value, dict):
            self.bag_id = value.get('id') or value.get('id_bag')
        else:
            try:
                self.bag_id = int(value)
            except (ValueError, TypeError):
                self.bag_id = None

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
    """Resíduo registrado diretamente em uma Ação (não via bag). Mesma lógica de
    soft-reference: acao_id é inteiro sem FK real, resolvido via property."""
    objects = SoftRefQuerySet.as_manager()

    def __init__(self, *args, **kwargs):
        acao_val = kwargs.pop('acao', None)
        super().__init__(*args, **kwargs)
        if acao_val is not None:
            self.acao = acao_val

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
    acao_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_column='acao_id',
        verbose_name='Ação (ID)',
    )

    @property
    def acao(self):
        """Resolve a Ação: tenta MongoDB primeiro, SQLite como fallback, proxy mínimo se tudo falhar."""
        if not self.acao_id:
            return None
        from config.mongodb import MongoAcaoProxy
        try:
            from acao.mongo_services import obter_acao_mongo
            doc = obter_acao_mongo(self.acao_id)
            if doc:
                return MongoAcaoProxy(doc)
        except Exception:
            pass
        try:
            from acao.models import Acao
            return Acao.objects.filter(pk=self.acao_id).first()
        except Exception:
            return MongoAcaoProxy({'id_sql': self.acao_id, 'tipo': f'Ação #{self.acao_id}'})

    @acao.setter
    def acao(self, value):
        if value is None:
            self.acao_id = None
        elif isinstance(value, int):
            self.acao_id = value
        elif hasattr(value, 'pk'):
            self.acao_id = value.pk
        elif isinstance(value, dict):
            self.acao_id = value.get('id_sql') or value.get('id') or value.get('id_acao')
        else:
            try:
                self.acao_id = int(value)
            except (ValueError, TypeError):
                self.acao_id = None

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
    """Destinação final de um resíduo coletado (reciclagem, compostagem, aterro, etc.)
    Pode estar vinculada a um ResiduoColetado (de ação) ou ItemColetaResiduo (de bag)."""
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
