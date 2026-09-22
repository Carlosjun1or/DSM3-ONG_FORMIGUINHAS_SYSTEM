from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Condominio(models.Model):
    PORTE_CHOICES = [
        ('PEQUENO', 'Pequeno'),
        ('MEDIO', 'Médio'),
        ('GRANDE', 'Grande'),
    ]
    CONFIABILIDADE_CHOICES = [
        ('EM_AVALIACAO', 'Em avaliação'),
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
    ]
    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('INATIVO', 'Inativo'),
        ('BLOQUEADO', 'Bloqueado'),
    ]

    id_condominio = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=150)
    responsavel_nome = models.CharField(max_length=150)
    responsavel_telefone = models.CharField(max_length=20)
    responsavel_email = models.EmailField(blank=True)
    endereco = models.CharField(max_length=255)
    numero = models.CharField(max_length=20)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2, default='SP')
    cep = models.CharField(max_length=9, blank=True)
    praia = models.ForeignKey(
        'praia.Praia',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='condominios',
    )
    porte = models.CharField(max_length=20, choices=PORTE_CHOICES, default='MEDIO')
    confiabilidade = models.CharField(
        max_length=20,
        choices=CONFIABILIDADE_CHOICES,
        default='EM_AVALIACAO',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ATIVO')
    observacoes = models.TextField(blank=True)
    dt_cadastro = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        related_name='condominios_cadastrados',
    )
    cadastrado_por_nome = models.CharField(max_length=150, blank=True)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='condominios_editados',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'condominio'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Bag(models.Model):
    STATUS_CHOICES = [
        ('DISPONIVEL', 'Disponível'),
        ('EM_USO', 'Em uso'),
        ('CHEIA', 'Cheia'),
        ('RETIRADA', 'Retirada'),
        ('EM_TRANSITO', 'Em trânsito'),
        ('ENTREGUE', 'Entregue à ONG'),
        ('DANIFICADA', 'Danificada'),
        ('PERDIDA', 'Perdida'),
    ]

    id_bag = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=40, unique=True)
    condominio = models.ForeignKey(
        Condominio,
        on_delete=models.PROTECT,
        related_name='bags',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DISPONIVEL')
    peso_atual_kg = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    percentual_ocupacao = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    observacoes = models.TextField(blank=True)
    dt_cadastro = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        related_name='bags_cadastradas',
    )
    cadastrado_por_nome = models.CharField(max_length=150, blank=True)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bags_editadas',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'bag'
        ordering = ['codigo']

    def __str__(self):
        return self.codigo


class MovimentacaoBag(models.Model):
    TIPO_CHOICES = [
        ('ENTREGA_CONDOMINIO', 'Entrega ao condomínio'),
        ('INICIO_USO', 'Início de uso'),
        ('REGISTRO_CHEIA', 'Registro de bag cheia'),
        ('RETIRADA', 'Retirada do condomínio'),
        ('ENVIO_ONG', 'Envio para a ONG'),
        ('RECEBIMENTO_ONG', 'Recebimento pela ONG'),
        ('DANO', 'Registro de dano'),
        ('PERDA', 'Registro de perda'),
        ('OUTRO', 'Outro'),
    ]

    id_movimentacao = models.AutoField(primary_key=True)
    bag = models.ForeignKey(Bag, on_delete=models.PROTECT, related_name='movimentacoes')
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    status_anterior = models.CharField(max_length=20, choices=Bag.STATUS_CHOICES)
    status_novo = models.CharField(max_length=20, choices=Bag.STATUS_CHOICES)
    data_movimentacao = models.DateTimeField(default=timezone.now)
    observacao = models.TextField(blank=True)
    registrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.PROTECT,
        related_name='movimentacoes_bag_registradas',
    )
    registrado_por_nome = models.CharField(max_length=150)
    dt_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'movimentacao_bag'
        ordering = ['-data_movimentacao', '-id_movimentacao']

    def __str__(self):
        return f'{self.bag.codigo} - {self.get_tipo_display()}'


class AuditoriaControle(models.Model):
    ENTIDADE_CHOICES = [
        ('CONDOMINIO', 'Condomínio'),
        ('BAG', 'Bag'),
        ('MOVIMENTACAO', 'Movimentação de bag'),
    ]
    ACAO_CHOICES = [
        ('CRIACAO', 'Criação'),
        ('EDICAO', 'Edição'),
        ('MUDANCA_STATUS', 'Mudança de status'),
        ('MOVIMENTACAO', 'Registro de movimentação'),
    ]

    id_auditoria = models.AutoField(primary_key=True)
    entidade = models.CharField(max_length=20, choices=ENTIDADE_CHOICES)
    id_registro = models.PositiveIntegerField()
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    usuario = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        related_name='auditorias_controle',
    )
    usuario_nome = models.CharField(max_length=150)
    data_evento = models.DateTimeField(auto_now_add=True)
    resumo = models.CharField(max_length=255)
    valores_anteriores = models.JSONField(default=dict, blank=True)
    valores_novos = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'auditoria_controle'
        ordering = ['-data_evento', '-id_auditoria']
        verbose_name = 'Auditoria do controle'
        verbose_name_plural = 'Auditorias do controle'

    def __str__(self):
        return f'{self.get_entidade_display()} - {self.get_acao_display()}'
