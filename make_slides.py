"""Generate the DataNova submission deck from artifacts/metrics.json.

Usage: python make_slides.py [--demo URL] [--github URL]
"""
import argparse
import json
import os
import random

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "artifacts")
AUTHOR = "Binetou Rassoul SEYE"

PAPER = RGBColor(0xF6, 0xF3, 0xEE)
INK = RGBColor(0x17, 0x18, 0x1C)
GREY = RGBColor(0x6E, 0x6A, 0x64)
LINE = RGBColor(0xD9, 0xD3, 0xC9)
TEAL = RGBColor(0x0F, 0x5C, 0x57)
TEAL_SOFT = RGBColor(0xDC, 0xE9, 0xE6)
RUST = RGBColor(0xC4, 0x51, 0x2B)
SAND = RGBColor(0xBF, 0xB7, 0xAA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK_MUTED = RGBColor(0x9A, 0x96, 0x8E)

HEAD = "Georgia"
BODY = "Segoe UI"
W, H = Inches(13.333), Inches(7.5)
TOTAL = 11


def pct(x, d=1):
    return f"{x * 100:.{d}f} %".replace(".", ",")


def num(n):
    return f"{n:,}".replace(",", " ")


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.layout = self.prs.slide_layouts[6]
        self.n = 0

    # ---------- primitives ----------
    def bg(self, s, color):
        f = s.background.fill
        f.solid()
        f.fore_color.rgb = color

    def box(self, s, x, y, w, h, fill=None, line=None, lw=1.0, shape=MSO_SHAPE.RECTANGLE):
        r = s.shapes.add_shape(shape, x, y, w, h)
        if fill is None:
            r.fill.background()
        else:
            r.fill.solid()
            r.fill.fore_color.rgb = fill
        if line is None:
            r.line.fill.background()
        else:
            r.line.color.rgb = line
            r.line.width = Pt(lw)
        r.shadow.inherit = False
        return r

    def hline(self, s, x, y, w, color=LINE, lw=0.75):
        ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x, y, x + w, y)
        ln.line.color.rgb = color
        ln.line.width = Pt(lw)
        return ln

    def arrow(self, s, x1, y1, x2, y2, color=GREY, lw=1.25):
        ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
        ln.line.color.rgb = color
        ln.line.width = Pt(lw)
        lnxml = ln.line._get_or_add_ln()
        tail = etree.SubElement(lnxml, qn("a:tailEnd"))
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")
        return ln

    def text(self, s, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, spacing=1.1):
        """paras: list of paragraphs; each paragraph is a list of runs
        (text, size, color, font, bold, italic) or a single run tuple."""
        tb = s.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        if isinstance(paras, tuple):
            paras = [paras]
        for i, para in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.line_spacing = spacing
            runs = [para] if isinstance(para, tuple) else para
            size = 12
            for run in runs:
                t, size, color, font, bold, italic = (list(run) + [None] * 6)[:6]
                r = p.add_run()
                r.text = t
                r.font.size = Pt(size or 14)
                r.font.color.rgb = color or INK
                r.font.name = font or BODY
                r.font.bold = bool(bold)
                r.font.italic = bool(italic)
            p.space_after = Pt((size or 14) * 0.6)
        return tb

    # ---------- page frame ----------
    def page(self, section, title, sub=None):
        s = self.prs.slides.add_slide(self.layout)
        self.n += 1
        self.bg(s, PAPER)
        self.text(s, Inches(0.75), Inches(0.5), Inches(8), Inches(0.3),
                  (f"{self.n:02d}   {section.upper()}", 10.5, TEAL, BODY, True))
        self.text(s, Inches(0.75), Inches(0.85), Inches(11.8), Inches(1.0),
                  (title, 30, INK, HEAD, False), spacing=1.0)
        if sub:
            self.text(s, Inches(0.75), Inches(1.65), Inches(11.5), Inches(0.5), (sub, 14, GREY))
        self.hline(s, Inches(0.75), Inches(6.95), Inches(11.83))
        self.text(s, Inches(0.75), Inches(7.05), Inches(6), Inches(0.3),
                  [[("NetGuard", 9.5, INK, BODY, True), ("   DataNova 2026 · DN-CY-01", 9.5, GREY)]])
        self.text(s, Inches(9.6), Inches(7.05), Inches(2.98), Inches(0.3),
                  (f"{self.n:02d} / {TOTAL:02d}", 9.5, GREY), align=PP_ALIGN.RIGHT)
        return s

    def node(self, s, x, y, w, h, title, sub, fill=WHITE, line=LINE, tcolor=INK, scolor=GREY):
        self.box(s, x, y, w, h, fill, line, 1.0)
        self.text(s, x + Inches(0.18), y, w - Inches(0.36), h,
                  [(title, 13, tcolor, BODY, True), (sub, 10.5, scolor)],
                  anchor=MSO_ANCHOR.MIDDLE, spacing=1.0)

    def style_chart(self, chart, size=11):
        chart.font.name = BODY
        chart.font.size = Pt(size)
        chart.font.color.rgb = GREY


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", default="")
    ap.add_argument("--github", default="")
    a = ap.parse_args()

    M = json.load(open(os.path.join(ART, "metrics.json"), encoding="utf-8"))
    b, h = M["baseline"], M["netguard_hybrid"]
    u = M["unseen_attack_detection"]
    tr, te, sm = M["train_counts"], M["test_counts"], M["smote_counts"]
    n_train, n_test = sum(tr.values()), sum(te.values())
    classes = ["normal", "DoS", "Probe", "R2L", "U2R"]

    d = Deck()

    # ============ 1. Cover ============
    s = d.prs.slides.add_slide(d.layout)
    d.n += 1
    d.bg(s, INK)
    # field of "connections": a few of them flagged
    random.seed(7)
    cols, rows = 13, 11
    x0, y0, step = Inches(7.55), Inches(0.95), Inches(0.42)
    flagged = {(9, 2), (3, 6), (11, 8), (6, 9)}
    for i in range(cols):
        for j in range(rows):
            if random.random() < 0.18:
                continue
            is_f = (i, j) in flagged
            r = Inches(0.13) if is_f else Inches(0.06)
            cx, cy = x0 + step * i, y0 + step * j
            dot = d.box(s, cx - r // 2, cy - r // 2, r, r, RUST if is_f else RGBColor(0x3A, 0x3C, 0x42),
                        shape=MSO_SHAPE.OVAL)
            if is_f:
                ring = d.box(s, cx - Inches(0.14), cy - Inches(0.14), Inches(0.28), Inches(0.28),
                             None, RUST, 0.75, MSO_SHAPE.OVAL)
    d.text(s, Inches(0.85), Inches(0.9), Inches(6), Inches(0.4),
           ("DATANOVA 2026  ·  CYBERSÉCURITÉ ET DÉTECTION DES FRAUDES", 10.5, DARK_MUTED, BODY, True))
    d.text(s, Inches(0.85), Inches(2.1), Inches(6.5), Inches(1.4), ("NetGuard", 66, WHITE, HEAD))
    d.text(s, Inches(0.85), Inches(3.45), Inches(6.2), Inches(1.6),
           ("Repérer les intrusions rares et inédites dans le trafic réseau, et expliquer chaque alerte.",
            20, RGBColor(0xD8, 0xD4, 0xCC), HEAD, False, True), spacing=1.15)
    d.box(s, Inches(0.85), Inches(5.55), Inches(0.05), Inches(0.75), TEAL_SOFT)
    d.text(s, Inches(1.1), Inches(5.5), Inches(6), Inches(0.9),
           [(AUTHOR, 17, WHITE, BODY, True), ("Problème DN-CY-01 · Novembre 2026", 12, DARK_MUTED)])

    # ============ 2. Problem ============
    s = d.page("Le problème", "Les attaques les plus graves sont aussi les plus rares")
    d.text(s, Inches(0.75), Inches(2.25), Inches(5.2), Inches(1.8),
           (pct(tr["U2R"] / n_train, 2), 88, RUST, HEAD))
    d.text(s, Inches(0.75), Inches(3.85), Inches(4.9), Inches(1.6),
           (f"du trafic d'entraînement correspond à une élévation de privilèges (U2R) : "
            f"{tr['U2R']} connexions sur {num(n_train)}.", 15, INK), spacing=1.2)
    vx = Inches(6.55)
    d.box(s, Inches(6.25), Inches(2.35), Pt(0.75), Inches(3.9), LINE)
    facts = [
        (pct(b["per_class_recall"]["U2R"]), "des élévations de privilèges sont détectées par un modèle entraîné sans précaution."),
        (pct(b["per_class_recall"]["R2L"]), "seulement des accès distants non autorisés (R2L) sont repérés."),
        (str(len(M["unseen_attack_types"])), "types d'attaques du jeu de test n'apparaissent jamais à l'entraînement."),
    ]
    for k, (big, txt) in enumerate(facts):
        y = Inches(2.35 + k * 1.35)
        d.text(s, vx, y, Inches(1.9), Inches(0.8), (big, 30, INK, HEAD))
        d.text(s, vx + Inches(2.0), y + Inches(0.08), Inches(4.0), Inches(1.1), (txt, 13.5, GREY), spacing=1.15)
    d.text(s, Inches(0.75), Inches(6.1), Inches(11.5), Inches(0.5),
           ("Un analyste ne peut pas réagir à une intrusion que son outil ne voit pas.", 14, TEAL, HEAD, False, True))

    # ============ 3. Obstacles ============
    s = d.page("Pourquoi c'est difficile", "Trois obstacles, un seul outil pour les traiter")
    items = [
        ("Rareté", "Un modèle classique optimise sa précision globale. Les 52 exemples U2R pèsent "
                   "presque rien face à 67 000 connexions normales : il apprend à les ignorer."),
        ("Nouveauté", "Les attaquants changent de technique. Un classifieur supervisé ne reconnaît "
                      "que ce qu'il a déjà vu pendant l'entraînement."),
        ("Opacité", "Une alerte sans justification finit souvent ignorée. L'analyste doit savoir "
                    "pourquoi la connexion est jugée dangereuse, et quoi faire."),
    ]
    for k, (t, txt) in enumerate(items):
        x = Inches(0.75 + k * 4.05)
        d.text(s, x, Inches(2.3), Inches(1), Inches(0.9), (f"{k + 1}", 44, TEAL, HEAD))
        d.hline(s, x, Inches(3.25), Inches(3.6), INK, 1.0)
        d.text(s, x, Inches(3.45), Inches(3.6), Inches(0.5), (t, 19, INK, HEAD, True))
        d.text(s, x, Inches(4.0), Inches(3.6), Inches(2.2), (txt, 13, GREY), spacing=1.25)
    d.box(s, Inches(0.75), Inches(5.95), Inches(11.83), Inches(0.75), TEAL_SOFT)
    d.text(s, Inches(1.0), Inches(5.95), Inches(11.4), Inches(0.75),
           [[("Pour qui ?  ", 13, TEAL, BODY, True),
             ("Les équipes sécurité de PME, d'universités et d'administrations, souvent sans surveillance 24 h/24.",
              13, INK)]], anchor=MSO_ANCHOR.MIDDLE)

    # ============ 4. Approach ============
    s = d.page("L'approche", "Deux filets plutôt qu'un")
    I = Inches
    d.node(s, I(0.75), I(3.3), I(2.0), I(1.0), "Connexion", "41 mesures réseau")
    d.node(s, I(3.35), I(3.15), I(2.75), I(1.3), "Filet 1 · Classifieur",
           "XGBoost entraîné avec SMOTE et pondération des classes rares", TEAL, TEAL, WHITE,
           RGBColor(0xCF, 0xE2, 0xDE))
    d.node(s, I(6.95), I(2.05), I(2.6), I(1.05), "Attaque reconnue", "DoS, Probe, R2L ou U2R")
    d.node(s, I(6.95), I(4.4), I(2.6), I(1.3), "Filet 2 · Anomalies",
           "Isolation Forest appris sur le trafic normal uniquement", TEAL, TEAL, WHITE,
           RGBColor(0xCF, 0xE2, 0xDE))
    d.node(s, I(10.35), I(2.05), I(2.23), I(1.05), "Alerte typée", "+ explication SHAP", WHITE, INK)
    d.node(s, I(10.35), I(3.95), I(2.23), I(0.95), "Alerte « suspecte »", "attaque possiblement inédite",
           WHITE, RUST, RUST)
    d.node(s, I(10.35), I(5.2), I(2.23), I(0.85), "Trafic accepté", "aucune action", PAPER, LINE)
    d.arrow(s, I(2.75), I(3.8), I(3.35), I(3.8))
    d.arrow(s, I(6.1), I(3.45), I(6.95), I(2.6))
    d.arrow(s, I(6.1), I(4.15), I(6.95), I(5.0))
    d.arrow(s, I(9.55), I(2.58), I(10.35), I(2.58))
    d.arrow(s, I(9.55), I(4.75), I(10.35), I(4.42), RUST)
    d.arrow(s, I(9.55), I(5.3), I(10.35), I(5.62))
    d.text(s, I(6.2), I(2.7), I(1.2), I(0.3), ("attaque", 10, GREY, BODY, False, True))
    d.text(s, I(6.2), I(4.75), I(1.2), I(0.3), ("« normal »", 10, GREY, BODY, False, True))
    d.text(s, I(9.6), I(4.15), I(0.8), I(0.3), ("anormal", 10, RUST, BODY, False, True))
    d.text(s, I(0.75), I(5.0), I(5.6), I(1.6),
           ("Le second filet n'apprend que le trafic normal. Il signale donc tout ce qui s'en écarte, "
            "y compris une attaque que personne n'a encore étiquetée.", 13, GREY), spacing=1.25)

    # ============ 5. Data ============
    s = d.page("Données et protocole", "Un jeu de test volontairement plus dur que l'entraînement")
    d.text(s, Inches(0.75), Inches(2.3), Inches(5.0), Inches(4.2), [
        [("NSL-KDD", 14, INK, BODY, True),
         (", référence publique de l'Université du Nouveau-Brunswick : chaque ligne décrit une connexion "
          "TCP/IP par 41 mesures (durée, octets, service, taux d'erreurs…).", 14, GREY)],
        [("Évaluation honnête. ", 14, INK, BODY, True),
         (f"Le modèle est jugé sur KDDTest+ ({num(n_test)} connexions), jamais utilisé pour l'entraînement "
          "ni pour régler les seuils.", 14, GREY)],
        [("Rééquilibrage. ", 14, INK, BODY, True),
         ("SMOTE crée des exemples synthétiques de R2L et U2R, uniquement dans les données d'entraînement.", 14, GREY)],
    ], spacing=1.25)
    # hand-built table
    tx, ty = Inches(6.6), Inches(2.3)
    cw = [Inches(1.6), Inches(1.45), Inches(1.45), Inches(1.45)]
    heads = ["Classe", "Entraînement", "Après SMOTE", "Test"]
    x = tx
    for c, hd in enumerate(heads):
        d.text(s, x, ty, cw[c], Inches(0.35), (hd, 11, GREY, BODY, True),
               align=PP_ALIGN.LEFT if c == 0 else PP_ALIGN.RIGHT)
        x += cw[c]
    d.hline(s, tx, ty + Inches(0.42), sum(cw, Inches(0)), INK, 1.0)
    for r, cl in enumerate(classes):
        y = ty + Inches(0.55 + r * 0.55)
        vals = [cl, num(tr.get(cl, 0)), num(sm[cl]), num(te.get(cl, 0))]
        x = tx
        hl = cl in ("R2L", "U2R")
        for c, v in enumerate(vals):
            color = RUST if (hl and c == 2) else INK
            d.text(s, x, y, cw[c], Inches(0.35), (v, 14, color, BODY, c == 0 or (hl and c == 2)),
                   align=PP_ALIGN.LEFT if c == 0 else PP_ALIGN.RIGHT)
            x += cw[c]
        d.hline(s, tx, y + Inches(0.45), sum(cw, Inches(0)), LINE)
    d.text(s, tx, ty + Inches(3.45), Inches(5.9), Inches(0.6),
           (f"Le test contient {len(M['unseen_attack_types'])} types d'attaques absents de l'entraînement "
            f"({num(u['n_samples'])} connexions).", 11.5, GREY, BODY, False, True))

    # ============ 6. Results ============
    s = d.page("Résultats", "Plus d'attaques détectées, sans noyer l'analyste",
               sub=f"Mesuré sur les {num(n_test)} connexions de KDDTest+, comparé au même modèle XGBoost sans traitement du déséquilibre.")
    big = [
        (pct(h["attack_detection_rate"]), "des attaques détectées", pct(b["attack_detection_rate"])),
        (pct(u["netguard_hybrid"]), "des attaques jamais vues à l'entraînement détectées", pct(u["baseline"])),
        (f"{h['macro_f1']:.2f}".replace(".", ","), "de F1 macro (chaque classe compte autant)",
         f"{b['macro_f1']:.2f}".replace(".", ",")),
    ]
    for k, (v, lab, ref) in enumerate(big):
        x = Inches(0.75 + k * 4.05)
        d.text(s, x, Inches(2.55), Inches(3.8), Inches(1.2), (v, 54, TEAL, HEAD))
        d.text(s, x, Inches(3.75), Inches(3.5), Inches(0.9), (lab, 14, INK), spacing=1.15)
        d.hline(s, x, Inches(4.75), Inches(3.5))
        d.text(s, x, Inches(4.88), Inches(3.5), Inches(0.4),
               [[("Modèle classique : ", 12, GREY), (ref, 12, GREY, BODY, True)]])
    d.text(s, Inches(0.75), Inches(5.75), Inches(11.5), Inches(0.9),
           [[("Le prix à payer : ", 13, RUST, BODY, True),
             (f"les fausses alertes passent de {pct(b['false_alarm_rate'])} à {pct(h['false_alarm_rate'])}. "
              "Le seuil reste réglable dans l'application selon la tolérance de l'équipe.", 13, GREY)]], spacing=1.2)

    # ============ 7. Per-class chart ============
    s = d.page("Où se fait le gain", "Le progrès se concentre sur les attaques rares")
    cd = CategoryChartData()
    cd.categories = classes
    cd.add_series("Modèle classique", [round(b["per_class_recall"][c] * 100) for c in classes])
    cd.add_series("NetGuard", [round(h["per_class_recall"][c] * 100) for c in classes])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.9),
                            Inches(8.2), Inches(4.85), cd)
    ch = gf.chart
    d.style_chart(ch)
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.TOP
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(11)
    va = ch.value_axis
    va.maximum_scale, va.minimum_scale = 100, 0
    va.tick_labels.number_format = '0" %"'
    va.tick_labels.number_format_is_linked = False
    va.major_gridlines.format.line.color.rgb = LINE
    va.format.line.fill.background()
    ch.category_axis.format.line.color.rgb = SAND
    ch.category_axis.tick_labels.font.size = Pt(12)
    ch.category_axis.tick_labels.font.color.rgb = INK
    plot = ch.plots[0]
    plot.gap_width = 70
    plot.overlap = -10
    for ser, col in zip(plot.series, [SAND, TEAL]):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = col
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = '0'
    dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(9.5)
    dl.font.color.rgb = GREY
    notes = [("U2R", "élévation de privilèges"), ("Probe", "scans et reconnaissance"), ("R2L", "accès distants")]
    y = Inches(2.2)
    for cl, desc in notes:
        bb, hh = b["per_class_recall"][cl], h["per_class_recall"][cl]
        d.text(s, Inches(9.3), y, Inches(3.3), Inches(0.35), (f"{cl} · {desc}", 11, GREY, BODY, True))
        d.text(s, Inches(9.3), y + Inches(0.35), Inches(3.3), Inches(0.7),
               [[(pct(bb, 0).replace(" ", " "), 24, SAND, HEAD), ("  →  ", 18, GREY),
                 (pct(hh, 0).replace(" ", " "), 24, TEAL, HEAD)]])
        d.hline(s, Inches(9.3), y + Inches(1.15), Inches(3.3))
        y += Inches(1.4)
    d.text(s, Inches(9.3), y + Inches(0.05), Inches(3.3), Inches(0.9),
           ("R2L reste le point faible : beaucoup de ces attaques imitent une connexion légitime.", 11, GREY, BODY, False, True),
           spacing=1.15)

    # ============ 8. Explainability ============
    s = d.page("Explicabilité", "Chaque alerte dit pourquoi elle a été levée")
    imp = M["shap_importance"][:8]
    cd = CategoryChartData()
    cd.categories = [n for n, _ in imp][::-1]
    cd.add_series("Importance", [round(v, 3) for _, v in imp][::-1])
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(2.0),
                            Inches(6.4), Inches(4.7), cd)
    ch = gf.chart
    d.style_chart(ch, 11)
    ch.has_legend = False
    ch.value_axis.visible = False
    ch.value_axis.has_major_gridlines = False
    ch.category_axis.format.line.color.rgb = SAND
    ch.category_axis.tick_labels.font.color.rgb = INK
    pl = ch.plots[0]
    pl.gap_width = 55
    ser = pl.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = TEAL
    pl.has_data_labels = True
    pl.data_labels.number_format = '0.00'
    pl.data_labels.number_format_is_linked = False
    pl.data_labels.font.size = Pt(9.5)
    pl.data_labels.font.color.rgb = GREY
    d.text(s, Inches(0.6), Inches(1.7), Inches(6.4), Inches(0.3),
           ("Variables les plus influentes (importance SHAP moyenne)", 11, GREY, BODY, True))
    d.text(s, Inches(7.6), Inches(2.0), Inches(4.95), Inches(0.4), ("Ce que voit l'analyste", 17, INK, HEAD, True))
    steps = [("Le verdict", "la famille d'attaque et la confiance du modèle"),
             ("Les raisons", "les mesures qui ont le plus pesé, par exemple un volume d'octets envoyés anormal"),
             ("L'action conseillée", "bloquer l'IP, forcer le MFA, isoler l'hôte… selon le type d'attaque"),
             ("Le réglage", "un curseur pour arbitrer entre détection et fausses alertes")]
    for k, (t, txt) in enumerate(steps):
        y = Inches(2.65 + k * 0.98)
        d.text(s, Inches(7.6), y, Inches(0.5), Inches(0.5), (f"{k + 1}", 20, TEAL, HEAD))
        d.text(s, Inches(8.15), y + Inches(0.03), Inches(4.4), Inches(0.9),
               [(t, 13, INK, BODY, True), (txt, 12, GREY)], spacing=1.05)

    # ============ 9. Demo ============
    s = d.page("Prototype", "Une application web prête à l'emploi")
    flow = [("Importer", "un fichier CSV de connexions, ou utiliser l'échantillon de test fourni"),
            ("Surveiller", "nombre d'alertes, alertes critiques, connexions suspectes, services visés"),
            ("Comprendre", "pour chaque alerte : probabilités, variables décisives et action conseillée"),
            ("Exporter", "le journal d'alertes en CSV, pour l'équipe sécurité")]
    for k, (t, txt) in enumerate(flow):
        x = Inches(0.75 + k * 3.03)
        d.box(s, x, Inches(2.3), Inches(2.75), Inches(2.6), WHITE, LINE)
        d.text(s, x + Inches(0.25), Inches(2.5), Inches(1), Inches(0.6), (f"0{k + 1}", 22, TEAL, HEAD))
        d.text(s, x + Inches(0.25), Inches(3.15), Inches(2.3), Inches(0.5), (t, 17, INK, HEAD, True))
        d.text(s, x + Inches(0.25), Inches(3.65), Inches(2.3), Inches(1.3), (txt, 12, GREY), spacing=1.2)
    d.text(s, Inches(0.75), Inches(5.25), Inches(11.5), Inches(0.4),
           ("Python · scikit-learn · XGBoost · imbalanced-learn · SHAP · Streamlit · Plotly", 12, GREY))
    links = []
    if a.demo:
        links.append([("Démo  ", 12, TEAL, BODY, True), (a.demo, 12, INK)])
    if a.github:
        links.append([("Code  ", 12, TEAL, BODY, True), (a.github, 12, INK)])
    if not links:
        links = [[("Démo et code source : ", 12, TEAL, BODY, True), ("liens sur la page Devpost du projet", 12, INK)]]
    d.text(s, Inches(0.75), Inches(5.8), Inches(11.5), Inches(0.9), links)

    # ============ 10. Impact ============
    s = d.page("Impact et limites", "Ce que NetGuard change, et ce qu'il reste à prouver")
    left = [("Accessible", "Outils libres, fonctionne sur un simple ordinateur : l'entraînement complet prend environ deux minutes."),
            ("Intégrable", "Les entrées sont des métadonnées de connexion, proches de ce que produisent Zeek ou NetFlow."),
            ("Respectueux", "Aucun contenu de paquet ni donnée personnelle n'est analysé.")]
    right = [("Données anciennes", "NSL-KDD date de 2009. Il faut ré-entraîner sur des flux récents (CICIDS, UNSW-NB15)."),
             ("U2R très rare", "52 exemples seulement : le résultat doit être confirmé sur davantage de données."),
             ("Prochaine étape", "Analyse en flux continu, ré-entraînement avec les retours de l'analyste, pilote sur un réseau universitaire.")]
    for col, (title, items, color) in enumerate([("Ce que ça change", left, TEAL), ("Ce qu'il reste à prouver", right, RUST)]):
        x = Inches(0.75 + col * 6.1)
        d.text(s, x, Inches(2.2), Inches(5.6), Inches(0.4), (title, 17, color, HEAD, True))
        d.hline(s, x, Inches(2.75), Inches(5.6), color, 1.0)
        for k, (t, txt) in enumerate(items):
            d.text(s, x, Inches(2.95 + k * 1.25), Inches(5.6), Inches(1.2),
                   [(t, 13, INK, BODY, True), (txt, 12.5, GREY)], spacing=1.1)

    # ============ 11. Closing ============
    s = d.prs.slides.add_slide(d.layout)
    d.n += 1
    d.bg(s, INK)
    d.text(s, Inches(0.85), Inches(2.3), Inches(10), Inches(1.3), ("Merci.", 60, WHITE, HEAD))
    d.text(s, Inches(0.85), Inches(3.6), Inches(9), Inches(0.9),
           ("Une alerte utile est une alerte qu'on voit, qu'on comprend et sur laquelle on peut agir.",
            18, RGBColor(0xD8, 0xD4, 0xCC), HEAD, False, True), spacing=1.15)
    d.box(s, Inches(0.85), Inches(5.0), Inches(0.05), Inches(0.75), TEAL_SOFT)
    lines = [(AUTHOR, 17, WHITE, BODY, True),
             ("Conception, données, modélisation, application et présentation", 12, DARK_MUTED)]
    d.text(s, Inches(1.1), Inches(4.95), Inches(9), Inches(0.9), lines)
    extra = "   ·   ".join(x for x in [a.demo, a.github] if x)
    if extra:
        d.text(s, Inches(0.85), Inches(6.3), Inches(11), Inches(0.4), (extra, 12, DARK_MUTED))

    assert d.n == TOTAL, d.n
    out = os.path.join(HERE, "NetGuard_DataNova2026.pptx")
    d.prs.save(out)
    print("Saved", out)


if __name__ == "__main__":
    main()
