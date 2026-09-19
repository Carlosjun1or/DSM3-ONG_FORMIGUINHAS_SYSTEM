from django.contrib import admin
from .models import Material, Movimentacao

# Register your models here.

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo', 'unidade', 'saldo')

@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('material', 'tipo', 'quantidade', 'data')
    list_filter = ('tipo', 'data')
