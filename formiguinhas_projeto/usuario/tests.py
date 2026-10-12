from django.test import RequestFactory, SimpleTestCase, TestCase

from .paginacao import paginar_queryset


class PaginacaoTests(SimpleTestCase):
    def test_paginacao_preserva_filtros_e_remove_pagina_anterior(self):
        request = RequestFactory().get(
            '/controle/',
            {'busca': 'Praia Central', 'status': 'ATIVA', 'page': '2'},
        )

        pagina, filtros_query = paginar_queryset(request, list(range(23)))

        self.assertEqual(pagina.number, 2)
        self.assertEqual(pagina.object_list, list(range(20, 23)))
        self.assertEqual(filtros_query, 'busca=Praia+Central&status=ATIVA')

    def test_pagina_invalida_vai_para_ultima_pagina(self):
        request = RequestFactory().get('/controle/', {'page': '999'})

        pagina, _ = paginar_queryset(request, list(range(22)))

        self.assertEqual(pagina.number, 2)
        self.assertEqual(pagina.object_list, [20, 21])

# Create your tests here.
