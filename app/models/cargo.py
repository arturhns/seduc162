from django.db import models


class Cargo(models.Model):
    nome = models.CharField(max_length=80, unique=True)
    abreviacao = models.CharField(max_length=20, null=True, blank=True)
    tipo = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "cargos"

    def __str__(self) -> str:
        return self.nome
