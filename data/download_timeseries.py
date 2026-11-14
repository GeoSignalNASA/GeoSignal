"""
Descarga reanudable de la serie temporal NISAR (GCOV + SME2) para el
Track 15 / Frame 23 (ascendente) sobre Calvos de Randín (jun-oct 2026).

Lee el token únicamente de la variable de entorno EARTHDATA_TOKEN (o fallback
a EARTHDATA_USERNAME/EARTHDATA_PASSWORD o ~/.netrc). Nunca lo imprime ni lo
guarda en disco.
"""

import os
import sys
import time

import asf_search as asf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import AOI_WKT, DATASET, PREFERRED_TRACK_FRAME, RAW_DIR

START_DATE = "2026-06-15"
END_DATE = "2026-11-01"
KEY_DATES = {"2026-09-19", "2026-10-01"}


def expected_size_bytes(result):
    fname = result.properties["fileName"]
    b = result.properties.get("bytes")
    if isinstance(b, dict) and fname in b and isinstance(b[fname], dict):
        return int(b[fname].get("bytes", 0))
    if isinstance(b, (int, float)):
        return int(b)
    return 0


def target_granules():
    path_num, frame_num = PREFERRED_TRACK_FRAME
    results = []
    for level in ("SME2", "GCOV"):
        res = asf.search(
            dataset=DATASET,
            processingLevel=level,
            intersectsWith=AOI_WKT,
            start=START_DATE,
            end=END_DATE,
        )
        for r in res:
            p = r.properties
            if p.get("pathNumber") == path_num and p.get("frameNumber") == frame_num:
                results.append(r)

    # Prioridad: SME2 primero (rápidos) y luego las fechas clave del incendio antes del historial
    def sort_key(r):
        p = r.properties
        is_gcov = 1 if p.get("processingLevel") == "GCOV" else 0
        is_key = 0 if p.get("startTime", "")[:10] in KEY_DATES else 1
        return (is_gcov, is_key, p.get("startTime", ""))

    return sorted(results, key=sort_key)


def get_session():
    token = os.environ.get("EARTHDATA_TOKEN")
    if token:
        return asf.ASFSession().auth_with_token(token)
    user = os.environ.get("EARTHDATA_USERNAME")
    pw = os.environ.get("EARTHDATA_PASSWORD")
    if user and pw:
        return asf.ASFSession().auth_with_creds(user, pw)
    return asf.ASFSession()


def download_granule(result, session, out_dir):
    fname = result.properties["fileName"]
    url = result.properties["url"]
    expected = expected_size_bytes(result)
    dest = os.path.join(out_dir, fname)
    tmp = dest + ".part"

    if os.path.exists(dest) and (expected == 0 or os.path.getsize(dest) == expected):
        print(f"  [skip] {fname} ({os.path.getsize(dest) / 1e6:.1f} MB)")
        return

    print(f"  [down] {fname} ({expected / 1e6:.1f} MB)")
    t0 = time.time()
    with session.get(url, stream=True, timeout=(30, 300)) as resp:
        resp.raise_for_status()
        written = 0
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=4 * 1024 * 1024):
                if chunk:
                    f.write(chunk)
                    written += len(chunk)
    if expected and written != expected:
        raise IOError(f"Tamaño incompleto en {fname}: {written} != {expected}")
    os.replace(tmp, dest)
    dt = max(time.time() - t0, 0.1)
    print(f"  [done] {fname} en {dt:.1f}s ({written / 1e6 / dt:.1f} MB/s)")


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    granules = target_granules()
    print(f"Granulos Track {PREFERRED_TRACK_FRAME[0]}/Frame {PREFERRED_TRACK_FRAME[1]}: {len(granules)}")
    session = get_session()
    for i, r in enumerate(granules, 1):
        print(f"[{i}/{len(granules)}] {r.properties['processingLevel']} {r.properties['startTime'][:10]}")
        download_granule(r, session, RAW_DIR)
    print("Serie temporal descargada por completo.")


if __name__ == "__main__":
    main()
