from django import forms

from app.models import AgenteEscolar


class AgenteEscolarForm(forms.ModelForm):
    class Meta:
        model = AgenteEscolar
        fields = ["nome_completo", "matricula_funcional", "status"]
        labels = {
            "nome_completo": "Nome completo",
            "matricula_funcional": "Matrícula funcional",
            "status": "Status",
        }
        widgets = {
            "nome_completo": forms.TextInput(attrs={"class": "form-control"}),
            "matricula_funcional": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }
