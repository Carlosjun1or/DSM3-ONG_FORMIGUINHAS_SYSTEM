from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Doador(models.Model):
    """
    Pessoa física ou jurídica que realizou uma doação.
    
    As constraints UniqueConstraint condicionais (~Q(documento='') e ~Q(email=''))
    garantem unicidade apenas quando o campo está preenchido — permitindo
    múltiplos doadores sem documento/email cadastrado, mas proibindo duplicatas
    quando o valor está presente. Isso evita erros de unique_violation para campos opcionais.
    """
    PESSOA_FISICA = 'PF'
    PESSOA_JURIDICA = 'PJ'
    TIPO_CHOICES = [
        (PESSOA_FISICA, 'Pessoa física'),
        (PESSOA_JURIDICA, 'Pessoa jurídica'),
    ]

    id_doador = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES)
    nome = models.CharField(max_length=180)
    documento = models.CharField(max_length=20, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    telefone = models.CharField(max_length=20, blank=True, default='')
    voluntario = models.OneToOneField(
        'usuario.Voluntario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='doador',
    )
    ativo = models.BooleanField(default=True)
    dt_cadastro = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='doadores_cadastrados',
    )
    cadastrado_por_nome = models.CharField(max_length=150)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='doadores_editados',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        db_table = 'doador'
        ordering = ('nome',)
        constraints = [
            models.UniqueConstraint(
                fields=('documento',),
                condition=~Q(documento=''),
                name='doador_documento_unico_nao_vazio',
            ),
            models.UniqueConstraint(
                fields=('email',),
                condition=~Q(email=''),
                name='doador_email_unico_nao_vazio',
            ),
        ]

    def clean(self):
        self.nome = self.nome.strip()
        self.documento = ''.join(char for char in self.documento if char.isalnum())
        self.email = self.email.strip().lower()
        self.telefone = self.telefone.strip()
        errors = {}
        if not self.nome:
            errors['nome'] = 'Informe o nome do doador.'
        if not self.email and not self.telefone:
            errors['email'] = 'Informe o e-mail ou o telefone do doador.'
        if self.documento and Doador.objects.filter(
            documento=self.documento,
        ).exclude(pk=self.pk).exists():
            errors['documento'] = 'Já existe um doador cadastrado com este documento.'
        if self.email and Doador.objects.filter(
            email=self.email,
        ).exclude(pk=self.pk).exists():
            errors['email'] = 'Já existe um doador cadastrado com este e-mail.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.documento = ''.join(char for char in (self.documento or '') if char.isalnum())
        self.email = (self.email or '').strip().lower()
        self.telefone = (self.telefone or '').strip()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nome



class DoacaoQuerySet(models.QuerySet):
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


class Doacao(models.Model):
    """
    Registro de doação financeira ou de material recebida pela ONG.
    
    Usa o mesmo padrão de soft-reference para acao_id (sem FK real) que os
    outros modelos. A doação pode ser anônima (anonima=True, doador=None) ou
    identificada. A finalidade ESPECIFICA exige descricao_finalidade preenchida.
    """
    objects = DoacaoQuerySet.as_manager()

    def __init__(self, *args, **kwargs):
        acao_val = kwargs.pop('acao', None)
        super().__init__(*args, **kwargs)
        if acao_val is not None:
            self.acao = acao_val

    FINANCEIRA = 'FINANCEIRA'
    MATERIAL = 'MATERIAL'
    TIPO_CHOICES = [
        (FINANCEIRA, 'Financeira'),
        (MATERIAL, 'Material'),
    ]
    PENDENTE = 'PENDENTE'
    CONFIRMADA = 'CONFIRMADA'
    CANCELADA = 'CANCELADA'
    STATUS_CHOICES = [
        (PENDENTE, 'Pendente'),
        (CONFIRMADA, 'Confirmada'),
        (CANCELADA, 'Cancelada'),
    ]
    FINALIDADE_GERAL = 'GERAL'
    FINALIDADE_ESPECIFICA = 'ESPECIFICA'
    FINALIDADE_CHOICES = [
        (FINALIDADE_GERAL, 'Manutenção geral'),
        (FINALIDADE_ESPECIFICA, 'Finalidade específica'),
    ]

    id_doacao = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES)
    doador = models.ForeignKey(
        Doador,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='doacoes',
    )
    anonima = models.BooleanField(default=False)
    data_recebimento = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDENTE)
    finalidade = models.CharField(
        max_length=12,
        choices=FINALIDADE_CHOICES,
        default=FINALIDADE_GERAL,
    )
    descricao_finalidade = models.CharField(max_length=255, blank=True, default='')
    praia = models.ForeignKey(
        'praia.Praia',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='doacoes',
    )
    acao_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_column='acao_id',
        verbose_name='Ação (ID)',
    )
    observacoes = models.TextField(blank=True, default='')
    referencia_comprovante = models.CharField(max_length=255, blank=True, default='')
    dt_cadastro = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='doacoes_registradas_doacao_app',
    )
    registrado_por_nome = models.CharField(max_length=150)
    registrado_por_tipo = models.CharField(max_length=20)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='doacoes_editadas',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, blank=True, default='')
    ultimo_editado_por_tipo = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        db_table = 'doacao'
        ordering = ('-data_recebimento', '-id_doacao')
        indexes = [
            models.Index(fields=('tipo', 'status')),
            models.Index(fields=('data_recebimento',)),
            models.Index(fields=('finalidade',)),
        ]


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

    def clean(self):
        errors = {}
        if self.anonima and self.doador_id:
            errors['doador'] = 'Doações anônimas não podem ter doador identificado.'
        elif not self.anonima and not self.doador_id:
            errors['doador'] = 'Informe o doador ou marque a doação como anônima.'
        if self.data_recebimento and self.data_recebimento > timezone.localdate():
            errors['data_recebimento'] = 'A data de recebimento não pode ser futura.'
        if self.finalidade == self.FINALIDADE_ESPECIFICA and not self.descricao_finalidade.strip():
            errors['descricao_finalidade'] = 'Descreva a finalidade específica da doação.'
        if self.acao_id and self.praia_id:
            acao_obj = self.acao
            if acao_obj and getattr(acao_obj, 'praia_id', None) and acao_obj.praia_id != self.praia_id:
                errors['praia'] = 'A praia deve ser a mesma praia da ação selecionada.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'Doação #{self.pk} - {self.get_tipo_display()}'


class DoacaoFinanceira(models.Model):
    PIX = 'PIX'
    TRANSFERENCIA = 'TRANSFERENCIA'
    DINHEIRO = 'DINHEIRO'
    OUTRA = 'OUTRA'
    FORMA_RECEBIMENTO_CHOICES = [
        (PIX, 'Pix'),
        (TRANSFERENCIA, 'Transferência bancária'),
        (DINHEIRO, 'Dinheiro'),
        (OUTRA, 'Outra'),
    ]

    id_doacao_financeira = models.AutoField(primary_key=True)
    doacao = models.OneToOneField(
        Doacao,
        on_delete=models.CASCADE,
        related_name='financeira',
    )
    valor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    forma_recebimento = models.CharField(max_length=15, choices=FORMA_RECEBIMENTO_CHOICES)

    class Meta:
        db_table = 'doacao_financeira'

    def __str__(self):
        return f'{self.valor} - {self.get_forma_recebimento_display()}'


class ItemDoacaoMaterial(models.Model):
    CONDICAO_NOVO = 'NOVO'
    CONDICAO_BOM = 'BOM'
    CONDICAO_USADO = 'USADO'
    CONDICAO_DANIFICADO = 'DANIFICADO'
    CONDICAO_NAO_INFORMADA = 'NAO_INFORMADA'
    CONDICAO_CHOICES = [
        (CONDICAO_NOVO, 'Novo'),
        (CONDICAO_BOM, 'Bom estado'),
        (CONDICAO_USADO, 'Usado'),
        (CONDICAO_DANIFICADO, 'Danificado'),
        (CONDICAO_NAO_INFORMADA, 'Não informada'),
    ]

    id_item = models.AutoField(primary_key=True)
    doacao = models.ForeignKey(
        Doacao,
        on_delete=models.CASCADE,
        related_name='itens_materiais',
    )
    material = models.ForeignKey(
        'estoque.Material',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='itens_doacao',
    )
    nome = models.CharField(max_length=150)
    categoria = models.CharField(max_length=100)
    quantidade = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    unidade = models.CharField(max_length=30)
    condicao = models.CharField(max_length=13, choices=CONDICAO_CHOICES)
    observacoes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'item_doacao_material'
        ordering = ('nome',)

    def __str__(self):
        return f'{self.nome} - {self.quantidade} {self.unidade}'
