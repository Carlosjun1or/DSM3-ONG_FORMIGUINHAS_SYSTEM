from django import forms

from .models import Praia


class PraiaForm(forms.ModelForm):
    class Meta:
        model = Praia
        fields = [
            'nome',
            'cidade',
            'latitude',
            'longitude',
            'praia_ativa',
            'descricao',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da praia',
            }),
            'cidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cidade',
            }),
            'latitude': forms.HiddenInput(attrs={
                'id': 'id_latitude',
            }),
            'longitude': forms.HiddenInput(attrs={
                'id': 'id_longitude',
            }),
            'praia_ativa': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Informações relevantes sobre a praia',
            }),
        }
        labels = {
            'praia_ativa': 'Praia ativa para atuação da ONG',
        }
