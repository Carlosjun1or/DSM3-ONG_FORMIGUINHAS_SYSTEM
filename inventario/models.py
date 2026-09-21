from django.db import models
from django.contrib.auth.models import User  # IMPORTANTE: Necessário para o campo de usuário funcionar

# 4.1 Cadastro de Materiais
class Material(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome")
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    quantidade_inicial = models.IntegerField(default=0, verbose_name="Quantidade inicial")
    unidade = models.CharField(max_length=20, verbose_name="Unidade")

    def __str__(self):
        return f"{self.nome} ({self.codigo})"

    @property
    def saldo(self):
        entradas = sum(m.quantidade for m in self.movimentacao_set.filter(tipo='entrada'))
        saidas = sum(m.quantidade for m in self.movimentacao_set.filter(tipo='saida'))
        return self.quantidade_inicial + entradas - saidas

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materiais"


# 4.2 Movimentação de Estoque
class Movimentacao(models.Model):
    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        verbose_name="Material"
    )
    tipo = models.CharField(
        max_length=10,
        choices=[('entrada', 'Entrada'), ('saida', 'Saída')],
        verbose_name="Tipo de movimentação"
    )
    quantidade = models.IntegerField(verbose_name="Quantidade")
    data = models.DateTimeField(auto_now_add=True, verbose_name="Data")
    
    # Movido para dentro da classe e perfeitamente alinhado:
    usuario = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Administrador"
    )

    def __str__(self):
        return f"{self.tipo} - {self.material.nome} ({self.quantidade})"

    class Meta:
        verbose_name = "Movimentação"
        verbose_name_plural = "Movimentações"
