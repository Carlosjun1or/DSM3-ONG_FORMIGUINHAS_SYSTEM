from django import forms

from .models import Doacao, Material, MovimentacaoEstoque


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
            'estoque_minimo', 'unidade', 'donativo', 'doador',
        ]
        labels = {
            'codigo': 'Código',
            'categoria': 'Categoria',
            'descricao': 'Descrição',
            'quantidade_inicial': 'Quantidade inicial',
            'estoque_minimo': 'Estoque mínimo',
            'unidade': 'Unidade de medida',
            'donativo': 'É donativo?',
        }
        error_messages = {
            'codigo': {'unique': 'Já existe um material com este código.'},
        }
        widgets = {
            'nome': forms.TextInput(attrs={'placeholder': 'Nome do material'}),
            'codigo': forms.TextInput(attrs={'placeholder': 'Ex.: MAT-0001'}),
            'categoria': forms.TextInput(attrs={
                'list': 'categorias-list',
                'autocomplete': 'off',
                'placeholder': 'Ex.: EPI, Limpeza, Papelaria',
            }),
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'quantidade_inicial': forms.NumberInput(attrs={'min': 0}),
            'estoque_minimo': forms.NumberInput(attrs={'min': 0}),
            'doador': forms.TextInput(attrs={'placeholder': 'Nome do doador'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unidade'].choices = (
            [('', 'Selecione uma opção')] + list(Material.UNIDADE_CHOICES)
        )
        if not self.instance.pk:
            self.fields['categoria'].initial = ''
        aplicar_classes(self)

    def clean(self):
        dados = super().clean()
        if not dados.get('donativo'):
            dados['doador'] = ''
        return dados


class MovimentacaoEstoqueForm(forms.ModelForm):
    """Regras de saldo, origem e justificativa ficam em MovimentacaoEstoque.clean()."""

    class Meta:
        model = MovimentacaoEstoque
        fields = ['material', 'tipo', 'quantidade', 'origem', 'justificativa']
        labels = {
            'tipo': 'Tipo de movimentação',
            'quantidade': 'Quantidade',
            'origem': 'Origem (apenas entradas)',
            'justificativa': 'Justificativa / destino',
        }
        widgets = {
            'quantidade': forms.NumberInput(attrs={'min': 1}),
            'justificativa': forms.Textarea(attrs={'rows': 3}),
        }
        error_messages = {
            'material': {
                'required': 'Selecione um item do catálogo.',
                'invalid_choice': 'Selecione um item do catálogo.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = Material.objects.order_by('nome')
        self.fields['material'].empty_label = 'Selecione um material'
        self.fields['tipo'].choices = (
            [('', 'Selecione o tipo')] + list(MovimentacaoEstoque.TIPO_CHOICES)
        )
        # Doação só pelo registro de doação.
        self.fields['origem'].choices = [('', 'Selecione a origem')] + [
            c for c in MovimentacaoEstoque.ORIGEM_CHOICES if c[0] != 'DOACAO'
        ]
        self.fields['origem'].required = False
        aplicar_classes(self)


class DoacaoForm(forms.ModelForm):
    class Meta:
        model = Doacao
        fields = ['doador', 'material', 'quantidade', 'observacao']
        labels = {'quantidade': 'Quantidade', 'observacao': 'Observação'}
        widgets = {
            'doador': forms.TextInput(attrs={'placeholder': 'Nome do doador'}),
            'quantidade': forms.NumberInput(attrs={'min': 1}),
            'observacao': forms.Textarea(attrs={'rows': 3}),
        }
        error_messages = {
            'material': {
                'required': 'Selecione um item do catálogo.',
                'invalid_choice': 'Selecione um item do catálogo.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = Material.objects.order_by('nome')
        self.fields['material'].empty_label = 'Selecione um material'
        aplicar_classes(self)
