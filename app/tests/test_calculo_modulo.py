"""Testes do serviço de cálculo de módulo (gestão + administrativo)."""

from __future__ import annotations

from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from app.models import Cargo, Escola, EscolaModalidade, Modalidade, PeriodoProcessamento
from app.services.calculo_modulo_service import CalculoModuloService

_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "calculo_modulo_base.json"


class CalculoModuloServiceTestCase(TestCase):
    """Caso base com modalidades, cargos, período e escola (fixture JSON + saneamento de tipos)."""

    @classmethod
    def setUpTestData(cls):
        cls._seed_modalidades()
        cls._seed_cargos()
        call_command("loaddata", str(_FIXTURE_PATH), verbosity=0)
        cls.periodo = PeriodoProcessamento.objects.get(pk=1)
        cls.escola_regular = Escola.objects.get(pk=1)

        cls.escola_ceja = Escola.objects.create(
            codigo_inep="FIXTURE02",
            nome="Escola somente CEEJA",
        )
        EscolaModalidade.objects.create(
            escola=cls.escola_ceja,
            modalidade_id=Modalidade.TIPO_CEEJA,
        )

    @staticmethod
    def _seed_modalidades():
        for pk, nome in [
            (Modalidade.TIPO_REGULAR, "Regular"),
            (Modalidade.TIPO_PEI, "PEI"),
            (Modalidade.TIPO_CASA, "CASA"),
            (Modalidade.TIPO_SISTEMA_PRISIONAL, "Sistema Prisional"),
            (Modalidade.TIPO_CEL, "CEL"),
            (Modalidade.TIPO_EEI, "EEI"),
            (Modalidade.TIPO_CEEJA, "CEEJA"),
        ]:
            Modalidade.objects.update_or_create(id=pk, defaults={"nome": nome})

    @staticmethod
    def _seed_cargos():
        rows = [
            (1, Cargo.TIPO_DIRETOR, "Diretor", "Diretor"),
            (2, Cargo.TIPO_VICE_DIRETOR, "Vice-Diretor", "Vice-Diretor"),
            (3, Cargo.TIPO_CGP, "Coordenador de Gestão Pedagógica", "CGP"),
            (4, Cargo.TIPO_CGPG, "Coordenador de Gestão Pedagógica em Tempo Integral", "CGPG"),
            (5, Cargo.TIPO_AOE, "Agente de Organização Escolar", "AOE"),
            (6, Cargo.TIPO_ASE, "Agente de Serviços Escolares", "ASE"),
        ]
        for pk, tipo, nome, abrev in rows:
            Cargo.objects.update_or_create(
                id=pk,
                defaults={"nome": nome, "abreviacao": abrev, "tipo": tipo},
            )

    def test_calcular_retorna_cinco_cargos_para_escola_regular(self):
        svc = CalculoModuloService()
        qtds = svc.calcular(self.escola_regular, 150, self.periodo)
        self.assertEqual(len(qtds), 5)
        tipos = {q.cargo.tipo for q in qtds}
        self.assertEqual(
            tipos,
            {
                Cargo.TIPO_DIRETOR,
                Cargo.TIPO_VICE_DIRETOR,
                Cargo.TIPO_CGP,
                Cargo.TIPO_AOE,
                Cargo.TIPO_ASE,
            },
        )

    def test_somente_ceeja_retorna_quantidades_zero(self):
        svc = CalculoModuloService()
        qtds = svc.calcular(self.escola_ceja, 500, self.periodo)
        self.assertTrue(all(q.quantidade == 0 for q in qtds))
