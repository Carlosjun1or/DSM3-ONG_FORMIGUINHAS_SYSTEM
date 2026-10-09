from django.contrib import admin

from .models import Doador, Doacao, DoacaoFinanceira, ItemDoacaoMaterial


admin.site.register([Doador, Doacao, DoacaoFinanceira, ItemDoacaoMaterial])
