"""Capture screenshots of the running NetGuard app (streamlit run app.py)."""
import os
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(OUT, exist_ok=True)


def settle(page, ms=3500):
    page.wait_for_timeout(ms)
    page.wait_for_function("!document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60000)


with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2,
                      color_scheme="dark")
    page.goto(URL)
    page.get_by_text("Connexions analysées").wait_for(timeout=90000)
    settle(page, 5000)
    page.wait_for_selector(".js-plotly-plot .main-svg", timeout=60000)
    page.wait_for_timeout(3000)
    page.add_style_tag(content="[data-testid='stToolbar'],[data-testid='stDecoration'],"
                               "[data-testid='stStatusWidget']{display:none !important}")
    page.screenshot(path=os.path.join(OUT, "1_tableau_de_bord.png"))
    page.mouse.move(900, 500)
    page.mouse.wheel(0, 700)
    page.wait_for_timeout(2500)
    page.screenshot(path=os.path.join(OUT, "2_journal_des_alertes.png"))

    page.get_by_role("tab", name="Expliquer une alerte").click()
    settle(page, 5000)
    page.mouse.wheel(0, -2000)
    page.wait_for_timeout(1000)
    page.screenshot(path=os.path.join(OUT, "3_explication_alerte.png"))

    page.get_by_role("tab", name="Performance du modèle").click()
    settle(page, 3000)
    page.screenshot(path=os.path.join(OUT, "4_performance.png"))
    b.close()
print("Saved to", OUT)
