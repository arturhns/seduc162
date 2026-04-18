from django.db import models


class Modalidade(models.Model):
    nome = models.CharField(max_length=50, unique=True)

    TIPO_REGULAR = 1
    TIPO_PEI = 2
    TIPO_CASA = 3
    TIPO_SISTEMA_PRISIONAL = 4
    TIPO_CEL = 5
    TIPO_EEI = 6
    TIPO_CEEJA = 7

    class Meta:
        db_table = "modalidades"

    def __str__(self) -> str:
        return self.nome
