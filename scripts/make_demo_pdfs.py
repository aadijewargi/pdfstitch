"""Generate the sample PDFs used for the README screenshots.

Needs reportlab (not a pdfstitch dependency): pip install reportlab
Usage: python scripts/make_demo_pdfs.py OUTPUT_FOLDER
"""

import math
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen.canvas import Canvas

INK = HexColor("#1d2433")
MUTED = HexColor("#5a6478")
ACCENT = HexColor("#2f6fd6")
RED = HexColor("#b0263b")


def paragraph_lines(c, x, y, n, width, seed=0):
    """Grey bars standing in for body text."""
    c.setFillColor(HexColor("#c9d1da"))
    for i in range(n):
        w = width * (0.62 + 0.38 * ((i * 37 + seed * 11) % 10) / 10) if i % 6 != 5 else width * 0.45
        c.rect(x, y - i * 16, w, 7, stroke=0, fill=1)
    return y - n * 16


def cover(path):
    c = Canvas(str(path), pagesize=A4)
    w, h = A4
    c.setFillColor(HexColor("#22304a"))
    c.rect(0, h * 0.45, w, h * 0.55, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Times-Roman", 40)
    c.drawString(60, h - 200, "The Simple Pendulum")
    c.setFont("Helvetica", 16)
    c.drawString(62, h - 235, "Measuring g from small-angle oscillations")
    c.setFillColor(INK)
    c.setFont("Helvetica", 13)
    c.drawString(62, h * 0.45 - 60, "Physics 1B laboratory report")
    c.setFillColor(MUTED)
    c.drawString(62, h * 0.45 - 82, "Autumn term")
    c.showPage()
    c.save()


def report(path, pages=5):
    c = Canvas(str(path), pagesize=A4)
    w, h = A4
    titles = ["1  Introduction", "2  Theory", "3  Method", "4  Results", "5  Discussion"]
    for p in range(pages):
        c.setFillColor(INK)
        c.setFont("Times-Bold", 20)
        c.drawString(60, h - 80, titles[p % len(titles)])
        y = paragraph_lines(c, 60, h - 120, 14, w - 120, seed=p)
        if p == 1:
            c.setFillColor(INK)
            c.setFont("Times-Italic", 22)
            c.drawCentredString(w / 2, y - 40, "T = 2π √(L / g)")
            paragraph_lines(c, 60, y - 90, 12, w - 120, seed=p + 3)
        elif p == 3:
            # a small damped-oscillation plot
            x0, y0, pw, ph = 80, y - 260, w - 160, 200
            c.setStrokeColor(MUTED)
            c.setLineWidth(1)
            c.line(x0, y0, x0 + pw, y0)
            c.line(x0, y0 - ph / 2, x0, y0 + ph / 2)
            c.setStrokeColor(ACCENT)
            c.setLineWidth(2.2)
            pts = [(x0 + pw * t / 400, y0 + (ph / 2 - 6) * math.exp(-t / 260) * math.cos(t / 400 * 2 * math.pi * 6))
                   for t in range(401)]
            path_ = c.beginPath()
            path_.moveTo(*pts[0])
            for pt in pts[1:]:
                path_.lineTo(*pt)
            c.drawPath(path_, stroke=1, fill=0)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 10)
            c.drawString(x0, y0 - ph / 2 - 18, "Figure 1. Angle against time, L = 0.85 m")
            paragraph_lines(c, 60, y0 - ph / 2 - 50, 8, w - 120, seed=p)
        else:
            paragraph_lines(c, 60, y - 30, 16, w - 120, seed=p + 5)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawCentredString(w / 2, 40, str(p + 1))
        c.showPage()
    c.save()


def scans(path, pages=4):
    c = Canvas(str(path), pagesize=letter)
    w, h = letter
    for p in range(pages):
        c.setFillColor(HexColor("#f3f0e8"))
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setFillColor(HexColor("#3a3f4a"))
        c.setFont("Courier", 13)
        c.drawString(70, h - 80, f"Data sheet {p + 1}: period timings")
        c.setFont("Courier", 11)
        for r in range(22):
            L = 0.30 + 0.05 * r
            T = 2 * math.pi * math.sqrt(L / 9.81)
            c.drawString(70, h - 120 - r * 22, f"L = {L:.2f} m    10T = {10 * T + 0.03 * math.sin(r * 7 + p):6.2f} s")
        c.setStrokeColor(RED)
        c.setLineWidth(1.4)
        c.circle(w - 120, 110, 34, stroke=1, fill=0)
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(w - 120, 106, "CHECKED")
        c.showPage()
    c.save()


def references(path):
    c = Canvas(str(path), pagesize=A4)
    w, h = A4
    c.setFillColor(INK)
    c.setFont("Times-Bold", 20)
    c.drawString(60, h - 80, "References")
    y = h - 120
    for i in range(6):
        c.setFont("Times-Roman", 12)
        c.drawString(60, y, f"[{i + 1}]")
        paragraph_lines(c, 95, y + 2, 2, w - 160, seed=i)
        y -= 46
    c.showPage()
    c.save()


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "demo")
    out.mkdir(parents=True, exist_ok=True)
    cover(out / "01 cover.pdf")
    report(out / "02 lab report.pdf")
    scans(out / "03 data sheets (scanned).pdf")
    references(out / "04 references.pdf")
    print(f"wrote 4 PDFs to {out}")
