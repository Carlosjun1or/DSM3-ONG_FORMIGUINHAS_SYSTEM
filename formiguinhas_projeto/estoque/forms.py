from django import forms

from .models import Material, MovimentacaoEstoque


class MaterialChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.nome} — saldo: {obj.saldo} {obj.get_unidade_display()}'


class MaterialCategoriaSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        material_id = str(getattr(value, 'value', value))
        categoria = getattr(self, 'categorias_por_material', {}).get(material_id)
        nome = getattr(self, 'nomes_por_material', {}).get(material_id)
        unidade = getattr(self, 'unidades_por_material', {}).get(material_id)
        if categoria:
            option['attrs']['data-categoria'] = categoria
        if nome:
            option['attrs']['data-nome'] = nome
        if unidade:
            option['attrs']['data-unidade'] = unidade
        return option


def aplicar_classes(form):
    """Padrão visual do sistema: form-control (e select-control nas listas)."""
    for field in form.fields.values():
        if isinstance(field.widget, forms.CheckboxInput):
            continue
        classes = field.widget.attrs.get('class', '').split()
        if isinstance(field.widget, forms.Select) and 'select-control' not in classes:
            classes.append('select-control')
        if 'form-control' not in classes:
            classes.append('form-control')
        field.widget.attrs['class'] = ' '.join(classes)


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = [
            'nome', 'codigo', 'categoria', 'descricao', 'quantidade_inicial',
            'estoque_minimo', 'unidade',
        ]
        labels = {
            'codigo': 'Código',
            'categoria': 'Categoria',
            'descricao': 'Descrição',
            'quantidade_inicial': 'Quantidade inicial',
            'estoque_minimo': 'Estoque mínimo',
            'unidade': 'Unidade de medida',
        }
        error_messages = {
            'codigo': {'unique': 'Já existe um material com este código.'},
        }
        widgets = {
            'nome': forms.TextInput(attrs={
                'placeholder': 'Ex.: Luvas de proteção tamanho M',
                'autofocus': True,
                'autocomplete': 'off',
                'aria-autocomplete': 'list',
                'aria-expanded': 'false',
                'aria-controls': 'materiais-nome-resultados',
            }),
            'codigo': forms.TextInput(attrs={'placeholder': 'Ex.: MAT-0001'}),
            'categoria': forms.TextInput(attrs={
                'placeholder': 'Digite ou escolha uma categoria',
                'autocomplete': 'off',
                'role': 'combobox',
                'aria-autocomplete': 'list',
                'aria-expanded': 'false',
                'aria-controls': 'lista-categorias-material',
                'aria-haspopup': 'listbox',
            }),
            'descricao': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Detalhes para identificar ou orientar o uso do material (opcional)',
            }),
            'quantidade_inicial': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'Ex.: 20',
                'inputmode': 'numeric',
            }),
            'estoque_minimo': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'Ex.: 5',
                'inputmode': 'numeric',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unidade'].choices = (
            [('', 'Selecione uma opção')] + list(Material.UNIDADE_CHOICES)
        )
        categorias_existentes = (
            Material.objects.order_by('categoria')
            .values_list('categoria', flat=True)
            .distinct()
        )
        self.categorias = []
        categorias_vistas = set()
        for categoria in categorias_existentes:
            normalizada = ' '.join(categoria.split())
            chave = normalizada.casefold()
            if chave and chave not in categorias_vistas:
                categorias_vistas.add(chave)
                self.categorias.append(normalizada)
        aplicar_classes(self)

    def clean(self):
        dados = super().clean()
        categoria = ' '.join((dados.get('categoria') or '').split())
        if categoria:
            categoria_existente = next(
                (
                    existente for existente in self.categorias
                    if existente.casefold() == categoria.casefold()
                ),
                None,
            )
            if categoria_existente:
                categoria = categoria_existente
        dados['categoria'] = categoria
        return dados


class MovimentacaoEstoqueForm(forms.ModelForm):
    """Regras de saldo, origem e justificativa ficam em MovimentacaoEstoque.clean()."""

    material = MaterialChoiceField(
        queryset=Material.objects.none(),
        error_messages={
            'required': 'Selecione um item do catálogo.',
            'invalid_choice': 'Selecione um item do catálogo.',
        },
    )

    class Meta:
        model = MovimentacaoEstoque
        fields = ['material', 'tipo', 'quantidade', 'origem', 'justificativa']
        labels = {
            'material': 'Material',
            'tipo': 'Tipo de movimentação',
            'quantidade': 'Quantidade',
            'origem': 'Origem (apenas entradas)',
            'justificativa': 'Justificativa / destino',
        }
        widgets = {
            'quantidade': forms.NumberInput(attrs={
                'min': 1,
                'placeholder': 'Ex.: 10',
                'inputmode': 'numeric',
            }),
            'justificativa': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Ex.: Entrega de 10 unidades para o mutirão de limpeza',
            }),
        }
        error_messages = {
            'material': {
                'required': 'Selecione um item do catálogo.',
                'invalid_choice': 'Selecione um item do catálogo.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = Material.objects.com_saldo().order_by('nome')
        self.fields['material'].empty_label = 'Selecione um material'
        self.fields['material'].help_text = 'O saldo atual aparece ao lado de cada material.'
        self.fields['tipo'].choices = (
            [('', 'Selecione o tipo')] + list(MovimentacaoEstoque.TIPO_CHOICES)
        )
        self.fields['tipo'].help_text = 'Escolha entrada para reposição ou saída para consumo/uso.'
        # Doação só pelo registro de doação.
        self.fields['origem'].choices = [('', 'Selecione a origem')] + [
            c for c in MovimentacaoEstoque.ORIGEM_CHOICES if c[0] != 'DOACAO'
        ]
        self.fields['origem'].required = False
        self.fields['origem'].help_text = 'Obrigatória para entradas; saídas não precisam de origem.'
        self.fields['quantidade'].help_text = 'Informe um número inteiro maior que zero.'
        self.fields['justificativa'].help_text = (
            'Descreva o motivo ou destino, especialmente para registrar uma saída.'
        )
        aplicar_classes(self)
