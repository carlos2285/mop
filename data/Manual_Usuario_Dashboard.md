# Manual de Usuario – Dashboard de Encuesta (Streamlit)

Este manual explica **cómo usar** y **mantener** el tablero de análisis de la encuesta: carga de datos, mapeo de variables, filtros, análisis por bloques, mapa GPS, abiertas (texto), exportación, y solución de problemas.

---

## 1) Requisitos y puesta en marcha

### 1.1. Requisitos
- Python 3.11+
- Paquetes (en `requirements.txt`):  
  `streamlit, pandas, numpy, xlsxwriter, openpyxl, plotly, wordcloud, scikit-learn, nltk, Unidecode`

### 1.2. Estructura del repositorio
```
/
├─ app.py
├─ requirements.txt
├─ runtime.txt
└─ data/
   ├─ respuestas.xlsx           (o respuestas.csv)
   ├─ Codebook.xlsx             (opcional, para recodificar)
   ├─ validation_report.txt     (opcional, de la limpieza previa)
   └─ README_DATA.txt           (opcional)
```

### 1.3. Ejecutar localmente
```bash
pip install -r requirements.txt
streamlit run app.py
```
La app abrirá en: `http://localhost:8501`

### 1.4. Ejecutar en Streamlit Cloud
- Conecta el repo de GitHub y despliega.
- En **Manage app** usa **Rerun** o **Reboot** cuando cambies `requirements.txt` o subas nuevos datos.

---

## 2) Preparación y carga de datos

### 2.1. Archivo principal
- Coloca tu base en `data/respuestas.xlsx` (o `data/respuestas.csv`).
- La app intentará leer **primero** `respuestas.xlsx` (con `openpyxl`) y, si no existe, `respuestas.csv`.

### 2.2. Codebook (opcional)
Para recodificar etiquetas/códigos en categorías limpias, usa `data/Codebook.xlsx` con alguno de estos esquemas:
- **Esquema A:** `variable | de | a`  
  (ej. p010, de=1 → a=“Propia”)
- **Esquema B:** `variable | codigo | etiqueta`  
  (ej. p014, codigo=2 → etiqueta=“Comercio”)

> Si existe, la app lo aplicará de manera automática cuando habilites la opción de **Correcciones** (si fue integrada) o si ejecutaste la limpieza previa.

### 2.3. Buenas prácticas de la base
- Guardar en **UTF‑8** (CSV) o Excel simple (sin fórmulas/hojas múltiples innecesarias).
- **PII** (nombres, teléfonos, correos, direcciones): anonimizar o eliminar antes de subir a GitHub.
- **Fechas**: usar formato consistente (dd/mm/aaaa o ISO).
- **GPS**: columnas **`lat`** y **`lon`** en grados decimales (o `p002__Latitude` / `p002__Longitude` que la app corrige).
- Evitar celdas combinadas y encabezados repetidos.

---

## 3) Interfaz y flujo de trabajo

### 3.1. Barra lateral – Datos
- **Sube archivo** (opcional): para cargar un dataset distinto en caliente, sin tocar `/data`.
- Si no subes nada, la app usa el archivo de `/data`.

### 3.2. Barra lateral – Mapeo de variables
Selecciona qué columnas del dataset corresponden a cada variable. El tablero está organizado por bloques (B–G) y además incluye:

- **GPS**:  
  - `LATITUD (GPS)` → elige `lat` o `p002__Latitude`  
  - `LONGITUD (GPS)` → elige `lon` o `p002__Longitude`
  - La app corrige longitudes mal escaladas (ej. -893155664 → -89.3155664).

- **Texto (abiertas)**:  
  - Selecciona las columnas abiertas (`p040`, `p041`, `p38tx`, `p024`).

### 3.3. Barra lateral – Filtros
- **Sector**: filtra por uno o varios sectores (si fue mapeado).  
  El resto de pestañas respetan el filtro activo.

---

## 4) Pestañas del tablero

### 4.1. B — Estructura
- Tabulados simples: p004 (uso), p005 (estado), p006/7/8 (materiales).
- Cruces: p004×p005, p005×materiales, p004×materiales.
- Los porcentajes son por fila y se evitan errores de JSON convirtiendo NaN de etiquetas a “(Sin dato)”.

### 4.2. C — Hogares (p004 = vivienda o mixto)
- Estadísticos numéricos (promedio/mediana/mín/máx) para nvivienda, p009a, p009b.
- Tabulados: p010 (tenencia), sexo jefatura, p011 (tamaño hogar).  
- Componentes del hogar (si existen): mujeres/hombres adultos, niños/niñas.
- Cruces clave: sexo jefatura con tenencia/servicios/estado/ingreso; tenencia×servicios/estado.

### 4.3. D — Socioeconómico (p004 = vivienda o mixto)
- Numéricos: p012 (años residencia), p013 (personas con ingreso).
- Tabulados: p014 (fuente ingreso), p022 (activos).
- Cruces: p014×sexo, p013×p011, p022×p010/p015.

### 4.4. E — Servicios (p004 = vivienda o mixto)
- Tabulados: p015–p021 (agua, saneamiento, basura).
- Cruces: p015×p010/sexo/p005; p016×p017; p018×p019; p020×p021.

### 4.5. F — Negocios (p004 = negocio o mixto)
- Numéricos: p026, p029, p030, p031.
- Tabulados: p025, p027, p028, p032.
- Cruces: actividad×permisos, permisos×tenencia, formales×total, tiempo×permisos, ingreso×permisos.

### 4.6. G — Espacios/Percepción
- Tabulados: p036 (seguridad), p035 (condiciones), p035tx (texto/códigos).
- Cruces: p036×p004/sexo, p035×p035tx.

### 4.7. I — Indicadores (ejecutivo)
- Indicadores heurísticos (editables en código):  
  - % estructuras en mal estado (p005 contiene “malo/mal”)
  - % jefatura femenina (texto contiene “mujer/femen”)
  - % tenencia precaria (p010 contiene “prest/ invad/ alquil sin/ sin titul”)
  - % hogares sin agua (p015 no contiene “agua/acued”)
  - % saneamiento inadecuado (p018 “letrin/ ninguno/ compart”)
  - % negocios sin permiso (p027 “no/ ninguno”)
  - Promedios de activos (p022, p032) y % formalización (p030/p029)

### 4.8. Mapa GPS
- Selecciona columnas **lat** y **lon** (o `p002__Latitude`/`p002__Longitude`).  
- La app corrige **auto-escalado** si las longitudes vinieran multiplicadas (microgrados).
- Muestra hasta 10.000 puntos (muestra aleatoria si hay más).

### 4.9. Texto (abiertas)
- **Frecuencias** de unigramas y bigramas (con stopwords en español).
- **Nube de palabras** por columna.
- **Codificación automática** por diccionario editable:
  - Formato: `categoria: palabra1|palabra2|...` (la primera coincidencia clasifica).
  - Descarga CSV con la categoría por fila.

### 4.10. Exportar
- Descarga **Anexo Estadístico (Excel)** con tabulados y cruces configurados.
- (Opcional) Descargar dataset corregido (si integraste la pestaña de **Correcciones**).

---

## 5) Actualizar/Corregir datos

### 5.1. Subir nuevos datos
- Opción 1: Subir archivo desde la barra lateral (aplica en caliente).  
- Opción 2: Reemplazar en `/data` y hacer push en GitHub; luego **Reboot** en Streamlit Cloud.

### 5.2. Usar Codebook
- Edita `data/Codebook.xlsx` con tus mapeos y vuelve a cargar la app.  
- La aplicación recodifica las variables que coinciden por nombre.

### 5.3. GPS
- Preferir columnas `lat` y `lon` en grados decimales.  
- Si tus datos son `p002__Latitude` / `p002__Longitude` escalados, la app auto-corrige; puedes también generar nuevas columnas `lat/lon` en la base final.

---

## 6) Solución de problemas (FAQ)

**No se ve el mapa.**  
- Verifica que en la barra lateral elegiste `LATITUD` y `LONGITUD` correctas.  
- Revisa que haya valores dentro de rango (lat [-90,90], lon [-180,180]).

**Error JSON con NaN en tablas.**  
- Ya está mitigado: convertimos etiquetas `NaN` a “(Sin dato)”. Si aparece de nuevo, asegúrate de que no hay columnas de tipo categoría con `NaN` como **etiqueta** (no valor).

**No aplica cambios del Codebook.**  
- Revisa encabezados del codebook y nombres exactos de las variables.  
- Confirma que el fichero está en `data/Codebook.xlsx`.

**Campos numéricos “como texto”.**  
- El dashboard intenta coerción, pero si hay símbolos (ej. “1,2 (aprox)”) quedarán `NaN`. Limpia la base de entrada o usa el script de limpieza.

**No aparecen columnas abiertas.**  
- Mapea `p040`, `p041`, `p38tx`, `p024` en la barra lateral. Si tienen otro nombre, selecciona las correspondientes.

**El conteo es raro tras filtrar sector.**  
- Asegúrate de que **Sector** está bien mapeado y que hay datos en esas categorías.

---

## 7) Buenas prácticas y mantenimiento
- Versiona tu data: `data/respuestas_YYYYMMDD.csv` si es necesario, pero deja el archivo “activo” como `respuestas.csv` o `respuestas.xlsx`.
- Mantén actualizado `requirements.txt` si agregas nuevas librerías.
- Evita subir PII a GitHub (anonimiza o elimina).
- Documenta cambios en `validation_report.txt` cuando corras limpiezas.

---

## 8) Personalización (opcional)
- Ajusta palabras clave de los **indicadores** en `tabI` para usar tus códigos exactos.  
- En **Texto (abiertas)**, adapta el diccionario base a tu dominio.  
- Cambia el muestreo máximo del mapa si necesitas más puntos.

---

## 9) Contacto y soporte
- Si algo “no hace nada”, revisa primero la **barra lateral** (mapeos y filtros) y el **log** de Streamlit (icono “hamburguesa” → “Clear cache & rerun”).  
- Para soporte, captura pantalla y adjunta el `validation_report.txt`.
