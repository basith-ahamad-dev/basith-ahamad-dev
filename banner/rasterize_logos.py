"""Rasterize logo SVGs to 512px masks using headless Edge (no cairo needed on Windows)."""
import subprocess
import sys
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
HERE = Path(__file__).parent
LOGOS = ["python", "code", "vercel"]


def main():
    out = HERE / "data"
    out.mkdir(exist_ok=True)
    for name in LOGOS:
        svg = (HERE / "logos" / f"{name}.svg").resolve()
        html = out / f"_{name}.html"
        html.write_text(
            f'<html><body style="margin:0;background:#fff"><img src="{svg.as_uri()}" '
            f'width="512" height="512" style="display:block"></body></html>'
        )
        png = out / f"logo_{name}.png"
        subprocess.run(
            [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--screenshot={png}", "--window-size=512,512", html.as_uri()],
            check=True, capture_output=True, timeout=60,
        )
        html.unlink()
        print("wrote", png)


if __name__ == "__main__":
    sys.exit(main())
