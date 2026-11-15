# AGENTS.md — Guía de Contexto Científico, Reglas del Hackathon y Dominio SAR

Este documento proporciona el contexto estratégico, científico y de evaluación del **NASA Space Apps Challenge** para que cualquier agente de desarrollo o diseño pueda tomar decisiones autónomas de producto, redacción de interfaz (*UX writing*), visualización y arquitectura alineadas con lo que valora el jurado de NASA.

---

## 1. ¿Qué es el NASA Space Apps Challenge y cómo evalúa el jurado?

El **NASA International Space Apps Challenge** es el mayor hackathon global de ciencia abierta y espacio (48 horas), organizado por la NASA junto a agencias espaciales asociadas (ESA, CSA, CONAE, JAXA, etc.).

### Los 5 Criterios Oficiales de Evaluación del Jurado
Toda decisión técnica, visual o narrativa debe optimizar al menos uno de estos cinco pilares:
1. **Impact (Impacto):** ¿Qué problema real y tangible resuelve la solución? ¿A quién ayuda (gestores de emergencias, protección civil, comunidades locales, científicos) y qué decisiones permite tomar?
2. **Creativity (Creatividad):** ¿Es original el enfoque? ¿Combina conjuntos de datos de formas novedosas o traduce datos científicos complejos en una experiencia visual intuitiva?
3. **Validity (Validez científica):** ¿Los datos son reales y están bien procesados? ¿Tiene rigor físico el modelo? **Crucial:** el jurado penaliza las afirmaciones exageradas sobre lo que un satélite puede medir y premia a los equipos que entienden y explican las limitaciones físicas del sensor.
4. **Relevance (Relevancia):** ¿Responde directamente al reto elegido (*Dancing with the SARs*) utilizando datos abiertos de la NASA (NISAR) y sus agencias asociadas?
5. **Presentation (Presentación y Storytelling):** ¿Puede una persona sin formación en teledetección entender en 30 segundos qué muestra la aplicación, por qué ocurre físicamente y por qué importa?

### Regla de Oro de Arquitectura para este Hackathon
- **Cero sobreingeniería en vivo:** Los archivos satelitales SAR pesan gigabytes. Nunca se debe intentar procesar `.h5` o `.tif` pesados en tiempo real desde un backend web durante la demo. El estándar ganador es **preprocesamiento científico reproducible en local (Python)** que genera capas geoespaciales ligeras y precisas (`.geojson`, `.png` georreferenciados), servidas en una **interfaz web estática, rápida y altamente interactiva**.

---

## 2. El Reto: "Dancing with the SARs"

### Enunciado y Propósito
La superficie terrestre está en una «danza» continua de procesos naturales y actividad humana (incendios, inundaciones, subsidencia, agricultura, glaciares) que suelen ser difíciles de visualizar y comunicar. El reto exige construir una **aplicación interactiva de código abierto y fácil de usar** que utilice datos de radar de la misión **NISAR** (*NASA-ISRO Synthetic Aperture Radar*) para rastrear, visualizar y explicar cambios en la superficie terrestre a lo largo del tiempo.

### Preguntas Obligatorias que el Proyecto Debe Responder
Según las directrices oficiales del reto, la aplicación y el *pitch* deben responder explícitamente a:
1. **Mecanismos físicos:** ¿Qué procesos físicos explican lo que se ve (y lo que *no* se ve) en los datos SAR?
2. **Polarizaciones:** ¿Qué polarizaciones destacan mejor estos cambios sobre el terreno?
3. **Factores humanos y ambientales:** ¿Cómo afectan los eventos naturales o la actividad humana a los ecosistemas, recursos hídricos y poblaciones locales?
4. **Aplicaciones futuras:** ¿Qué aplicaciones futuras de NISAR (o en sinergia con otras misiones) son posibles?

### Requisitos y Recomendaciones Oficiales de NASA
- Seleccionar un área de estudio concreta con fechas clave de antes, durante y después de un evento.
- Descargar y procesar datos reales de **NISAR** (complementados opcionalmente con otras frecuencias SAR como Sentinel-1/RCM/SAOCOM).
- Integrar **capas auxiliares** (imágenes ópticas para demostrar que el radar ve a través de humo/nubes, modelos digitales de elevación, población o infraestructuras) para contextualizar la señal radar.
- Construir una **visualización interactiva** (deslizadores antes/después, mapas de cambio, series temporales clicables) acompañada de narración clara.

---

## 3. Fundamentos Físicos: Radar SAR y Misión NISAR

El agente debe utilizar este vocabulario científico con precisión al redactar etiquetas, *tooltips*, documentación o lógica de análisis:

### Sensor Activo (SAR) vs. Sensor Pasivo (Óptico)
- **Satélites ópticos (Sentinel-2, Landsat):** Son *pasivos*; dependen de la luz del Sol reflejada. Quedan completamente ciegos cuando hay **nubes densas, humo de incendios forestales o es de noche**.
- **Radar de Apertura Sintética (SAR):** Es un sensor *activo*; emite sus propios pulsos de microondas hacia la Tierra y mide cuánta energía rebota de vuelta (**retrodispersión** o *backscatter*). Al combinar señales a lo largo de su órbita, sintetiza una antena virtual de kilómetros de largo para lograr alta resolución espacial de día, de noche y atravesando nubes o humo.

### La Misión NISAR (NASA + ISRO)
- Primer satélite radar de doble frecuencia diseñado para mapear casi toda la superficie terrestre cada **12 días** (primeros datos calibrados *Provisional* liberados el 20 de julio de 2026).
- Opera principalmente en **Banda L** (~24 cm de longitud de onda), una onda larga capaz de penetrar las copas de los árboles y los primeros ~5 cm de suelo, complementada por **Banda S** (~10 cm).

### Los 2 Factores Físicos que Alteran la Señal Radar
1. **Rugosidad y Geometría (cómo rebota la onda):**
   - **Dispersión especular (superficies lisas):** El agua en calma o el suelo raso desvían la onda lejos del satélite como un espejo $\rightarrow$ aparece **muy oscuro** (bajo *backscatter*).
   - **Dispersión volumétrica (estructura 3D):** Las copas de los bosques (ramas y hojas orientadas aleatoriamente) provocan rebotes múltiples que giran el plano de vibración de la onda $\rightarrow$ señal **brillante en polarización cruzada**.
   - **Doble rebote (*double-bounce*):** La onda rebota en el suelo y luego contra troncos verticales en pie o edificios, volviendo directa al sensor $\rightarrow$ puntos **muy brillantes en polarización paralela**.
2. **Constante Dieléctrica (presencia de agua):**
   - El agua líquida tiene una constante dieléctrica altísima ($\varepsilon_r \approx 80$) frente al suelo seco ($\varepsilon_r \approx 3\text{–}5$). Los cambios en la humedad del suelo modifican drásticamente la intensidad reflejada.

### Polarizaciones (`HH` vs `HV`) y Escala Logarítmica (`dB`)
- **`HH` (*Horizontal transmit, Horizontal receive*):** Polarización paralela. Sensible al suelo desnudo, humedad superficial y efecto de doble rebote en troncos quemados en pie.
- **`HV` (*Horizontal transmit, Vertical receive*):** Polarización cruzada. Funciona como un **detector de biomasa y estructura de copa tridimensional**.
  - *Antes de un incendio:* Bosque denso $\rightarrow$ alta dispersión volumétrica $\rightarrow$ **`HV` alto**.
  - *Después de un incendio:* El fuego consume hojas y ramas finas $\rightarrow$ desaparece el volumen dispersor $\rightarrow$ **desplome brusco de `HV`**.
- **Decibelios (`dB`):** Escala logarítmica ($10 \cdot \log_{10}(\text{potencia})$). Restar `post - pre` en `dB` mide la proporción de caída energética:
  - `0 dB`: sin cambios.
  - `-1.5 dB`: caída de ~29 % en la energía devuelta (umbral estándar de quema en Banda L).
  - `-3.0 dB`: caída del 50 % de la señal estructural.
  - `-6.0 dB`: caída del 75 % (calcinación extrema del dosel).

### Rigor Científico: Qué Mide y Qué NO Mide el SAR en Incendios
- El radar **no** detecta químicamente la hidrofobicidad del suelo (la costra impermeable de resinas vaporizadas tras el fuego).
- Sin embargo, al combinar la **severidad de pérdida de copa (`ΔHV`)**, la **sequedad superficial del suelo (`SME2`)** y la **pendiente topográfica (`DEM`)**, se obtiene un **Índice Físico de Susceptibilidad de Escorrentía y Arrastre de Lodos Post-Incendio**: laderas empinadas, desprovistas de vegetación que intercepte la lluvia y con suelo seco/repelente donde las precipitaciones otoñales arrastrarán ceniza y barro hacia los valles.

---

## 4. Catálogo de Productos NISAR y Recursos Oficiales del Reto

### Productos NISAR Relevantes
- **`GCOV` (*Geocoded Polarimetric Covariance*, Nivel 2):** Producto calibrado radiométricamente y ortorrectificado sobre rejilla UTM (10–20 m de resolución) en formato **HDF5**. Contiene matrices de retrodispersión (`HHHH`, `HVHV`).
- **`SME2` (*Soil Moisture*, Nivel 3):** Humedad volumétrica superficial del suelo ($\text{m}^3/\text{m}^3$) a 200 m de resolución en proyección **EASE-Grid 2.0 (`EPSG:6933`)**, aprovechando la penetración de ~5 cm de la Banda L.
- **`GUNW` (*Geocoded Unwrapped Interferogram*, Nivel 2):** Interferogramas de fase (80 m) para medir deformaciones centimétricas del terreno (terremotos, subsidencia).

### Portales y Recursos de Referencia
- **ASF Data Search Vertex (`asf_search` / `api.daac.asf.alaska.edu`):** Archivo principal de NASA para buscar y descargar escenas NISAR (`GCOV`, `SME2`) y Sentinel-1 (`GRD`).
- **NASA Earthdata Search:** Catálogo global para capas auxiliares: modelos de elevación (**NASADEM** 30 m), imágenes ópticas (**HLS** Sentinel-2/Landsat) y focos térmicos (**FIRMS**).
- **Copernicus EFFIS / GWIS (`maps.effis.emergency.copernicus.eu`):** Servicio europeo de información sobre incendios forestales; provee perímetros oficiales NRT (`nrt.ba.poly`).
- **Agencias Asociadas:**
  - **CONAE (Argentina) — Catálogo SAOCOM:** Constelación SAR en Banda L (misma frecuencia que NISAR) para extender series temporales históricas.
  - **CSA (Canadá) — RADARSAT Constellation Mission (RCM) & RADARSAT-1:** Datos en Banda C para contraste multifrecuencia y tutoriales oficiales en Python/QGIS.
- **Material de Diseño y Narrativa NASA:**
  - **NISAR StoryMaps:** Estándar de referencia UX/UI sobre cómo estructurar mapas deslizantes y explicaciones divulgativas.
  - **NISAR Applications White Papers:** Casos documentados de impacto socioeconómico en gestión hídrica, riesgos naturales y ecosistemas.
  - **NASA ARSET Trainings:** Guías metodológicas aplicadas en español e inglés sobre análisis SAR y NISAR.

---

## 5. Contexto del Proyecto ("GeoSignal") y Narrativa Local

- **Caso de Estudio:** Incendio forestal de **Calvos de Randín (Ourense, Galicia, España)**, frontera hispano-portuguesa (cabecera de los ríos **Limia** y **Salas**). Ignición: `2026-09-24`; controlado: `2026-09-27`. Obligó a activar la Situación 2 preventiva en el núcleo de **As Meaus (Baltar)**.
- **Hallazgo Científico Clave (Discrepancia de Hectáreas):**
  - Perímetro oficial de la Xunta de Galicia: **~518 ha** (desglosado en **370 ha de monte arbolado** + **148 ha de pasto/matorral**).
  - Detección automática térmica/óptica de Copernicus EFFIS: **1.234 ha** (y referencia óptica **Sentinel-2 `dNBR ≥ 0,27`**: **483,12 ha**).
  - Par único húmedo inicial NISAR (`ΔHV <= -1.5 dB`, `19-sep` vs `01-oct`): **87,5 ha** suavizadas (`239 ha` raw antes de corregir por potencia lineal), sesgado por la subida de humedad superficial `SME2` el 1 de octubre (`+1,16 dB` en control exterior, `qa_pass: false`).
  - **Compuesto multitemporal lineal NISAR (`5` pasadas secas pre vs `13 + 25 oct`, `5×5` en potencia lineal + calibración de control a `−1,5 dB`):** **`324,88 ha`** (`0,16 %` FP en control; **`F1 = 0,799`**, precisión `0,993` frente a `dNBR ≥ 0,27`).
  - *Cómo debe presentarlo el agente:* Nunca ocultar la diferencia ni sostener que NISAR aísla «quema severa en masa arbolada». Explicar la realidad física verificada: al cruzar `ΔHV` con **ESA WorldCover 2021** (que en Galicia agrupa monte bajo/tojo en «pasto/herbáceo»), la Banda L (24 cm) detecta con gran precisión la desaparición del matorral abierto (`247,5 ha`), mientras que el fuego de superficie bajo copa arbolada intacta apenas atenúa el volumen superior (`63,6 ha` detectadas de `576,3 ha`; `ΔHV ≈ −0,07 dB` en las `98,84 ha` omitidas con `dNBR ≥ 0,27`).
- **Contexto Regional y Escalabilidad (España / Portugal):**
  - **Precedente real en Galicia:** El megaincendio de la **Ribeira Sacra (Pantón y Sober, Lugo, sept. 2025, 1.805 ha)** demostró que las lluvias posteriores en laderas gallegas quemadas provocan arrastres críticos de ceniza hacia ríos (Cabe y Sil), obligando a obras de emergencia.
  - **Escalabilidad inmediata:** El **27 de octubre de 2026**, el Gobierno de España declaró conjuntamente a **Calvos de Randín (Ourense) y Quiroga (Lugo, Ribeira Sacra)** como *Zonas Afectadas Gravemente por una Emergencia de Protección Civil*. El pipeline de GeoSignal es replicable directamente sobre ambos incendios.
  - **Visión de futuro (Sinergia espacial ibérica):** Proponer la integración de **NISAR** (radiografía estructural de alta resolución cada 12 días) con la **Constelación Atlántica (PERTE Aeroespacial España-Portugal)** (16 microsatélites con revisita de ~3 horas, reflectometría GNSS-R en Banda L para humedad rápida y sensores IoT pluviométricos en las microcuencas).

---

## 6. Directrices de Actuación para el Agente

1. **Traducir la física a lenguaje humano:** Siempre que generes componentes de interfaz, leyendas o explicaciones, acompaña los términos técnicos (`HV`, `dB`, `SME2`, `dNBR`, *speckle*) con lenguaje llano, glosarios desplegables (`.glossary`) y nombres reales de poblaciones aguas abajo (`As Meaus`, `Calvos`, `Guntumil`) en lugar de identificadores internos sin contexto.
2. **Proponer mejoras con criterio de jurado:** Al sugerir nuevas funcionalidades o visualizaciones, prioriza aquellas que refuercen la narrativa física (comparativa óptico con humo vs. radar nítido, impacto por microcuenca sobre pueblos específicos aguas abajo, sensibilidad de umbrales y trazabilidad en `Fuentes y equipo`).
3. **Proteger la integridad geoespacial y de repositorio:** Verificar siempre alineación de proyecciones (`EPSG`) y rejillas antes de operar entre rásteres, recortar estadísticas usando el perímetro real de EFFIS (nunca el `bbox` rectangular que sobrestima ~4.5x), y mantener los archivos pesados (`.h5`, `.tif`) fuera del control de versiones.
