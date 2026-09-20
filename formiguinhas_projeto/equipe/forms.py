from django import forms
from django.db.models import Q

from praia.models import Praia
from usuario.models import Voluntario

from .models import Equipe, EquipeMembro


class EquipeForm(forms.ModelForm):
    class Meta:
        model = Equipe
        fields = ['nome', 'praia', 'descricao', 'status']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da equipe',
            }),
            'praia': forms.Select(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Descreva a equipe',
                'rows': 4,
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        praias_ativas = Praia.objects.filter(praia_ativa='ATIVA')
        if self.instance and self.instance.praia_id:
            praias_ativas = Praia.objects.filter(
                Q(praia_ativa='ATIVA') | Q(pk=self.instance.praia_id)
            )
        self.fields['praia'].queryset = praias_ativas.order_by('nome')
        self.fields['praia'].empty_label = 'Selecione uma praia'
        self.fields['praia'].label_from_instance = (
            lambda praia: f'{praia.nome} - {praia.cidade}'
        )
        self.fields['praia'].required = True


class EquipeMembroForm(forms.ModelForm):
    class Meta:
        model = EquipeMembro
        fields = ['voluntario', 'papel']
        widgets = {
            'voluntario': forms.Select(attrs={'class': 'form-control'}),
            'papel': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, equipe=None, permitir_coordenador=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['voluntario'].queryset = Voluntario.objects.filter(
            status='ATIVO'
        ).order_by('nome')
        self.fields['voluntario'].empty_label = 'Selecione um voluntário'
        self.fields['voluntario'].label_from_instance = (
            lambda voluntario: f'{voluntario.nome} - {voluntario.email}'
        )

        if equipe:
            membros_ativos = EquipeMembro.objects.filter(
                equipe=equipe,
                status='ATIVO',
            )
            if self.instance and self.instance.pk:
                membros_ativos = membros_ativos.exclude(pk=self.instance.pk)
            self.fields['voluntario'].queryset = self.fields[
                'voluntario'
            ].queryset.exclude(
                pk__in=membros_ativos.values('voluntario_id')
            )

        if not permitir_coordenador:
            self.fields.pop('papel')
