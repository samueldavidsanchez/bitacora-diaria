import os
from pathlib import Path

import pandas as pd
import requests

PUBLIC_EXCEL_URL = os.environ["PUBLIC_EXCEL_URL"]

OUT_XLSX = Path("data/bitacora.xlsx")
OUT_CSV = Path("data/bitacora.csv")
OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)


def download_file(url: str, out_path: Path) -> None:
    with requests.get(url, stream=True, timeout=180, allow_redirects=True) as r:
        r.raise_for_status()

        ctype = (r.headers.get("Content-Type") or "").lower()
        if "text/html" in ctype:
            sample = r.content[:1500].decode("utf-8", errors="ignore")
            raise RuntimeError(
                "La URL devolvió HTML (no un .xlsx). "
                "Revisa que el link sea descarga directa.\n"
                f"Content-Type={ctype}\nMuestra:\n{sample}"
            )

        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def excel_to_csv() -> None:
    df = pd.read_excel(OUT_XLSX)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed", regex=True)]
    df.to_csv(OUT_CSV, index=False, sep=";", encoding="latin1")


def main():
    download_file(PUBLIC_EXCEL_URL, OUT_XLSX)
    excel_to_csv()
    print(f"OK: updated {OUT_XLSX} and {OUT_CSV}")


if __name__ == "__main__":
    main()
