from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce


class MaterialQuerySet(models.QuerySet):
    def com_saldo(self):
        """Anota `saldo_db` em uma única consulta (evita N+1)."""
        return self.annotate(
            entradas_total=Coalesce(
                Sum('movimentacoes__quantidade', filter=Q(movimentacoes__tipo='ENTRADA')), 0
            ),
            saidas_total=Coalesce(
                Sum('movimentacoes__quantidade', filter=Q(movimentacoes__tipo='SAIDA')), 0
            ),
        ).annotate(saldo_db=F('quantidade_inicial') + F('entradas_total') - F('saidas_total'))


class Material(models.Model):
    UNIDADE_CHOICES = [
        ('UNIDADE', 'Unidade'),
        ('CAIXA', 'Caixa'),
        ('PACOTE', 'Pacote'),
        ('KG', 'Kg'),
        ('LITRO', 'Litro'),
        ('METRO', 'Metro'),
    ]

    id_material = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True)
    categoria = models.CharField(max_length=50, default='Geral')
    descricao = models.TextField(blank=True)
    quantidade_inicial = models.PositiveIntegerField(default=0)
    estoque_minimo = models.PositiveIntegerField(default=0)
    unidade = models.CharField(max_length=20, choices=UNIDADE_CHOICES)
    donativo = models.BooleanField(default=False)
    doador = models.CharField(max_length=100, blank=True)
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

    def __str__(self):
        origem = 'Donativo' if self.donativo else 'Comprado'
        return f'{self.nome} ({self.codigo}) - {origem}'

    def clean(self):
        if self.nome:
            duplicado = Material.objects.filter(
                nome__iexact=self.nome.strip()
            ).exclude(pk=self.pk)
            if duplicado.exists():
                raise ValidationError({'nome': 'Este material já existe no estoque.'})

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


class Doacao(models.Model):
    """Registro de doação. Gera automaticamente a entrada correspondente."""

    id_doacao = models.AutoField(primary_key=True)
    doador = models.CharField(max_length=100)
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='doacoes')
    quantidade = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    observacao = models.TextField(blank=True)
    dt_cadastro = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='doacoes_registradas',
    )
    registrado_por_nome = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'doacao'
        ordering = ['-dt_cadastro', '-id_doacao']
        verbose_name = 'Doação'
        verbose_name_plural = 'Doações'

    def __str__(self):
        return f'{self.doador} - {self.material.nome} ({self.quantidade})'

    def save(self, *args, **kwargs):
        with transaction.atomic():
            nova = self._state.adding
            super().save(*args, **kwargs)
            if nova:
                MovimentacaoEstoque.objects.create(
                    material=self.material,
                    tipo='ENTRADA',
                    quantidade=self.quantidade,
                    origem='DOACAO',
                    doacao=self,
                    registrado_por=self.registrado_por,
                    registrado_por_nome=self.registrado_por_nome,
                    justificativa=self.observacao,
                )


class MovimentacaoEstoque(models.Model):
    TIPO_CHOICES = [('ENTRADA', 'Entrada'), ('SAIDA', 'Saída')]
    ORIGEM_CHOICES = [('DOACAO', 'Doação'), ('COMPRA', 'Compra'), ('AJUSTE', 'Ajuste')]

    id_movimentacao = models.AutoField(primary_key=True)
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name='movimentacoes'
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    quantidade = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    origem = models.CharField(max_length=10, choices=ORIGEM_CHOICES, blank=True)
    justificativa = models.TextField(blank=True)
    doacao = models.ForeignKey(
        Doacao,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movimentacoes',
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
            return f'Doação ({self.doacao.doador})'
        return self.get_origem_display() or '-'

    def _validar(self, material):
        if self.quantidade is None or self.quantidade < 1:
            raise ValidationError('A quantidade deve ser maior que zero.')
        if self.origem == 'DOACAO' and not self.doacao_id:
            raise ValidationError(
                'Entradas de doação só podem ser criadas pelo registro de doação.'
            )
        if self.doacao_id and self.origem != 'DOACAO':
            raise ValidationError("Movimentação vinculada a doação deve ter origem 'Doação'.")
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
