# GeoSignal — Calvos de Randín (Ourense)

Mapa de severidad de incendio (NISAR L-band, pre vs. post) y riesgo de
arrastre por microcuenca, para el incendio de Calvos de Randín (Ourense,
Galicia): ignición 2026-09-24, controlado 2026-09-27, ~518 ha.

## Estructura

```
data/
  config.py            AOI, fechas pre/post-fuego, umbral de quemado
  search_download.py   busca y descarga GCOV + SME2 + Sentinel-1 en ASF
  compute_change.py    diff de HV (dB) pre/post -> burn_severity.tif
  convert_sme2.py       SME2 (EASE-Grid, 200m) -> GeoTIFF alineado a burn_severity.tif
  risk_index.py         severidad x pendiente x humedad -> riesgo por cuenca
web/
  index.html / app.js / style.css   slider óptico-vs-radar + mapa de riesgo
  demo.html             maqueta sin datos reales, para probar la interacción
  data/                 geojson/png generados por el pipeline (no se commitea)
```

## Datos confirmados (comprobado en vivo contra ASF el 2026-11-14)

Esto no son fechas supuestas — se verificaron contra la API de búsqueda de
ASF (`api.daac.asf.alaska.edu/services/search/param`, no necesita login):

| Producto | Track/Frame | Antes | Después |
|---|---|---|---|
| NISAR GCOV | **15/23 (asc.) — usar este** | 2026-09-19 | 2026-10-01 |
| NISAR GCOV | 124/68 (desc.) — descartado, ver abajo | 2026-09-14 | 2026-10-08 |
| NISAR GCOV | 52/67 (desc.) | 2026-09-09 | 2026-10-15 |
| NISAR GCOV | 124/67 (desc.) | 2026-09-14 | 2026-10-20 |
| NISAR SME2 | mismos track/frame | ✓ disponible sep-oct | ✓ disponible sep-oct |
| Sentinel-1 GRD | paths 147 (asc.) / 52 (desc.) | 48 escenas ago-nov, cada ~6 días | — |

**Perímetro real del incendio**, no un bbox: `data/raw/effis_perimeter_calvos_de_randin.geojson`,
bajado de la WFS en vivo de EFFIS (`maps.effis.emergency.copernicus.eu/gwis`,
capa `nrt.ba.poly`, `fire_id` 15925129, ignición 2026-09-24 12:32 — coincide
con la hora real). Área según EFFIS: **1.234 ha** (su propia detección NRT
automática, no coincide con los 518 ha oficiales de la Xunta — es una
discrepancia conocida entre detección satelital automática y medición de
extinción sobre el terreno; contadlo así en el pitch, no escondáis el número).

**Probado y validado end-to-end (2026-11-14):**
- Track 124/frame 68 (descendente) solo tiene dato válido en ~35% del
  perímetro real — el borde de la rejilla geocodificada corta justo por
  la zona del incendio. Descartado, no lo uséis.
- Track 15/frame 23 (ascendente) cubre el **99,9%** del perímetro real.
  Con el umbral de -1,5 dB en HV: **239 ha** de píxeles "quemados", frente
  a 518 ha oficiales y 1.234 ha de EFFIS. Nuestro número es más bajo que
  los dos, probablemente porque la caída de HV es sobre todo una señal de
  pérdida de estructura de copa — el desglose oficial es 370 ha de monte
  arbolado + 148 ha de pasto, y el pasto quemado no da la misma firma en
  L-band. Presentadlo como "núcleo de quema severa en zona arbolada", no
  como el área total quemada.

**Ya descargado y procesado**: el par track 15/frame 23 (GCOV + SME2,
~4,1 GB) y el perímetro de EFFIS en `data/raw/`. `data/out/burn_severity.tif`
generado. `data/raw/soil_moisture.tif` generado del SME2 del 1-oct,
reproyectado y alineado a la rejilla de la severidad (`convert_sme2.py`).
Falta: pendiente, cuencas y activos — ninguno sale de una API con una query.

## Pipeline de datos (equipo de datos)

**Todos los comandos siguientes se ejecutan desde la raíz del repo, no
desde dentro de `data/`.** `RAW_DIR`/`OUT_DIR` en `config.py` y las rutas
de `risk_index.py` son relativas a la raíz (`data/raw`, `data/out`,
`web/data/...`) — si entráis en `data/` primero, todo se descarga uno
nivel de más abajo, en `data/data/raw/`.

1. `python3 -m venv data/.venv && data/.venv/bin/pip install -r data/requirements.txt`
2. Credenciales de Earthdata (solo para descargar, no para buscar):
   crea una cuenta gratis en `urs.earthdata.nasa.gov`, autoriza la app de
   ASF (visita `https://urs.earthdata.nasa.gov/approve_app?client_id=BO_n7nTIlMljdvU6kRRB3g`
   y acepta el EULA — si no, la descarga falla con un 403 "EULA Acceptance
   Failure"), y luego pon el token en una variable de entorno de tu
   terminal, nunca en un archivo del repo ni pegado en un chat:
   `export EARTHDATA_TOKEN=...` (o `EARTHDATA_USERNAME`/`EARTHDATA_PASSWORD`,
   o un `~/.netrc` con la entrada de `urs.earthdata.nasa.gov`).
3. `data/.venv/bin/python3 data/search_download.py` — busca GCOV y SME2
   (empareja track/frame igual en pre y post) y lista la serie de
   Sentinel-1 GRD. Descarga automáticamente los pares de GCOV/SME2;
   Sentinel-1 se lista pero no se descarga entero por defecto (escenas de
   ~1 GB+ cada una) — elegid 2-3 fechas concretas.
4. `data/.venv/bin/python3 data/compute_change.py data/raw/<pre.h5> data/raw/<post.h5>`
   — usad el par de track 15/frame 23 (19-sep / 1-oct, ya descargado y ya
   generado en `data/out/burn_severity.tif`; banda 1: diff HV en dB,
   banda 2: máscara de quemado). Para sacar estadísticas de verdad,
   recortad con `data/raw/effis_perimeter_calvos_de_randin.geojson`
   (`rasterio.mask.mask`), no con `AOI_BBOX` — el bbox sobreestima ~4,5x.
5. `data/.venv/bin/python3 data/convert_sme2.py data/raw/<sme2_post.h5> data/out/burn_severity.tif data/raw/soil_moisture.tif`
   — ya hecho con el SME2 del 1-oct: `data/raw/soil_moisture.tif`, reproyectado
   de EASE-Grid2 (EPSG:6933, 200m) a la rejilla de `burn_severity.tif`.
   Dentro del perímetro real: 0,175–0,293 m³/m³, media 0,225.
6. Consigue por tu cuenta (no están en este repo):
   - `data/raw/slope.tif` — pendiente desde el MDT del IGN o Copernicus DEM
   - `data/raw/basins.geojson` — microcuencas (WhiteboxTools o pysheds
     sobre el mismo DEM) — la zona cae en la cabecera del Limia/Salas
   - `data/raw/assets.geojson` — núcleos/embalses aguas abajo (OSM):
     Randín, Calvos de Randín, As Meaus (Baltar), Baltar
6. `data/.venv/bin/python3 data/risk_index.py` — escribe `web/data/basins_risk.geojson`.
7. Exporta la severidad a PNG para el slider:
   `gdal_translate -of PNG -scale data/out/burn_severity.tif web/data/severity.png`

## Web (equipo de frontend)

No necesita esperar al pipeline completo: `web/app.js` ya apunta a
`web/data/basins_risk.geojson` y `web/data/severity.png`, así que podéis
trabajar con datos de prueba mientras el pipeline no esté listo. También
hay un mockup 100% autocontenido en `web/demo.html` (datos de ejemplo,
pensado para probar la interacción del slider y el clic por cuenca).

```
cd web && python -m http.server 8000
```

Pendiente de conectar: la capa óptica (Sentinel-2) del panel "before" en
`app.js` usa de momento el mismo tile de OSM — hay que cambiarla por una
fuente Sentinel-2 real de la fecha del incendio para que se vea el humo.

## Validación mínima antes de construir sobre esto

- El umbral de -1.5 dB en HV es el que dio ~0.70 de precisión en el
  estudio de Bobcat citado en el pitch, pero aquí da 239 ha frente a 518
  oficiales — tratadlo como punto de partida, no como verdad asumida.
  Antes de confiar en el número para el pitch, probad a bajar el umbral
  (p.ej. a -1.0 dB) y ved si os acerca más a 518 ha sin disparar los
  falsos positivos fuera del perímetro.
- Al recortar por el perímetro real comprobamos que el par de track/frame
  importa mucho para la cobertura (35% vs 99,9% de dato válido dentro del
  perímetro) — comprobad siempre `valid_px / expected_px` antes de confiar
  en un porcentaje de quemado.
- Si la imagen "post" cae en un día de lluvia, la retrodispersión del
  suelo sube y puede enmascarar la caída de HV. El par usado (19-sep /
  1-oct) es una ventana corta a propósito por esto. Si cambiáis de par,
  preferid ventanas cortas y en seco, o usad el cociente HV/HH.
