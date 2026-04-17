from django.db import models


class AgenteEscolar(models.Model):
    class Status(models.IntegerChoices):
        INATIVO = 0, "Inativo"
        ATIVO = 1, "Ativo"
        LICENCA = 2, "Licença"

    nome_completo = models.CharField(max_length=150)
    matricula_funcional = models.CharField(max_length=30, unique=True)
    status = models.PositiveSmallIntegerField(
        choices=Status.choices,
        default=Status.ATIVO,
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agentes_escolares"
        verbose_name = "Agente escolar"
        verbose_name_plural = "Agentes escolares"

    def __str__(self) -> str:
        return f"{self.nome_completo} ({self.matricula_funcional})"
