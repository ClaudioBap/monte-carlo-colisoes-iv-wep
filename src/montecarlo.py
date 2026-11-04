"""
Motor de simulação de Monte Carlo para colisões de IV.

Modelo: cada pacote usa um IV sorteado de forma uniforme e independente no
espaço {0, ..., 2^b - 1}. Há colisão quando dois pacotes partilham o mesmo IV
(e, portanto, a mesma chave RC4 de sessão no WEP).

São implementados dois estimadores, que medem a mesma grandeza por caminhos
diferentes e servem de validação cruzada um do outro:

1. Método direto (o do enunciado): para um n fixo, repetem-se T ensaios
   independentes, cada um com n IVs, e conta-se a fração de ensaios em que
   ocorreu pelo menos uma colisão.

2. Método da primeira colisão: em cada ensaio geram-se IVs até à primeira
   repetição e regista-se o índice K em que ela ocorre. Como
   "há colisão em n pacotes" <=> K <= n, a função de distribuição empírica
   de K dá P(n) para todos os n de uma só vez.
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

# Limite de elementos por lote no método direto (~32 MB em uint64).
_ELEMENTOS_POR_LOTE = 4_000_000

# Geradores pseudoaleatórios disponíveis. O Philox (gerador baseado em contador,
# pensado para fluxos paralelos) é o usado nos resultados finais; os outros
# servem para a validação cruzada do gerador (experiência E7).
GERADORES = {"philox": np.random.Philox, "mt19937": np.random.MT19937, "pcg64": np.random.PCG64}
GERADOR_PADRAO = "philox"


def criar_gerador(semente, nome: str = GERADOR_PADRAO) -> np.random.Generator:
    """Gerador NumPy com o bit generator `nome`, inicializado com `semente`."""
    return np.random.Generator(GERADORES[nome](semente))


# --------------------------------------------------------------------------- #
# Estatística auxiliar
# --------------------------------------------------------------------------- #
def intervalo_wilson(sucessos: int, ensaios: int, z: float = 1.959964):
    """Intervalo de confiança de Wilson (95% por omissão) para uma proporção."""
    if ensaios == 0:
        return (0.0, 1.0)
    p = sucessos / ensaios
    den = 1.0 + z * z / ensaios
    centro = (p + z * z / (2 * ensaios)) / den
    meia = z * math.sqrt(p * (1 - p) / ensaios + z * z / (4 * ensaios * ensaios)) / den
    return (max(0.0, centro - meia), min(1.0, centro + meia))


# --------------------------------------------------------------------------- #
# Método 1: estimador direto para um n fixo
# --------------------------------------------------------------------------- #
def simular_direto(bits: int, n: int, ensaios: int, rng: np.random.Generator) -> int:
    """
    Devolve o número de ensaios (de um total de `ensaios`) em que n IVs
    aleatórios de `bits` bits contêm pelo menos uma colisão.

    Os ensaios são processados em lotes vetorizados: cada linha de uma matriz
    (lote x n) é um ensaio; ordena-se cada linha e procuram-se vizinhos iguais.
    """
    N = 2 ** bits
    linhas_por_lote = max(1, _ELEMENTOS_POR_LOTE // max(n, 1))
    com_colisao = 0
    restantes = ensaios
    while restantes > 0:
        b = min(linhas_por_lote, restantes)
        ivs = rng.integers(0, N, size=(b, n), dtype=np.uint64)
        ivs.sort(axis=1)
        com_colisao += int(np.count_nonzero(np.any(ivs[:, 1:] == ivs[:, :-1], axis=1)))
        restantes -= b
    return com_colisao


# --------------------------------------------------------------------------- #
# Método 2: índice da primeira colisão
# --------------------------------------------------------------------------- #
def primeira_colisao(bits: int, rng: np.random.Generator, fator: float = 3.0) -> int:
    """
    Gera IVs até ocorrer a primeira repetição e devolve o seu índice K (1-based).

    Em vez de inserir IVs um a um num conjunto (lento em Python), gera-se de uma
    vez um bloco de comprimento L = fator*sqrt(N), que contém uma colisão com
    probabilidade 1 - exp(-fator^2/2) (~98,9% para fator=3). Se não contiver,
    o bloco é prolongado — o resultado continua exato, só fica mais caro.

    Para localizar a primeira colisão sem um argsort completo (caro para 2^48):
      1) ordena-se uma cópia e extraem-se os valores repetidos (poucos);
      2) localizam-se as posições originais desses valores;
      3) percorrem-se essas posições por ordem: a primeira cujo valor já
         apareceu antes é a primeira colisão.
    """
    N = 2 ** bits
    L = int(fator * math.sqrt(N)) + 2
    ivs = rng.integers(0, N, size=L, dtype=np.uint64)
    while True:
        ordenados = np.sort(ivs)
        repetidos = ordenados[1:][ordenados[1:] == ordenados[:-1]]
        if repetidos.size:
            break
        ivs = np.concatenate([ivs, rng.integers(0, N, size=L, dtype=np.uint64)])

    # Há tipicamente poucos valores repetidos (~fator²/2), pelo que comparações
    # diretas são muito mais rápidas do que np.isin (que recorre a um argsort).
    mascara = np.zeros(ivs.size, dtype=bool)
    for valor in np.unique(repetidos):
        mascara |= ivs == valor
    posicoes = np.flatnonzero(mascara)
    vistos = set()
    for pos, valor in zip(posicoes.tolist(), ivs[posicoes].tolist()):
        if valor in vistos:
            return pos + 1
        vistos.add(valor)
    raise RuntimeError("inconsistência: valores repetidos sem segunda ocorrência")


def _tarefa_primeiras_colisoes(args) -> np.ndarray:
    bits, ensaios, semente, gerador = args
    rng = criar_gerador(semente, gerador)
    return np.array([primeira_colisao(bits, rng) for _ in range(ensaios)], dtype=np.int64)


def amostrar_primeiras_colisoes(
    bits: int, ensaios: int, semente: int, processos: int | None = None, gerador: str = GERADOR_PADRAO
) -> np.ndarray:
    """
    Executa `ensaios` ensaios independentes do método da primeira colisão,
    distribuídos por vários processos.

    Cada tarefa recebe uma semente filha de numpy.random.SeedSequence, o que
    garante fluxos aleatórios independentes entre processos e resultados
    reprodutíveis para a mesma semente-mãe.
    """
    processos = processos or os.cpu_count() or 1
    n_tarefas = min(ensaios, processos * 4)
    base, resto = divmod(ensaios, n_tarefas)
    tamanhos = [base + (1 if i < resto else 0) for i in range(n_tarefas)]
    sementes = np.random.SeedSequence(semente).spawn(n_tarefas)
    tarefas = [(bits, t, s, gerador) for t, s in zip(tamanhos, sementes)]

    if processos == 1:
        partes = [_tarefa_primeiras_colisoes(t) for t in tarefas]
    else:
        with ProcessPoolExecutor(max_workers=processos) as ex:
            partes = list(ex.map(_tarefa_primeiras_colisoes, tarefas))
    return np.concatenate(partes)


def cdf_empirica(amostras_k: np.ndarray, ns) -> np.ndarray:
    """P_hat(n) = fração de ensaios com K <= n (colisão nos primeiros n pacotes)."""
    ordenadas = np.sort(amostras_k)
    return np.searchsorted(ordenadas, np.asarray(ns), side="right") / len(ordenadas)
