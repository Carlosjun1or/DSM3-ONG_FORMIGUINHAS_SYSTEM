from django.contrib import admin

from .models import Praia


@admin.register(Praia)
class PraiaAdmin(admin.ModelAdmin):
	list_display = ('nome', 'cidade', 'praia_ativa', 'cadastrado_por', 'dt_cadastro')
	list_filter = ('praia_ativa', 'cidade')
	search_fields = ('nome', 'cidade')
