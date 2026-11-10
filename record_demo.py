"""Record a captioned walkthrough video of the running NetGuard app.

Usage: python record_demo.py [URL]   ->  demo/NetGuard_demo.mp4
"""
import glob
import os
import shutil
import subprocess
import sys
import time

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "demo")
RAW = os.path.join(OUT, "raw")
W, H = 1280, 720

OVERLAY_JS = """
() => {
  if (document.getElementById('ng-cap')) return;
  const st = document.createElement('style');
  st.textContent = `
    #ng-cap{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:2147483647;
      max-width:900px;padding:14px 22px;border-radius:10px;background:rgba(10,12,16,.88);
      color:#fff;font:500 21px/1.35 'Segoe UI',system-ui,sans-serif;text-align:center;
      box-shadow:0 6px 24px rgba(0,0,0,.35);transition:opacity .35s;opacity:0}
    #ng-cap b{color:#5fd3b8}
    #ng-card{position:fixed;inset:0;z-index:2147483647;background:#17181c;display:flex;
      flex-direction:column;justify-content:center;padding:0 110px;transition:opacity .6s;
      font-family:Georgia,serif;color:#fff}
    #ng-card h1{font-size:76px;font-weight:400;margin:0 0 14px}
    #ng-card p{font-size:26px;font-style:italic;color:#d8d4cc;margin:0 0 40px;max-width:820px}
    #ng-card small{font:600 18px 'Segoe UI',sans-serif;color:#9a968e;letter-spacing:.04em}
    [data-testid='stToolbar'],[data-testid='stDecoration'],[data-testid='stStatusWidget']{display:none!important}`;
  document.head.appendChild(st);
  const c = document.createElement('div'); c.id = 'ng-cap'; document.body.appendChild(c);
}
"""


def caption(page, html, hold):
    page.evaluate("""(h) => { const c = document.getElementById('ng-cap');
        c.style.opacity = 0; setTimeout(() => { c.innerHTML = h; c.style.opacity = 1; }, 300); }""", html)
    page.wait_for_timeout(int(hold * 1000))


def clear(page):
    page.evaluate("() => { const c = document.getElementById('ng-cap'); if (c) c.style.opacity = 0; }")
    page.wait_for_timeout(350)


def card(page, title, sub, foot, hold):
    page.evaluate("""([t, s, f]) => { let d = document.getElementById('ng-card');
        if (!d) { d = document.createElement('div'); d.id = 'ng-card'; document.body.appendChild(d); }
        d.innerHTML = `<h1>${t}</h1><p>${s}</p><small>${f}</small>`; d.style.opacity = 1; }""",
                  [title, sub, foot])
    page.wait_for_timeout(int(hold * 1000))


def hide_card(page):
    page.evaluate("() => { const d = document.getElementById('ng-card'); if (d) { d.style.opacity = 0;"
                  " setTimeout(() => d.remove(), 650); } }")
    page.wait_for_timeout(800)


def smooth_scroll(page, dy, steps=12, pause=60):
    for _ in range(steps):
        page.mouse.wheel(0, dy / steps)
        page.wait_for_timeout(pause)


def settle(page, ms=2500):
    page.wait_for_timeout(ms)
    page.wait_for_function("!document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60000)


def main():
    shutil.rmtree(RAW, ignore_errors=True)
    os.makedirs(RAW, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, color_scheme="dark",
                            record_video_dir=RAW, record_video_size={"width": W, "height": H})
        t0 = time.time()
        page = ctx.new_page()
        page.goto(URL)
        page.get_by_text("Connexions analysées").wait_for(timeout=120000)
        settle(page, 3000)
        page.wait_for_selector(".js-plotly-plot .main-svg", timeout=60000)
        page.wait_for_timeout(1500)
        page.evaluate(OVERLAY_JS)
        start = time.time() - t0  # trim everything before this point
        page.mouse.move(W * 0.6, H * 0.5)

        card(page, "NetGuard", "Explainable intrusion detection for rare and never-seen network attacks",
             "DATANOVA 2026  ·  DN-CY-01  ·  BINETOU RASSOUL SEYE", 4.0)
        hide_card(page)

        # --- Tab 1: traffic analysis
        caption(page, "<b>Traffic analysis</b> — 707 real connections from the NSL-KDD test set", 4.0)
        caption(page, "NetGuard raises alerts, flags critical attacks (U2R / R2L) and <b>unknown suspicious</b> traffic", 4.5)
        smooth_scroll(page, 520)
        caption(page, "Which attack families were found, and which services they target", 4.5)
        smooth_scroll(page, 560)
        caption(page, "The <b>alert log</b>: verdict, confidence, anomaly score — exportable as CSV for the security team", 5.0)
        smooth_scroll(page, -2000, steps=8)

        # --- Tab 2: explain an alert
        clear(page); page.get_by_role("tab", name="Expliquer une alerte").click()
        settle(page, 2500)
        caption(page, "<b>Explain an alert</b>: every decision comes with its reasons", 3.5)
        caption(page, "Verdict, confidence, and a <b>recommended response</b> for the analyst", 4.0)
        try:
            page.locator("[data-testid='stSelectbox']").first.click()
            page.wait_for_timeout(700)
            for _ in range(3):
                page.keyboard.press("ArrowDown")
                page.wait_for_timeout(250)
            page.keyboard.press("Enter")
            settle(page, 2500)
            caption(page, "Picking another alert updates the explanation instantly", 3.5)
        except Exception:
            pass
        caption(page, "<b>SHAP values</b> show which network features pushed the model to this verdict", 4.5)
        smooth_scroll(page, 450)
        caption(page, "Probabilities for each attack family", 3.5)
        smooth_scroll(page, -1500, steps=8)

        # --- Sidebar threshold
        try:
            clear(page); page.get_by_role("tab", name="Analyse du trafic").click()
            settle(page, 2000)
            thumb = page.locator("[data-testid='stSlider'] input").first
            thumb.focus(timeout=5000)
            caption(page, "The analyst tunes the trade-off between <b>detection</b> and <b>false alarms</b>", 2.5)
            for _ in range(10):
                thumb.press("ArrowRight", timeout=3000)
                page.wait_for_timeout(120)
            settle(page, 2500)
            caption(page, "Higher threshold → more connections flagged as suspicious", 3.5)
            for _ in range(10):
                thumb.press("ArrowLeft", timeout=3000)
                page.wait_for_timeout(120)
            settle(page, 1500)
        except Exception:
            pass

        # --- Tab 3: performance
        clear(page); page.get_by_role("tab", name="Performance du modèle").click()
        settle(page, 2500)
        caption(page, "<b>Model performance</b> on KDDTest+ (22,544 connections, 17 unseen attack types)", 4.5)
        caption(page, "Attack detection: <b>65.1% → 76.5%</b> · unseen attacks: <b>35.9% → 62.7%</b>", 5.0)
        smooth_scroll(page, 380)
        caption(page, "The gain is concentrated on rare attacks: U2R recall <b>7.5% → 43.3%</b>", 5.0)
        smooth_scroll(page, -1500, steps=8)

        # --- Tab 4: about
        clear(page); page.get_by_role("tab", name="À propos").click()
        settle(page, 2000)
        caption(page, "<b>About</b>: approach, data and known limitations", 4.0)

        page.evaluate("() => { const c = document.getElementById('ng-cap'); c.style.opacity = 0; }")
        card(page, "NetGuard", "netguard-datanova.streamlit.app<br>github.com/Binetuuu/netguard",
             "BINETOU RASSOUL SEYE  ·  DATANOVA 2026", 4.0)
        end = time.time() - t0
        video_path = page.video.path()
        ctx.close()
        b.close()

    mp4 = os.path.join(OUT, "NetGuard_demo.mp4")
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", video_path,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
                    "-r", "30", "-movflags", "+faststart", mp4],
                   check=True, capture_output=True)
    print(f"Saved {mp4}  ({end - start:.0f}s)")


if __name__ == "__main__":
    main()
