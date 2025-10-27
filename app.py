# -*- coding: utf-8 -*-
# =========================================================
# Dashboard de Plan de Tabulados — Encuesta (Streamlit)
# Requisitos (requirements.txt):
#   streamlit
#   pandas
#   numpy
#   pydeck
#   matplotlib
#   wordcloud
#   openpyxl
# Estructura de archivos (recomendada):
#   data/respuestas.xlsx
#   data/Codebook.xlsx
# =========================================================

import os, re, io, unicodedata
from io import BytesIO
from collections import Counter

import numpy as np
import pandas as pd
import streamlit as st

# Visualización
import pydeck as pdk
import matplotlib.pyplot as plt
from wordcloud import WordCloud

# ---------------------------------------------------------
# Configuración básica de la app
# ---------------------------------------------------------
st.set_page_config(
    page_title="Plan de Tabulados — Encuesta",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Plan de Tabulados — Encuesta")
st.caption("Panel interactivo para tabulados, cruces, diccionario, mapa GPS y nubes de palabras (abiertas).")

# =========================================================
# Helpers de limpieza y utilidades
# =========================================================
def clean_label(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip()
    rep = {
        "√≠": "í", "√≥": "ó", "√±": "ñ", "√©": "é", "√í": "á", "√∫": "ú", "###": ""
    }
    for k, v in rep.items():
        s = s.replace(k, v)
    return s


def ensure_string_cols(df: pd.DataFrame) -> pd.DataFrame:
    # Convierte columnas tipo "object" a string para evitar errores en filtros/agrupaciones
    for c in df.columns:
        if df[c].dtype == "object":
            df[c] = df[c].astype("string")
    return df


# ---------- Helpers de % y crosstab (seguros y explícitos) ----------
def vc_percent(df, col, by=None, by_label=None):
    """
    Devuelve conteos y % con denominador claro.
    - Si by is None: '%' = % del total.
    - Si by: '%' = % dentro de cada categoría de 'by'.
    """
    if df is None or len(df) == 0 or col in [None, "<ninguna>"]:
        return pd.DataFrame()

    col = str(col)
    if by not in [None, "<ninguna>"]:
        by = str(by)
        t = df.groupby([by, col], dropna=False)[col].count().rename("n").reset_index()
        denom_name = f"% dentro de {by_label or by}"
        # Evita división por cero
        t_group_sum = t.groupby(by)["n"].transform("sum").replace(0, np.nan)
        t[denom_name] = (t["n"] / t_group_sum * 100).round(1)
        return t
    else:
        t = df[col].value_counts(dropna=False).rename_axis(col).reset_index(name="n")
        total = t["n"].sum()
        t["% del total"] = (t["n"] / total * 100).round(1) if total else 0
        return t


def crosstab_pct(df, r, c, by=None, by_label=None):
    """
    Cruzadas con conteo y % por fila. Si hay 'by', calcula dentro de cada grupo.
    Devuelve una tabla apilada con columna 'Métrica' = {'Conteo','% por fila (dentro de .../global)'}.
    """
    if df is None or len(df) == 0 or any(x in [None, "<ninguna>"] for x in [r, c]):
        return pd.DataFrame()

    r, c = str(r), str(c)
    label_pct = f"% por fila (dentro de {by_label or by})" if by not in [None, "<ninguna>"] else "% por fila (global)"

    def _one_ct(sub, group_value=None):
        if len(sub) == 0:
            return pd.DataFrame()
        tab = pd.crosstab(sub[r], sub[c], dropna=False)
        if tab.shape[0] == 0:
            return pd.DataFrame()
        # Conteo
        tab_n = tab.copy()
        tab_n["Métrica"] = "Conteo"
        tab_n = tab_n.reset_index()
        # % por fila
        denom = tab.sum(axis=1).replace(0, np.nan)
        tab_pct = (tab.div(denom, axis=0) * 100).round(1)
        tab_pct["Métrica"] = label_pct
        tab_pct = tab_pct.reset_index()
        if group_value is not None:
            tab_n[by_label or "Grupo"] = group_value
            tab_pct[by_label or "Grupo"] = group_value
        return pd.concat([tab_n, tab_pct], ignore_index=True)

    if by not in [None, "<ninguna>"]:
        out = []
        for g, sub in df.groupby(by):
            out.append(_one_ct(sub, g))
        out = [x for x in out if x is not None and len(x) > 0]
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    else:
        return _one_ct(df)


# ---------- Texto (abiertas) ----------
STOPWORDS_ES = {
    "de","la","que","el","en","y","a","los","del","se","las","por","un","para",
    "con","no","una","su","al","lo","como","más","pero","sus","le","ya","o",
    "este","sí","porque","esta","entre","cuando","muy","sin","sobre","también",
    "me","hasta","hay","donde","quien","desde","todo","nos","durante","todos",
    "uno","les","ni","contra","otros","ese","eso","ante","ellos","e","esto","mí",
    "antes","algunos","qué","unos","yo","otro","otras","otra","él","tanto","esa",
    "estos","mucho","quienes","nada","muchos","cual","poco","ella","estar","estas",
    "algunas","algo","nosotros","mi","mis","tú","te","ti","tu","tus","ellas","nosotras",
    "vosotros","vosotras","os","mío","mía","míos","mías","tuyo","tuya","tuyos","tuyas",
    "suyo","suya","suyos","suyas","nuestro","nuestra","nuestros","nuestras",
    "vuestro","vuestra","vuestros","vuestras","esos","esas","estoy","estás","está",
    "estamos","estáis","están","esté","estés","estemos","estéis","estén","estaré",
    "estarás","estará","estaremos","estaréis","estarán","estaba","estabas","estábamos",
    "estabais","estaban","estuve","estuviste","estuvo","estuvimos","estuvisteis",
    "estuvieron","estuviera","estuvieras","estuviéramos","estuvierais","estuvieran",
    "estuviese","estuvieses","estuviésemos","estuvieseis","estuviesen","estando",
    "estado","estada","estados","estadas","estad","ser","soy","eres","es","somos",
    "sois","son","sea","seas","seamos","seáis","sean","seré","serás","será","seremos",
    "seréis","serán","era","eras","éramos","erais","eran","fui","fuiste","fue",
    "fuimos","fuisteis","fueron","fuera","fueras","fuéramos","fuerais","fueran",
    "fuese","fueses","fuésemos","fueseis","fuesen","siendo","sido","hoy","año",
    "años","mes","meses","día","días","así","cada"
}

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def clean_text_spanish(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.lower()
    s = _strip_accents(s)
    s = re.sub(r"http\S+|www\.\S+", " ", s)    # URLs
    s = re.sub(r"[@#]\w+", " ", s)             # @usuario, #hashtag
    s = re.sub(r"[\U00010000-\U0010ffff]", " ", s)  # emojis/símbolos
    s = re.sub(r"[^a-z0-9\s]", " ", s)         # mantener letras/números/espacio
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokenize_es(s: str, min_len: int = 3, stopwords_extra: set | None = None, keep_numbers: bool = False):
    if not s:
        return []
    tokens = s.split()
    sw = set(STOPWORDS_ES)
    if stopwords_extra:
        sw |= {clean_text_spanish(x) for x in stopwords_extra if x}
    out = []
    for t in tokens:
        if not keep_numbers and t.isdigit():
            continue
        if len(t) < min_len:
            continue
        if t in sw:
            continue
        out.append(t)
    return out

def make_ngrams(tokens, n=2, min_len=3):
    if n < 2:
        return []
    grams = []
    for i in range(len(tokens) - n + 1):
        g = tokens[i:i+n]
        if all(len(w) >= min_len for w in g):
            grams.append("_".join(g))
    return grams


# =========================================================
# Carga de datos
# =========================================================
st.sidebar.header("📁 Datos")

DATA_PATH = "data/respuestas.xlsx"
CODEBOOK_PATH = "data/Codebook.xlsx"

df = None
cb = None

# Carga principal (con fallback a file_uploader)
if os.path.exists(DATA_PATH):
    try:
        df = pd.read_excel(DATA_PATH)
    except Exception as e:
        st.error(f"No se pudo leer {DATA_PATH}: {e}")
else:
    st.sidebar.info("No se encontró 'data/respuestas.xlsx'. Sube el archivo para continuar.")
    up = st.sidebar.file_uploader("Subir respuestas.xlsx", type=["xlsx"])
    if up:
        try:
            df = pd.read_excel(up)
        except Exception as e:
            st.error(f"Error leyendo el archivo subido: {e}")

if df is not None:
    df = ensure_string_cols(df)
    # Limpieza leve de encabezados
    df.columns = [clean_label(c) for c in df.columns]

# Codebook (opcional)
if os.path.exists(CODEBOOK_PATH):
    try:
        cb = pd.read_excel(CODEBOOK_PATH)
        cb.columns = [clean_label(c) for c in cb.columns]
    except Exception as e:
        st.warning(f"No se pudo leer Codebook en {CODEBOOK_PATH}: {e}")
else:
    # Permite subir Codebook si no existe
    up_cb = st.sidebar.file_uploader("Subir Codebook.xlsx (opcional)", type=["xlsx"])
    if up_cb:
        try:
            cb = pd.read_excel(up_cb)
            cb.columns = [clean_label(c) for c in cb.columns]
        except Exception as e:
            st.warning(f"No se pudo leer el Codebook subido: {e}")

if df is None:
    st.stop()

# =========================================================
# Filtros globales (Sidebar)
# =========================================================
st.sidebar.header("🎛️ Filtros")

cols = df.columns.tolist()

# Filtro por SECTOR si existe
sector_col = "SECTOR" if "SECTOR" in df.columns else None
sector_value = "<todos>"
if sector_col:
    sectores = ["<todos>"] + sorted([x for x in df[sector_col].dropna().unique().tolist()])
    sector_value = st.sidebar.selectbox("SECTOR", sectores, index=0)

# Otros filtros genéricos (puedes duplicar este patrón para más columnas)
# Ejemplo: Tipo de estructura, si existe
extra_filters = {}
for candidate in ["TIPO", "TIPO_ESTRUCTURA", "Tipo", "tipo"]:
    if candidate in df.columns:
        vals = ["<todos>"] + sorted([x for x in df[candidate].dropna().unique().tolist()])
        extra_filters[candidate] = st.sidebar.selectbox(candidate, vals, index=0)
        break

# Aplica filtros
work = df.copy()
if sector_col and sector_value != "<todos>":
    work = work.loc[work[sector_col] == sector_value]

for k, v in extra_filters.items():
    if v != "<todos>":
        work = work.loc[work[k] == v]

work = work.copy()  # evita SetWithCopy
work = ensure_string_cols(work)

# =========================================================
# Tabs principales
# =========================================================
tab_resumen, tab_tabulados, tab_cruces, tab_mapa, tab_nube, tab_dict, tab_export = st.tabs(
    ["Resumen", "Tabulados", "Cruces", "🗺️ Mapa", "🧩 Nube — Abiertas", "📚 Diccionario", "Exportar"]
)

# Usaremos session_state para exportar el último resultado mostrado
if "last_table" not in st.session_state:
    st.session_state["last_table"] = pd.DataFrame()
if "last_table_name" not in st.session_state:
    st.session_state["last_table_name"] = "resultado"

# ---------------------------------------------------------
# Resumen
# ---------------------------------------------------------
with tab_resumen:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Registros (df)", len(df))
    with c2:
        st.metric("Registros (filtro activo)", len(work))
    with c3:
        st.metric("Columnas", df.shape[1])
    with c4:
        st.metric("Columnas texto", sum(str(df[c].dtype) in ("object", "string") for c in df.columns))

    st.markdown("### Vista rápida (primeras 50 filas del filtro actual)")
    st.dataframe(work.head(50), use_container_width=True, height=420)

# ---------------------------------------------------------
# Tabulados
# ---------------------------------------------------------
with tab_tabulados:
    st.subheader("Tabulados con porcentajes claros")
    # Selección de variable y opcional 'by'
    numeric_hint = st.checkbox("Excluir columnas numéricas", value=True)
    candidates = [c for c in work.columns if (not numeric_hint or work[c].dtype not in [np.number, "float64", "int64"])]
    var = st.selectbox("Variable a tabular", ["<ninguna>"] + candidates, index=0)

    by = st.selectbox("Desagregar por (opcional)", ["<ninguna>"] + candidates, index=(1 if sector_col else 0))
    by_label = "SECTOR" if (sector_col and by == sector_col) else None

    if var != "<ninguna>":
        t = vc_percent(work, var, by=None if by == "<ninguna>" else by, by_label=by_label)
        if len(t) == 0:
            st.info("No hay datos para tabular con el filtro actual.")
        else:
            st.dataframe(t, use_container_width=True)
            st.session_state["last_table"] = t.copy()
            st.session_state["last_table_name"] = f"tabulado_{var}" + ("" if by == "<ninguna>" else f"_by_{by}")

# ---------------------------------------------------------
# Cruces
# ---------------------------------------------------------
with tab_cruces:
    st.subheader("Cruces con conteo y % por fila")
    candidates = [c for c in work.columns]
    r = st.selectbox("Filas (r)", ["<ninguna>"] + candidates, index=0)
    c = st.selectbox("Columnas (c)", ["<ninguna>"] + candidates, index=0)
    by = st.selectbox("Corte (opcional)", ["<ninguna>"] + candidates, index=(1 if sector_col else 0))
    by_label = "SECTOR" if (sector_col and by == sector_col) else None

    if r != "<ninguna>" and c != "<ninguna>":
        tab = crosstab_pct(work, r, c, by=None if by == "<ninguna>" else by, by_label=by_label)
        if len(tab) == 0:
            st.info("No hay datos suficientes para este cruce con el filtro actual.")
        else:
            st.dataframe(tab, use_container_width=True)
            st.session_state["last_table"] = tab.copy()
            st.session_state["last_table_name"] = f"cruce_{r}_x_{c}" + ("" if by == "<ninguna>" else f"_by_{by}")

# ---------------------------------------------------------
# Mapa (GPS)
# ---------------------------------------------------------
with tab_mapa:
    st.subheader("Mapa de puntos GPS")

    def _guess(options, names):
        s = set([c.lower() for c in options])
        for n in names:
            if n.lower() in s:
                return n
        return "<ninguna>"

    lat_default = _guess(work.columns, ["p002__Latitude", "lat", "latitude"])
    lon_default = _guess(work.columns, ["p002__Longitude", "lon", "longitude"])

    lat_col = st.selectbox("Columna Latitud", ["<ninguna>"] + list(work.columns),
                           index=(["<ninguna>"] + list(work.columns)).index(lat_default) if lat_default != "<ninguna>" else 0)
    lon_col = st.selectbox("Columna Longitud", ["<ninguna>"] + list(work.columns),
                           index=(["<ninguna>"] + list(work.columns)).index(lon_default) if lon_default != "<ninguna>" else 0)

    if lat_col == "<ninguna>" or lon_col == "<ninguna>":
        st.info("Selecciona columnas de Latitud y Longitud.")
    else:
        mdf = work.copy()
        mdf["_lat"] = pd.to_numeric(mdf[lat_col], errors="coerce")
        mdf["_lon"] = pd.to_numeric(mdf[lon_col], errors="coerce")
        mdf = mdf.dropna(subset=["_lat", "_lon"])

        if len(mdf) == 0:
            st.info("No hay puntos válidos para graficar con el filtro actual.")
        else:
            color_by_sector = st.toggle("Colorear por SECTOR", value=("SECTOR" in mdf.columns))
            tooltip_txt = "{SECTOR}" if "SECTOR" in mdf.columns else ""

            if color_by_sector:
                # Codifica sector (0..n) para color
                codes = mdf["SECTOR"].astype("category").cat.codes if "SECTOR" in mdf.columns else 0
                mdf = mdf.assign(_color=(codes * 35) % 255)
                get_color = "[_color, 80, 200]"
            else:
                get_color = [0, 100, 200]

            layer = pdk.Layer(
                "ScatterplotLayer",
                mdf,
                get_position=["_lon", "_lat"],
                get_radius=10,
                get_color=get_color,
                pickable=True,
            )
            view_state = pdk.ViewState(
                latitude=float(mdf["_lat"].mean()),
                longitude=float(mdf["_lon"].mean()),
                zoom=13
            )
            st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state,
                                     tooltip={"text": tooltip_txt}))
            st.caption("El mapa respeta los filtros activos (ej. SECTOR).")

# ---------------------------------------------------------
# Nube — Abiertas
# ---------------------------------------------------------
with tab_nube:
    st.subheader("Nube de palabras para preguntas abiertas")

    text_cols = [c for c in work.columns if str(work[c].dtype) in ("object", "string")]
    if not text_cols:
        st.info("No se detectan columnas de texto en el filtro actual.")
    else:
        st.markdown("Selecciona **una o varias** columnas de texto (abiertas):")
        cols_sel = st.multiselect("Columnas de texto", text_cols)

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            max_pal = st.slider("Máx. palabras nube", 50, 1000, 200, step=50)
            min_len = st.slider("Mín. largo de palabra", 2, 8, 3, step=1)
        with col2:
            min_freq = st.slider("Frecuencia mínima", 1, 20, 2, step=1)
            use_bigrams = st.checkbox("Incluir bigramas (2-gramas)", value=True,
                                      help="Genera combinaciones frecuentes (ej. 'apoyo_tecnico').")
        with col3:
            keep_numbers = st.checkbox("Conservar números", value=False)
            collocations = st.checkbox("Colocaciones WordCloud", value=False,
                                       help="Si está activo, WordCloud detecta combinaciones frecuentes internamente.")

        st.markdown("Stopwords personalizadas (una por línea, ej. nombres de proyecto/siglas):")
        _sw_text = st.text_area("Stopwords adicionales", value="")
        sw_extra = {w.strip() for w in _sw_text.splitlines() if w.strip()}

        btn = st.button("Generar nube y frecuencias")

        if btn:
            if not cols_sel:
                st.warning("Selecciona al menos una columna de texto.")
            else:
                textos = work[cols_sel].astype(str).fillna("")
                concatenado = "\n".join([" ".join(row) for row in textos.values.tolist()])
                limpio = clean_text_spanish(concatenado)
                tokens = tokenize_es(limpio, min_len=min_len, stopwords_extra=sw_extra, keep_numbers=keep_numbers)

                if use_bigrams:
                    tokens += make_ngrams(tokens, n=2, min_len=min_len)

                freqs = Counter(tokens)
                freqs = Counter({k: v for k, v in freqs.items() if v >= min_freq})

                if len(freqs) == 0:
                    st.info("Sin términos suficientes con los criterios actuales. Ajusta filtros/columnas.")
                else:
                    wc = WordCloud(
                        background_color="white",
                        width=1400,
                        height=700,
                        max_words=max_pal,
                        collocations=collocations
                    ).generate_from_frequencies(freqs)

                    fig = plt.figure(figsize=(12, 6))
                    plt.imshow(wc, interpolation="bilinear")
                    plt.axis("off")
                    st.pyplot(fig, use_container_width=True)

                    # Descarga de la nube (PNG)
                    buf = BytesIO()
                    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
                    st.download_button("⬇️ Descargar nube (PNG)", data=buf.getvalue(),
                                       file_name="nube_palabras.png", mime="image/png")

                    # Tabla de frecuencias (CSV)
                    df_freq = (pd.DataFrame(freqs.items(), columns=["termino", "frecuencia"])
                               .sort_values("frecuencia", ascending=False)
                               .reset_index(drop=True))
                    st.markdown("### Frecuencias (top términos)")
                    st.dataframe(df_freq, use_container_width=True, height=420)

                    st.download_button(
                        "⬇️ Descargar frecuencias (CSV)",
                        data=df_freq.to_csv(index=False).encode("utf-8"),
                        file_name="frecuencias_abiertas.csv",
                        mime="text/csv"
                    )

# ---------------------------------------------------------
# Diccionario (Codebook)
# ---------------------------------------------------------
with tab_dict:
    st.subheader("📚 Diccionario de campos (Codebook)")
    if cb is None or len(cb) == 0:
        st.info("No se cargó un Codebook. Coloca `data/Codebook.xlsx` o súbelo en el sidebar.")
    else:
        st.dataframe(cb, use_container_width=True, height=500)

    st.markdown("""
**Ayuda de lectura de resultados**  
- Los tabulados muestran `n` y el porcentaje con su **denominador explícito**:  
  - **% del total**: respecto a todos los registros del filtro actual.  
  - **% dentro de SECTOR**: respecto al total de cada sector.  
- Los cruces reportan dos métricas: `Conteo` y `**% por fila**` (global o dentro del corte).  
- El mapa y la nube de palabras **respetan los filtros** activos del panel lateral.
    """)

# ---------------------------------------------------------
# Exportar
# ---------------------------------------------------------
with tab_export:
    st.subheader("Exportar último resultado mostrado")
    if st.session_state["last_table"] is None or len(st.session_state["last_table"]) == 0:
        st.info("Aún no hay una tabla para exportar. Genera un tabulado o cruce primero.")
    else:
        st.dataframe(st.session_state["last_table"].head(50), use_container_width=True, height=350)
        fn = f"{st.session_state['last_table_name']}.xlsx"
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            st.session_state["last_table"].to_excel(writer, index=False, sheet_name="Resultado")
        st.download_button("⬇️ Descargar Excel", data=buffer.getvalue(),
                           file_name=fn, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------
st.caption("© 2025 — Panel de tabulados con mapa y nubes de palabras. Listo para GitHub.")
