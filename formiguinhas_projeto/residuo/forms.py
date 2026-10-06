from django import forms

from .models import (
    ColetaResiduo,
    DestinacaoResiduo,
    ItemColetaResiduo,
    ResiduoColetado,
)


class ColetaResiduoForm(forms.ModelForm):
    class Meta:
        model = ColetaResiduo
        fields = ['data_coleta', 'observacao']
        labels = {'data_coleta': 'Data e hora da coleta', 'observacao': 'Observação'}
        widgets = {
            'data_coleta': forms.DateTimeInput(
                format='%d/%m/%Y %H:%M',
                attrs={
                    'class': 'form-control',
                    'type': 'text',
                    'placeholder': 'dd/mm/aaaa hh:mm',
                },
            ),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descreva a coleta (opcional)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_coleta'].input_formats = ['%d/%m/%Y %H:%M', '%Y-%m-%dT%H:%M']


class ItemColetaResiduoForm(forms.ModelForm):
    class Meta:
        model = ItemColetaResiduo
        fields = ['tipo', 'categoria', 'quantidade', 'unidade', 'observacao']
        labels = {
            'tipo': 'Tipo de resíduo',
            'categoria': 'Categoria',
            'quantidade': 'Quantidade ou peso',
            'unidade': 'Unidade de medida',
            'observacao': 'Observação',
        }
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'step': '0.01',
                'placeholder': 'Ex.: 12,50',
            }),
            'unidade': forms.Select(attrs={'class': 'form-control'}),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'Detalhes deste tipo de resíduo (opcional)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
        self.fields['tipo'].choices = [('', 'Selecione o tipo'), *ResiduoColetado.TIPO_CHOICES]
        self.fields['categoria'].choices = [('', 'Selecione a categoria'), *ResiduoColetado.CATEGORIA_CHOICES]
        self.fields['unidade'].choices = [('', 'Selecione a unidade'), *ResiduoColetado.UNIDADE_CHOICES]


class ResiduoColetadoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
        self.fields['tipo'].choices = [
            ('', 'Selecione o tipo de resíduo'),
            *ResiduoColetado.TIPO_CHOICES,
        ]
        self.fields['categoria'].choices = [
            ('', 'Selecione a categoria'),
            *ResiduoColetado.CATEGORIA_CHOICES,
        ]
        self.fields['unidade'].choices = [
            ('', 'Selecione a unidade'),
            *ResiduoColetado.UNIDADE_CHOICES,
        ]

    class Meta:
        model = ResiduoColetado
        fields = ['tipo', 'categoria', 'quantidade', 'unidade', 'observacao']
        labels = {
            'tipo': 'Tipo de resíduo',
            'categoria': 'Categoria',
            'quantidade': 'Quantidade ou peso',
            'unidade': 'Unidade de medida',
            'observacao': 'Observação',
        }
        help_texts = {
            'tipo': 'Selecione o material predominante, se já souber.',
            'categoria': 'Organiza o resíduo para consultas e relatórios.',
            'quantidade': 'Você pode preencher este dado depois.',
            'unidade': 'Escolha kg, litro ou unidade quando informar uma quantidade.',
        }
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0',
                'inputmode': 'decimal', 'placeholder': 'Ex.: 12,50',
            }),
            'unidade': forms.Select(attrs={'class': 'form-control'}),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Descreva o material ou outra informação (opcional)',
            }),
        }


class DestinacaoResiduoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
        self.fields['tipo'].choices = [
            ('', 'Selecione a destinação'),
            *DestinacaoResiduo.TIPO_CHOICES,
        ]
        self.fields['unidade'].choices = [
            ('', 'Selecione a unidade'),
            *DestinacaoResiduo.UNIDADE_CHOICES,
        ]

    class Meta:
        model = DestinacaoResiduo
        fields = ['tipo', 'quantidade', 'unidade', 'observacao']
        labels = {
            'tipo': 'Tipo de destinação',
            'quantidade': 'Quantidade destinada',
            'unidade': 'Unidade de medida',
            'observacao': 'Observação',
        }
        help_texts = {
            'tipo': 'Selecione o destino dado ao material, se já estiver definido.',
            'quantidade': 'Use para registrar apenas uma parte do resíduo, se necessário.',
            'unidade': 'Informe a unidade quando preencher a quantidade destinada.',
        }
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0',
                'inputmode': 'decimal', 'placeholder': 'Ex.: 5,00',
            }),
            'unidade': forms.Select(attrs={'class': 'form-control'}),
            'observacao': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Informe detalhes do destino (opcional)',
            }),
        }

    def clean(self):
        return super().clean()
