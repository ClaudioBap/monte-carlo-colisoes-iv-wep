"""
Geração das figuras do trabalho (matplotlib).

Convenções visuais, iguais em todas as figuras:
    - WEP (24 bits)  -> azul;  TKIP (48 bits) -> laranja
    - Teoria exata   -> linha contínua escura; aproximações -> tracejado
    - Simulação      -> marcadores com barras de erro (IC 95% de Wilson)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import numpy as np  # noqa: E402

COR_WEP = "#2a78d6"
COR_TKIP = "#eb6834"
COR_EXTRA = "#1baf7a"
COR_TEORIA = "#0b0b0b"
COR_TEXTO_2 = "#52514e"
COR_GRELHA = "#e4e3df"
COR_SUPERFICIE = "#ffffff"

plt.rcParams.update({
    "figure.facecolor": COR_SUPERFICIE,
    "axes.facecolor": COR_SUPERFICIE,
    "axes.edgecolor": COR_TEXTO_2,
    "axes.labelcolor": COR_TEORIA,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": COR_GRELHA,
    "grid.linewidth": 0.8,
    "xtick.color": COR_TEXTO_2,
    "ytick.color": COR_TEXTO_2,
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "legend.frameon": False,
    "lines.linewidth": 2.0,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})


def _formatar_milhares(ax, eixo="x"):
    fmt = mticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))
    (ax.xaxis if eixo == "x" else ax.yaxis).set_major_formatter(fmt)


def _cientifico(x: float) -> str:
    """Formata x como 'm,m × 10^e' em mathtext (ex.: 1,2 × 10⁷)."""
    e = int(np.floor(np.log10(x)))
    m = f"{x / 10 ** e:.1f}".replace(".", "{,}")  # {,} evita o espaço do mathtext
    return rf"${m} \times 10^{{{e}}}$"


def _guardar(fig, pasta: Path, nome: str) -> Path:
    caminho = pasta / nome
    fig.savefig(caminho)
    plt.close(fig)
    return caminho


def fig_wep_teoria_vs_simulacao(r, pasta: Path) -> Path:
    """P(n) do WEP: teoria exata, aproximação, método direto e CDF da 1.ª colisão."""
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(r["n_curva"], r["p_exata"], color=COR_TEORIA, label="Teoria exata  1 − ∏(1 − k/N)")
    ax.plot(r["n_curva"], r["p_aprox"], color=COR_TEXTO_2, ls="--", lw=1.4,
            label="Aproximação  1 − exp(−n(n−1)/2N)")
    ax.plot(r["n_curva"], r["p_cdf"], color=COR_EXTRA, lw=1.4,
            label=f"Simulação — 1.ª colisão (T = {r['ensaios_cdf']:,})".replace(",", " "))
    erro = np.vstack([r["p_direto"] - r["ic_inf"], r["ic_sup"] - r["p_direto"]])
    ax.errorbar(r["n_direto"], r["p_direto"], yerr=erro, fmt="o", ms=5.5, color=COR_WEP,
                mec=COR_SUPERFICIE, mew=1.0, capsize=2.5, elinewidth=1.2,
                label=f"Simulação — método direto (T = {r['ensaios_direto']:,} por ponto)".replace(",", " "),
                zorder=5)
    ax.axhline(0.5, color=COR_GRELHA, lw=1.2, zorder=0)
    ax.axvline(r["n50"], color=COR_TEXTO_2, lw=1.0, ls=":")
    ax.annotate(f"n = {r['n50']}  →  P ≈ 50%", xy=(r["n50"], 0.5), xytext=(r["n50"] + 900, 0.33),
                fontsize=9, color=COR_TEORIA,
                arrowprops=dict(arrowstyle="-", color=COR_TEXTO_2, lw=0.8))
    ax.set_xlim(0, r["n_curva"][-1])
    ax.set_ylim(0, 1.02)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    _formatar_milhares(ax)
    ax.set_xlabel("Número de pacotes transmitidos (n)")
    ax.set_ylabel("Probabilidade de ≥ 1 colisão de IV")
    ax.set_title("WEP (IV de 24 bits): probabilidade de colisão — teoria vs. Monte Carlo")
    ax.legend(loc="lower right", fontsize=8.5)
    return _guardar(fig, pasta, "fig1_wep_teoria_vs_simulacao.png")


def fig_wep_vs_tkip_log(r_wep, r_tkip, pasta: Path) -> Path:
    """Curvas WEP e TKIP em eixo logarítmico de n, com pontos simulados de ambos."""
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(r_wep["n_log"], r_wep["p_log"], color=COR_WEP, label="WEP — IV 24 bits (teoria)")
    ax.plot(r_tkip["n_log"], r_tkip["p_log"], color=COR_TKIP, label="TKIP — IV 48 bits (teoria)")
    ax.plot(r_wep["n_pts"], r_wep["p_pts"], "o", ms=6, color=COR_WEP, mec=COR_SUPERFICIE,
            label=f"WEP — simulação (T = {r_wep['ensaios']:,})".replace(",", " "))
    ax.plot(r_tkip["n_pts"], r_tkip["p_pts"], "s", ms=6, color=COR_TKIP, mec=COR_SUPERFICIE,
            label=f"TKIP — simulação (T = {r_tkip['ensaios']:,})".replace(",", " "))
    for r, cor in ((r_wep, COR_WEP), (r_tkip, COR_TKIP)):
        ax.axvline(r["n50"], color=cor, lw=1.0, ls=":")
    y = 0.62
    ax.annotate("", xy=(r_tkip["n50"], y), xytext=(r_wep["n50"], y),
                arrowprops=dict(arrowstyle="<->", color=COR_TEORIA, lw=1.0))
    ax.text(np.sqrt(r_wep["n50"] * r_tkip["n50"]), y + 0.04,
            f"× {r_tkip['n50'] / r_wep['n50']:,.0f} pacotes".replace(",", " "),
            ha="center", fontsize=9.5, color=COR_TEORIA)
    for r, cor in ((r_wep, COR_WEP), (r_tkip, COR_TKIP)):
        ax.text(r["n50"] * 1.3, 0.04, f"n₅₀ = {r['n50']:,}".replace(",", " "),
                ha="left", fontsize=8.5, color=cor)
    ax.axhline(0.5, color=COR_GRELHA, lw=1.2, zorder=0)
    ax.set_xscale("log")
    ax.set_ylim(0, 1.02)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_xlabel("Número de pacotes transmitidos (n, escala log)")
    ax.set_ylabel("Probabilidade de ≥ 1 colisão de IV")
    ax.set_title("WEP vs. TKIP: a mesma curva, deslocada 2¹² vezes para a direita")
    ax.legend(loc="upper left", fontsize=8.5)
    return _guardar(fig, pasta, "fig2_wep_vs_tkip_log.png")


def fig_mesmos_pacotes(r, pasta: Path) -> Path:
    """Mesmo número de pacotes: escala linear (a) e escala logarítmica de P (b)."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.6, 3.8))
    for ax in (a, b):
        ax.plot(r["n"], r["p_wep"], color=COR_WEP, label="WEP (24 bits)")
        ax.plot(r["n"], r["p_tkip"], color=COR_TKIP, label="TKIP (48 bits)")
        ax.set_xlim(0, r["n"][-1])
        ax.set_xlabel("Número de pacotes (n)")
        ax.set_xticks(np.arange(0, r["n"][-1] + 1, 3000))
        _formatar_milhares(ax)
    a.plot(r["n_sim"], r["p_sim_wep"], "o", ms=5, color=COR_WEP, mec=COR_SUPERFICIE)
    a.plot(r["n_sim"], r["p_sim_tkip"], "s", ms=5, color=COR_TKIP, mec=COR_SUPERFICIE,
           label=f"Simulação TKIP ({r['colisoes_tkip']} colisões)")
    a.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    a.set_ylabel("Probabilidade de colisão")
    a.set_title("(a) Escala linear")
    a.legend(loc="center right", fontsize=8.5)
    b.set_yscale("log")
    b.set_ylim(1e-10, 2)
    b.set_ylabel("Probabilidade de colisão (escala log)")
    b.set_title("(b) Escala logarítmica")
    idx = int(np.argmin(np.abs(r["n"] - r["n50_wep"])))
    b.annotate(f"em n = {r['n50_wep']}:\n" + r"$P_{\mathrm{WEP}}\,/\,P_{\mathrm{TKIP}}$ ≈ "
               + _cientifico(r["p_wep"][idx] / r["p_tkip"][idx]),
               xy=(r["n"][idx], np.sqrt(r["p_wep"][idx] * r["p_tkip"][idx])),
               xytext=(r["n"][idx] + 1500, 3e-5), fontsize=9, color=COR_TEORIA)
    b.vlines(r["n"][idx], r["p_tkip"][idx], r["p_wep"][idx], color=COR_TEXTO_2, lw=1.0, ls=":")
    fig.suptitle("Mesmo número de pacotes: o TKIP permanece praticamente imune a colisões",
                 x=0.01, ha="left", fontweight="bold", fontsize=11)
    fig.tight_layout()
    return _guardar(fig, pasta, "fig3_mesmos_pacotes.png")


def fig_distribuicao_primeira_colisao(r, pasta: Path) -> Path:
    """Histograma do índice da primeira colisão K (WEP) contra a pmf teórica."""
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    ax.hist(r["k"], bins=r["bins"], density=True, color=COR_WEP, alpha=0.55,
            edgecolor=COR_SUPERFICIE, linewidth=0.6, label="Simulação (histograma de K)")
    ax.plot(r["k_teo"], r["pmf_teo"], color=COR_TEORIA, label="Teoria  P(K = k)")
    ax.axvline(r["media_sim"], color=COR_WEP, lw=1.4, ls="--",
               label=f"Média simulada = {r['media_sim']:,.0f}".replace(",", " "))
    ax.axvline(r["media_teo"], color=COR_TEORIA, lw=1.0, ls=":",
               label=f"Média teórica √(πN/2)+2/3 = {r['media_teo']:,.0f}".replace(",", " "))
    ax.set_xlim(0, r["bins"][-1])
    _formatar_milhares(ax)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v * 1e4:.1f}".replace(".", ",")))
    ax.set_xlabel("Pacote em que ocorre a primeira colisão (K)")
    ax.set_ylabel("Densidade (×10⁻⁴)")
    ax.set_title("WEP: distribuição do instante da primeira colisão de IV")
    ax.legend(loc="upper right", fontsize=8.5)
    return _guardar(fig, pasta, "fig4_distribuicao_primeira_colisao.png")


def fig_convergencia(r, pasta: Path) -> Path:
    """(a) Estimativa acumulada com funil de ±1,96σ; (b) erro RMS vs. T (lei 1/√T)."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.6, 3.8))
    T = r["t_traj"]
    a.fill_between(T, r["p_ref"] - r["banda"], r["p_ref"] + r["banda"], color=COR_WEP, alpha=0.15,
                   lw=0, label="p ± 1,96·√(p(1−p)/T)")
    a.plot(T, r["traj"], color=COR_WEP, lw=1.4, label=r"Estimativa acumulada $\hat{P}(T)$")
    a.axhline(r["p_ref"], color=COR_TEORIA, lw=1.0, ls="--",
              label=f"Valor exato = {r['p_ref']:.4f}".replace(".", ","))
    a.set_xscale("log")
    a.set_ylim(0, 1)
    a.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    a.set_xlabel("Número de ensaios T (escala log)")
    a.set_ylabel(rf"$\hat{{P}}$(colisão) com n = {r['n']}")
    a.set_title("(a) Convergência de uma realização")
    a.legend(loc="lower right", fontsize=8.5)

    b.plot(r["t_grid"], r["rmse"], "o-", ms=6, color=COR_WEP, mec=COR_SUPERFICIE,
           label="Erro RMS medido")
    b.plot(r["t_grid"], r["rmse_teo"], color=COR_TEORIA, ls="--", lw=1.2,
           label="√(p(1−p)/T)  (declive −½)")
    b.set_xscale("log")
    b.set_yscale("log")
    b.set_xlabel("Número de ensaios T (escala log)")
    b.set_ylabel(r"Erro RMS de $\hat{P}$")
    b.set_title("(b) Erro de Monte Carlo ∝ 1/√T")
    b.legend(loc="upper right", fontsize=8.5)
    fig.tight_layout()
    return _guardar(fig, pasta, "fig5_convergencia.png")


def fig_escala_bits(r, pasta: Path) -> Path:
    """Mediana empírica de K (≈ n para 50%) em função do número de bits do IV."""
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    bits = np.array(r["bits"])
    ax.plot(bits, r["n50_teo"], color=COR_TEORIA, label="Teoria  n₅₀ ≈ 1,1774·2^(b/2)")
    ax.plot(bits, r["mediana_sim"], "o", ms=7, color=COR_EXTRA, mec=COR_SUPERFICIE,
            label="Simulação — mediana de K", zorder=5)
    for b_, cor, nome, desvio, ha in ((24, COR_WEP, "WEP", (12, -16), "left"),
                                      (48, COR_TKIP, "TKIP", (-14, 4), "right")):
        i = int(np.where(bits == b_)[0][0])
        ax.plot(b_, r["mediana_sim"][i], "o", ms=11, mfc="none", mec=cor, mew=2)
        ax.annotate(f"{nome}: mediana = {r['mediana_sim'][i]:,.0f}".replace(",", " "),
                    xy=(b_, r["mediana_sim"][i]), xytext=desvio, textcoords="offset points",
                    ha=ha, va="center", fontsize=9, color=cor, fontweight="bold")
    ax.set_yscale("log", base=2)
    ax.set_ylim(top=max(r["mediana_sim"].max(), r["n50_teo"].max()) * 6)  # espaço para o rótulo do TKIP
    ax.set_xticks(bits)
    ax.set_xlabel("Dimensão do IV (bits)")
    ax.set_ylabel("Pacotes para P(colisão) = 50%  (escala log₂)")
    ax.set_title("Lei de escala: cada 2 bits extra apenas duplicam n₅₀ (∝ √N)")
    ax.legend(loc="upper left", fontsize=8.5)
    return _guardar(fig, pasta, "fig6_escala_bits.png")
