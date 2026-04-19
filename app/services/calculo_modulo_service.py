"""
Cálculo do módulo de gestão e administrativo conforme Resolução SEDUC nº 162/2025.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Iterator

from django.db.models import Prefetch

from app.models import CalculoModulo, CalculoQuantidade, Cargo, Escola, EscolaModalidade, Modalidade


@dataclass
class CriterioExplicacao:
    artigo: str  # ex: "Art. 1º, caput"
    descricao: str  # ex: "Faixa 501-600 alunos"
    impactos: list[str]  # ex: ["1 Diretor", "1 Vice-diretor", "1 CGP"]


@dataclass(frozen=True)
class _GestaoBase:
    diretor: int
    vice: int
    coordenadores: int


class CalculoModuloService:
    """Serviço de cálculo do módulo (gestão + administrativo) — Resolução SEDUC 162/2025."""

    @staticmethod
    def _trecho_faixa_alunos(n_min: int, n_max: int | None) -> str:
        if n_max is None:
            return f"a partir de {n_min} alunos."
        if n_min <= 1:
            return f"até {n_max} alunos."
        return f"de {n_min} a {n_max} alunos."

    @classmethod
    def _frase_faixa_matricula(cls, n_min: int, n_max: int | None) -> str:
        trecho = cls._trecho_faixa_alunos(n_min, n_max)
        if trecho:
            trecho = trecho[0].upper() + trecho[1:]
        return trecho

    @classmethod
    def _intervalo_ase_sec1_sec4(cls, n: int) -> tuple[int, int | None]:
        if n <= 210:
            return (1, 210)
        if n <= 630:
            return (211, 630)
        if n <= 1050:
            return (631, 1050)
        if n <= 1290:
            return (1051, 1290)
        if n <= 1530:
            return (1291, 1530)
        return (1531, None)

    @classmethod
    def _intervalo_ase_sec7(cls, n: int) -> tuple[int, int | None]:
        if n <= 300:
            return (1, 300)
        if n <= 900:
            return (301, 900)
        if n <= 1200:
            return (901, 1200)
        if n <= 1500:
            return (1201, 1500)
        if n <= 1740:
            return (1501, 1740)
        return (1741, None)

    @classmethod
    def _desc_ase_com_rubrica(
        cls,
        rubrica: str,
        n: int,
        intervalo_fn: Callable[[int], tuple[int, int | None]],
    ) -> str:
        lo, hi = intervalo_fn(n)
        trecho = cls._trecho_faixa_alunos(lo, hi)
        if trecho:
            trecho = trecho[0] + trecho[1:]
        return f"{rubrica}, {trecho}"

    @classmethod
    def _desc_aoe_caput(cls, n: int) -> str:
        if n <= 0:
            return "Não foi informado total de matrícula ativa (ou o total é zero), então não há AOE por esta regra."
        if n >= 1321:
            return "Situação em que se aplica o teto de AOE da regra geral."
        k = (n - 1) // 120
        n_min = k * 120 + 1
        n_max = (k + 1) * 120
        return cls._frase_faixa_matricula(n_min, n_max)

    @classmethod
    def _desc_aoe_pei_nove_horas(cls, n: int) -> str:
        if n <= 0:
            return "Não foi informado total de matrícula ativa (ou o total é zero), então não há AOE por esta regra."
        if n >= 1441:
            return (
                "Situação em que se aplica o teto de AOE para escolas PEI com jornada de 9 horas."
            )
        k = (n - 1) // 80
        n_min = k * 80 + 1
        n_max = (k + 1) * 80
        return (
            "Escola em PEI com jornada de 9 horas; "
            + cls._frase_faixa_matricula(n_min, n_max)
        )

    def calcular(
        self,
        escola: Escola,
        matricula_ativa: int,
        periodo,
        *,
        professores_dedicados=None,
        matricula_cel=None,
    ) -> tuple[list[CalculoQuantidade], list[CriterioExplicacao]]:
        """
        Retorna (`CalculoQuantidade`…, critérios da Resolução SEDUC 162/2025).
        Quantidades: Diretor, Vice, CGP ou CGPG, AOE, ASE na mesma instância não salva
        de `CalculoModulo`.
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

        tem_pei = Modalidade.TIPO_PEI in tipos_modalidade
        usa_cgpg = tem_pei
        coord_abrev = "CGPG" if usa_cgpg else "CGP"

        gestao, explicacoes_gestao = self._gestao_base(n, coord_abrev=coord_abrev)

        diretor = gestao.diretor
        vice = gestao.vice
        coords = gestao.coordenadores

        acres_cgp, explicacoes_cgp = self._acrescimo_cgp_casa_prisional_cel(
            calculo, tipos_modalidade, coord_abrev=coord_abrev
        )
        coords += acres_cgp

        explicacoes: list[CriterioExplicacao] = []
        explicacoes.extend(explicacoes_gestao)
        explicacoes.extend(explicacoes_cgp)

        if tem_pei and getattr(escola, "pei_turno_diverso_tempo_parcial", False):
            (av, ac), explicacoes_pei_td = self._acrescimo_gestores_pei_parcial_diverso(n)
            vice += av
            coords += ac
            explicacoes.extend(explicacoes_pei_td)

        aoe, explicacoes_aoe = self._aoe(n, tem_pei and getattr(escola, "pei_nove_horas", False))
        acres_aoe, explicacoes_aoe_extra = self._acrescimo_aoe_casa_prisional(
            calculo, tipos_modalidade
        )
        aoe += acres_aoe
        explicacoes.extend(explicacoes_aoe)
        explicacoes.extend(explicacoes_aoe_extra)

        ase, explicacoes_ase = self._ase(escola, n)
        explicacoes.extend(explicacoes_ase)

        cargo_dir = self._cargo(Cargo.TIPO_DIRETOR)
        cargo_vice = self._cargo(Cargo.TIPO_VICE_DIRETOR)
        cargo_coord = self._cargo(Cargo.TIPO_CGPG if usa_cgpg else Cargo.TIPO_CGP)
        cargo_aoe = self._cargo(Cargo.TIPO_AOE)
        cargo_ase = self._cargo(Cargo.TIPO_ASE)

        quantidades = [
            CalculoQuantidade(calculo_modulo=calculo, cargo=cargo_dir, quantidade=diretor),
            CalculoQuantidade(calculo_modulo=calculo, cargo=cargo_vice, quantidade=vice),
            CalculoQuantidade(calculo_modulo=calculo, cargo=cargo_coord, quantidade=coords),
            CalculoQuantidade(calculo_modulo=calculo, cargo=cargo_aoe, quantidade=aoe),
            CalculoQuantidade(calculo_modulo=calculo, cargo=cargo_ase, quantidade=ase),
        ]
        return quantidades, explicacoes

    def _cargo(self, tipo: int) -> Cargo:
        c = Cargo.objects.filter(pk=tipo).order_by("id").first()
        if c is None:
            raise ValueError(f"Cargo com id={tipo} não cadastrado na tabela `cargos`.")
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
    ) -> tuple[list[CalculoQuantidade], list[CriterioExplicacao]]:
        _ = tipos_modalidade
        usa_cgpg = Modalidade.TIPO_PEI in tipos_modalidade
        cargos = (
            Cargo.TIPO_DIRETOR,
            Cargo.TIPO_VICE_DIRETOR,
            Cargo.TIPO_CGPG if usa_cgpg else Cargo.TIPO_CGP,
            Cargo.TIPO_AOE,
            Cargo.TIPO_ASE,
        )
        quantidades = [
            CalculoQuantidade(calculo_modulo=calculo, cargo=self._cargo(t), quantidade=0)
            for t in cargos
        ]
        explicacoes = [
            CriterioExplicacao(
                artigo="Resolução SEDUC 162/2025",
                descricao=(
                    "A unidade está somente na modalidade CEEJA; nesta situação o módulo não prevê "
                    "cargos de gestão nem de apoio administrativo para esta contagem."
                ),
                impactos=[
                    "0 Diretor",
                    "0 Vice-diretor",
                    "0 CGP/CGPG",
                    "0 AOE",
                    "0 ASE",
                ],
            )
        ]
        return quantidades, explicacoes

    @staticmethod
    def _gestao_base(
        n: int, *, coord_abrev: str = "CGP"
    ) -> tuple[_GestaoBase, list[CriterioExplicacao]]:
        """Art. 1º, caput — tempo parcial / estrutura geral por faixas de matrícula ativa."""
        if n <= 200:
            base = _GestaoBase(1, 0, 1)
            faixa = "Até 200 alunos."
        elif n <= 500:
            base = _GestaoBase(1, 1, 1)
            faixa = "De 201 a 500 alunos."
        elif n <= 600:
            base = _GestaoBase(1, 1, 2)
            faixa = "De 501 a 600 alunos."
        elif n <= 800:
            base = _GestaoBase(1, 2, 2)
            faixa = "De 601 a 800 alunos."
        elif n <= 1000:
            base = _GestaoBase(1, 2, 3)
            faixa = "De 801 a 1000 alunos."
        elif n <= 1100:
            base = _GestaoBase(1, 3, 3)
            faixa = "De 1001 a 1100 alunos."
        elif n <= 1500:
            base = _GestaoBase(1, 3, 4)
            faixa = "De 1101 a 1500 alunos."
        else:
            base = _GestaoBase(1, 3, 5)
            faixa = "Mais de 1500 alunos."

        impactos: list[str] = ["1 Diretor"]
        if base.vice:
            vd = "Vice-diretor" if base.vice == 1 else "Vice-diretores"
            impactos.append(f"{base.vice} {vd}")
        impactos.append(f"{base.coordenadores} {coord_abrev}")

        explicacao = CriterioExplicacao(
            artigo="Art. 1º, caput",
            descricao=faixa,
            impactos=impactos,
        )
        return base, [explicacao]

    def _acrescimo_cgp_casa_prisional_cel(
        self, calculo: CalculoModulo, tipos: set[int], *, coord_abrev: str = "CGP"
    ) -> tuple[int, list[CriterioExplicacao]]:
        """Art. 1º §§ 1º a 3º — acréscimos de CGP (ou CGPG, no PEI) em coordenadores."""
        extra = 0
        explicacoes: list[CriterioExplicacao] = []
        prof_ok = int(calculo.professores_dedicados or 0) >= 6
        tem_casa = Modalidade.TIPO_CASA in tipos
        tem_prisional = Modalidade.TIPO_SISTEMA_PRISIONAL in tipos
        tem_cel = Modalidade.TIPO_CEL in tipos

        if tem_prisional and prof_ok:
            extra += 1
            explicacoes.append(
                CriterioExplicacao(
                    artigo="Art. 1º, §§ 1º a 3º",
                    descricao=(
                        "Há ensino no sistema prisional e foram informados pelo menos seis professores "
                        "dedicados à unidade."
                    ),
                    impactos=[f"+1 {coord_abrev} (coordenação)"],
                )
            )
        elif tem_casa and prof_ok:
            extra += 1
            explicacoes.append(
                CriterioExplicacao(
                    artigo="Art. 1º, §§ 1º a 3º",
                    descricao=(
                        "Há modalidade CASA e foram informados pelo menos seis professores dedicados à unidade."
                    ),
                    impactos=[f"+1 {coord_abrev} (coordenação)"],
                )
            )

        mat_cel = int(calculo.matricula_cel or 0)
        if tem_cel and mat_cel >= 200:
            extra += 1
            explicacoes.append(
                CriterioExplicacao(
                    artigo="Art. 1º, §§ 1º a 3º",
                    descricao=(
                        "Há modalidade CEL e o número de alunos informado para a CEL é pelo menos 200."
                    ),
                    impactos=[f"+1 {coord_abrev} (coordenação)"],
                )
            )

        return extra, explicacoes

    @staticmethod
    def _acrescimo_gestores_pei_parcial_diverso(
        n: int,
    ) -> tuple[tuple[int, int], list[CriterioExplicacao]]:
        """
        Art. 1º, § 6º — acréscimo para segmento tempo parcial em PEI com turno diverso.
        Retorna ((acréscimo em vice, acréscimo em CGP/CGPG), explicações).
        Distribuição padrão: prioriza Vice; excedente em coordenador pedagógico.
        """
        if n <= 100:
            return (0, 0), []
        if n <= 200:
            return (1, 0), [
                CriterioExplicacao(
                    artigo="Art. 1º, § 6º",
                    descricao=(
                        "PEI com turnos diferentes e parte dos alunos em tempo parcial; "
                        f"{CalculoModuloService._frase_faixa_matricula(101, 200)}"
                    ),
                    impactos=["+1 Vice-diretor"],
                )
            ]
        return (1, 1), [
            CriterioExplicacao(
                artigo="Art. 1º, § 6º",
                descricao=(
                    "PEI com turnos diferentes e parte dos alunos em tempo parcial; "
                    f"{CalculoModuloService._frase_faixa_matricula(201, None)}"
                ),
                impactos=["+1 Vice-diretor", "+1 CGP/CGPG"],
            )
        ]

    @staticmethod
    def _acrescimo_aoe_casa_prisional(
        calculo: CalculoModulo, tipos: set[int]
    ) -> tuple[int, list[CriterioExplicacao]]:
        """Art. 3º §§ 2º e 3º — +1 AOE; prisional não cumulativo com CASA."""
        prof_ok = int(calculo.professores_dedicados or 0) >= 6
        if Modalidade.TIPO_SISTEMA_PRISIONAL in tipos and prof_ok:
            return 1, [
                CriterioExplicacao(
                    artigo="Art. 3º, §§ 2º e 3º",
                    descricao=(
                        "Há ensino no sistema prisional e foram informados pelo menos seis professores "
                        "dedicados à unidade."
                    ),
                    impactos=["+1 AOE"],
                )
            ]
        if Modalidade.TIPO_CASA in tipos and prof_ok:
            return 1, [
                CriterioExplicacao(
                    artigo="Art. 3º, §§ 2º e 3º",
                    descricao=(
                        "Há modalidade CASA e foram informados pelo menos seis professores dedicados à unidade."
                    ),
                    impactos=["+1 AOE"],
                )
            ]
        return 0, []

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

    def _aoe(self, n: int, pei_nove_horas: bool) -> tuple[int, list[CriterioExplicacao]]:
        if pei_nove_horas:
            total = self._aoe_pei_nove_horas(n)
            return total, [
                CriterioExplicacao(
                    artigo="Art. 3º, § 1º",
                    descricao=self._desc_aoe_pei_nove_horas(n),
                    impactos=[f"{total} AOE"],
                )
            ]
        total = self._aoe_caput(n)
        return total, [
            CriterioExplicacao(
                artigo="Art. 3º, caput",
                descricao=self._desc_aoe_caput(n),
                impactos=[f"{total} AOE"],
            )
        ]

    def _ase(self, escola: Escola, n: int) -> tuple[int, list[CriterioExplicacao]]:
        """Art. 2º — ASE conforme merenda, limpeza, faixas e número de turnos."""
        explicacoes: list[CriterioExplicacao] = []
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
            explicacoes.append(
                CriterioExplicacao(
                    artigo="Art. 2º",
                    descricao=(
                        "Limpeza feita por empresa terceirizada e merenda terceirizada ou preparada na própria "
                        "escola (descentralizada); nessa combinação não há ASE neste cálculo."
                    ),
                    impactos=["0 ASE"],
                )
            )
            return 0, explicacoes

        art_paragrafo = ""
        descricao = ""
        if merenda == Escola.MERENDA_CENTRALIZADA and limpeza == Escola.LIMPEZA_CENTRALIZADA:
            base_sem_turno = self._ase_merenda_cent_limpeza_cent(n)
            art_paragrafo = "Art. 2º, § 1º"
            descricao = self._desc_ase_com_rubrica(
                "Merenda centralizada na escola e limpeza também centralizada",
                n,
                self._intervalo_ase_sec1_sec4,
            )
        elif merenda_terc_ou_desc and limpeza == Escola.LIMPEZA_CENTRALIZADA:
            base_sem_turno = self._ase_merenda_terc_desc_limpeza_cent(n)
            art_paragrafo = "Art. 2º, § 4º"
            descricao = self._desc_ase_com_rubrica(
                "Merenda terceirizada ou preparada na própria escola (descentralizada), com limpeza centralizada",
                n,
                self._intervalo_ase_sec1_sec4,
            )
        elif merenda == Escola.MERENDA_CENTRALIZADA and limpeza_terc:
            base_sem_turno = self._ase_merenda_cent_limpeza_terc(n)
            art_paragrafo = "Art. 2º, § 7º"
            descricao = self._desc_ase_com_rubrica(
                "Merenda centralizada na escola e limpeza feita por empresa terceirizada",
                n,
                self._intervalo_ase_sec7,
            )
        else:
            base_sem_turno = self._ase_merenda_cent_limpeza_cent(n)
            art_paragrafo = "Art. 2º, § 1º (combinado não previsto; aplicação da tabela § 1º)"
            descricao = (
                "A combinação informada de merenda e limpeza não aparece em um quadro próprio; "
                "por isso usamos o mesmo critério da merenda e limpeza centralizadas. "
                + self._desc_ase_com_rubrica(
                    "Merenda centralizada na escola e limpeza também centralizada",
                    n,
                    self._intervalo_ase_sec1_sec4,
                )
            )

        base = base_sem_turno
        explicacoes.append(
            CriterioExplicacao(
                artigo=art_paragrafo,
                descricao=descricao,
                impactos=[f"{base_sem_turno} ASE"],
            )
        )

        if turnos == 2:
            base += 1
            explicacoes.append(
                CriterioExplicacao(
                    artigo="Art. 2º",
                    descricao="A escola funciona em dois turnos; isso aumenta o ASE em uma vaga.",
                    impactos=["+1 ASE"],
                )
            )
        elif turnos == 3:
            base += 2
            explicacoes.append(
                CriterioExplicacao(
                    artigo="Art. 2º",
                    descricao="A escola funciona em três turnos; isso aumenta o ASE em duas vagas.",
                    impactos=["+2 ASE"],
                )
            )

        return base, explicacoes

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
