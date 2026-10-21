from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Exists, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce, Lower, Trim


class MaterialQuerySet(models.QuerySet):
    def com_saldo(self):
        """Anota `saldo_db` em uma única consulta (evita N+1)."""
        movimentacoes_doacao = MovimentacaoEstoque.objects.filter(
            material_id=OuterRef('pk'),
            doacao__isnull=False,
        )
        return self.annotate(
            entradas_total=Coalesce(
                Sum('movimentacoes__quantidade', filter=Q(movimentacoes__tipo='ENTRADA')), 0
            ),
            saidas_total=Coalesce(
                Sum('movimentacoes__quantidade', filter=Q(movimentacoes__tipo='SAIDA')), 0
            ),
        ).annotate(
            saldo_db=F('quantidade_inicial') + F('entradas_total') - F('saidas_total'),
            eh_donativo_db=Exists(movimentacoes_doacao),
            doador_origem_db=Subquery(
                movimentacoes_doacao.order_by('-dt_cadastro', '-pk')
                .values('doacao__doador__nome')[:1]
            ),
        )


class Material(models.Model):
    UNIDADE_CHOICES = [
        ('UNIDADE', 'Unidade'),
        ('CAIXA', 'Caixa'),
        ('PACOTE', 'Pacote'),
        ('KG', 'Kg'),
        ('LITRO', 'Litro'),
    ]

    id_material = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True)
    categoria = models.CharField(max_length=50, default='Geral')
    descricao = models.TextField(blank=True)
    quantidade_inicial = models.PositiveIntegerField(default=0)
    estoque_minimo = models.PositiveIntegerField(default=0)
    unidade = models.CharField(max_length=20, choices=UNIDADE_CHOICES)
    dt_cadastro = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='materiais_cadastrados',
    )
    cadastrado_por_nome = models.CharField(max_length=150, blank=True)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='materiais_editados',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, blank=True)

    objects = MaterialQuerySet.as_manager()

    class Meta:
        db_table = 'material'
        ordering = ['nome']
        verbose_name = 'Material'
        verbose_name_plural = 'Materiais'
        constraints = [
            models.UniqueConstraint(
                Lower(Trim('nome')),
                name='material_nome_normalizado_unico',
            ),
        ]

    @property
    def eh_donativo(self):
        """Um material é doado quando pelo menos uma movimentação registrada parte de uma doação."""
        if hasattr(self, 'eh_donativo_db'):
            return self.eh_donativo_db
        return self.movimentacoes.filter(doacao__isnull=False).exists()

    @property
    def doador_origem(self):
        """Retorna o doador mais recente da origem da doação do material."""
        if hasattr(self, 'doador_origem_db'):
            return self.doador_origem_db or ''
        movimentacao = self.movimentacoes.select_related('doacao__doador').filter(
            doacao__isnull=False,
        ).order_by('-dt_cadastro').first()
        if movimentacao and movimentacao.doacao and movimentacao.doacao.doador_id:
            return movimentacao.doacao.doador.nome
        return ''

    def __str__(self):
        origem = 'Donativo' if self.eh_donativo else 'Comprado'
        return f'{self.nome} ({self.codigo}) - {origem}'

    def clean(self):
        if self.nome:
            nome_normalizado = self.nome.strip().casefold()
            duplicados = Material.objects.exclude(pk=self.pk).only('pk', 'nome')
            if any(
                material.nome.strip().casefold() == nome_normalizado
                for material in duplicados
            ):
                raise ValidationError({'nome': 'Este material já existe no estoque.'})

        if self.categoria:
            self.categoria = self.categoria.strip()

    def calcular_saldo(self, excluir_movimentacao_pk=None):
        movimentacoes = self.movimentacoes.all()
        if excluir_movimentacao_pk:
            movimentacoes = movimentacoes.exclude(pk=excluir_movimentacao_pk)
        total = movimentacoes.aggregate(
            entradas=Sum('quantidade', filter=Q(tipo='ENTRADA')),
            saidas=Sum('quantidade', filter=Q(tipo='SAIDA')),
        )
        return self.quantidade_inicial + (total['entradas'] or 0) - (total['saidas'] or 0)

    @property
    def saldo(self):
        if hasattr(self, 'saldo_db'):
            return self.saldo_db
        return self.calcular_saldo()

    @property
    def sem_estoque(self):
        return self.saldo <= 0

    @property
    def baixo_estoque(self):
        return self.saldo <= 0 or self.saldo < self.estoque_minimo



class MovimentacaoEstoqueQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        if 'acao' in kwargs:
            val = kwargs.pop('acao')
            kwargs['acao_id'] = val.pk if hasattr(val, 'pk') else val
        return super().filter(*args, **kwargs)

    def get(self, *args, **kwargs):
        if 'acao' in kwargs:
            val = kwargs.pop('acao')
            kwargs['acao_id'] = val.pk if hasattr(val, 'pk') else val
        return super().get(*args, **kwargs)


class MovimentacaoEstoque(models.Model):
    objects = MovimentacaoEstoqueQuerySet.as_manager()

    def __init__(self, *args, **kwargs):
        acao_val = kwargs.pop('acao', None)
        super().__init__(*args, **kwargs)
        if acao_val is not None:
            self.acao = acao_val

    TIPO_CHOICES = [('ENTRADA', 'Entrada'), ('SAIDA', 'Saída')]
    ORIGEM_CHOICES = [('DOACAO', 'Doação'), ('COMPRA', 'Compra'), ('AJUSTE', 'Ajuste')]

    id_movimentacao = models.AutoField(primary_key=True)
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name='movimentacoes'
    )
    acao_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_column='acao_id',
        verbose_name='Ação (ID)',
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    quantidade = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    origem = models.CharField(max_length=10, choices=ORIGEM_CHOICES, blank=True)
    justificativa = models.TextField(blank=True)
    doacao = models.ForeignKey(
        'doacao.Doacao',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movimentacoes_estoque',
    )
    item_doacao = models.OneToOneField(
        'doacao.ItemDoacaoMaterial',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movimentacao_estoque',
    )
    dt_cadastro = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes_estoque_registradas',
    )
    registrado_por_nome = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'movimentacao_estoque'
        ordering = ['-dt_cadastro', '-id_movimentacao']
        verbose_name = 'Movimentação de estoque'
        verbose_name_plural = 'Movimentações de estoque'

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.material.nome} ({self.quantidade})'

    @property
    def origem_detalhada(self):
        if self.origem == 'DOACAO' and self.doacao_id:
            doador = self.doacao.doador.nome if self.doacao.doador_id else 'Anônima'
            return f'Doação ({doador})'
        return self.get_origem_display() or '-'


    @property
    def acao(self):
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

    def _validar(self, material):
        if self.quantidade is None or self.quantidade < 1:
            raise ValidationError('A quantidade deve ser maior que zero.')
        if self.acao_id and self.tipo != 'SAIDA':
            raise ValidationError('Uma ação só pode ser vinculada a uma saída de estoque.')
        if self.origem == 'DOACAO' and not self.doacao_id:
            raise ValidationError(
                'Entradas de doação só podem ser criadas pelo registro de doação.'
            )
        if self.doacao_id and self.origem != 'DOACAO':
            raise ValidationError("Movimentação vinculada a doação deve ter origem 'Doação'.")
        if self.item_doacao_id and (
            self.item_doacao.doacao_id != self.doacao_id
            or self.item_doacao.material_id != self.material_id
        ):
            raise ValidationError(
                'O item movimentado deve pertencer à doação e ao material vinculados.'
            )
        if self.item_doacao_id and self.tipo != 'ENTRADA':
            raise ValidationError('Itens de doação só podem gerar entradas no estoque.')
        if self.tipo == 'SAIDA':
            saldo = material.calcular_saldo(excluir_movimentacao_pk=self.pk)
            if self.quantidade > saldo:
                raise ValidationError('Movimentação inválida: saldo insuficiente.')

    def clean(self):
        if not (self.material_id and self.tipo and self.quantidade is not None):
            return
        if self.tipo == 'SAIDA':
            self.origem = ''
            if not self.justificativa.strip():
                raise ValidationError('Informe a justificativa/destino da saída.')
        elif self._state.adding and not self.origem:
            raise ValidationError('Informe a origem da entrada (compra ou ajuste).')
        self._validar(self.material)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            material = Material.objects.select_for_update().get(pk=self.material_id)
            self._validar(material)
            super().save(*args, **kwargs)
