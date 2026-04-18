from django.db import migrations


MODALIDADE_NOMES = [
    "Regular",
    "PEI",
    "CASA",
    "Sistema Prisional",
    "CEL",
    "EEI",
    "CEEJA",
]


def populate_modalidades(apps, schema_editor):
    Modalidade = apps.get_model("app", "Modalidade")
    for nome in MODALIDADE_NOMES:
        Modalidade.objects.get_or_create(nome=nome)


def reverse_modalidades(apps, schema_editor):
    Modalidade = apps.get_model("app", "Modalidade")
    Modalidade.objects.filter(nome__in=MODALIDADE_NOMES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_agente_escolar_status_choices"),
    ]

    operations = [
        migrations.RunPython(populate_modalidades, reverse_modalidades),
    ]
