# Manual de Usuario — Dashboard de Encuesta (FUSADES / SmartDataIA)

> **Versión**: 1.0  
> **Pensado para:** usuarios no técnicos (“paso a paso, anti‑errores”).  
> **Funciona con:** `appfn.py` (versión corregida).

---

## 0) Resumen (TL;DR)

1. Abre el enlace del dashboard (o corre `streamlit run appfn.py`).  
2. En la **barra lateral**: sube el archivo de datos, o deja el que viene en `data/respuestas.xlsx`.  
3. En **Mapeo de variables**, selecciona qué columna corresponde a cada pregunta (p004, p005, etc.).  
4. Si tienes coordenadas, elige **LATITUD** y **LONGITUD** (la app corrige automáticamente escalas raras).  
5. Usa **Filtros** por sector si los necesitas.  
6. Revisa los resultados en las pestañas **B–G, Indicadores, Mapa GPS, Texto (abiertas)**.  
7. Para descargar todo a Excel, ve a **Exportar** → “Descargar Anexo Estadístico (Excel)”.  
8. Si quieres editar este manual, reemplaza `Manual_Usuario_Dashboard.md` en la raíz o `data/` y recarga la app.

---

## 1) Requisitos técnicos

- **Python 3.10+**
- Paquetes: `streamlit`, `pandas`, `numpy`, `openpyxl`, `xlsxwriter`, `plotly`, `scikit-learn`, `wordcloud`, `unidecode`, `nltk`  
- Instala con:
  ```bash
  pip install -r requirements.txt
  ```
- Ejecuta localmente:
  ```bash
  streamlit run appfn.py
  ```

> **Nota:** En Streamlit Cloud no necesitas instalar manualmente; los paquetes vienen del `requirements.txt` del repo.

---

## 2) Estructura del repositorio

```
├─ appfn.py                        # App principal (versión estable)
├─ data/
│  ├─ respuestas.xlsx              # Base por defecto (puede ser .csv)
│  ├─ Codebook.xlsx (opcional)     # Diccionario de variables
│  └─ Manual_Usuario_Dashboard.md  # (opcional) manual alterno
├─ MANUAL.md (opcional)            # También funciona si lo prefieres en raíz
├─ requirements.txt
└─ README.md
```

> La app busca el manual en este orden: `MANUAL.md` (raíz), `data/MANUAL.md`, `Manual_Usuario_Dashboard.md` (raíz) y `data/Manual_Usuario_Dashboard.md`.

---

## 3) Carga de datos

- **Automática**: si **no subes nada**, la app intenta abrir `data/respuestas.xlsx` y si no existe, `data/respuestas.csv`.
- **Manual (recomendado)**: usa el **cargador** de la barra lateral “Sube CSV/Excel” y elige tu archivo.

**Requisitos del dataset:**
- Una fila por **estructura** o **unidad de observación**.
- Encabezados claros. La app limpia caracteres raros, pero evita duplicados y typos.
- Si usas **coordenadas**, coloca cada una en su columna (ver §5).

---

## 4) Mapeo de variables (barra lateral)

En “**🧭 Mapeo de variables**” tendrás selectores para **vincular** las columnas reales de tu dataset con las variables del cuestionario. Si una columna **no existe**, elige “`<ninguna>`”.

### Lista de variables

**Sector / filtro**  
- `SECTOR`: columna con el barrio, zona o bloque que quieras usar como filtro.

**Bloque B — Estructura**
- `p004` Uso de la estructura (p.ej., vivienda, negocio, mixto).
- `p005` Estado físico de la estructura.
- `p006` Material del techo.
- `p007` Material de las paredes.
- `p008` Material del piso.

**Bloque C — Hogares (se calcula sólo sobre p004 = vivienda/mixto)**
- `nvivienda` Nº de hogares en la estructura.
- `p009a` Nº de **espacios habitables** (internos).
- `p009b` Nº de **niveles**.
- `p010` Tenencia del inmueble.
- `sexo jefatura` Sexo de la jefatura del hogar.
- `p011` Tamaño del hogar (# personas).
- `sexom`, `sexoh`, `sexonh`, `sexonm` (componentes del hogar, si existen).

**Bloque D — Socioeconómico (sobre p004 = vivienda/mixto)**
- `p012` Años de residencia.
- `p013` Nº de personas con ingresos.
- `p014` Fuente principal de ingreso.
- `p022` Activos del hogar.

**Bloque E — Servicios (sobre p004 = vivienda/mixto)**
- `p015` Servicios básicos disponibles.
- `p016` Frecuencia de acceso al agua.
- `p017` Fuente de agua.
- `p018` Tipo de sanitario.
- `p019` Uso del sanitario.
- `p020` Eliminación de aguas grises.
- `p021` Eliminación de basura.

**Bloque F — Negocios (sobre p004 = negocio/mixto)**
- `p025` Actividad principal.
- `p026` Tiempo de operación.
- `p027` Permisos de operación.
- `p028` Tenencia del local.
- `p029` Nº de trabajadores.
- `p030` Nº de empleados formales.
- `p031` Ingreso mensual de empleados.
- `p032` Activos del negocio.

**Bloque G — Espacios/Percepción (todos los registros)**
- `p035` Condiciones del espacio público.
- `p035tx` Problemas identificados (texto).
- `p036` Percepción de seguridad.

**GPS**
- `LATITUD (GPS)` y `LONGITUD (GPS)`: elige las columnas. 
  - Acepta nombres típicos: `lat`, `lon`, `latitude`, `longitude`, `p002__Latitude`, `p002__Longitude`, etc.
  - La app **autocorrige escalas** si detecta microgrados (divide entre `1e6` o `1e7`).

**Texto (abiertas)**
- `p040`, `p041`, `p38tx`, `p024`: selecciona las que existan para análisis de texto.

---

## 5) Mapa GPS

1. Selecciona tus columnas de **LATITUD** y **LONGITUD** en el mapeo.  
2. La app convierte a numérico, elimina `NaN` y **filtra por rangos válidos** (`lat` ∈ [-90,90], `lon` ∈ [-180,180]).  
3. Si tus coordenadas vienen en **microgrados** (ej. -893155664), la app intentará **corregir automáticamente** la escala.  
4. Verás los puntos en **Mapa GPS** con `st.map`. Abajo se reporta cuántos puntos fueron válidos.

**Diagnóstico rápido si no ves puntos:**
- Verifica que mapeaste **ambas** columnas (lat/lon).
- Abre la tabla original y revisa que haya al menos **algunos** valores numéricos; si están como texto (“13.7, -89.3” con coma), corrige el separador antes de subir.
- Quita filtros de **SECTOR** que puedan dejar el dataset vacío.

---

## 6) Tablas y cruces

Las pestañas **B a G** muestran tabulados simples y cruces (con porcentaje **por fila**).  
- Las **etiquetas faltantes** se normalizan como “**(Sin dato)**”, pero **no** se incluyen en los porcentajes.  
- Si necesitas cambiar el conjunto de “faltantes”, edítalo en el archivo (`MISSING_LABELS`).

**Interpretación de tablas:**  
- Columnas con `n` y `%` donde el porcentaje se calcula sobre el total del grupo (o fila en crosstabs).  
- En cruces, verás dos bloques por cada tabla: `n` (conteo) y `%` (porcentaje).

---

## 7) Indicadores (pestaña I)

Incluye un **resumen ejecutivo** con métricas útiles:  
- % estructuras en mal estado (`p005` contiene “mal” o “malo”).  
- % hogares con jefatura femenina.  
- % tenencia precaria.  
- % hogares sin acceso a agua potable.  
- % saneamiento inadecuado.  
- % negocios sin permisos.  
- Promedios de activos (`p022`, `p032`) y % de personal formalizado (`p030/p029`).

> **Nota**: Son **heurísticos**; si cambian tus categorías, actualiza las reglas en `appfn.py` (bloque **Indicadores**).

---

## 8) Texto (abiertas)

En la pestaña **Texto (abiertas)**:

1. Activa el **switch** “Activar análisis de texto (abiertas)”.  
2. La app elimina **no-respuestas** (p.ej., “No contestó”, “NS/NR”, “N/A”, etc.).  
3. Podrás ver **frecuencias** (unigramas/bigramas) y una **nube de palabras**.  
4. También incluye una **codificación automática** por diccionario editable (ej.: “seguridad: robo|asalto|…”).  
5. Descarga un **CSV** con la codificación aplicada.

**Evitar errores comunes:**
- Si aparece `DuplicateWidgetID`, recarga la app (Ctrl+R). La versión actual ya usa keys únicas.  
- Si la nube no se muestra, revisa que haya **texto suficiente** tras filtrar no-respuestas.

---

## 9) Exportar (Excel)

En **Exportar** → “Descargar Anexo Estadístico (Excel)” obtendrás un libro con múltiples hojas:
- Tabulados simples por variable.
- Cruces clave (con `n` y `%`).

> **Tip**: Asegúrate de que las variables estén **mapeadas**. Si todas están en “`<ninguna>`”, no se exporta nada.

---

## 10) Tratamiento de valores faltantes (lo que la app hace por ti)

- Convierte `NaN`, `nan`, celdas vacías y variaciones de “No respondió/No contesta/NSNR/NA/N/A` → “**(Sin dato)**” **sólo** para mostrar.  
- **Excluye** esos valores de los porcentajes (no sesga la distribución).  
- Si quieres incluirlos, comenta la línea que filtra `MISSING_LABELS` en `vc_percent` y `crosstab_pct` (no recomendado).

---

## 11) “Checklist” para subir datos a GitHub sin errores

1. **Encabezados**: sin duplicados, sin comas o saltos de línea.  
2. **Coordenadas**: cada una en su columna; evita “lat,lon” en la misma celda.  
3. **Codificaciones**: intenta que categorías estén **homogeneizadas** (misma ortografía).  
4. **PII**: elimina datos personales (nombres, teléfonos).  
5. **Revisión rápida**: abre el archivo, filtra nulos, confirma que las columnas clave existen.

---

## 12) Solución de problemas (FAQ)

**Q1. Veo “JSON Parse error: NaN”.**  
A1. Eso lo causaba un bug previo (etiquetas NaN). Con `appfn.py` actualizado ya queda resuelto. Si persiste, revisa que tu dataset no tenga la cadena **"NaN"** literal como categoría y vuelve a cargar.

**Q2. La nube de palabras dice: “unexpected keyword 'use_container_width'”.**  
A2. La versión actual usa `use_column_width=True` para imágenes de WordCloud; ya está corregido.

**Q3. No aparecen puntos en el mapa.**  
A3. Ver §5; usualmente es mapeo incorrecto o escala de coordenadas. La app ya corrige microgrados.

**Q4. El manual no se muestra.**  
A4. Pon tu `Manual_Usuario_Dashboard.md` en la **raíz** o en **`/data`** y recarga. Si no lo encuentra, verás este manual de respaldo.

**Q5. ¿Cómo agrego mis propias reglas de indicadores?**  
A5. Edita el bloque **Indicadores** en `appfn.py` (búsqueda por `with tabI:`) y modifica las expresiones `.str.contains(...)`.

---

## 13) Glosario (rápido)

- **Tabulados simples**: distribución de frecuencias y % por categoría.  
- **Crosstab / Cruce**: tabla de doble entrada; aquí el % se calcula **por fila**.  
- **(Sin dato)**: etiqueta neutra para faltantes; **no** se incluye en % por defecto.  
- **Microgrados**: coordenadas multiplicadas por 10^6 o 10^7 (típico en ciertas APIs).

---

## 14) Buenas prácticas

- Mantén un **codebook** (diccionario de variables).  
- Documenta **versiones** de la base (fecha, cambios).  
- Para preguntas abiertas, usa **codificación** (diccionario) y guarda la tabla resultante.  
- Exporta el **Anexo** al final de cada iteración; facilita auditoría.

---

## 15) Contacto / Soporte

- Si algo se rompe, anota la **pestaña**, una captura del **mensaje** y el **archivo** que subiste.  
- Verifica primero el **mapeo** de variables y que el dataset no esté vacío tras filtros.

---

¡Listo! Con esto deberías poder operar el dashboard de punta a punta sin sorpresas.
