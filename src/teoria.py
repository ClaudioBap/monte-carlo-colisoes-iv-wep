"""
Modelos teóricos para a probabilidade de colisão de IV (problema do aniversário).

Notação usada em todo o projeto:
    N  -> dimensão do espaço de IVs (2^b, com b = número de bits do IV)
    n  -> número de pacotes transmitidos (IVs gerados)

Probabilidade exata de pelo menos uma colisão entre n IVs uniformes e independentes:

    P(n) = 1 - prod_{k=0}^{n-1} (1 - k/N)

O produto é avaliado em domínio logarítmico (soma de log1p(-k/N)) para evitar
underflow e perda de precisão quando N é muito grande (ex.: 2^48).
"""

from __future__ import annotations

import math

import numpy as np

# Dimensão dos blocos usados na soma em streaming (limita a memória a ~32 MB).
_CHUNK = 4_000_000


def espaco_iv(bits: int) -> int:
    """Número de IVs distintos para um IV de `bits` bits."""
    return 2 ** bits


def log_prob_sem_colisao(ns, N: int) -> np.ndarray:
    """
    log P(nenhuma colisão em n pacotes) = sum_{k=1}^{n-1} log1p(-k/N), exato.

    Aceita um escalar ou um vetor de valores de n (em qualquer ordem). A soma é
    acumulada uma única vez, por blocos, até ao maior n pedido, pelo que o custo
    é O(max(n)) independentemente de quantos pontos se avaliam.
    """
    ns_arr = np.atleast_1d(np.asarray(ns, dtype=np.int64))
    if np.any(ns_arr < 0):
        raise ValueError("n tem de ser >= 0")

    ordem = np.argsort(ns_arr)
    alvo = ns_arr[ordem]
    resultado = np.empty(len(alvo), dtype=np.float64)

    acumulado = 0.0  # soma de log1p(-k/N) para k = 1 .. k_atual-1
    k_atual = 1
    i = 0
    while i < len(alvo):
        n = int(alvo[i])
        if n > N:
            # Princípio do pombal: com mais pacotes do que IVs a colisão é certa.
            resultado[i:] = -np.inf
            break
        # Avançar a soma até k = n-1, em blocos.
        while k_atual < n:
            fim = min(n, k_atual + _CHUNK)
            k = np.arange(k_atual, fim, dtype=np.float64)
            # np.sum usa soma pairwise: erro relativo ~ eps*log2(n), desprezável aqui.
            acumulado += float(np.sum(np.log1p(-k / N)))
            k_atual = fim
        resultado[i] = acumulado
        i += 1

    saida = np.empty_like(resultado)
    saida[ordem] = resultado
    return saida if np.ndim(ns) else saida[0]


def prob_colisao_exata(ns, N: int):
    """P(n) = 1 - prod (1 - k/N): fórmula exata do aniversário generalizado."""
    return -np.expm1(log_prob_sem_colisao(ns, N))


def prob_colisao_aprox_exp(ns, N: int):
    """Aproximação exponencial clássica: P(n) ~ 1 - exp(-n(n-1) / 2N)."""
    n = np.asarray(ns, dtype=np.float64)
    return -np.expm1(-n * (n - 1) / (2.0 * N))


def prob_colisao_aprox_quadratica(ns, N: int):
    """Majorante de Boole (union bound): P(n) <= n(n-1) / 2N. Só útil para P pequeno."""
    n = np.asarray(ns, dtype=np.float64)
    return n * (n - 1) / (2.0 * N)


def n_para_probabilidade_aprox(p: float, N: int) -> float:
    """Inversão da aproximação exponencial: n ~ sqrt(2 N ln(1/(1-p)))."""
    return math.sqrt(2.0 * N * math.log(1.0 / (1.0 - p)))


def n_para_probabilidade_exato(p: float, N: int) -> int:
    """
    Menor n tal que P(n) >= p, usando a fórmula exata.

    Faz pesquisa binária numa janela à volta da aproximação analítica; a função
    P(n) é monótona crescente em n, pelo que a pesquisa é correta.
    """
    aprox = n_para_probabilidade_aprox(p, N)
    lo = max(1, int(aprox * 0.9))
    hi = int(aprox * 1.1) + 2
    while prob_colisao_exata(lo, N) >= p:
        lo = max(1, lo // 2)
    while prob_colisao_exata(hi, N) < p:
        hi *= 2
    while hi - lo > 1:
        meio = (lo + hi) // 2
        if prob_colisao_exata(meio, N) >= p:
            hi = meio
        else:
            lo = meio
    return hi


def pmf_primeira_colisao(ks, N: int) -> np.ndarray:
    """
    P(K = k): probabilidade de a primeira colisão ocorrer exatamente no pacote k.

    K = k  <=>  os primeiros k-1 IVs são distintos e o k-ésimo repete um deles:
        P(K = k) = P(sem colisão em k-1) * (k-1)/N
    """
    ks = np.asarray(ks, dtype=np.int64)
    return np.exp(log_prob_sem_colisao(ks - 1, N)) * (ks - 1) / N


def media_primeira_colisao(N: int) -> float:
    """E[K] ~ sqrt(pi N / 2) + 2/3 (expansão assintótica de Ramanujan/Knuth)."""
    return math.sqrt(math.pi * N / 2.0) + 2.0 / 3.0


def desvio_padrao_primeira_colisao(N: int) -> float:
    """sd[K] ~ sqrt((2 - pi/2) N)."""
    return math.sqrt((2.0 - math.pi / 2.0) * N)
