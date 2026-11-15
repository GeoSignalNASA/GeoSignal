"""
Shared config for the Calvos de Randin (Ourense) fire pipeline.

Fire: ignited 2026-09-24 in the Randin parish (Calvos de Randin, Ourense),
contained 2026-09-27, ~518 ha -- the second largest wildfire in Galicia in
2026. https://www.elespanol.com/treintayseis/actualidad/provincia-de-ourense/20260927/

AOI_BBOX is a box around the municipality centroid (41.90472 N,
-7.87556 W), kept only for the ASF search (intersectsWith needs
something, and the box is a superset of the real fire). It overcounts
burned area by ~4.5x if used for stats -- use EFFIS_PERIMETER_GEOJSON
below for anything you actually measure or clip.

Everything below was checked live against the ASF Search API
(api.daac.asf.alaska.edu/services/search/param) on 2026-11-14 -- these are
real granules, not guesses. No credentials needed for search, only for
download (set EARTHDATA_USERNAME / EARTHDATA_PASSWORD, or use ~/.netrc).
"""

AOI_BBOX = {
    "min_lon": -7.96,
    "min_lat": 41.85,
    "max_lon": -7.80,
    "max_lat": 41.97,
}

AOI_WKT = (
    f"POLYGON(("
    f"{AOI_BBOX['min_lon']} {AOI_BBOX['min_lat']},"
    f"{AOI_BBOX['max_lon']} {AOI_BBOX['min_lat']},"
    f"{AOI_BBOX['max_lon']} {AOI_BBOX['max_lat']},"
    f"{AOI_BBOX['min_lon']} {AOI_BBOX['max_lat']},"
    f"{AOI_BBOX['min_lon']} {AOI_BBOX['min_lat']}"
    f"))"
)

# Confirmed NISAR GCOV track/frame pairs covering this AOI, with real
# pre- and post-fire acquisitions on each (checked 2026-11-14):
#   track  15 / frame 23 (ascending):  pre 2026-09-19, post 2026-10-01 <- USE THIS ONE, see below
#   track 124 / frame 68 (descending): pre 2026-09-14, post 2026-10-08  <- DON'T: only ~35% of the
#                                       real fire perimeter has valid data in this swath (geocoded
#                                       grid edge cuts through the fire area). Tested 2026-11-14.
#   track  52 / frame 67 (descending): pre 2026-09-09, post 2026-10-15
#   track 124 / frame 67 (descending): pre 2026-09-14, post 2026-10-20
#
# track 15/23 covers 99.9% of the real EFFIS perimeter (see EFFIS_PERIMETER
# below) -- tested 2026-11-14.
# Nota de hallazgo (2026-11-15): usar solo el par 2026-09-19 -> 2026-10-01 daba
# ~239 ha crudas / ~88 ha suavizadas porque el 01-oct coincidió con suelo mojado
# (SME2 0.18->0.23, offset +1.16 dB en control). Con compuesto multitemporal lineal
# de pasadas secas QA-pass (5 pre jul-sep vs 13-oct + 25-oct) y umbral -1.5 dB se
# detectan ~325 ha (F1 = 0.80 vs Sentinel-2 dNBR >= 0.27); el resto hasta 483-518 ha
# corresponde a quema superficial bajo copa sin cambio estructural en banda L.
PREFERRED_TRACK_FRAME = (15, 23)

# Real fire perimeter from EFFIS's NRT burnt-area WFS
# (maps.effis.emergency.copernicus.eu/gwis, layer nrt.ba.poly, fire_id
# 15925129, ignited 2026-09-24 12:32). Use this to clip/mask instead of
# AOI_BBOX wherever possible -- the bbox overcounts burned area by ~4.5x
# because it includes unburned land outside the fire.
EFFIS_PERIMETER_GEOJSON = "data/raw/effis_perimeter_calvos_de_randin.geojson"

PRE_FIRE_START = "2026-09-01"
PRE_FIRE_END = "2026-09-20"
POST_FIRE_START = "2026-09-28"
POST_FIRE_END = "2026-10-27"

DATASET = "NISAR"
PROCESSING_LEVEL = "GCOV"

# NISAR L3 soil moisture -- confirmed granules on the same track/frame grid
# in this window (124/68, 124/67, 52/67, 15/23), so the dryness term in
# risk_index.py has real data behind it, not just a plan.
SME2_PROCESSING_LEVEL = "SME2"

# Sentinel-1 GRD -- dense backup time series over the same AOI: ~48 granules
# Aug-Nov 2026, S1C/S1D, VV+VH, ~6-day revisit (ascending path 147,
# descending path 52). Useful for the smoothed soil-moisture trend and as a
# fallback if a specific NISAR pass has an artifact.
S1_DATASET = "SENTINEL-1"
S1_PROCESSING_LEVEL = "GRD_HD"

# dB drop in HV between before/after below which a pixel counts as burned.
# From the Bobcat-fire L-band study referenced in the pitch deck.
HV_BURN_THRESHOLD_DB = -1.5

OUT_DIR = "data/out"
RAW_DIR = "data/raw"
