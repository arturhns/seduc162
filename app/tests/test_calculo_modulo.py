"""Testes do serviço de cálculo de módulo (gestão + administrativo)."""

from __future__ import annotations

from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from app.models import Cargo, Escola, EscolaModalidade, Modalidade, PeriodoProcessamento
from app.services.calculo_modulo import CalculoModuloService

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

    def _qtd_por_tipo(self, qtds):
        return {q.cargo.tipo: q.quantidade for q in qtds}

    def _escola(
        self,
        codigo_inep: str,
        modalidade_ids: list[int],
        *,
        numero_turnos: int = 1,
        tipo_merenda: int = Escola.MERENDA_CENTRALIZADA,
        tipo_limpeza: int = Escola.LIMPEZA_CENTRALIZADA,
        pei_turno_diverso_tempo_parcial: bool = False,
        pei_nove_horas: bool = False,
    ) -> Escola:
        e = Escola.objects.create(
            codigo_inep=codigo_inep,
            nome=f"Escola {codigo_inep}",
            numero_turnos=numero_turnos,
            tipo_merenda=tipo_merenda,
            tipo_limpeza=tipo_limpeza,
            pei_turno_diverso_tempo_parcial=pei_turno_diverso_tempo_parcial,
            pei_nove_horas=pei_nove_horas,
        )
        for mid in modalidade_ids:
            EscolaModalidade.objects.create(escola=e, modalidade_id=mid)
        return e

    def _calc(
        self,
        escola: Escola,
        matricula_ativa: int,
        *,
        professores_dedicados=None,
        matricula_cel=None,
    ):
        qtds, _explicacoes = CalculoModuloService().calcular(
            escola,
            matricula_ativa,
            self.periodo,
            professores_dedicados=professores_dedicados,
            matricula_cel=matricula_cel,
        )
        return qtds

    # --- Smoke / estrutura ---

    def test_calcular_retorna_cinco_cargos_para_escola_regular(self):
        qtds = self._calc(self.escola_regular, 150)
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
        qtds = self._calc(self.escola_ceja, 500)
        d = self._qtd_por_tipo(qtds)
        self.assertEqual(d[Cargo.TIPO_DIRETOR], 0)
        self.assertEqual(d[Cargo.TIPO_VICE_DIRETOR], 0)
        self.assertEqual(d[Cargo.TIPO_CGP], 0)
        self.assertEqual(d[Cargo.TIPO_AOE], 0)
        self.assertEqual(d[Cargo.TIPO_ASE], 0)

    def test_ceeja_com_outra_modalidade_nao_zera_modulo(self):
        escola = Escola.objects.create(codigo_inep="CEEMIX", nome="CEEJA + Regular")
        EscolaModalidade.objects.create(escola=escola, modalidade_id=Modalidade.TIPO_CEEJA)
        EscolaModalidade.objects.create(escola=escola, modalidade_id=Modalidade.TIPO_REGULAR)
        d = self._qtd_por_tipo(self._calc(escola, 100))
        self.assertEqual(d[Cargo.TIPO_DIRETOR], 1)
        self.assertGreater(d[Cargo.TIPO_ASE], 0)

    def test_escola_com_pei_usa_cgpg_no_resultado(self):
        escola = self._escola("PEI01", [Modalidade.TIPO_PEI])
        d = self._qtd_por_tipo(self._calc(escola, 100))
        self.assertIn(Cargo.TIPO_CGPG, d)
        self.assertNotIn(Cargo.TIPO_CGP, d)

    # --- Art. 1º caput: faixas de matrícula (gestão base) ---

    def test_gestao_base_faixas_matricula(self):
        escola = self._escola("GEST01", [Modalidade.TIPO_REGULAR])
        casos = [
            (0, 1, 0, 1),
            (1, 1, 0, 1),
            (200, 1, 0, 1),
            (201, 1, 1, 1),
            (500, 1, 1, 1),
            (501, 1, 1, 2),
            (600, 1, 1, 2),
            (601, 1, 2, 2),
            (800, 1, 2, 2),
            (801, 1, 2, 3),
            (1000, 1, 2, 3),
            (1001, 1, 3, 3),
            (1100, 1, 3, 3),
            (1101, 1, 3, 4),
            (1500, 1, 3, 4),
            (1501, 1, 3, 5),
            (5000, 1, 3, 5),
        ]
        for n, exp_dir, exp_vice, exp_coord in casos:
            with self.subTest(n=n):
                d = self._qtd_por_tipo(self._calc(escola, n))
                self.assertEqual(d[Cargo.TIPO_DIRETOR], exp_dir)
                self.assertEqual(d[Cargo.TIPO_VICE_DIRETOR], exp_vice)
                self.assertEqual(d[Cargo.TIPO_CGP], exp_coord)

    def test_matricula_negativa_tratada_como_zero(self):
        escola = self._escola("NEG01", [Modalidade.TIPO_REGULAR])
        d = self._qtd_por_tipo(self._calc(escola, -50))
        self.assertEqual(d[Cargo.TIPO_DIRETOR], 1)
        self.assertEqual(d[Cargo.TIPO_VICE_DIRETOR], 0)
        self.assertEqual(d[Cargo.TIPO_CGP], 1)
        self.assertEqual(d[Cargo.TIPO_AOE], 0)

    # --- Art. 1º §§ 1º–3º: CASA / prisional / CEL + professores dedicados ---

    def test_acrescimo_coord_casa_com_professores_dedicados(self):
        escola = self._escola("CASA01", [Modalidade.TIPO_REGULAR, Modalidade.TIPO_CASA])
        d = self._qtd_por_tipo(self._calc(escola, 300, professores_dedicados=5))
        self.assertEqual(d[Cargo.TIPO_CGP], 1)
        d6 = self._qtd_por_tipo(self._calc(escola, 300, professores_dedicados=6))
        self.assertEqual(d6[Cargo.TIPO_CGP], 2)

    def test_professores_dedicados_none_nao_conta_para_acrescimo(self):
        escola = self._escola("CASAN", [Modalidade.TIPO_REGULAR, Modalidade.TIPO_CASA])
        d_none = self._qtd_por_tipo(self._calc(escola, 300, professores_dedicados=None))
        d0 = self._qtd_por_tipo(self._calc(escola, 300, professores_dedicados=0))
        self.assertEqual(d_none[Cargo.TIPO_CGP], 1)
        self.assertEqual(d0[Cargo.TIPO_CGP], 1)

    def test_acrescimo_coord_prisional_com_professores_dedicados(self):
        escola = self._escola("PRIS01", [Modalidade.TIPO_REGULAR, Modalidade.TIPO_SISTEMA_PRISIONAL])
        d = self._qtd_por_tipo(self._calc(escola, 300, professores_dedicados=5))
        self.assertEqual(d[Cargo.TIPO_CGP], 1)
        d6 = self._qtd_por_tipo(self._calc(escola, 300, professores_dedicados=6))
        self.assertEqual(d6[Cargo.TIPO_CGP], 2)

    def test_prisional_prevalece_sobre_casa_para_acrescimo_coord_unico(self):
        escola = self._escola(
            "AMB01",
            [Modalidade.TIPO_REGULAR, Modalidade.TIPO_CASA, Modalidade.TIPO_SISTEMA_PRISIONAL],
        )
        d = self._qtd_por_tipo(self._calc(escola, 400, professores_dedicados=10))
        self.assertEqual(d[Cargo.TIPO_CGP], 2)

    def test_acrescimo_coord_cel_matricula_cel(self):
        escola = self._escola("CEL01", [Modalidade.TIPO_REGULAR, Modalidade.TIPO_CEL])
        d199 = self._qtd_por_tipo(self._calc(escola, 400, matricula_cel=199))
        self.assertEqual(d199[Cargo.TIPO_CGP], 1)
        d200 = self._qtd_por_tipo(self._calc(escola, 400, matricula_cel=200))
        self.assertEqual(d200[Cargo.TIPO_CGP], 2)

    def test_matricula_cel_none_ou_zero_nao_acresce_coord_cel(self):
        escola = self._escola("CELZ", [Modalidade.TIPO_REGULAR, Modalidade.TIPO_CEL])
        d_none = self._qtd_por_tipo(self._calc(escola, 400, matricula_cel=None))
        d0 = self._qtd_por_tipo(self._calc(escola, 400, matricula_cel=0))
        self.assertEqual(d_none[Cargo.TIPO_CGP], 1)
        self.assertEqual(d0[Cargo.TIPO_CGP], 1)

    def test_cel_soma_com_casa_quando_ambos(self):
        escola = self._escola("CELCA", [Modalidade.TIPO_REGULAR, Modalidade.TIPO_CASA, Modalidade.TIPO_CEL])
        d = self._qtd_por_tipo(self._calc(escola, 400, professores_dedicados=6, matricula_cel=200))
        self.assertEqual(d[Cargo.TIPO_CGP], 3)

    def test_acrescimos_coord_em_escola_com_pei_usa_cgpg(self):
        escola = self._escola("PEICG", [Modalidade.TIPO_PEI, Modalidade.TIPO_CASA])
        d = self._qtd_por_tipo(self._calc(escola, 300, professores_dedicados=6))
        self.assertEqual(d[Cargo.TIPO_CGPG], 2)

    # --- Art. 1º § 6º: PEI tempo parcial turno diverso ---

    def test_pei_turno_diverso_parcial_acrescimo_vice_coord(self):
        escola = self._escola(
            "PEIDV",
            [Modalidade.TIPO_PEI],
            pei_turno_diverso_tempo_parcial=True,
        )
        for n, exp_v, exp_c in [
            (50, 0, 1),
            (100, 0, 1),
            (101, 1, 1),
            (200, 1, 1),
            (201, 2, 2),
        ]:
            with self.subTest(n=n):
                d = self._qtd_por_tipo(self._calc(escola, n))
                self.assertEqual(d[Cargo.TIPO_VICE_DIRETOR], exp_v)
                self.assertEqual(d[Cargo.TIPO_CGPG], exp_c)

    # --- Art. 3º caput: AOE faixas 120 (sem PEI 9h) ---

    def test_aoe_caput_faixas(self):
        escola = self._escola("AOE01", [Modalidade.TIPO_REGULAR], pei_nove_horas=False)
        casos = [
            (0, 0),
            (1, 2),
            (120, 2),
            (121, 3),
            (1320, 12),
            (1321, 13),
            (2000, 13),
        ]
        for n, exp in casos:
            with self.subTest(n=n):
                d = self._qtd_por_tipo(self._calc(escola, n))
                self.assertEqual(d[Cargo.TIPO_AOE], exp)

    def test_aoe_pei_nove_horas_faixas_80(self):
        escola = self._escola("AOE9H", [Modalidade.TIPO_PEI], pei_nove_horas=True)
        casos = [
            (0, 0),
            (1, 2),
            (80, 2),
            (81, 3),
            (1440, 19),
            (1441, 20),
            (2000, 20),
        ]
        for n, exp in casos:
            with self.subTest(n=n):
                d = self._qtd_por_tipo(self._calc(escola, n))
                self.assertEqual(d[Cargo.TIPO_AOE], exp)

    def test_aoe_acrescimo_casa_com_professores(self):
        escola = self._escola("AOECA", [Modalidade.TIPO_REGULAR, Modalidade.TIPO_CASA])
        d5 = self._qtd_por_tipo(self._calc(escola, 200, professores_dedicados=5))
        d6 = self._qtd_por_tipo(self._calc(escola, 200, professores_dedicados=6))
        base = 2 + (200 - 1) // 120
        self.assertEqual(d5[Cargo.TIPO_AOE], base)
        self.assertEqual(d6[Cargo.TIPO_AOE], base + 1)

    def test_aoe_acrescimo_prisional_com_professores(self):
        escola = self._escola("AOEPR", [Modalidade.TIPO_REGULAR, Modalidade.TIPO_SISTEMA_PRISIONAL])
        d6 = self._qtd_por_tipo(self._calc(escola, 200, professores_dedicados=6))
        base = 2 + (200 - 1) // 120
        self.assertEqual(d6[Cargo.TIPO_AOE], base + 1)

    def test_aoe_prisional_nao_cumulativo_com_casa_mesmo_com_professores(self):
        escola = self._escola(
            "AOEAM",
            [Modalidade.TIPO_REGULAR, Modalidade.TIPO_CASA, Modalidade.TIPO_SISTEMA_PRISIONAL],
        )
        d = self._qtd_por_tipo(self._calc(escola, 200, professores_dedicados=10))
        base = 2 + (200 - 1) // 120
        self.assertEqual(d[Cargo.TIPO_AOE], base + 1)

    # --- Art. 2º: ASE merenda/limpeza/turnos ---

    def test_ase_merenda_limpeza_centralizadas_faixas_um_turno(self):
        escola = self._escola(
            "ASECC",
            [Modalidade.TIPO_REGULAR],
            tipo_merenda=Escola.MERENDA_CENTRALIZADA,
            tipo_limpeza=Escola.LIMPEZA_CENTRALIZADA,
            numero_turnos=1,
        )
        casos = [
            (1, 4),
            (210, 4),
            (211, 5),
            (630, 5),
            (631, 6),
            (1050, 6),
            (1051, 7),
            (1290, 7),
            (1291, 8),
            (1530, 8),
            (1531, 9),
        ]
        for n, exp in casos:
            with self.subTest(n=n):
                d = self._qtd_por_tipo(self._calc(escola, n))
                self.assertEqual(d[Cargo.TIPO_ASE], exp)

    def test_ase_merenda_terceirizada_limpeza_centralizada_faixas(self):
        escola = self._escola(
            "ASETC",
            [Modalidade.TIPO_REGULAR],
            tipo_merenda=Escola.MERENDA_TERCEIRIZADA,
            tipo_limpeza=Escola.LIMPEZA_CENTRALIZADA,
            numero_turnos=1,
        )
        casos = [
            (210, 2),
            (211, 3),
            (630, 3),
            (631, 4),
            (1050, 4),
            (1051, 5),
            (1290, 5),
            (1291, 6),
            (1530, 6),
            (1531, 7),
        ]
        for n, exp in casos:
            with self.subTest(n=n):
                d = self._qtd_por_tipo(self._calc(escola, n))
                self.assertEqual(d[Cargo.TIPO_ASE], exp)

    def test_ase_merenda_descentralizada_usa_mesma_tabela_terc_desc_com_limpeza_cent(self):
        escola = self._escola(
            "ASEDC",
            [Modalidade.TIPO_REGULAR],
            tipo_merenda=Escola.MERENDA_DESCENTRALIZADA,
            tipo_limpeza=Escola.LIMPEZA_CENTRALIZADA,
            numero_turnos=1,
        )
        d = self._qtd_por_tipo(self._calc(escola, 500))
        self.assertEqual(d[Cargo.TIPO_ASE], 3)

    def test_ase_merenda_cent_limpeza_terc_faixas(self):
        escola = self._escola(
            "ASECT",
            [Modalidade.TIPO_REGULAR],
            tipo_merenda=Escola.MERENDA_CENTRALIZADA,
            tipo_limpeza=Escola.LIMPEZA_TERCEIRIZADA,
            numero_turnos=1,
        )
        casos = [
            (300, 2),
            (301, 3),
            (900, 3),
            (901, 4),
            (1200, 4),
            (1201, 5),
            (1500, 5),
            (1501, 6),
            (1740, 6),
            (1741, 7),
        ]
        for n, exp in casos:
            with self.subTest(n=n):
                d = self._qtd_por_tipo(self._calc(escola, n))
                self.assertEqual(d[Cargo.TIPO_ASE], exp)

    def test_ase_merenda_terc_e_limpeza_terc_retorna_zero(self):
        escola = self._escola(
            "ASE00",
            [Modalidade.TIPO_REGULAR],
            tipo_merenda=Escola.MERENDA_TERCEIRIZADA,
            tipo_limpeza=Escola.LIMPEZA_TERCEIRIZADA,
            numero_turnos=3,
        )
        d = self._qtd_por_tipo(self._calc(escola, 2000))
        self.assertEqual(d[Cargo.TIPO_ASE], 0)

    def test_ase_merenda_desc_com_limpeza_terc_retorna_zero(self):
        escola = self._escola(
            "ASE0B",
            [Modalidade.TIPO_REGULAR],
            tipo_merenda=Escola.MERENDA_DESCENTRALIZADA,
            tipo_limpeza=Escola.LIMPEZA_TERCEIRIZADA,
            numero_turnos=2,
        )
        d = self._qtd_por_tipo(self._calc(escola, 2000))
        self.assertEqual(d[Cargo.TIPO_ASE], 0)

    def test_ase_turnos_acrescimo_sobre_base_cent_cent(self):
        escola1 = self._escola(
            "AST1",
            [Modalidade.TIPO_REGULAR],
            numero_turnos=1,
            tipo_merenda=Escola.MERENDA_CENTRALIZADA,
            tipo_limpeza=Escola.LIMPEZA_CENTRALIZADA,
        )
        escola2 = self._escola(
            "AST2",
            [Modalidade.TIPO_REGULAR],
            numero_turnos=2,
            tipo_merenda=Escola.MERENDA_CENTRALIZADA,
            tipo_limpeza=Escola.LIMPEZA_CENTRALIZADA,
        )
        escola3 = self._escola(
            "AST3",
            [Modalidade.TIPO_REGULAR],
            numero_turnos=3,
            tipo_merenda=Escola.MERENDA_CENTRALIZADA,
            tipo_limpeza=Escola.LIMPEZA_CENTRALIZADA,
        )
        n = 400
        b = self._qtd_por_tipo(self._calc(escola1, n))[Cargo.TIPO_ASE]
        self.assertEqual(self._qtd_por_tipo(self._calc(escola2, n))[Cargo.TIPO_ASE], b + 1)
        self.assertEqual(self._qtd_por_tipo(self._calc(escola3, n))[Cargo.TIPO_ASE], b + 2)

    def test_ase_tipo_merenda_e_limpeza_zero_usa_centralizado(self):
        escola = self._escola(
            "ASEDF",
            [Modalidade.TIPO_REGULAR],
            tipo_merenda=0,
            tipo_limpeza=0,
            numero_turnos=1,
        )
        d = self._qtd_por_tipo(self._calc(escola, 100))
        self.assertEqual(d[Cargo.TIPO_ASE], 4)

    def test_ase_fallback_else_merenda_desc_limpeza_desc_usa_tabela_cent_cent(self):
        escola = self._escola(
            "ASEEL",
            [Modalidade.TIPO_REGULAR],
            tipo_merenda=Escola.MERENDA_DESCENTRALIZADA,
            tipo_limpeza=Escola.LIMPEZA_DESCENTRALIZADA,
            numero_turnos=1,
        )
        d = self._qtd_por_tipo(self._calc(escola, 100))
        self.assertEqual(d[Cargo.TIPO_ASE], 4)

    def test_numero_turnos_maior_que_tres_apenas_soma_dois(self):
        escola = self._escola(
            "AST9",
            [Modalidade.TIPO_REGULAR],
            numero_turnos=9,
            tipo_merenda=Escola.MERENDA_CENTRALIZADA,
            tipo_limpeza=Escola.LIMPEZA_CENTRALIZADA,
        )
        escola1 = self._escola(
            "AST1B",
            [Modalidade.TIPO_REGULAR],
            numero_turnos=1,
            tipo_merenda=Escola.MERENDA_CENTRALIZADA,
            tipo_limpeza=Escola.LIMPEZA_CENTRALIZADA,
        )
        n = 200
        b = self._qtd_por_tipo(self._calc(escola1, n))[Cargo.TIPO_ASE]
        self.assertEqual(self._qtd_por_tipo(self._calc(escola, n))[Cargo.TIPO_ASE], b + 2)

    # --- Integração: cenário completo ---

    def test_cenario_completo_pei_modalidades_extras_professores_cel(self):
        escola = self._escola(
            "FULL1",
            [
                Modalidade.TIPO_PEI,
                Modalidade.TIPO_CASA,
                Modalidade.TIPO_CEL,
            ],
            pei_turno_diverso_tempo_parcial=True,
            pei_nove_horas=True,
            numero_turnos=2,
            tipo_merenda=Escola.MERENDA_CENTRALIZADA,
            tipo_limpeza=Escola.LIMPEZA_CENTRALIZADA,
        )
        n = 250
        d = self._qtd_por_tipo(
            self._calc(
                escola,
                n,
                professores_dedicados=6,
                matricula_cel=200,
            )
        )
        self.assertEqual(d[Cargo.TIPO_DIRETOR], 1)
        self.assertEqual(d[Cargo.TIPO_VICE_DIRETOR], 2)
        self.assertEqual(d[Cargo.TIPO_CGPG], 4)
        aoe_base = 2 + (n - 1) // 80
        self.assertEqual(d[Cargo.TIPO_AOE], aoe_base + 1)
        ase_base_cent = 5
        self.assertEqual(d[Cargo.TIPO_ASE], ase_base_cent + 1)
