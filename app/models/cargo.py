from django.db import models


class Cargo(models.Model):
    nome = models.CharField(max_length=80, unique=True)
    abreviacao = models.CharField(max_length=20, null=True, blank=True)
    tipo = models.PositiveSmallIntegerField(default=0)
    
    TIPO_DIRETOR = 1
    TIPO_VICE_DIRETOR = 2
    TIPO_CGP = 3
    TIPO_CGPG = 4
    TIPO_AOE = 5
    TIPO_ASE = 6

    TIPO_GESTAO = 0
    TIPO_ADMINISTRACAO = 1

    class Meta:
        db_table = "cargos"

    def __str__(self) -> str:
        return self.nome
