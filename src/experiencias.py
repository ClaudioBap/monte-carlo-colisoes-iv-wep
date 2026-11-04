"""
Trabalho 6 — Simulação de Monte Carlo da probabilidade de colisão de IV no WEP.

Executa todas as experiências, grava resultados (JSON/CSV/NPY) e figuras.

Uso:
    python experiencias.py            # configuração completa (alguns minutos)
    python experiencias.py --rapido   # configuração reduzida, para testes

Experiências:
    E1  WEP (24 bits), método direto: fração de ensaios com colisão para vários n
    E2  WEP, método da primeira colisão: curva P(n) completa + distribuição de K
    E3  TKIP (48 bits), método da primeira colisão
    E4  WEP vs. TKIP para o mesmo número de pacotes (método direto)
    E5  Convergência do estimador de Monte Carlo (erro ∝ 1/√T)
    E6  Lei de escala: n para 50% em função do número de bits do IV
    E7  Validação do gerador pseudoaleatório (Philox vs. MT19937 vs. PCG64)
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

import graficos as G
import montecarlo as M
import teoria as T

RAIZ = Path(__file__).resolve().parent.parent
PASTA_FIG = RAIZ / "figuras"
PASTA_RES = RAIZ / "resultados"

SEMENTE = 20261031
BITS_WEP = 24
BITS_TKIP = 48

CONFIG = {
    "completo": {
        "ensaios_direto": 5000,
        "ensaios_cdf_wep": 200_000,
        "ensaios_cdf_tkip": 500,
        "ensaios_escala": {16: 20000, 20: 20000, 28: 20000, 32: 10000, 36: 5000, 40: 2000, 44: 1000},
        "ensaios_e7": 300_000,
    },
    "rapido": {
        "ensaios_direto": 1000,
        "ensaios_cdf_wep": 20_000,
        "ensaios_cdf_tkip": 40,
        "ensaios_escala": {16: 2000, 20: 2000, 28: 2000, 32: 1000, 36: 500, 40: 200, 44: 100},
        "ensaios_e7": 20_000,
    },
}

N_DIRETO = [500, 1000, 2000, 3000, 4000, 4823, 6000, 7000, 8000, 10000, 12000, 15000]


def _semente(etiqueta: int) -> int:
    """Semente determinística e distinta para cada experiência."""
    return SEMENTE * 100 + etiqueta


def _cronometrar(nome, func, *args, **kwargs):
    t0 = time.perf_counter()
    print(f"  > {nome} ...", flush=True)
    res = func(*args, **kwargs)
    dt = time.perf_counter() - t0
    print(f"    concluído em {dt:.1f} s", flush=True)
    return res, dt


def _para_json(obj):
    if isinstance(obj, dict):
        return {str(k): _para_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_para_json(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def _escrever_csv(caminho: Path, cabecalho, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cabecalho)
        w.writerows(linhas)


# --------------------------------------------------------------------------- #
# Experiências
# --------------------------------------------------------------------------- #
def e1_wep_direto(cfg):
    N = T.espaco_iv(BITS_WEP)
    rng = M.criar_gerador(_semente(1))
    ensaios = cfg["ensaios_direto"]
    linhas = []
    for n in N_DIRETO:
        c = M.simular_direto(BITS_WEP, n, ensaios, rng)
        inf, sup = M.intervalo_wilson(c, ensaios)
        linhas.append({
            "n": n, "colisoes": c, "ensaios": ensaios, "p_sim": c / ensaios,
            "ic95_inf": inf, "ic95_sup": sup,
            "p_exata": float(T.prob_colisao_exata(n, N)),
            "p_aprox_exp": float(T.prob_colisao_aprox_exp(n, N)),
        })
    return linhas


def e4_tkip_direto(cfg):
    rng = M.criar_gerador(_semente(4))
    ensaios = cfg["ensaios_direto"]
    N = T.espaco_iv(BITS_TKIP)
    return [{
        "n": n, "colisoes": M.simular_direto(BITS_TKIP, n, ensaios, rng), "ensaios": ensaios,
        "p_exata": float(T.prob_colisao_exata(n, N)),
    } for n in N_DIRETO]


def e5_convergencia(k_wep, n_ref):
    N = T.espaco_iv(BITS_WEP)
    p_ref = float(T.prob_colisao_exata(n_ref, N))
    ind = (k_wep <= n_ref).astype(np.float64)
    traj_completa = np.cumsum(ind) / np.arange(1, len(ind) + 1)
    t_traj = np.unique(np.geomspace(1, len(ind), 400).astype(int))
    t_grid = [10, 30, 100, 300, 1000, 3000, 10000]
    rmse = []
    for t in t_grid:
        g = len(ind) // t
        est = ind[: g * t].reshape(g, t).mean(axis=1)
        rmse.append(float(np.sqrt(np.mean((est - p_ref) ** 2))))
    return {
        "n": n_ref, "p_ref": p_ref,
        "t_traj": t_traj, "traj": traj_completa[t_traj - 1],
        "banda": 1.959964 * np.sqrt(p_ref * (1 - p_ref) / t_traj),
        "t_grid": t_grid, "rmse": rmse,
        "rmse_teo": [float(np.sqrt(p_ref * (1 - p_ref) / t)) for t in t_grid],
        "p_final": float(traj_completa[-1]), "ensaios": len(ind),
    }


def e6_escala(cfg, k_wep, k_tkip, processos):
    amostras = {BITS_WEP: k_wep, BITS_TKIP: k_tkip}
    tempos = {}
    for bits, ensaios in cfg["ensaios_escala"].items():
        amostras[bits], tempos[bits] = _cronometrar(
            f"E6: primeira colisão, {bits} bits, {ensaios} ensaios",
            M.amostrar_primeiras_colisoes, bits, ensaios, _semente(60 + bits), processos)
    bits_ord = sorted(amostras)
    linhas = []
    for b in bits_ord:
        N = T.espaco_iv(b)
        k = amostras[b]
        linhas.append({
            "bits": b, "ensaios": len(k),
            "mediana_sim": float(np.median(k)),
            "n50_exato": T.n_para_probabilidade_exato(0.5, N),
            "n50_aprox": T.n_para_probabilidade_aprox(0.5, N),
            "media_sim": float(np.mean(k)), "media_teo": T.media_primeira_colisao(N),
        })
    return linhas, tempos


def e7_validacao_gerador(cfg, processos):
    """
    Validação do gerador pseudoaleatório: repete o estimador por primeira colisão
    para o WEP com três bit generators diferentes (Philox, MT19937, PCG64) e
    compara a média de K e P(n50) com os valores exatos através do z-score.
    Inclui ainda um caso com N pequeno (10 bits), onde a pmf é exata e barata.
    """
    casos = [(10, cfg["ensaios_e7"] * 2, "philox")] + [(24, cfg["ensaios_e7"], g) for g in M.GERADORES]
    linhas = []
    for i, (bits, ensaios, gerador) in enumerate(casos):
        N = T.espaco_iv(bits)
        k = M.amostrar_primeiras_colisoes(bits, ensaios, _semente(70 + i), processos, gerador)
        ks = np.arange(1, 10 * int(np.sqrt(N)))
        media_exata = float(np.sum(ks * T.pmf_primeira_colisao(ks, N)))
        n50 = T.n_para_probabilidade_exato(0.5, N)
        p50 = float(T.prob_colisao_exata(n50, N))
        ph = float(np.mean(k <= n50))
        linhas.append({
            "bits": bits, "gerador": gerador, "ensaios": ensaios,
            "media_sim": float(k.mean()), "media_exata": media_exata,
            "z_media": float((k.mean() - media_exata) / (k.std(ddof=1) / np.sqrt(len(k)))),
            "n50": n50, "p_sim_n50": ph, "p_exata_n50": p50,
            "z_p": float((ph - p50) / np.sqrt(p50 * (1 - p50) / len(k))),
        })
    return linhas


def tabela_probabilidades(k_wep, k_tkip):
    N24, N48 = T.espaco_iv(BITS_WEP), T.espaco_iv(BITS_TKIP)
    n50_tkip = T.n_para_probabilidade_exato(0.5, N48)
    ns = [1000, 2000, 4823, 10000, 20000, 100_000, 1_000_000, n50_tkip, 50_000_000]
    p24 = T.prob_colisao_exata(ns, N24)
    p48 = T.prob_colisao_exata(ns, N48)
    s24 = M.cdf_empirica(k_wep, ns)
    s48 = M.cdf_empirica(k_tkip, ns)
    return [{"n": n, "p_wep_exata": float(a), "p_wep_sim": float(c),
             "p_tkip_exata": float(b), "p_tkip_sim": float(d)}
            for n, a, b, c, d in zip(ns, p24, p48, s24, s48)]


def tabela_aproximacoes():
    N = T.espaco_iv(BITS_WEP)
    linhas = []
    for n in [1000, 2000, 4823, 10000, 20000]:
        linhas.append({
            "n": n, "exata": float(T.prob_colisao_exata(n, N)),
            "aprox_exp": float(T.prob_colisao_aprox_exp(n, N)),
            "aprox_quad": float(T.prob_colisao_aprox_quadratica(n, N)),
        })
    return linhas


def tabela_tempos(n50_wep, n50_tkip):
    seg_ano = 365.25 * 24 * 3600
    linhas = []
    for taxa in [100, 500, 1000, 5000]:
        linhas.append({
            "taxa_pps": taxa,
            "wep_t50_s": n50_wep / taxa,
            "tkip_t50_h": n50_tkip / taxa / 3600,
            "wep_esgotar_h": 2 ** BITS_WEP / taxa / 3600,
            "tkip_esgotar_anos": 2 ** BITS_TKIP / taxa / seg_ano,
        })
    return linhas


def gerar_figuras(resultados, k_wep, k_tkip):
    """Gera todas as figuras a partir dos resultados (permite regenerá-las sem simular)."""
    N24, N48 = T.espaco_iv(BITS_WEP), T.espaco_iv(BITS_TKIP)
    resumo, e1, e4, e6 = (resultados[k] for k in ("resumo", "e1_wep_direto", "e4_tkip_direto", "e6_escala"))
    n50_wep, n50_tkip = resumo["wep"]["n50_exato"], resumo["tkip"]["n50_exato"]
    e5 = e5_convergencia(k_wep, n50_wep)

    n_curva = np.arange(0, 15001, 25)
    G.fig_wep_teoria_vs_simulacao({
        "n_curva": n_curva,
        "p_exata": T.prob_colisao_exata(n_curva, N24),
        "p_aprox": T.prob_colisao_aprox_exp(n_curva, N24),
        "p_cdf": M.cdf_empirica(k_wep, n_curva), "ensaios_cdf": len(k_wep),
        "n_direto": np.array([l["n"] for l in e1]),
        "p_direto": np.array([l["p_sim"] for l in e1]),
        "ic_inf": np.array([l["ic95_inf"] for l in e1]),
        "ic_sup": np.array([l["ic95_sup"] for l in e1]),
        "ensaios_direto": e1[0]["ensaios"], "n50": n50_wep,
    }, PASTA_FIG)

    n_log_wep = np.unique(np.geomspace(10, 1e5, 300).astype(int))
    n_log_tkip = np.unique(np.geomspace(1e4, 2e8, 300).astype(int))
    n_pts_wep = np.unique(np.geomspace(800, 15000, 9).astype(int))
    n_pts_tkip = np.unique(np.geomspace(5e6, 6e7, 8).astype(int))
    G.fig_wep_vs_tkip_log(
        {"n_log": n_log_wep, "p_log": T.prob_colisao_exata(n_log_wep, N24),
         "n_pts": n_pts_wep, "p_pts": M.cdf_empirica(k_wep, n_pts_wep),
         "ensaios": len(k_wep), "n50": n50_wep},
        {"n_log": n_log_tkip, "p_log": T.prob_colisao_exata(n_log_tkip, N48),
         "n_pts": n_pts_tkip, "p_pts": M.cdf_empirica(k_tkip, n_pts_tkip),
         "ensaios": len(k_tkip), "n50": n50_tkip},
        PASTA_FIG)

    n_lin = np.arange(1, 15001, 25)
    G.fig_mesmos_pacotes({
        "n": n_lin, "p_wep": T.prob_colisao_exata(n_lin, N24), "p_tkip": T.prob_colisao_exata(n_lin, N48),
        "n_sim": np.array(N_DIRETO), "p_sim_wep": np.array([l["p_sim"] for l in e1]),
        "p_sim_tkip": np.array([l["colisoes"] / l["ensaios"] for l in e4]), "n50_wep": n50_wep,
        "colisoes_tkip": sum(l["colisoes"] for l in e4),
    }, PASTA_FIG)

    k_teo = np.arange(1, 16001)
    G.fig_distribuicao_primeira_colisao({
        "k": k_wep, "bins": np.arange(0, 16001, 400),
        "k_teo": k_teo, "pmf_teo": T.pmf_primeira_colisao(k_teo, N24),
        "media_sim": resumo["wep"]["media_k_sim"], "media_teo": resumo["wep"]["media_k_teo"],
    }, PASTA_FIG)

    G.fig_convergencia(e5, PASTA_FIG)
    G.fig_escala_bits({
        "bits": [l["bits"] for l in e6],
        "mediana_sim": np.array([l["mediana_sim"] for l in e6]),
        "n50_teo": np.array([l["n50_exato"] for l in e6]),
    }, PASTA_FIG)


# --------------------------------------------------------------------------- #
# Programa principal
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rapido", action="store_true", help="configuração reduzida (teste)")
    ap.add_argument("--processos", type=int, default=None, help="n.º de processos (omissão: n.º de CPUs)")
    ap.add_argument("--so-figuras", action="store_true",
                    help="regenera as figuras a partir de resultados/ sem voltar a simular")
    args = ap.parse_args()
    if args.so_figuras:
        with open(PASTA_RES / "resultados.json", encoding="utf-8") as f:
            resultados = json.load(f)
        gerar_figuras(resultados, np.load(PASTA_RES / "amostras_k_wep.npy"),
                      np.load(PASTA_RES / "amostras_k_tkip.npy"))
        print(f"Figuras regeneradas em {PASTA_FIG}")
        return
    cfg = CONFIG["rapido" if args.rapido else "completo"]
    PASTA_FIG.mkdir(exist_ok=True)
    PASTA_RES.mkdir(exist_ok=True)

    N24, N48 = T.espaco_iv(BITS_WEP), T.espaco_iv(BITS_TKIP)
    tempos = {}
    t_inicio = time.perf_counter()
    print(f"Trabalho 6 — Monte Carlo de colisões de IV  (modo: {'rápido' if args.rapido else 'completo'})")

    # Valores teóricos de referência
    n50_wep = T.n_para_probabilidade_exato(0.5, N24)
    n50_tkip = T.n_para_probabilidade_exato(0.5, N48)

    e1, tempos["E1"] = _cronometrar("E1: WEP, método direto", e1_wep_direto, cfg)
    k_wep, tempos["E2"] = _cronometrar(
        f"E2: WEP, primeira colisão ({cfg['ensaios_cdf_wep']} ensaios)",
        M.amostrar_primeiras_colisoes, BITS_WEP, cfg["ensaios_cdf_wep"], _semente(2), args.processos)
    k_tkip, tempos["E3"] = _cronometrar(
        f"E3: TKIP, primeira colisão ({cfg['ensaios_cdf_tkip']} ensaios)",
        M.amostrar_primeiras_colisoes, BITS_TKIP, cfg["ensaios_cdf_tkip"], _semente(3), args.processos)
    e4, tempos["E4"] = _cronometrar("E4: TKIP com o mesmo n.º de pacotes, método direto", e4_tkip_direto, cfg)
    e5, tempos["E5"] = _cronometrar("E5: convergência", e5_convergencia, k_wep, n50_wep)
    (e6, tempos_e6), tempos["E6"] = _cronometrar("E6: lei de escala", e6_escala, cfg, k_wep, k_tkip, args.processos)
    e7, tempos["E7"] = _cronometrar("E7: validação do gerador", e7_validacao_gerador, cfg, args.processos)

    np.save(PASTA_RES / "amostras_k_wep.npy", k_wep)
    np.save(PASTA_RES / "amostras_k_tkip.npy", k_tkip)

    # Estatísticas-chave
    c_wep = int(np.count_nonzero(k_wep <= n50_wep))
    c_tkip = int(np.count_nonzero(k_tkip <= n50_tkip))
    resumo = {
        "semente": SEMENTE, "gerador": M.GERADOR_PADRAO, "modo": "rapido" if args.rapido else "completo",
        "wep": {
            "bits": BITS_WEP, "N": N24, "n50_exato": n50_wep,
            "n50_aprox": T.n_para_probabilidade_aprox(0.5, N24),
            "p_exata_4823": float(T.prob_colisao_exata(4823, N24)),
            "p_aprox_4823": float(T.prob_colisao_aprox_exp(4823, N24)),
            "p_sim_direto_4823": next(l["p_sim"] for l in e1 if l["n"] == 4823),
            "ic95_direto_4823": next((l["ic95_inf"], l["ic95_sup"]) for l in e1 if l["n"] == 4823),
            "p_sim_cdf_4823": c_wep / len(k_wep),
            "ic95_cdf_4823": M.intervalo_wilson(c_wep, len(k_wep)),
            "ensaios_cdf": len(k_wep),
            "mediana_k": float(np.median(k_wep)),
            "media_k_sim": float(np.mean(k_wep)), "media_k_teo": T.media_primeira_colisao(N24),
            "dp_k_sim": float(np.std(k_wep, ddof=1)), "dp_k_teo": T.desvio_padrao_primeira_colisao(N24),
            "min_k": int(k_wep.min()), "max_k": int(k_wep.max()),
        },
        "tkip": {
            "bits": BITS_TKIP, "N": N48, "n50_exato": n50_tkip,
            "n50_aprox": T.n_para_probabilidade_aprox(0.5, N48),
            "p_exata_4823": float(T.prob_colisao_exata(4823, N48)),
            "p_exata_n50": float(T.prob_colisao_exata(n50_tkip, N48)),
            "p_sim_cdf_n50": c_tkip / len(k_tkip),
            "ic95_cdf_n50": M.intervalo_wilson(c_tkip, len(k_tkip)),
            "ensaios_cdf": len(k_tkip),
            "mediana_k": float(np.median(k_tkip)),
            "media_k_sim": float(np.mean(k_tkip)), "media_k_teo": T.media_primeira_colisao(N48),
            "colisoes_mesmos_pacotes": sum(l["colisoes"] for l in e4),
            "ensaios_mesmos_pacotes": sum(l["ensaios"] for l in e4),
        },
        "razao_n50": n50_tkip / n50_wep,
        "razao_teorica": 2 ** ((BITS_TKIP - BITS_WEP) / 2),
        "razao_p_4823": float(T.prob_colisao_exata(4823, N24) / T.prob_colisao_exata(4823, N48)),
    }

    resultados = {
        "resumo": resumo,
        "e1_wep_direto": e1,
        "e4_tkip_direto": e4,
        "e5_convergencia": {k: e5[k] for k in ("n", "p_ref", "t_grid", "rmse", "rmse_teo", "p_final", "ensaios")},
        "e6_escala": e6,
        "e7_validacao_gerador": e7,
        "tabela_probabilidades": tabela_probabilidades(k_wep, k_tkip),
        "tabela_aproximacoes": tabela_aproximacoes(),
        "tabela_tempos": tabela_tempos(n50_wep, n50_tkip),
        "tempos_execucao_s": {**tempos, "E6_por_bits": tempos_e6},
    }

    print("  > a gerar figuras ...", flush=True)
    gerar_figuras(resultados, k_wep, k_tkip)

    # ---------------------------------------------------------------- gravação
    resultados["tempos_execucao_s"]["total"] = time.perf_counter() - t_inicio
    with open(PASTA_RES / "resultados.json", "w", encoding="utf-8") as f:
        json.dump(_para_json(resultados), f, indent=2, ensure_ascii=False)
    _escrever_csv(PASTA_RES / "e1_wep_metodo_direto.csv",
                  ["n", "colisoes", "ensaios", "p_sim", "ic95_inf", "ic95_sup", "p_exata", "p_aprox_exp"],
                  [[l[k] for k in ("n", "colisoes", "ensaios", "p_sim", "ic95_inf", "ic95_sup",
                                   "p_exata", "p_aprox_exp")] for l in e1])
    _escrever_csv(PASTA_RES / "e6_lei_de_escala.csv",
                  ["bits", "ensaios", "mediana_sim", "n50_exato", "media_sim", "media_teo"],
                  [[l[k] for k in ("bits", "ensaios", "mediana_sim", "n50_exato", "media_sim", "media_teo")]
                   for l in e6])

    # ------------------------------------------------------------------ resumo
    w, t = resumo["wep"], resumo["tkip"]
    print("\n================ RESUMO ================")
    print(f"WEP  n50 exato = {w['n50_exato']}  (aprox. {w['n50_aprox']:.1f})")
    print(f"WEP  P(4823): exata {w['p_exata_4823']:.4%} | direto {w['p_sim_direto_4823']:.2%} "
          f"IC95 [{w['ic95_direto_4823'][0]:.2%}, {w['ic95_direto_4823'][1]:.2%}] | "
          f"1.ª colisão {w['p_sim_cdf_4823']:.2%}")
    print(f"WEP  E[K]: sim {w['media_k_sim']:.1f} | teo {w['media_k_teo']:.1f}")
    print(f"TKIP n50 exato = {t['n50_exato']}  | mediana sim {t['mediana_k']:.0f}")
    print(f"TKIP P(n50): sim {t['p_sim_cdf_n50']:.2%} IC95 [{t['ic95_cdf_n50'][0]:.2%}, {t['ic95_cdf_n50'][1]:.2%}]")
    print(f"TKIP P(4823) exata = {t['p_exata_4823']:.3e}; colisões simuladas com os mesmos pacotes: "
          f"{t['colisoes_mesmos_pacotes']}/{t['ensaios_mesmos_pacotes']}")
    print(f"Razão n50 TKIP/WEP = {resumo['razao_n50']:.1f}  (teórica 2^12 = {resumo['razao_teorica']:.0f})")
    for l in e7:
        print(f"E7   {l['bits']} bits, {l['gerador']:8s}: z(média K) = {l['z_media']:+.2f}, z(P(n50)) = {l['z_p']:+.2f}")
    print(f"Tempo total: {resultados['tempos_execucao_s']['total']:.1f} s")


if __name__ == "__main__":
    main()
