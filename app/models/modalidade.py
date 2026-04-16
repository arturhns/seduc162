from django.db import models


class Modalidade(models.Model):
    nome = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "modalidades"

    def __str__(self) -> str:
        return self.nome
