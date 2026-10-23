from django.core.paginator import Paginator


def paginar_queryset(request, queryset, por_pagina=20):
    """Pagina um queryset ou lista e preserva os filtros da URL na query string.
    
    Retorna (pagina, filtros_query) onde filtros_query é a URL-encoded dos
    parâmetros GET sem 'page', para usar nos links de próxima/anterior.
    Usado por todas as views de listagem (condominios, bags, ações, etc.).
    """
    pagina = Paginator(queryset, por_pagina).get_page(request.GET.get('page'))
    parametros = request.GET.copy()
    parametros.pop('page', None)
    return pagina, parametros.urlencode()
