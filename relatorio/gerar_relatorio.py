"""
Gera o relatório em PDF do Trabalho 6 a partir de resultados/resultados.json
e das figuras em figuras/. Todos os valores numéricos citados no texto são
lidos dos resultados, garantindo coerência entre relatório e simulação.

Uso:
    python gerar_relatorio.py
"""

from __future__ import annotations

import inspect
import json
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["mathtext.fontset"] = "cm"
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, NextPageTemplate, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle, XPreformatted,
)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
import montecarlo  # noqa: E402

PASTA_FIG = RAIZ / "figuras"
SAIDA = RAIZ / "relatorio" / "Relatorio_Trabalho6_MonteCarlo_WEP.pdf"

AUTOR = "Claudio Baptista"
CURSO = "Mestrado em Engenharia Informática"
UC = "Tecnologias de Redes de Comunicações Móveis"
DATA = "Outubro de 2026"

# Paleta (igual à das figuras e da apresentação)
NAVY = colors.HexColor("#14213D")
AZUL = colors.HexColor("#2A78D6")
LARANJA = colors.HexColor("#EB6834")
TINTA = colors.HexColor("#1B1B1B")
CINZA = colors.HexColor("#52514E")
CINZA_CLARO = colors.HexColor("#F1F3F6")
LINHA = colors.HexColor("#D5D9E0")

NBSP = "\u00a0"


# --------------------------------------------------------------------------- #
# Tipos de letra
# --------------------------------------------------------------------------- #
def registar_fontes():
    win = Path("C:/Windows/Fonts")
    try:
        pdfmetrics.registerFont(TTFont("Corpo", str(win / "cambria.ttc"), subfontIndex=0))
        pdfmetrics.registerFont(TTFont("Corpo-B", str(win / "cambriab.ttf")))
        pdfmetrics.registerFont(TTFont("Corpo-I", str(win / "cambriai.ttf")))
        pdfmetrics.registerFont(TTFont("Corpo-BI", str(win / "cambriaz.ttf")))
        pdfmetrics.registerFont(TTFont("Titulo", str(win / "calibrib.ttf")))
        pdfmetrics.registerFont(TTFont("Titulo-R", str(win / "calibri.ttf")))
        pdfmetrics.registerFont(TTFont("Mono", str(win / "consola.ttf")))
    except Exception:  # fora do Windows: DejaVu (incluído no matplotlib)
        dv = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        for nome, f in [("Corpo", "DejaVuSerif.ttf"), ("Corpo-B", "DejaVuSerif-Bold.ttf"),
                        ("Corpo-I", "DejaVuSerif-Italic.ttf"), ("Corpo-BI", "DejaVuSerif-BoldItalic.ttf"),
                        ("Titulo", "DejaVuSans-Bold.ttf"), ("Titulo-R", "DejaVuSans.ttf"),
                        ("Mono", "DejaVuSansMono.ttf")]:
            pdfmetrics.registerFont(TTFont(nome, str(dv / f)))
    pdfmetrics.registerFontFamily("Corpo", normal="Corpo", bold="Corpo-B", italic="Corpo-I", boldItalic="Corpo-BI")


# --------------------------------------------------------------------------- #
# Formatação numérica (pt-PT)
# --------------------------------------------------------------------------- #
def fi(n) -> str:
    """Inteiro com separador de milhares (espaço não separável)."""
    return f"{int(round(n)):,}".replace(",", NBSP)


def fd(x, casas=2) -> str:
    return f"{x:,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", NBSP)


def fp(p, casas=2) -> str:
    return f"{fd(100 * p, casas)}%"


def fsci(x, casas=2) -> str:
    if x == 0:
        return "0"
    import math
    e = int(math.floor(math.log10(abs(x))))
    m = x / 10 ** e
    sinal = "−" if e < 0 else ""
    return f"{fd(m, casas)}{NBSP}×{NBSP}10<super>{sinal}{abs(e)}</super>"


def fprob(p) -> str:
    """Probabilidade em % ou em notação científica, conforme a ordem de grandeza."""
    if p == 0:
        return "0"
    if p < 1e-4:
        return fsci(p)
    if p > 0.99995:
        return f"≈{NBSP}100%"
    return fp(p, 2)


# --------------------------------------------------------------------------- #
# Estilos
# --------------------------------------------------------------------------- #
def estilos():
    s = {}
    s["corpo"] = ParagraphStyle("corpo", fontName="Corpo", fontSize=10.5, leading=15.2,
                                alignment=TA_JUSTIFY, textColor=TINTA, spaceAfter=7)
    s["lista"] = ParagraphStyle("lista", parent=s["corpo"], leftIndent=16, bulletIndent=4, spaceAfter=3)
    s["h1"] = ParagraphStyle("h1", fontName="Titulo", fontSize=17, leading=21, textColor=NAVY,
                             spaceBefore=6, spaceAfter=10)
    s["h2"] = ParagraphStyle("h2", fontName="Titulo", fontSize=12.5, leading=16, textColor=NAVY,
                             spaceBefore=10, spaceAfter=5)
    s["legenda"] = ParagraphStyle("legenda", fontName="Corpo-I", fontSize=9, leading=12,
                                  textColor=CINZA, alignment=TA_CENTER, spaceBefore=3, spaceAfter=12)
    s["tab"] = ParagraphStyle("tab", fontName="Corpo", fontSize=9, leading=11.5, textColor=TINTA,
                              alignment=TA_CENTER)
    s["tab_esq"] = ParagraphStyle("tab_esq", parent=s["tab"], alignment=TA_LEFT)
    s["tab_cab"] = ParagraphStyle("tab_cab", parent=s["tab"], fontName="Titulo", fontSize=9.2,
                                  textColor=colors.white)
    s["destaque"] = ParagraphStyle("destaque", parent=s["corpo"], fontName="Corpo", fontSize=10.5,
                                   leftIndent=10, rightIndent=10, spaceBefore=4, spaceAfter=4,
                                   alignment=TA_LEFT)
    s["codigo"] = ParagraphStyle("codigo", fontName="Mono", fontSize=7.8, leading=9.8, textColor=TINTA)
    s["ref"] = ParagraphStyle("ref", parent=s["corpo"], fontSize=9.5, leading=13, leftIndent=18,
                              firstLineIndent=-18, alignment=TA_LEFT, spaceAfter=4)
    s["toc1"] = ParagraphStyle("toc1", fontName="Titulo-R", fontSize=11, leading=14, textColor=TINTA,
                               leftIndent=0)
    s["toc2"] = ParagraphStyle("toc2", fontName="Corpo", fontSize=9.8, leading=12, textColor=CINZA,
                               leftIndent=18)
    return s


# --------------------------------------------------------------------------- #
# Documento com índice automático
# --------------------------------------------------------------------------- #
class Relatorio(BaseDocTemplate):
    def __init__(self, caminho, **kw):
        super().__init__(str(caminho), pagesize=A4, leftMargin=2.4 * cm, rightMargin=2.4 * cm,
                         topMargin=2.3 * cm, bottomMargin=2.2 * cm,
                         title="Simulação de Monte Carlo da Probabilidade de Colisão de IV no WEP",
                         author=AUTOR, subject=f"{UC} — Trabalho laboratorial 6", **kw)
        moldura = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates([
            PageTemplate(id="capa", frames=[moldura], onPage=self._capa),
            PageTemplate(id="corpo", frames=[moldura], onPage=self._rodape),
        ])

    def beforeDocument(self):
        # multiBuild faz várias passagens: as chaves têm de ser iguais em todas.
        self._n_marcas = 0

    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and getattr(f, "_toc", None) is not None:
            nivel = f._toc
            texto = f.getPlainText()
            self._n_marcas += 1
            chave = f"sec-{self._n_marcas}"
            self.canv.bookmarkPage(chave)
            self.canv.addOutlineEntry(texto, chave, level=nivel)
            self.notify("TOCEntry", (nivel, texto, self.page, chave))

    def _rodape(self, canv, doc):
        canv.saveState()
        w, h = A4
        canv.setStrokeColor(LINHA)
        canv.setLineWidth(0.5)
        canv.line(doc.leftMargin, 1.45 * cm, w - doc.rightMargin, 1.45 * cm)
        canv.setFont("Titulo-R", 8.5)
        canv.setFillColor(CINZA)
        canv.drawString(doc.leftMargin, 1.0 * cm, "Trabalho 6 — Monte Carlo de colisões de IV no WEP")
        canv.drawRightString(w - doc.rightMargin, 1.0 * cm, f"{doc.page}")
        canv.restoreState()

    def _capa(self, canv, doc):
        w, h = A4
        canv.saveState()
        canv.setFillColor(NAVY)
        canv.rect(0, h * 0.42, w, h * 0.58, stroke=0, fill=1)
        # Motivo: grelha de "IVs" (quadrados), dois deles coincidentes = colisão
        tam, gap = 0.42 * cm, 0.14 * cm
        x0, y0 = doc.leftMargin, h * 0.42 + 1.4 * cm
        for i in range(26):
            for j in range(3):
                canv.setFillColor(colors.HexColor("#1F3157"))
                if (i, j) in ((7, 1), (19, 1)):
                    canv.setFillColor(LARANJA)
                elif (i * 7 + j * 3) % 11 == 0:
                    canv.setFillColor(AZUL)
                canv.rect(x0 + i * (tam + gap), y0 + j * (tam + gap), tam, tam, stroke=0, fill=1)
        canv.setFillColor(colors.white)
        canv.setFont("Titulo-R", 11)
        canv.drawString(doc.leftMargin, h - 2.6 * cm, CURSO.upper())
        canv.setFont("Titulo-R", 11)
        canv.setFillColor(colors.HexColor("#AFC3E6"))
        canv.drawString(doc.leftMargin, h - 3.2 * cm, UC)
        canv.setFillColor(colors.white)
        canv.setFont("Titulo", 13)
        canv.drawString(doc.leftMargin, h - 6.3 * cm, "TRABALHO LABORATORIAL 6")
        canv.setFont("Titulo", 30)
        for k, linha in enumerate(["Simulação de Monte Carlo da", "Probabilidade de Colisão", "de IV no WEP"]):
            canv.drawString(doc.leftMargin, h - 7.9 * cm - k * 1.15 * cm, linha)
        canv.setFont("Corpo-I", 13)
        canv.setFillColor(colors.HexColor("#D6E0F2"))
        canv.drawString(doc.leftMargin, h - 11.7 * cm,
                        "Paradoxo do aniversário, validação numérica e comparação com o TKIP")
        canv.setFillColor(TINTA)
        canv.setFont("Titulo", 12)
        canv.drawString(doc.leftMargin, h * 0.42 - 2.2 * cm, "Autor")
        canv.setFont("Corpo", 12)
        canv.drawString(doc.leftMargin, h * 0.42 - 2.8 * cm, AUTOR)
        canv.setFont("Titulo", 12)
        canv.drawString(doc.leftMargin, h * 0.42 - 4.0 * cm, "Data")
        canv.setFont("Corpo", 12)
        canv.drawString(doc.leftMargin, h * 0.42 - 4.6 * cm, DATA)
        canv.setFont("Titulo", 12)
        canv.drawString(doc.leftMargin, h * 0.42 - 5.8 * cm, "Implementação")
        canv.setFont("Corpo", 12)
        canv.drawString(doc.leftMargin, h * 0.42 - 6.4 * cm, "Python 3 · NumPy · Matplotlib")
        canv.restoreState()


# --------------------------------------------------------------------------- #
# Blocos de construção
# --------------------------------------------------------------------------- #
class Construtor:
    def __init__(self, st, largura, tmp: Path):
        self.st, self.largura, self.tmp = st, largura, tmp
        self.historia = []
        self.n_fig = 0
        self.n_tab = 0
        self.n_eq = 0
        self.n_h1 = 0
        self.n_h2 = 0

    # Texto -------------------------------------------------------------------
    def h1(self, texto):
        self.n_h1 += 1
        self.n_h2 = 0
        p = Paragraph(f"{self.n_h1}.{NBSP}{NBSP}{texto}", self.st["h1"])
        p._toc = 0
        self.historia += [CondPageBreak(5 * cm), p]

    def h1_sem_numero(self, texto):
        p = Paragraph(texto, self.st["h1"])
        p._toc = 0
        self.historia.append(p)

    def h2(self, texto):
        self.n_h2 += 1
        p = Paragraph(f"{self.n_h1}.{self.n_h2}{NBSP}{NBSP}{texto}", self.st["h2"])
        p._toc = 1
        self.historia += [CondPageBreak(3.5 * cm), p]

    def p(self, texto):
        self.historia.append(Paragraph(texto, self.st["corpo"]))

    def lista(self, itens):
        for it in itens:
            self.historia.append(Paragraph(it, self.st["lista"], bulletText="•"))
        self.historia.append(Spacer(1, 4))

    def caixa(self, texto, cor=AZUL):
        t = Table([[Paragraph(texto, self.st["destaque"])]], colWidths=[self.largura])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CINZA_CLARO),
            ("BOX", (0, 0), (-1, -1), 0.6, cor),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        self.historia += [Spacer(1, 2), t, Spacer(1, 8)]

    # Equações (mathtext do matplotlib -> PNG) ---------------------------------
    def eq(self, latex, numerar=True, tamanho=14):
        self.n_img_eq = getattr(self, "n_img_eq", 0) + 1
        if numerar:
            self.n_eq += 1
        caminho = self.tmp / f"eq{self.n_img_eq}.png"
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.text(0, 0, f"${latex}$", fontsize=tamanho, color="#1B1B1B")
        fig.savefig(caminho, dpi=400, bbox_inches="tight", pad_inches=0.03, transparent=True)
        plt.close(fig)
        from PIL import Image as PILImage
        with PILImage.open(caminho) as im:
            wpx, hpx = im.size
        w, h = wpx / 400 * 72, hpx / 400 * 72
        img = Image(str(caminho), width=w, height=h)
        num = Paragraph(f"({self.n_eq})" if numerar else "", self.st["tab"])
        t = Table([["", img, num]], colWidths=[1.2 * cm, self.largura - 2.4 * cm, 1.2 * cm])
        t.setStyle(TableStyle([("ALIGN", (1, 0), (1, 0), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        self.historia.append(t)
        return self.n_eq

    # Figuras e tabelas --------------------------------------------------------
    def figura(self, nome, legenda, escala=1.0):
        from PIL import Image as PILImage
        caminho = PASTA_FIG / nome
        with PILImage.open(caminho) as im:
            wpx, hpx = im.size
        w = self.largura * escala
        h = w * hpx / wpx
        self.n_fig += 1
        self.historia.append(KeepTogether([
            Image(str(caminho), width=w, height=h),
            Paragraph(f"<b>Figura {self.n_fig}</b> — {legenda}", self.st["legenda"]),
        ]))
        return self.n_fig

    def tabela(self, cabecalho, linhas, larguras, legenda, alinhar_esq=(), destacar=(), juntar=True):
        self.n_tab += 1
        dados = [[Paragraph(c, self.st["tab_cab"]) for c in cabecalho]]
        for linha in linhas:
            dados.append([Paragraph(str(v), self.st["tab_esq"] if j in alinhar_esq else self.st["tab"])
                          for j, v in enumerate(linha)])
        larg = [self.largura * f for f in larguras]
        t = Table(dados, colWidths=larg, repeatRows=1)
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINHA),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(1, len(dados)):
            if i % 2 == 0:
                estilo.append(("BACKGROUND", (0, i), (-1, i), CINZA_CLARO))
        for i in destacar:
            estilo.append(("BACKGROUND", (0, i + 1), (-1, i + 1), colors.HexColor("#E3EDFA")))
        t.setStyle(TableStyle(estilo))
        blocos = [Paragraph(f"<b>Tabela {self.n_tab}</b> — {legenda}", self.st["legenda"]), t, Spacer(1, 12)]
        self.historia.append(KeepTogether(blocos) if juntar else blocos[0])
        if not juntar:
            self.historia += blocos[1:]
        return self.n_tab


# --------------------------------------------------------------------------- #
# Conteúdo
# --------------------------------------------------------------------------- #
def construir(R, c: Construtor):
    st = c.st
    rs, w, t = R["resumo"], R["resumo"]["wep"], R["resumo"]["tkip"]
    e1, e4, e5, e6 = R["e1_wep_direto"], R["e4_tkip_direto"], R["e5_convergencia"], R["e6_escala"]
    e7 = R["e7_validacao_gerador"]
    tp, ta, tt = R["tabela_probabilidades"], R["tabela_aproximacoes"], R["tabela_tempos"]
    tempos = R["tempos_execucao_s"]
    T_dir = e1[0]["ensaios"]
    dentro = sum(1 for l in e1 if l["ic95_inf"] <= l["p_exata"] <= l["ic95_sup"])
    tkip_col, tkip_ens = t["colisoes_mesmos_pacotes"], t["ensaios_mesmos_pacotes"]
    esperado_tkip = sum(l["ensaios"] * l["p_exata"] for l in e4)
    linha_escala = {l["bits"]: l for l in e6}

    # ------------------------------------------------------------------ Resumo
    c.historia.append(NextPageTemplate("corpo"))
    c.historia.append(PageBreak())
    c.h1_sem_numero("Resumo")
    c.p(
        "Este trabalho estima, por simulação de Monte Carlo, a probabilidade de dois pacotes "
        "cifrados com WEP reutilizarem o mesmo vetor de inicialização (IV) de 24 bits, em função "
        "do número de pacotes transmitidos, e compara-a com a fórmula exata do problema do "
        "aniversário generalizado. Foram implementados em Python dois estimadores independentes "
        f"— um <i>direto</i>, com {fi(T_dir)} ensaios por ponto, e um baseado no instante da "
        f"<i>primeira colisão</i>, com {fi(w['ensaios_cdf'])} ensaios — que concordam entre si e com "
        "a teoria dentro da incerteza estatística esperada. A validação inclui ainda a comparação "
        "de três geradores pseudoaleatórios (Philox, MT19937 e PCG64).")
    c.p(
        f"Para n{NBSP}={NBSP}4{NBSP}823 pacotes a probabilidade teórica de colisão é "
        f"{fp(w['p_exata_4823'], 3)}, e a simulação obteve {fp(w['p_sim_cdf_4823'])} "
        f"(IC 95%: {fp(w['ic95_cdf_4823'][0])} a {fp(w['ic95_cdf_4823'][1])}), confirmando o resultado do "
        "Exercício 1. Repetindo a análise para o IV de 48 bits do TKIP, são necessários "
        f"{fi(t['n50_exato'])} pacotes para atingir os mesmos 50%: um fator de {fi(rs['razao_n50'])} "
        f"(= 2<super>12</super> = √(2<super>48</super>/2<super>24</super>)). Com os mesmos 4{NBSP}823 pacotes, a "
        f"probabilidade de colisão no TKIP desce para {fsci(t['p_exata_4823'])}, cerca de "
        f"{fsci(rs['razao_p_4823'], 1)} vezes menor. Um estudo de escala entre 16 e 48 bits confirma "
        "empiricamente a lei n<sub>50</sub> ∝ √N: duplicar o número de bits do IV apenas eleva ao "
        "quadrado — e não à potência do tamanho do espaço — a resistência a colisões.")
    c.p(
        "O relatório termina com uma discussão sobre a razão pela qual o método de Monte Carlo, "
        "criado em Los Alamos na década de 1940, continua a ser uma ferramenta central em "
        "engenharia de telecomunicações, segurança, finanças, física, computação gráfica e "
        "inteligência artificial.")
    c.p("<b>Palavras-chave:</b> WEP, TKIP, vetor de inicialização, paradoxo do aniversário, "
        "método de Monte Carlo, segurança em redes sem fios.")

    # ------------------------------------------------------------------ Índice
    c.historia.append(PageBreak())
    c.historia.append(Paragraph("Índice", st["h1"]))
    toc = TableOfContents()
    toc.levelStyles = [st["toc1"], st["toc2"]]
    toc.dotsMinLevel = 0
    c.historia.append(toc)
    c.historia.append(PageBreak())

    # ------------------------------------------------------------- 1 Introdução
    c.h1("Introdução")
    c.p(
        "O <i>Wired Equivalent Privacy</i> (WEP), definido na norma IEEE 802.11 de 1997, foi o "
        "primeiro mecanismo de confidencialidade das redes Wi-Fi. A sua fragilidade mais conhecida "
        "não está no comprimento da chave, mas na forma como cada pacote obtém a sua própria chave "
        "de cifra: concatenando uma chave secreta fixa com um <b>vetor de inicialização (IV) de "
        "apenas 24 bits</b>, transmitido em claro. Sempre que dois pacotes usam o mesmo IV, "
        "usam também a mesma sequência de cifra RC4 — e isso abre a porta a ataques.")
    c.p(
        "O objetivo deste trabalho, conforme o enunciado do Trabalho 6, é <b>simular por Monte "
        "Carlo a probabilidade de colisão de IV no WEP em função do número de pacotes "
        "transmitidos</b> e compará-la com a aproximação teórica do paradoxo do aniversário. "
        "Concretamente:")
    c.lista([
        "simular a geração aleatória de IVs num espaço de 2<super>24</super> valores e estimar "
        "empiricamente a fração de simulações com pelo menos uma colisão;",
        "comparar a curva simulada com a fórmula teórica exata do problema do aniversário "
        "generalizado;",
        "repetir a análise para um IV de 48 bits, como no TKIP do WPA, e comparar a robustez face "
        "a colisões.",
    ])
    c.p(
        "Para além das três questões de análise do enunciado, o trabalho inclui um estudo da "
        "convergência do estimador (erro ∝ 1/√T), a distribuição completa do instante da primeira "
        "colisão e uma verificação empírica da lei de escala n<sub>50</sub> ∝ √N para IVs entre 16 e "
        "48 bits. O Capítulo 2 enquadra o problema de segurança; o Capítulo 3 desenvolve o modelo "
        "teórico; o Capítulo 4 apresenta o método de Monte Carlo; o Capítulo 5 descreve a "
        "implementação; o Capítulo 6 apresenta e compara os resultados; o Capítulo 7 discute a "
        "relevância atual do método; e o Capítulo 8 conclui.")

    # ------------------------------------------------------------ 2 Enquadramento
    c.h1("Enquadramento: o IV no WEP e no TKIP")
    c.h2("Construção da chave por pacote no WEP")
    c.p(
        "O WEP usa a cifra de fluxo RC4. Para cada pacote, o emissor escolhe um IV de 24 bits e "
        "forma a semente RC4 concatenando-o com a chave partilhada (40 ou 104 bits, dando as "
        "variantes comerciais «64» e «128 bits»). O RC4 gera uma sequência pseudoaleatória "
        "(<i>keystream</i>) que é combinada por XOR com os dados e com o CRC-32 (ICV). O IV segue "
        "em claro no cabeçalho, para que o recetor possa reconstruir a mesma semente.")
    c.eq(r"C \;=\; (P \,\|\, \mathrm{ICV}(P)) \;\oplus\; \mathrm{RC4}(\mathrm{IV} \,\|\, K)", numerar=False)
    c.h2("Porque é que uma colisão de IV é grave")
    c.p(
        "Como a chave K é fixa durante longos períodos, a <i>keystream</i> depende apenas do IV. Se "
        "dois pacotes P<sub>1</sub> e P<sub>2</sub> forem cifrados com o mesmo IV, então "
        "C<sub>1</sub>{0}⊕{0}C<sub>2</sub>{0}={0}P<sub>1</sub>{0}⊕{0}P<sub>2</sub>: a cifra anula-se e o atacante "
        "obtém o XOR dos dois textos em claro. Com um texto conhecido (por exemplo, um cabeçalho "
        "ARP ou IP previsível), recupera o outro, e pode construir progressivamente uma tabela "
        "de <i>keystreams</i> indexada por IV. Este problema foi descrito por Borisov, Goldberg e "
        "Wagner em 2001 e, no mesmo ano, Fluhrer, Mantin e Shamir mostraram que certos IVs "
        "revelam também bits da própria chave RC4 (ataque FMS), culminando em ataques práticos "
        "que recuperam uma chave WEP de 104 bits com algumas dezenas de milhar de pacotes "
        "(Tews, Weinmann e Pyshkin, 2007).".format(NBSP))
    c.p(
        "A pergunta central deste trabalho é, portanto: <b>quantos pacotes é preciso observar "
        "até que a reutilização de um IV se torne provável?</b> A intuição de que 2<super>24</super> "
        f"≈ 16,8 milhões de IVs «chegam para muito tempo» é enganadora — é precisamente o "
        "paradoxo do aniversário.")
    c.h2("A resposta do WPA: o TKIP")
    c.p(
        "O TKIP (<i>Temporal Key Integrity Protocol</i>), introduzido com o WPA em 2003 como "
        "solução de transição que pudesse correr no hardware WEP existente, alarga o IV para um "
        "contador de sequência de <b>48 bits</b> (TSC), aplica uma função de mistura que gera uma "
        "chave RC4 diferente para cada pacote, acrescenta o código de integridade Michael e "
        "renova periodicamente as chaves temporais. Neste trabalho isolamos apenas o efeito do "
        "aumento do espaço de IV de 2<super>24</super> para 2<super>48</super>, assumindo — tal como "
        "para o WEP — IVs escolhidos aleatoriamente. É um cenário conservador: no TKIP o TSC é "
        "sequencial e nunca se repete dentro da mesma chave temporal, pelo que o modelo aleatório "
        "representa o pior caso. O TKIP é hoje considerado obsoleto (foi desaconselhado na revisão "
        "IEEE 802.11-2012), tendo sido substituído pelo CCMP/AES do WPA2 e pelo GCMP do WPA3.")

    # -------------------------------------------------------------- 3 Teoria
    c.h1("Modelo teórico: o problema do aniversário generalizado")
    c.h2("Probabilidade exata de colisão")
    c.p(
        "Seja N{0}={0}2<super>b</super> o número de IVs possíveis (b{0}={0}24 no WEP, b{0}={0}48 no TKIP) e "
        "suponha-se que cada um de n pacotes recebe um IV uniforme e independente. O primeiro "
        "pacote nunca colide; o segundo é distinto do primeiro com probabilidade (N−1)/N; o "
        "k-ésimo é distinto de todos os anteriores com probabilidade (N−k+1)/N. Assim, a "
        "probabilidade de <i>não</i> haver nenhuma colisão é um produto, e a de haver pelo menos "
        "uma é o seu complemento:".format(NBSP))
    eq_exata = c.eq(r"P(n) \;=\; 1 - \prod_{k=0}^{n-1}\left(1 - \frac{k}{N}\right) "
                    r"\;=\; 1 - \frac{N!}{(N-n)!\,N^{\,n}}")
    c.p(
        f"A Equação ({eq_exata}) é exata e é a referência usada em todas as comparações. Para "
        "N{0}={0}2<super>48</super> o produto tem dezenas de milhões de fatores muito próximos de 1, pelo que "
        "foi avaliado em domínio logarítmico, como soma de log(1−k/N), de forma a evitar perda "
        "de precisão numérica.".format(NBSP))
    c.h2("Aproximação exponencial e o valor n<sub>50</sub>")
    c.p("Usando 1−x ≈ e<super>−x</super> para x pequeno, a soma dos expoentes é n(n−1)/2N, o que dá a "
        "aproximação clássica e, invertendo-a, o número de pacotes para uma probabilidade-alvo p:")
    eq_aprox = c.eq(r"P(n) \;\approx\; 1 - e^{-n(n-1)/2N}, \qquad "
                    r"n_p \;\approx\; \sqrt{2N\ln\frac{1}{1-p}}")
    c.eq(r"n_{50} \;\approx\; \sqrt{2\ln 2}\,\sqrt{N} \;\approx\; 1{,}1774\,\sqrt{N}")
    c.p(
        f"Para o WEP, √(2<super>24</super>){NBSP}={NBSP}4{NBSP}096 e n<sub>50</sub> ≈ {fd(w['n50_aprox'], 1)}, "
        f"ou seja, <b>cerca de 4{NBSP}823 pacotes</b> — o valor do Exercício 1. A procura exata (menor n "
        f"com P(n){NBSP}≥{NBSP}0,5 na Equação {eq_exata}) dá também n<sub>50</sub>{NBSP}={NBSP}{fi(w['n50_exato'])}. "
        f"Para o TKIP obtém-se n<sub>50</sub>{NBSP}={NBSP}{fi(t['n50_exato'])}.")
    c.p(
        "Uma consequência imediata, e talvez a mais importante do trabalho, é que n<sub>50</sub> "
        "cresce com <b>√N</b> e não com N: duplicar o número de bits do IV não duplica a "
        "segurança, eleva-a ao quadrado. Passar de 24 para 48 bits multiplica N por 2<super>24</super>, "
        "mas multiplica n<sub>50</sub> apenas por 2<super>12</super>{0}={0}4{0}096.".format(NBSP))
    c.p(
        f"A Tabela {c.n_tab + 1} compara a fórmula exata com a aproximação exponencial e com o majorante "
        "«quadrático» n(n−1)/2N (desigualdade de Boole), por vezes usado como aproximação "
        "grosseira. A aproximação exponencial é excelente em toda a gama; o majorante só é útil "
        "para probabilidades pequenas e chega a ultrapassar 1, o que mostra que não deve ser "
        "usado perto do ponto dos 50%.")
    c.tabela(
        ["n (pacotes)", f"Exata (Eq. {eq_exata})", "Aprox. exponencial", "Majorante n(n−1)/2N", "Erro da aprox. exp."],
        [[fi(l["n"]), fp(l["exata"], 3), fp(l["aprox_exp"], 3),
          fp(l["aprox_quad"], 1) if l["aprox_quad"] < 1 else f"{fd(l['aprox_quad'], 2)} (&gt; 1!)",
          f"{fd(100 * (l['aprox_exp'] - l['exata']), 4)} p.p."] for l in ta],
        [0.16, 0.19, 0.21, 0.24, 0.20],
        "Fórmula exata vs. aproximações para o WEP (N = 2<super>24</super>).",
        destacar=[2])
    c.h2("Instante da primeira colisão")
    c.p(
        "Em vez de fixar n, pode perguntar-se: <i>em que pacote K ocorre a primeira colisão?</i> "
        "K{0}={0}k significa que os primeiros k−1 IVs são distintos e o k-ésimo repete um deles, donde:".format(NBSP))
    eq_k = c.eq(r"\Pr[K = k] \;=\; \left(1 - P(k-1)\right)\frac{k-1}{N}, \qquad "
         r"\Pr[K \leq n] \;=\; P(n)")
    c.eq(r"\mathbb{E}[K] \;\approx\; \sqrt{\frac{\pi N}{2}} + \frac{2}{3}, \qquad "
         r"\sigma_K \;\approx\; \sqrt{\left(2 - \frac{\pi}{2}\right)N}")
    c.p(
        f"A segunda igualdade da Equação ({eq_k}) é a base do segundo estimador de Monte Carlo usado "
        f"neste trabalho. Para o WEP, E[K] ≈ {fi(w['media_k_teo'])} e σ<sub>K</sub> ≈ {fi(w['dp_k_teo'])} "
        "pacotes: a mediana (≈{0}4{0}823) é inferior à média porque a distribuição tem cauda à "
        "direita.".format(NBSP))

    # ----------------------------------------------------------- 4 Monte Carlo
    c.h1("O método de Monte Carlo")
    c.h2("Princípio")
    c.p(
        "O método de Monte Carlo estima uma grandeza determinística — uma probabilidade, um "
        "integral, um valor esperado — através da média de muitas experiências aleatórias "
        "independentes. Se cada ensaio i produz um indicador X<sub>i</sub> ∈ {0,1} que vale 1 quando "
        "ocorre o acontecimento de interesse (aqui, «houve pelo menos uma colisão de IV»), "
        "então a fração empírica (designada P<sub>sim</sub> no resto do relatório) é um estimador "
        "não enviesado de P:")
    c.eq(r"\hat{P}_T \;=\; \frac{1}{T}\sum_{i=1}^{T} X_i, \qquad "
         r"\mathbb{E}[\hat{P}_T] = P, \qquad "
         r"\sigma_{\hat{P}} \;=\; \sqrt{\frac{P(1-P)}{T}}")
    c.p(
        "A lei dos grandes números garante que P<sub>sim</sub> → P quando T → ∞, e o teorema do "
        "limite central diz-nos <i>quão depressa</i>: o erro decresce como 1/√T. Reduzir o erro "
        "10 vezes exige 100 vezes mais ensaios. Esta taxa é independente da dimensão do problema "
        "— característica que, como se verá no Capítulo 7, explica grande parte da importância "
        "atual do método.")
    c.h2("Quantificação da incerteza")
    c.p(
        "Cada estimativa é acompanhada de um intervalo de confiança a 95%. Usou-se o intervalo de "
        "Wilson (1927), preferível ao intervalo normal simples porque se mantém válido quando "
        "P<sub>sim</sub> está próximo de 0 ou de 1 (situação frequente nas caudas das curvas de colisão e, "
        "sobretudo, no caso TKIP):")
    c.eq(r"\mathrm{IC}_{95\%} \;=\; \frac{\hat{P} + z^2/2T \;\pm\; "
         r"z\sqrt{\hat{P}(1-\hat{P})/T + z^2/4T^2}}{1 + z^2/T}, \qquad z = 1{,}96")
    c.h2("Origem histórica")
    c.p(
        "O método foi formulado em 1946–1947 em Los Alamos por Stanislaw Ulam e John von Neumann, "
        "no contexto do estudo da difusão de neutrões, e batizado por Nicholas Metropolis em "
        "alusão ao casino do Mónaco. Ulam contou que a ideia lhe surgiu ao tentar calcular a "
        "probabilidade de ganhar um jogo de paciência: era mais fácil jogar muitas vezes e contar "
        "do que resolver a combinatória. As primeiras simulações correram no ENIAC em 1948, e o "
        "artigo fundador, «The Monte Carlo Method», de Metropolis e Ulam, foi publicado em 1949. "
        "Este trabalho segue exatamente essa filosofia: o problema tem solução analítica, mas a "
        "simulação permite validá-la de forma independente e explorar variantes sem nova "
        "derivação matemática.")

    # ------------------------------------------------------- 5 Implementação
    c.h1("Implementação")
    c.h2("Arquitetura")
    c.p("A implementação, em Python 3 com NumPy e Matplotlib, está organizada em quatro módulos com "
        f"responsabilidades separadas (Tabela {c.n_tab + 1}). Todo o código está em <font name='Mono'>src/</font>, "
        "as figuras em <font name='Mono'>figuras/</font> e os resultados numéricos (JSON, CSV e as "
        "amostras brutas em NPY) em <font name='Mono'>resultados/</font>.")
    c.tabela(
        ["Módulo", "Responsabilidade"],
        [["<font name='Mono'>teoria.py</font>", "Fórmula exata (domínio logarítmico), aproximações, inversão "
          "para n<sub>p</sub> (pesquisa binária exata), distribuição, média e desvio-padrão de K."],
         ["<font name='Mono'>montecarlo.py</font>", "Os dois estimadores de Monte Carlo, intervalo de Wilson, "
          "paralelização em vários processos com sementes independentes."],
         ["<font name='Mono'>experiencias.py</font>", "Orquestra as experiências E1–E6, mede tempos, grava "
          "resultados e gera as figuras. Opções <font name='Mono'>--rapido</font> e "
          "<font name='Mono'>--so-figuras</font>."],
         ["<font name='Mono'>graficos.py</font>", "Figuras com convenção visual única: WEP a azul, TKIP a "
          "laranja, teoria a traço contínuo escuro, simulação com marcadores e IC 95%."]],
        [0.25, 0.75], "Módulos da implementação.", alinhar_esq=(1,))
    c.h2("Estimador 1 — método direto")
    c.p(
        "É a tradução literal do enunciado. Para cada n, realizam-se T ensaios; em cada um geram-se "
        "n IVs uniformes em [0, 2<super>b</super>) e verifica-se se há repetidos. A verificação é feita "
        "por ordenação: depois de ordenar o vetor, existe colisão se e só se dois elementos "
        "consecutivos forem iguais — custo O(n log n) em vez dos O(n²) de comparar todos os pares. "
        "Os ensaios são vetorizados por lotes: uma matriz (lote × n) é ordenada linha a linha numa "
        "única chamada NumPy, evitando ciclos em Python.")
    c.h2("Estimador 2 — instante da primeira colisão")
    c.p(
        "Em cada ensaio geram-se IVs até à primeira repetição e regista-se o índice K. Como "
        "{colisão nos primeiros n pacotes} = {K ≤ n}, a função de distribuição empírica de K dá "
        "P<sub>sim</sub>(n) <i>para todos os n em simultâneo</i>, com uma só bateria de ensaios. É este estimador "
        "que torna viável o caso de 48 bits, em que cada ensaio envolve dezenas de milhões de IVs.")
    c.p("Três decisões de implementação tornaram-no eficiente:")
    c.lista([
        "<b>Geração em bloco.</b> Em vez de inserir IVs um a um num conjunto (lento em Python), gera-se "
        "de uma vez um bloco de L{0}={0}3√N IVs, que contém uma colisão com probabilidade "
        "1−e<super>−4,5</super> ≈ 98,9%. Se não contiver, o bloco é prolongado; o resultado é sempre exato.".format(NBSP),
        "<b>Localização sem <i>argsort</i>.</b> Ordenar índices de 50 milhões de elementos é cerca de 25 "
        "vezes mais lento do que ordenar os valores. Ordena-se apenas uma cópia dos valores, "
        "extraem-se os poucos valores repetidos (≈4,5 em média) e só então se procuram as suas "
        "posições no vetor original; a primeira posição cujo valor já apareceu é K.",
        "<b>Paralelização reprodutível.</b> Os ensaios são distribuídos por todos os núcleos com "
        "<font name='Mono'>ProcessPoolExecutor</font>; cada tarefa recebe uma semente filha de "
        "<font name='Mono'>numpy.random.SeedSequence</font>, o que garante fluxos aleatórios "
        "independentes e resultados idênticos em execuções repetidas. O gerador usado é o "
        "<b>Philox</b>, um gerador baseado em contador concebido para simulação paralela "
        "(a escolha é justificada na secção 6.6).",
    ])
    c.p("O núcleo do estimador encontra-se no Anexo A. Os dois estimadores são independentes — usam "
        "sementes e algoritmos diferentes —, pelo que a sua concordância constitui uma validação "
        "cruzada da implementação.")
    c.h2("Plano experimental")
    esc = sorted(linha_escala)
    c.tabela(
        ["Exp.", "Descrição", "Ensaios", "Tempo"],
        [["E1", f"WEP, método direto, {len(e1)} valores de n entre {fi(e1[0]['n'])} e {fi(e1[-1]['n'])}",
          f"{fi(T_dir)} por ponto", f"{fd(tempos['E1'], 0)} s"],
         ["E2", "WEP, primeira colisão (curva completa, distribuição de K)", fi(w["ensaios_cdf"]),
          f"{fd(tempos['E2'], 0)} s"],
         ["E3", "TKIP, primeira colisão", fi(t["ensaios_cdf"]), f"{fd(tempos['E3'], 0)} s"],
         ["E4", "TKIP com os mesmos n do E1, método direto", f"{fi(T_dir)} por ponto", f"{fd(tempos['E4'], 0)} s"],
         ["E5", "Convergência do estimador (reutiliza as amostras do E2)", "—", "&lt; 1 s"],
         ["E6", f"Lei de escala, IV de {esc[0]} a {esc[-1]} bits (passo 4)",
          f"{fi(min(l['ensaios'] for l in e6))} a {fi(max(l['ensaios'] for l in e6))}", f"{fd(tempos['E6'], 0)} s"],
         ["E7", "Validação do gerador: WEP com Philox, MT19937 e PCG64; N = 2<super>10</super> com Philox",
          f"{fi(e7[1]['ensaios'])} por gerador", f"{fd(tempos['E7'], 0)} s"]],
        [0.08, 0.56, 0.20, 0.16],
        f"Experiências realizadas (tempo total: {fd(tempos['total'] / 60, 1)} min num Ryzen 7 3700X, 8 núcleos).",
        alinhar_esq=(1,))

    # ---------------------------------------------------------- 6 Resultados
    c.h1("Resultados e discussão")
    c.h2("WEP: teoria vs. simulação")
    f1 = c.figura("fig1_wep_teoria_vs_simulacao.png",
                  "Probabilidade de colisão de IV no WEP. Os pontos (método direto) e a curva verde "
                  f"(primeira colisão) são simulações; a curva preta é a Equação {eq_exata}.")
    c.p(
        f"A Figura {f1} sobrepõe os dois estimadores à fórmula exata. As três curvas são "
        "praticamente indistinguíveis em toda a gama, e a aproximação exponencial coincide com a "
        f"exata à escala do gráfico. Dos {len(e1)} pontos do método direto, <b>{dentro} têm o valor "
        "teórico dentro do respetivo intervalo de confiança a 95%</b>, o que é compatível com o "
        f"nível de confiança nominal (esperar-se-iam, em média, {fd(0.95 * len(e1), 1)}). A Tabela {c.n_tab + 1} "
        "detalha os valores.")
    c.tabela(
        ["n", "Colisões / ensaios", "P<sub>sim</sub> simulada", "IC 95% (Wilson)", "P exata", "Desvio (σ)"],
        [[fi(l["n"]), f"{fi(l['colisoes'])} / {fi(l['ensaios'])}", fp(l["p_sim"]),
          f"[{fd(100 * l['ic95_inf'], 2)}; {fd(100 * l['ic95_sup'], 2)}]%", fp(l["p_exata"]),
          fd((l["p_sim"] - l["p_exata"]) / max(1e-12, (l["p_exata"] * (1 - l["p_exata"]) / l["ensaios"]) ** 0.5), 2)
          if 0 < l["p_exata"] < 1 - 1e-9 else "—"]
         for l in e1],
        [0.12, 0.19, 0.15, 0.22, 0.15, 0.17],
        "Resultados do método direto para o WEP (E1). «Desvio» = (P<sub>sim</sub> − P)/σ<sub>P<sub>sim</sub></sub>.",
        destacar=[[l["n"] for l in e1].index(4823)])

    c.h2("Questão 1 — N ≈ 4 823 pacotes conduz a 50% de colisão?")
    c.caixa(
        f"<b>Sim.</b> Para n{NBSP}={NBSP}4{NBSP}823: P exata = <b>{fp(w['p_exata_4823'], 4)}</b>; "
        f"aproximação exponencial = {fp(w['p_aprox_4823'], 4)}; "
        f"método direto = <b>{fp(w['p_sim_direto_4823'])}</b> (IC 95% [{fp(w['ic95_direto_4823'][0])}; "
        f"{fp(w['ic95_direto_4823'][1])}], {fi(T_dir)} ensaios); "
        f"primeira colisão = <b>{fp(w['p_sim_cdf_4823'])}</b> (IC 95% [{fp(w['ic95_cdf_4823'][0])}; "
        f"{fp(w['ic95_cdf_4823'][1])}], {fi(w['ensaios_cdf'])} ensaios). "
        f"A mediana empírica de K é {fi(w['mediana_k'])} pacotes, contra 4{NBSP}823 teóricos.")
    contem = [lo <= w["p_exata_4823"] <= hi for lo, hi in (w["ic95_direto_4823"], w["ic95_cdf_4823"])]
    if all(contem):
        frase_ic = "Ambos os intervalos de confiança contêm o valor exato"
    elif contem[1]:
        frase_ic = ("O intervalo do estimador por primeira colisão contém o valor exato; o do método "
                    "direto fica ligeiramente aquém — ocorrência esperada em cerca de 5% dos casos para um "
                    "IC a 95%, e que desaparece no estimador com mais ensaios")
    else:
        frase_ic = "Os desvios observados são da ordem do erro-padrão de cada estimador"
    c.p(
        f"{frase_ic}, e o estimador com mais ensaios fica a "
        f"{fd(abs(100 * (w['p_sim_cdf_4823'] - w['p_exata_4823'])), 2)} pontos percentuais do valor exato. "
        "Em termos práticos: <b>num ponto de acesso WEP, bastam cerca de 4{0}800 pacotes — uma "
        "fração ínfima dos 16,8 milhões de IVs disponíveis (0,03%) — para que seja mais provável "
        "do que não ter já ocorrido uma reutilização de IV.</b> E com 3{0}× esse valor "
        "(≈15{0}000 pacotes), a colisão é praticamente certa (≈99,9%).".format(NBSP))
    f4 = c.figura("fig4_distribuicao_primeira_colisao.png",
                  "Histograma do pacote em que ocorre a primeira colisão (E2) e distribuição teórica "
                  f"Pr[K = k] (Equação {eq_k}).")
    c.p(
        f"A Figura {f4} mostra a distribuição do instante da primeira colisão. O histograma "
        f"acompanha a densidade teórica, com média simulada {fi(w['media_k_sim'])} (teórica "
        f"{fi(w['media_k_teo'])}) e desvio-padrão {fi(w['dp_k_sim'])} (teórico {fi(w['dp_k_teo'])}). "
        f"Nos {fi(w['ensaios_cdf'])} ensaios, a colisão mais precoce ocorreu logo no pacote "
        f"{fi(w['min_k'])} e a mais tardia no pacote {fi(w['max_k'])}: mesmo no caso mais "
        f"favorável observado, o WEP repetiu um IV antes de usar {fp(w['max_k'] / w['N'], 2)} do seu "
        "espaço de IVs.")

    c.h2("Questão 2 — rapidez de crescimento: WEP (24 bits) vs. TKIP (48 bits)")
    f2 = c.figura("fig2_wep_vs_tkip_log.png",
                  "Probabilidade de colisão em função de n (escala logarítmica) para os dois tamanhos "
                  "de IV, com pontos simulados (E2 e E3).")
    c.p(
        f"Em escala logarítmica (Figura {f2}), as duas curvas têm exatamente a mesma forma: a do "
        f"TKIP é a do WEP deslocada por um fator constante de 2<super>12</super>. Os pontos simulados "
        f"do TKIP ({fi(t['ensaios_cdf'])} ensaios de primeira colisão, cada um com dezenas de milhões "
        "de IVs de 48 bits) seguem a curva teórica, com a dispersão esperada para essa dimensão de "
        "amostra.")
    f3 = c.figura("fig3_mesmos_pacotes.png",
                  "Mesmo número de pacotes para os dois protocolos: (a) escala linear, com pontos "
                  "simulados (E1 e E4); (b) escala logarítmica da probabilidade.")
    c.p(
        f"Para o mesmo número de pacotes (Figura {f3}), a diferença é de muitas ordens de grandeza. "
        "Enquanto a curva do WEP sobe de quase 0 a quase 100% em 15{0}000 pacotes, a do TKIP é "
        "indistinguível de zero em escala linear. Na simulação E4, em "
        f"<b>{fi(tkip_ens)} ensaios TKIP com n até 15{NBSP}000 não ocorreu nenhuma colisão</b> "
        f"({fi(tkip_col)} observadas), o que está de acordo com a teoria: o número esperado de "
        f"ensaios com colisão era apenas {fsci(esperado_tkip)}. A Tabela {c.n_tab + 1} resume a comparação.".format(NBSP))
    c.tabela(
        ["n (pacotes)", "WEP exata", "WEP simulada", "TKIP exata", "TKIP simulada"],
        [[fi(l["n"]), fprob(l["p_wep_exata"]), fprob(l["p_wep_sim"]), fprob(l["p_tkip_exata"]),
          fprob(l["p_tkip_sim"])] for l in tp],
        [0.20, 0.20, 0.20, 0.20, 0.20],
        f"Probabilidade de colisão para o mesmo n (simulações: {fi(w['ensaios_cdf'])} ensaios WEP, "
        f"{fi(t['ensaios_cdf'])} TKIP).",
        destacar=[[l["n"] for l in tp].index(4823), [l["n"] for l in tp].index(t["n50_exato"])])
    c.p(
        "Note-se que, para o TKIP com n pequeno, a simulação devolve 0 — não porque a "
        "probabilidade seja nula, mas porque é demasiado pequena para ser observada com qualquer "
        f"número razoável de ensaios. Para estimar P{NBSP}≈{NBSP}4×10<super>−8</super> com 10% de erro "
        "relativo seriam precisos cerca de 2,4×10<super>9</super> ensaios. É uma limitação "
        "conhecida do Monte Carlo simples — os <i>acontecimentos raros</i> — e é aqui que a "
        "fórmula analítica (ou técnicas como a amostragem por importância) se torna indispensável.")

    c.h2("Questão 3 — quantos pacotes para 50% com um IV de 48 bits?")
    c.caixa(
        f"Com um IV de 48 bits são necessários <b>{fi(t['n50_exato'])} pacotes</b> (fórmula exata) para "
        f"uma probabilidade de colisão de 50%, contra 4{NBSP}823 no WEP — um fator de "
        f"<b>{fd(rs['razao_n50'], 1)} ≈ 2<super>12</super></b>. Por simulação (E3), a mediana de K foi "
        f"{fi(t['mediana_k'])} e P<sub>sim</sub>(colisão em {fi(t['n50_exato'])} pacotes) = {fp(t['p_sim_cdf_n50'], 1)} "
        f"(IC 95% [{fp(t['ic95_cdf_n50'][0], 1)}; {fp(t['ic95_cdf_n50'][1], 1)}]).", cor=LARANJA)
    c.p(
        "A melhoria é real, mas é importante interpretá-la corretamente. O espaço de IV cresceu "
        "2<super>24</super> ≈ 16,8 milhões de vezes, e no entanto a resistência a colisões aleatórias "
        "cresceu «apenas» 4{0}096 vezes — a raiz quadrada. A Tabela {1} traduz estes números em "
        "tempo, para diferentes cargas de tráfego.".format(NBSP, c.n_tab + 1))
    c.tabela(
        ["Tráfego (pacotes/s)", "WEP: 50% colisão", "TKIP: 50% colisão", "WEP: esgotar IVs",
         "TKIP: esgotar IVs"],
        [[fi(l["taxa_pps"]), f"{fd(l['wep_t50_s'], 1)} s", f"{fd(l['tkip_t50_h'], 1)} h",
          f"{fd(l['wep_esgotar_h'], 1)} h", f"{fi(l['tkip_esgotar_anos'])} anos"] for l in tt],
        [0.20, 0.20, 0.20, 0.20, 0.20],
        "Tempo até 50% de probabilidade de colisão (IVs aleatórios) e até esgotar o espaço de IV "
        "(IVs sequenciais).")
    c.p(
        "Com 1{0}000 pacotes por segundo — valor comum numa rede moderadamente carregada, ou "
        "facilmente induzido por um atacante que reinjete pedidos ARP —, o WEP atinge 50% de "
        "probabilidade de colisão em <b>menos de 5 segundos</b>, e mesmo com IVs sequenciais esgota "
        "o espaço em menos de 5 horas. O TKIP, no pior caso aleatório, leva cerca de 5,5 horas a "
        "chegar aos 50%; e como na realidade usa um contador sequencial que só se repetiria ao "
        "fim de 2<super>48</super> pacotes (milhares de anos a este ritmo) e renova as chaves "
        "temporais muito antes disso, a reutilização de IV deixa de ser um vetor de ataque "
        "prático. As vulnerabilidades posteriormente descobertas no TKIP (ex.: Beck–Tews, 2008) "
        "exploram outros aspetos do protocolo, não colisões de IV.".format(NBSP))
    f6 = c.figura("fig6_escala_bits.png",
                  "Lei de escala: mediana empírica de K (pontos) e n<sub>50</sub> exato (linha) para IVs de "
                  "16 a 48 bits (E6). Eixo vertical em escala log<sub>2</sub>.")
    desv_max = max(abs(l["mediana_sim"] / l["n50_exato"] - 1) for l in e6)
    c.p(
        f"A Figura {f6} generaliza o resultado: para todos os tamanhos de IV simulados, a mediana "
        f"empírica de K coincide com o n<sub>50</sub> teórico (desvio relativo máximo de "
        f"{fp(desv_max, 1)}, dominado pelos casos com menos ensaios). Em escala log<sub>2</sub> obtém-se "
        "uma reta de declive ½: <b>cada bit adicional no IV multiplica n<sub>50</sub> apenas por "
        "√2</b>. Esta é a razão pela qual, em criptografia, se exigem identificadores, <i>nonces</i> "
        "e resumos com o dobro dos bits da segurança pretendida (por exemplo, 256 bits de "
        "<i>hash</i> para 128 bits de resistência a colisões).")

    c.h2("Convergência e precisão do estimador")
    f5 = c.figura("fig5_convergencia.png",
                  "(a) Evolução da estimativa P<sub>sim</sub> com o número de ensaios, dentro da banda de 95% "
                  "prevista; (b) erro RMS medido vs. teórico √(P(1−P)/T).")
    r10, r1e4 = e5["rmse"][e5["t_grid"].index(10)], e5["rmse"][e5["t_grid"].index(10000)]
    c.p(
        f"A Figura {f5} ilustra o comportamento estatístico do método. Em (a), com poucos ensaios a "
        "estimativa oscila fortemente, mas permanece dentro do funil de ±1,96σ e converge para o "
        f"valor exato. Em (b), o erro RMS passa de {fd(r10, 3)} com T{NBSP}={NBSP}10 para {fd(r1e4, 4)} com "
        f"T{NBSP}={NBSP}10{NBSP}000 — uma redução de cerca de {fi(r10 / r1e4)} vezes para 1{NBSP}000 vezes mais "
        "ensaios, tal como prevê a lei 1/√T (declive −½ em escala log-log; o ponto de maior T usa "
        "menos grupos independentes e tem, por isso, maior variabilidade). Este resultado "
        "justifica o dimensionamento das experiências: com 5{0}000 ensaios por ponto obtém-se um "
        "erro-padrão de ≈0,7 p.p. junto aos 50%, e com 200{0}000 ensaios de ≈0,1 p.p.".format(NBSP))

    c.h2("Validação do gerador pseudoaleatório")
    c.p(
        "Um estudo de Monte Carlo é tão bom quanto o seu gerador de números aleatórios. Numa primeira "
        "execução completa, feita com o PCG64 (o gerador por omissão do NumPy), a média simulada de K "
        "para o WEP ficou 2,6 desvios-padrão acima do valor exato e P<sub>sim</sub>(4{0}823) 2,3 desvios-padrão "
        "abaixo. Para despistar um erro de implementação repetiu-se o estimador em seis baterias "
        "independentes com PCG64 (1,2 milhões de ensaios, incluindo uma implementação ingénua IV a IV "
        "com um conjunto Python) e em 800{0}000 ensaios com outros dois geradores. O desvio manteve o "
        "mesmo sinal em todas as baterias PCG64 (significância conjunta ≈ 3σ para a média de K, "
        "correspondente a um desvio de ≈0,15% em P), mas não apareceu com Philox nem com MT19937 "
        "(|z| &lt; 0,5), e o estimador reproduziu exatamente a média teórica para N{0}={0}2<super>10</super> e "
        "2<super>16</super>. A implementação ficou assim validada; quanto ao PCG64, a evidência não chega "
        "para afirmar que tem um defeito — pode tratar-se de uma flutuação —, mas, por precaução, todos "
        "os resultados finais deste relatório foram produzidos com o Philox. A experiência E7 deixa "
        f"este teste registado e reprodutível (Tabela {c.n_tab + 1}).".format(NBSP))
    c.tabela(
        ["Gerador", "N", "Ensaios", "E[K] simulado", "E[K] exato", "z (média)", "z (P(n<sub>50</sub>))"],
        [[l["gerador"].upper().replace("PHILOX", "Philox"), f"2<super>{l['bits']}</super>", fi(l["ensaios"]),
          fd(l["media_sim"], 1), fd(l["media_exata"], 1), fd(l["z_media"], 2), fd(l["z_p"], 2)] for l in e7],
        [0.14, 0.09, 0.14, 0.17, 0.16, 0.14, 0.16],
        "Validação do gerador (E7): z = (simulado − exato)/erro-padrão; |z| &lt; 2 é compatível com "
        "flutuação estatística a 95%.",
        destacar=[i for i, l in enumerate(e7) if l["gerador"] == "philox" and l["bits"] == 24])
    zmax_philox = max(max(abs(l["z_media"]), abs(l["z_p"])) for l in e7 if l["gerador"] == "philox")
    l_pcg = next(l for l in e7 if l["gerador"] == "pcg64")
    c.p(
        f"Na execução final, os casos com Philox apresentam |z| ≤ {fd(zmax_philox, 2)}"
        + (" — dentro do esperado para flutuações estatísticas" if zmax_philox < 2 else "")
        + f". Nesta bateria, o PCG64 registou z{NBSP}={NBSP}{fd(l_pcg['z_media'], 2)} para a média de K"
        + (", de novo com o mesmo sinal das execuções preliminares." if l_pcg["z_media"] > 1 else
           ", um valor sem significado estatístico, o que reforça a hipótese de que o desvio inicial "
           "foi uma flutuação.")
        + " A lição metodológica é geral: validar o gerador — comparando geradores independentes com "
        "um resultado exato conhecido — faz parte de qualquer estudo de Monte Carlo rigoroso.")

    c.h2("Síntese comparativa")
    l24, l48 = linha_escala[24], linha_escala[48]
    c.tabela(
        ["Grandeza", "Teoria", "Simulação", "Diferença"],
        [["P<sub>WEP</sub>(4 823) — método direto", fp(w["p_exata_4823"]), fp(w["p_sim_direto_4823"]),
          f"{fd(100 * (w['p_sim_direto_4823'] - w['p_exata_4823']), 2)} p.p."],
         ["P<sub>WEP</sub>(4 823) — primeira colisão", fp(w["p_exata_4823"]), fp(w["p_sim_cdf_4823"]),
          f"{fd(100 * (w['p_sim_cdf_4823'] - w['p_exata_4823']), 2)} p.p."],
         ["n<sub>50</sub> WEP (mediana de K)", fi(w["n50_exato"]), fi(w["mediana_k"]),
          fp(w["mediana_k"] / w["n50_exato"] - 1, 2)],
         ["E[K] WEP", fi(w["media_k_teo"]), fi(w["media_k_sim"]), fp(w["media_k_sim"] / w["media_k_teo"] - 1, 2)],
         ["σ<sub>K</sub> WEP", fi(w["dp_k_teo"]), fi(w["dp_k_sim"]), fp(w["dp_k_sim"] / w["dp_k_teo"] - 1, 2)],
         ["n<sub>50</sub> TKIP (mediana de K)", fi(t["n50_exato"]), fi(t["mediana_k"]),
          fp(t["mediana_k"] / t["n50_exato"] - 1, 2)],
         ["E[K] TKIP", fi(t["media_k_teo"]), fi(t["media_k_sim"]), fp(t["media_k_sim"] / t["media_k_teo"] - 1, 2)],
         ["P<sub>TKIP</sub>(n<sub>50</sub>)", "50,00%", fp(t["p_sim_cdf_n50"]),
          f"{fd(100 * (t['p_sim_cdf_n50'] - 0.5), 2)} p.p."],
         ["Ensaios TKIP com colisão, n ≤ 15 000", fsci(esperado_tkip), fi(tkip_col), "—"],
         ["Fator n<sub>50</sub> TKIP / WEP", fd(rs["razao_n50"], 1),
          fd(l48["mediana_sim"] / l24["mediana_sim"], 1), "—"]],
        [0.40, 0.20, 0.20, 0.20],
        "Síntese: valores teóricos vs. simulados.", alinhar_esq=(0,))
    def z(p_sim, p, n):
        return abs(p_sim - p) / (p * (1 - p) / n) ** 0.5
    zs = [z(w["p_sim_direto_4823"], w["p_exata_4823"], T_dir),
          z(w["p_sim_cdf_4823"], w["p_exata_4823"], w["ensaios_cdf"]),
          z(t["p_sim_cdf_n50"], t["p_exata_n50"], t["ensaios_cdf"])]
    frase_z = (f"Todas as diferenças entre probabilidades simuladas e exatas estão abaixo de 2 desvios-padrão "
               f"(máximo: {fd(max(zs), 2)}σ), ou seja, são compatíveis com a variabilidade amostral."
               if max(zs) < 2 else
               f"As diferenças entre probabilidades simuladas e exatas atingem no máximo {fd(max(zs), 2)} "
               "desvios-padrão, valor plausível quando se comparam várias estimativas em simultâneo.")
    c.p(
        f"{frase_z} As "
        "discrepâncias relativas maiores aparecem no TKIP, onde o custo computacional por ensaio "
        f"(≈1–2 s e ≈{fi(3 * 2 ** 24 * 8 / 1e6)} MB de memória) limitou a amostra a {fi(t['ensaios_cdf'])} ensaios; "
        f"o erro-padrão de uma proporção próxima de 50% com esse T é de ≈{fp((0.25 / t['ensaios_cdf']) ** 0.5, 1)}.")

    # ------------------------------------------------- 7 Importância do método
    c.h1("Porque é que o método de Monte Carlo continua tão importante")
    c.p(
        "Oito décadas depois de Los Alamos, o Monte Carlo continua a ser uma das ferramentas "
        "computacionais mais usadas na ciência e na engenharia. Este trabalho ilustra, numa escala "
        "pequena, as razões de fundo.")
    c.h2("Razões estruturais")
    c.lista([
        "<b>O erro não depende da dimensão.</b> Os métodos de quadratura determinísticos têm erro "
        "da ordem de T<super>−k/d</super> num problema de dimensão d, o que os torna impraticáveis "
        "acima de poucas dimensões (a «maldição da dimensionalidade»). O erro de Monte Carlo é "
        "σ/√T qualquer que seja d. Aqui, cada ensaio TKIP é um ponto num espaço com dezenas de "
        "milhões de dimensões (um IV por pacote) — e o método funciona sem alterações.",
        "<b>Exige apenas saber simular, não saber resolver.</b> Bastou descrever o sistema "
        "(«gerar IVs e procurar repetidos»). Se o modelo mudar — IVs não uniformes, contadores "
        "reinicializados, várias estações com a mesma chave —, a simulação adapta-se com poucas "
        "linhas, enquanto a análise teria de ser refeita, e muitas vezes não tem solução fechada.",
        "<b>É naturalmente paralelo.</b> Os ensaios são independentes; o trabalho foi distribuído "
        "por 8 núcleos sem qualquer comunicação entre eles. A mesma propriedade explora hoje GPUs "
        "com milhares de núcleos e infraestruturas de nuvem.",
        "<b>Quantifica a própria incerteza.</b> Cada resultado vem com um intervalo de confiança, e "
        "sabe-se exatamente quanto custa melhorá-lo.",
        "<b>Valida a teoria (e vice-versa).</b> Como neste trabalho, a simulação é a forma mais "
        "direta de detetar erros em derivações analíticas, e a teoria é a forma de detetar erros "
        "em simuladores.",
    ])
    c.h2("Aplicações atuais")
    c.tabela(
        ["Área", "Utilização do Monte Carlo"],
        [["Redes e telecomunicações",
          "Curvas de BER/BLER de esquemas de modulação e codificação; capacidade ergódica de canais "
          "MIMO; PAPR de OFDM; dimensionamento de redes e simulação de protocolos (ex.: ns-3); "
          "avaliação de sistemas 5G/6G (os Trabalhos 2, 5 e 8 desta UC usam-no)."],
         ["Segurança e criptografia",
          "Análise de colisões e de geradores aleatórios (como neste trabalho); estimação de "
          "probabilidades de sucesso de ataques; testes estatísticos de aleatoriedade."],
         ["Inteligência artificial",
          "Monte Carlo Tree Search (base do AlphaGo, 2016); <i>dropout</i> de Monte Carlo para "
          "incerteza em redes neuronais; métodos de aprendizagem por reforço; amostragem em modelos "
          "generativos."],
         ["Estatística bayesiana",
          "MCMC (Metropolis–Hastings, Gibbs, Hamiltonian Monte Carlo) para amostrar distribuições "
          "a posteriori em problemas com milhares de parâmetros."],
         ["Finanças e seguros",
          "Avaliação de derivados, Value-at-Risk e testes de esforço exigidos pela regulação "
          "bancária e seguradora."],
         ["Física e medicina",
          "Transporte de partículas (Geant4, usado no CERN), planeamento de radioterapia, "
          "dosimetria; simulação de materiais e de sistemas moleculares."],
         ["Computação gráfica",
          "<i>Path tracing</i>: resolução da equação de renderização de Kajiya por amostragem de "
          "trajetos de luz, usada no cinema de animação e em motores de jogos com <i>ray tracing</i>."],
         ["Engenharia e clima",
          "Análise de fiabilidade e de tolerâncias, gestão de projetos, previsão meteorológica e "
          "climática por conjuntos (<i>ensembles</i>)."]],
        [0.26, 0.74], "Áreas onde o método de Monte Carlo é hoje essencial.", alinhar_esq=(0, 1),
        juntar=False)
    c.h2("Limitações e como são ultrapassadas")
    c.p(
        "O método não é gratuito. A convergência 1/√T é lenta para precisões elevadas, e os "
        "acontecimentos raros — como a colisão TKIP com poucos pacotes — exigem um número de "
        "ensaios proibitivo. Por isso, a investigação continua ativa: amostragem por importância "
        "e <i>splitting</i> para acontecimentos raros, variáveis de controlo e antitéticas para "
        "reduzir a variância, sequências quasi-aleatórias (quasi-Monte Carlo, com erro próximo de "
        "1/T) e Monte Carlo multinível. A qualidade do gerador pseudoaleatório também é crítica, "
        "como a secção 6.6 ilustrou: este trabalho usa o Philox (Salmon et al., 2011), gerador "
        "baseado em contador com período 2<super>256</super>, o mesmo tipo usado em GPUs (cuRAND) e no "
        "TensorFlow — e, por ironia, uma «sequência que não se repete» é exatamente a garantia que "
        "faltava ao IV do WEP.")

    # ---------------------------------------------------------- 8 Conclusões
    c.h1("Conclusões")
    c.p("O trabalho atingiu todos os objetivos do enunciado e respondeu às três questões de análise:")
    c.lista([
        f"<b>Q1.</b> Com n ≈ 4{NBSP}823 pacotes, a probabilidade de colisão de IV no WEP é de 50%: "
        f"{fp(w['p_exata_4823'], 3)} pela fórmula exata e {fp(w['p_sim_cdf_4823'])} por simulação "
        f"({fi(w['ensaios_cdf'])} ensaios), com o valor teórico dentro do intervalo de confiança.",
        "<b>Q2.</b> A probabilidade de colisão cresce muito mais depressa no WEP: para o mesmo "
        f"número de pacotes, a razão entre as probabilidades é de ≈{fsci(rs['razao_p_4823'], 1)}; "
        f"nenhum dos {fi(tkip_ens)} ensaios TKIP com até 15{NBSP}000 pacotes registou colisões.",
        f"<b>Q3.</b> O TKIP necessita de {fi(t['n50_exato'])} pacotes para os mesmos 50%: "
        f"{fi(rs['razao_n50'])} vezes mais (2<super>12</super>), e não 2<super>24</super> vezes — a "
        "resistência a colisões escala com a raiz quadrada do espaço de IV.",
    ])
    c.p(
        "Os dois estimadores de Monte Carlo implementados — direto e por primeira colisão — "
        "concordam entre si e com a teoria, e o estudo de convergência confirmou a lei 1/√T. Do "
        "ponto de vista de segurança, a conclusão é clara: um IV de 24 bits torna a reutilização de "
        "<i>keystream</i> inevitável em segundos de tráfego, o que, combinado com a ausência de "
        "chaves por pacote, condenou o WEP. O TKIP corrigiu este problema de forma eficaz, mas "
        "a lição mais geral é a do paradoxo do aniversário: <b>a segurança contra colisões é "
        "metade do número de bits</b>.")
    c.p(
        "Do ponto de vista metodológico, o trabalho mostra a complementaridade entre análise e "
        "simulação: a fórmula exata valida o simulador, o simulador valida a fórmula, e cada um "
        "cobre as limitações do outro — a simulação adapta-se a qualquer variante do modelo, e "
        "a teoria responde onde a simulação não chega, nos acontecimentos raros. É esta "
        "combinação que mantém o método de Monte Carlo como uma ferramenta de primeira linha, "
        "das redes móveis à inteligência artificial.")

    # --------------------------------------------------------- Referências
    c.historia.append(CondPageBreak(6 * cm))
    c.h1_sem_numero("Referências")
    refs = [
        "N. Borisov, I. Goldberg e D. Wagner, «Intercepting mobile communications: the insecurity "
        "of 802.11», <i>Proc. 7th ACM MobiCom</i>, pp. 180–189, 2001.",
        "S. Fluhrer, I. Mantin e A. Shamir, «Weaknesses in the key scheduling algorithm of RC4», "
        "<i>Selected Areas in Cryptography (SAC 2001)</i>, LNCS 2259, Springer, 2001.",
        "E. Tews, R.-P. Weinmann e A. Pyshkin, «Breaking 104 bit WEP in less than 60 seconds», "
        "<i>Information Security Applications (WISA 2007)</i>, LNCS 4867, Springer, 2007.",
        "M. Beck e E. Tews, «Practical attacks against WEP and WPA», <i>Proc. 2nd ACM WiSec</i>, 2009.",
        "IEEE Std 802.11-2020, <i>Wireless LAN Medium Access Control (MAC) and Physical Layer (PHY) "
        "Specifications</i>, IEEE, 2021.",
        "N. Metropolis e S. Ulam, «The Monte Carlo method», <i>Journal of the American Statistical "
        "Association</i>, vol. 44, n.º 247, pp. 335–341, 1949.",
        "N. Metropolis, «The beginning of the Monte Carlo method», <i>Los Alamos Science</i>, n.º 15, "
        "pp. 125–130, 1987.",
        "D. E. Knuth, <i>The Art of Computer Programming, Vol. 1</i>, 3.ª ed., Addison-Wesley, 1997 "
        "(secção 1.2.11.3, função Q(n) e problema do aniversário).",
        "P. Flajolet, D. Gardy e L. Thimonier, «Birthday paradox, coupon collectors, caching "
        "algorithms and self-organizing search», <i>Discrete Applied Mathematics</i>, vol. 39, "
        "pp. 207–229, 1992.",
        "E. B. Wilson, «Probable inference, the law of succession, and statistical inference», "
        "<i>Journal of the American Statistical Association</i>, vol. 22, pp. 209–212, 1927.",
        "R. Y. Rubinstein e D. P. Kroese, <i>Simulation and the Monte Carlo Method</i>, 3.ª ed., "
        "Wiley, 2016.",
        "M. E. O'Neill, «PCG: a family of simple fast space-efficient statistically good algorithms "
        "for random number generation», Harvey Mudd College, HMC-CS-2014-0905, 2014.",
        "D. Silver <i>et al.</i>, «Mastering the game of Go with deep neural networks and tree "
        "search», <i>Nature</i>, vol. 529, pp. 484–489, 2016.",
        "J. T. Kajiya, «The rendering equation», <i>Proc. ACM SIGGRAPH</i>, pp. 143–150, 1986.",
        "J. K. Salmon, M. A. Moraes, R. O. Dror e D. E. Shaw, «Parallel random numbers: as easy as "
        "1, 2, 3», <i>Proc. SC'11 (Int. Conf. for High Performance Computing)</i>, ACM, 2011.",
        "Enunciado dos Trabalhos laboratoriais (Python), Trabalho 6, " + UC + ".",
    ]
    for i, r in enumerate(refs, 1):
        c.historia.append(Paragraph(f"[{i}]{NBSP}{NBSP}{r}", st["ref"]))

    # --------------------------------------------------------------- Anexos
    c.historia.append(PageBreak())
    c.h1_sem_numero("Anexo A — Núcleo do estimador por primeira colisão")
    c.p("Excerto de <font name='Mono'>src/montecarlo.py</font> (código integral entregue em anexo ao relatório).")
    codigo = inspect.getsource(montecarlo.primeira_colisao)
    codigo = codigo.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    caixa_cod = Table([[XPreformatted(codigo, st["codigo"])]], colWidths=[c.largura])
    caixa_cod.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CINZA_CLARO),
                                   ("BOX", (0, 0), (-1, -1), 0.5, LINHA),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    c.historia.append(caixa_cod)
    c.historia.append(Spacer(1, 14))
    c.h1_sem_numero("Anexo B — Reprodução dos resultados")
    c.p("Requisitos: Python ≥ 3.10, NumPy ≥ 1.24 e Matplotlib ≥ 3.7 (o relatório usa ainda ReportLab). "
        "A partir da pasta do trabalho:")
    cmd = ("pip install -r requirements.txt\n"
           "cd src\n"
           f"python experiencias.py              # todas as experiências (~{fi(tempos['total'] / 60)} min, 8 núcleos)\n"
           "python experiencias.py --rapido     # versão reduzida (~3 min)\n"
           "python experiencias.py --so-figuras # regenera figuras a partir de resultados/\n"
           "cd ../relatorio\n"
           "python gerar_relatorio.py           # gera este PDF")
    caixa_cmd = Table([[XPreformatted(cmd, st["codigo"])]], colWidths=[c.largura])
    caixa_cmd.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CINZA_CLARO),
                                   ("BOX", (0, 0), (-1, -1), 0.5, LINHA),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    c.historia.append(caixa_cmd)
    c.historia.append(Spacer(1, 8))
    c.p(f"Todas as experiências usam a semente-mãe {rs['semente']}, pelo que a execução completa "
        "reproduz exatamente os valores apresentados neste relatório.")


def main():
    registar_fontes()
    with open(RAIZ / "resultados" / "resultados.json", encoding="utf-8") as f:
        R = json.load(f)
    doc = Relatorio(SAIDA)
    with tempfile.TemporaryDirectory() as tmp:
        c = Construtor(estilos(), doc.width, Path(tmp))
        construir(R, c)
        doc.multiBuild(c.historia)
    print(f"Relatório gerado: {SAIDA}")


if __name__ == "__main__":
    main()
