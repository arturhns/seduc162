"""
Cálculo do módulo de gestão e administrativo conforme Resolução SEDUC nº 162/2025.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from django.db.models import Prefetch

from app.models import CalculoModulo, CalculoQuantidade, Cargo, Escola, EscolaModalidade, Modalidade


@dataclass(frozen=True)
class _GestaoBase:
    diretor: int
    vice: int
    coordenadores: int


class CalculoModuloService:
    """Serviço de cálculo do módulo (gestão + administrativo) — Resolução SEDUC 162/2025."""

    def calcular(
        self,
        escola: Escola,
        matricula_ativa: int,
        periodo,
        *,
        professores_dedicados=None,
        matricula_cel=None,
    ) -> list[CalculoQuantidade]:
        """
        Retorna lista de `CalculoQuantidade` (Diretor, Vice, CGP ou CGPG, AOE, ASE),
        todas vinculadas à mesma instância **não salva** de `CalculoModulo` (escola, período,
        matrícula). Salve primeiro o `CalculoModulo` e depois as quantidades em transação.
        """
        if escola.pk:
            escola = (
                Escola.objects.filter(pk=escola.pk)
                .prefetch_related(
                    Prefetch("escolamodalidade_set", queryset=EscolaModalidade.objects.all())
                )
                .first()
                or escola
            )

        tipos_modalidade = set(self._tipos_modalidade_escola(escola))

        calculo = CalculoModulo(
            escola=escola,
            periodo=periodo,
            matricula_ativa=matricula_ativa,
            professores_dedicados=professores_dedicados,
            matricula_cel=matricula_cel,
        )

        if self._somente_ceja(tipos_modalidade):
            return self._quantidades_todos_zeros(calculo, tipos_modalidade)

        n = max(0, int(matricula_ativa))

        gestao = self._gestao_base(n)
        tem_pei = Modalidade.TIPO_PEI in tipos_modalidade
        usa_cgpg = tem_pei

        diretor = gestao.diretor
        vice = gestao.vice
        coords = gestao.coordenadores

        coords += self._acrescimo_cgp_casa_prisional_cel(calculo, tipos_modalidade)

        if tem_pei and getattr(escola, "pei_turno_diverso_tempo_parcial", False):
            av, ac = self._acrescimo_gestores_pei_parcial_diverso(n)
            vice += av
            coords += ac

        aoe = self._aoe(n, tem_pei and getattr(escola, "pei_nove_horas", False))
        aoe += self._acrescimo_aoe_casa_prisional(calculo, tipos_modalidade)

        ase = self._ase(escola, n)

        cargo_dir = self._cargo(Cargo.TIPO_DIRETOR)
        cargo_vice = self._cargo(Cargo.TIPO_VICE_DIRETOR)
        cargo_coord = self._cargo(Cargo.TIPO_CGPG if usa_cgpg else Cargo.TIPO_CGP)
        cargo_aoe = self._cargo(Cargo.TIPO_AOE)
        cargo_ase = self._cargo(Cargo.TIPO_ASE)

        return [
            CalculoQuantidade(calculo_modulo=calculo, cargo=cargo_dir, quantidade=diretor),
            CalculoQuantidade(calculo_modulo=calculo, cargo=cargo_vice, quantidade=vice),
            CalculoQuantidade(calculo_modulo=calculo, cargo=cargo_coord, quantidade=coords),
            CalculoQuantidade(calculo_modulo=calculo, cargo=cargo_aoe, quantidade=aoe),
            CalculoQuantidade(calculo_modulo=calculo, cargo=cargo_ase, quantidade=ase),
        ]

    def _cargo(self, tipo: int) -> Cargo:
        c = Cargo.objects.filter(tipo=tipo).order_by("id").first()
        if c is None:
            raise ValueError(f"Cargo com tipo={tipo} não cadastrado na tabela `cargos`.")
        return c

    def _tipos_modalidade_escola(self, escola: Escola) -> Iterator[int]:
        """IDs de `modalidade` em `EscolaModalidade` (alinhados a `Modalidade.TIPO_*` na base)."""
        for em in escola.escolamodalidade_set.all():
            yield int(em.modalidade_id)

    @staticmethod
    def _somente_ceja(tipos: set[int]) -> bool:
        return tipos == {Modalidade.TIPO_CEEJA}

    def _quantidades_todos_zeros(
        self, calculo: CalculoModulo, tipos_modalidade: set[int]
    ) -> list[CalculoQuantidade]:
        _ = tipos_modalidade
        usa_cgpg = Modalidade.TIPO_PEI in tipos_modalidade
        cargos = (
            Cargo.TIPO_DIRETOR,
            Cargo.TIPO_VICE_DIRETOR,
            Cargo.TIPO_CGPG if usa_cgpg else Cargo.TIPO_CGP,
            Cargo.TIPO_AOE,
            Cargo.TIPO_ASE,
        )
        return [
            CalculoQuantidade(calculo_modulo=calculo, cargo=self._cargo(t), quantidade=0)
            for t in cargos
        ]

    @staticmethod
    def _gestao_base(n: int) -> _GestaoBase:
        """Art. 1º, caput — tempo parcial / estrutura geral por faixas de matrícula ativa."""
        if n <= 200:
            return _GestaoBase(1, 0, 1)
        if n <= 500:
            return _GestaoBase(1, 1, 1)
        if n <= 600:
            return _GestaoBase(1, 1, 2)
        if n <= 800:
            return _GestaoBase(1, 2, 2)
        if n <= 1000:
            return _GestaoBase(1, 2, 3)
        if n <= 1100:
            return _GestaoBase(1, 3, 3)
        if n <= 1500:
            return _GestaoBase(1, 3, 4)
        return _GestaoBase(1, 3, 5)

    def _acrescimo_cgp_casa_prisional_cel(self, calculo: CalculoModulo, tipos: set[int]) -> int:
        """Art. 1º §§ 1º a 3º — acréscimos de CGP (ou CGPG, no PEI) em coordenadores."""
        extra = 0
        prof_ok = int(calculo.professores_dedicados or 0) >= 6
        tem_casa = Modalidade.TIPO_CASA in tipos
        tem_prisional = Modalidade.TIPO_SISTEMA_PRISIONAL in tipos
        tem_cel = Modalidade.TIPO_CEL in tipos

        if tem_prisional and prof_ok:
            extra += 1
        elif tem_casa and prof_ok:
            extra += 1

        mat_cel = int(calculo.matricula_cel or 0)
        if tem_cel and mat_cel >= 200:
            extra += 1

        return extra

    @staticmethod
    def _acrescimo_gestores_pei_parcial_diverso(n: int) -> tuple[int, int]:
        """
        Art. 1º, § 6º — acréscimo para segmento tempo parcial em PEI com turno diverso.
        Retorna (acréscimo em vice, acréscimo em CGP/CGPG).
        Distribuição padrão: prioriza Vice; excedente em coordenador pedagógico.
        """
        if n <= 100:
            return (0, 0)
        if n <= 200:
            return (1, 0)
        return (1, 1)

    @staticmethod
    def _acrescimo_aoe_casa_prisional(calculo: CalculoModulo, tipos: set[int]) -> int:
        """Art. 3º §§ 2º e 3º — +1 AOE; prisional não cumulativo com CASA."""
        prof_ok = int(calculo.professores_dedicados or 0) >= 6
        if Modalidade.TIPO_SISTEMA_PRISIONAL in tipos and prof_ok:
            return 1
        if Modalidade.TIPO_CASA in tipos and prof_ok:
            return 1
        return 0

    @staticmethod
    def _aoe_caput(n: int) -> int:
        """Art. 3º, caput — faixas de 120 alunos (2 + floor((n-1)/120)), teto 13."""
        if n <= 0:
            return 0
        if n >= 1321:
            return 13
        return 2 + (n - 1) // 120

    @classmethod
    def _aoe_pei_nove_horas(cls, n: int) -> int:
        """Art. 3º, § 1º — PEI de 9 horas; faixas de 80 alunos até 20 AOE."""
        if n <= 0:
            return 0
        if n >= 1441:
            return 20
        return 2 + (n - 1) // 80

    def _aoe(self, n: int, pei_nove_horas: bool) -> int:
        return self._aoe_pei_nove_horas(n) if pei_nove_horas else self._aoe_caput(n)

    def _ase(self, escola: Escola, n: int) -> int:
        """Art. 2º — ASE conforme merenda, limpeza, faixas e número de turnos."""
        merenda = int(escola.tipo_merenda or 0)
        limpeza = int(escola.tipo_limpeza or 0)
        if merenda == 0:
            merenda = Escola.MERENDA_CENTRALIZADA
        if limpeza == 0:
            limpeza = Escola.LIMPEZA_CENTRALIZADA

        turnos = max(1, min(3, int(escola.numero_turnos or 1)))

        merenda_terc_ou_desc = merenda in (
            Escola.MERENDA_TERCEIRIZADA,
            Escola.MERENDA_DESCENTRALIZADA,
        )
        limpeza_terc = limpeza == Escola.LIMPEZA_TERCEIRIZADA

        if limpeza_terc and merenda_terc_ou_desc:
            return 0

        base = 0
        if merenda == Escola.MERENDA_CENTRALIZADA and limpeza == Escola.LIMPEZA_CENTRALIZADA:
            base = self._ase_merenda_cent_limpeza_cent(n)
        elif merenda_terc_ou_desc and limpeza == Escola.LIMPEZA_CENTRALIZADA:
            base = self._ase_merenda_terc_desc_limpeza_cent(n)
        elif merenda == Escola.MERENDA_CENTRALIZADA and limpeza_terc:
            base = self._ase_merenda_cent_limpeza_terc(n)
        else:
            base = self._ase_merenda_cent_limpeza_cent(n)

        if turnos == 2:
            base += 1
        elif turnos == 3:
            base += 2

        return base

    @staticmethod
    def _ase_merenda_cent_limpeza_cent(n: int) -> int:
        """Art. 2º, § 1º."""
        if n <= 210:
            return 4
        if n <= 630:
            return 5
        if n <= 1050:
            return 6
        if n <= 1290:
            return 7
        if n <= 1530:
            return 8
        return 9

    @staticmethod
    def _ase_merenda_terc_desc_limpeza_cent(n: int) -> int:
        """Art. 2º, § 4º."""
        if n <= 210:
            return 2
        if n <= 630:
            return 3
        if n <= 1050:
            return 4
        if n <= 1290:
            return 5
        if n <= 1530:
            return 6
        return 7

    @staticmethod
    def _ase_merenda_cent_limpeza_terc(n: int) -> int:
        """Art. 2º, § 7º."""
        if n <= 300:
            return 2
        if n <= 900:
            return 3
        if n <= 1200:
            return 4
        if n <= 1500:
            return 5
        if n <= 1740:
            return 6
        return 7
