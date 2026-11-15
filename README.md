# GeoSignal — Calvos de Randín (Ourense)

Mapa de severidad de incendio (NISAR L-band, pre vs. post) y riesgo de
arrastre por microcuenca, para el incendio de Calvos de Randín (Ourense,
Galicia): ignición 2026-09-24, controlado 2026-09-27, ~518 ha.

## Estructura

```
data/
  config.py            AOI, fechas pre/post-fuego, umbral de quemado
  search_download.py   busca y descarga GCOV + SME2 + Sentinel-1 en ASF
  compute_change.py    diff de HV (dB) pre/post, suavizado -> burn_severity.tif
  convert_sme2.py       SME2 (EASE-Grid, 200m) -> GeoTIFF alineado a burn_severity.tif
  compute_slope.py      Copernicus DEM GLO-30 -> slope.tif alineado a burn_severity.tif
  delineate_basins.py   DEM -> microcuencas reales (WhiteboxTools) -> basins.geojson
  risk_index.py         quema x (pendiente + sequedad) -> riesgo por cuenca
web/
  index.html / app.js / style.css   slider óptico-vs-radar + mapa de riesgo
  demo.html             maqueta sin datos reales, para probar la interacción
  data/                 geojson/png generados por el pipeline (no se commitea)
alerts/
  __main__.py           CLI: check / run / serve / subscribe / unsubscribe / list / places
  server.py             web + API para el capítulo 11 del StoryMap (story/alerts.js)
  forecast.py           lluvia prevista (Open-Meteo) o escenario simulado
  engine.py             nivel de alerta, volumen de escorrentía, no repetir avisos
  geodata.py            cuencas y exposición de cada núcleo desde web/assets/data
  report.py             informe del estudio en lenguaje llano (es/en)
  compose.py            aviso de lluvia + render de texto y HTML (vecino o técnico)
  mailer.py             envío SMTP o volcado a alerts/outbox/
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
  Con el umbral de -1,5 dB en HV sin suavizar: 239 ha. Con el suavizado
  de 100m que añadimos después (ver más abajo): **89 ha** — baja porque
  buena parte de esos 239 ha eran speckle, no señal real (lo confirma que
  cuencas sin incendio marcaban ~12-14% "quemado" antes de suavizar). 89 ha
  frente a 518 oficiales y 1.234 de EFFIS: preséntalo como "núcleo de quema
  severa en zona arbolada" (official: 370 ha arbolado + 148 ha pasto — el
  pasto no da la misma firma en L-band), no como el área total quemada.

**Ya descargado y procesado**: el par track 15/frame 23 (GCOV + SME2,
~4,1 GB), el perímetro de EFFIS, el DEM de Copernicus (GLO-30, bucket
público de AWS, sin login) y las 26 microcuencas reales delineadas desde
ese DEM — todo en `data/raw/`. `data/out/burn_severity.tif`,
`data/raw/soil_moisture.tif`, `data/raw/slope.tif` y `data/out/risk_index.tif`
generados y verificados. Falta solo `data/raw/assets.geojson` (núcleos/
embalses de OSM) para que `risk_index.py` escriba el geojson final para
la web.

**Riesgo por cuenca, validado (2026-11-14):** las cuencas 8 y 9 — las que
contienen el incendio real — salen en el puesto **#1 y #2 de 26** por
riesgo medio, con >20x de margen sobre la tercera. No fue automático;
hicieron falta dos correcciones:
- **Suavizado antes de umbralizar.** El diff de HV crudo a 20m tiene
  speckle suficiente para que el umbral de -1,5 dB marque ~12-14% de
  "quemado" en cuencas que el fuego nunca tocó. `compute_change.py`
  ahora aplica un boxcar de 100m (NaN-aware) antes de umbralizar —
  práctica estándar en SAR que me había saltado.
- **Multiplicar, no sumar.** La fracción de área quemada por cuenca es
  pequeña (máx ~1,6%) comparada con pendiente/sequedad normalizadas
  (0–1), así que en una suma ponderada quedaba aplastada. `risk_index.py`
  ahora usa `riesgo = quemado × (pendiente + sequedad)`: sin quema no hay
  riesgo elevado, sin importar lo empinado o seco que esté el terreno.

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
6. `data/.venv/bin/python3 data/compute_slope.py data/raw/<dem.tif> data/out/burn_severity.tif data/raw/slope.tif`
   — ya hecho con el tile Copernicus GLO-30 que cubre el AOI
   (`https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N41_00_W008_00_DEM/...tif`,
   público, sin login). Pendiente media dentro del perímetro real: 11,1°.
7. `data/.venv/bin/python3 data/delineate_basins.py data/raw/<dem_sin_predictor>.tif data/raw/hydro data/raw/basins.geojson`
   — ya hecho: 26 microcuencas reales (WhiteboxTools: fill → D8 → acumulación
   → red de drenaje → subbasins → vectorizar), umbral de 10.000 celdas
   ajustado para que el incendio caiga en 2 cuencas, no en 23. **Nota:** el
   GeoTIFF de Copernicus usa un predictor de compresión que WhiteboxTools no
   lee — hay que reescribirlo con rasterio (`compress='lzw', predictor=1`)
   antes de pasárselo, y `set_working_dir()` necesita ruta absoluta o falla
   en silencio.
8. Consigue por tu cuenta (no está en este repo, no sale de ninguna API):
   - `data/raw/assets.geojson` — núcleos/embalses aguas abajo (OSM):
     Randín, Calvos de Randín, As Meaus (Baltar), Baltar
9. `data/.venv/bin/python3 data/risk_index.py` — escribe `web/data/basins_risk.geojson`.
10. Exporta la severidad a PNG para el slider:
    `gdal_translate -of PNG -scale data/out/burn_severity.tif web/data/severity.png`

## Web (StoryMap + exploradores)

El punto de entrada principal (`web/index.html`) es un **informe narrativo estilo StoryMap** en 11 capítulos sobre el incendio de Calvos de Randín (Ourense, sep 2026) con la serie temporal completa de NISAR desde junio de 2026, comparativa óptico-vs-radar, sensibilidad multinivel en `dB` (`-1.5` / `-3.0` / `-6.0 dB`), cruce con coberturas ESA WorldCover, riesgo hidrogeomorfológico por microcuenca y simulación dinámica de escorrentía:

```bash
devenv up   # o: cd web && python -m http.server 8000
# -> http://localhost:8000/

# con el capítulo de alertas activo (desde la raíz del repo):
python3 -m alerts serve   # -> http://127.0.0.1:8765/
```

El explorador técnico original sigue disponible en `web/real_demo.html`. Para regenerar los insumos ligeros (`web/assets/data/`) desde las escenas `.h5` locales:

```bash
python data/extract_aoi_stack.py
python data/build_story_data.py
python data/validate_story_data.py
```

## Alertas por correo (`alerts/`)

Manda dos tipos de correo, los dos escritos para vecinos y sin
tecnicismos:

- **Informe del estudio.** Lo recibe cada persona al suscribirse: cuánto
  se quemó según cada fuente, por qué se usó radar, qué tipo de terreno
  ardió, por dónde puede bajar el agua, qué da el simulador de lluvia para
  20 / 40 / 80 l/m², dónde convendrían barreras y qué significa para su
  pueblo. Solo se reenvía si se regeneran los datos del estudio.
- **Aviso de lluvia.** Solo cuando la previsión real alcanza el nivel que
  eligió la persona. Los simulacros no se envían nunca por correo.

Solo
usa la biblioteca estándar de Python (no necesita `data/.venv`) y lee los
mismos insumos que la web (`web/assets/data/`). Se ejecuta desde la raíz
del repo, como el pipeline.

Qué hace en cada ejecución:

1. Pide a Open-Meteo (gratis, sin clave) la lluvia horaria de los próximos
   3 días en el centro del perímetro del incendio.
2. Asigna un nivel por día: amarillo / naranja / rojo si la lluvia en 24 h
   llega a 20 / 40 / 80 mm o la intensidad horaria a 10 / 20 / 40 mm/h.
3. Escribe un correo distinto para cada suscriptor (texto + HTML, en
   español o inglés) y lo envía por SMTP. El correo está escrito para
   vecinos: litros por metro cuadrado, exposición alta/media/baja de su
   núcleo y qué hacer. El perfil `technical` añade al final las cifras
   (hectáreas, m³, microcuencas, candidatas a barrera).

```bash
python3 -m alerts places                      # núcleos y su exposición
python3 -m alerts subscribe ana@ejemplo.org --name Ana --place "As Meaus"
python3 -m alerts subscribe pc@ejemplo.org --profile technical --min-level 2
python3 -m alerts check                       # nivel con el pronóstico real
python3 -m alerts report                      # informe del estudio, en seco -> alerts/outbox/*.html
python3 -m alerts run                         # informes pendientes + avisos, en seco
python3 -m alerts run --send                  # envía de verdad (lo que ejecuta cron)
python3 -m alerts report --send --force       # reenvía el informe a todos
python3 -m alerts run --rain-mm 60            # vista previa de cómo se vería un aviso con 60 mm
python3 -m alerts unsubscribe ana@ejemplo.org
```

**En la web.** `python3 -m alerts serve` sirve `web/` en
`http://127.0.0.1:8765/` con una API mínima, y activa el capítulo
«11 · Alertas por correo» al final del StoryMap: nivel de hoy, formulario
de suscripción y vista previa del informe que recibiría cada persona
(cambia con el pueblo elegido). Con un servidor
estático (`python -m http.server`) el capítulo solo muestra un aviso. Antes
de publicarlo fuera de localhost: la suscripción no pide confirmación por
correo (cualquiera puede apuntar cualquier dirección) y no hay límite de
peticiones.

Sin `--send` no sale ningún correo: se escriben un `.eml` y un `.html` por
suscriptor en `alerts/outbox/` para revisarlos en el navegador. `--rain-mm`
solo sirve para esa vista previa; combinado con `--send` se rechaza.

**Envío con Gmail** (el proveedor por defecto). Copia `.env.example` a
`.env` en la raíz (ya está en `.gitignore`) y rellena dos líneas:

```bash
ALERTS_SMTP_USER=cuenta-que-envia@gmail.com
ALERTS_SMTP_PASSWORD=xxxx xxxx xxxx xxxx   # contraseña de aplicación, no la normal
```

La contraseña de aplicación se crea en
`https://myaccount.google.com/apppasswords` (la cuenta necesita la
verificación en dos pasos activada). Gmail limita a unos 500 destinatarios
al día en cuentas gratuitas. Para otro proveedor, define además
`ALERTS_SMTP_HOST` / `ALERTS_SMTP_PORT` / `ALERTS_SMTP_SECURITY`; el resto
de variables opcionales está en `.env.example`.

Prueba a una sola dirección ya suscrita:

```bash
python3 -m alerts report --only alguien@ejemplo.org --send --force
```

**Automatizarlo**: una línea de cron, por ejemplo cada 3 horas:

```
0 */3 * * * cd /ruta/a/GeoSignal && python3 -m alerts run --send >> alerts/cron.log 2>&1
```

`alerts/state.json` recuerda qué versión del informe y qué episodio de
lluvia recibió ya cada dirección, así que el cron no repite correos; si el nivel sube para el
mismo día (amarillo → naranja) sí vuelve a avisar.

**Qué es real y qué no.** Área quemada, microcuencas, ranking, distancias
a los cauces y candidatas a barrera salen del pipeline. La lluvia es un
pronóstico de modelo. El volumen de escorrentía usa `C = 0,6`, el mismo
supuesto que el simulador de la web (120 mm dan los mismos 269.021 m³), y
los umbrales de nivel están en `alerts/config.py` sin calibrar sobre el
terreno: ajustadlos con Protección Civil / AEMET antes de usarlo fuera de
una demo. Cada correo dice que es un sistema experimental y remite a los
avisos oficiales y al 112.

`alerts/subscribers.json`, `alerts/state.json` y `alerts/outbox/` no se
commitean (son datos personales y salidas locales); el formato está en
`alerts/subscribers.example.json`. Pruebas:
`python3 -m unittest discover -s alerts/tests -t .`

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
