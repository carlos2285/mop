# app.py
import os, io, re, pathlib
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Plan de Tabulados — Encuesta", layout="wide")

# ---------- Estilos (tabs más espacios y wrap) ----------
st.markdown("""
<style>
.stTabs [data-baseweb="tab-list"]{ gap: .75rem; flex-wrap: wrap; }
.stTabs [data-baseweb="tab"]{
  padding: 8px 14px; border-radius: 10px;
  background: rgba(255,255,255,.05); color:#ddd;
}
.stTabs [aria-selected="true"]{
  background: rgba(255,255,255,.14); color:#fff; font-weight:600;
}
</style>
""", unsafe_allow_html=True)

# ---------- Convenciones de faltantes ----------
MISSING_LABELS = {
    "", "(Sin dato)", "No contestó", "No contesto", "No respondió", "No responde",
    "No sabe/No responde", "NS/NR", "Ns/Nr", "NSNR", "No aplica", "NA", "N/A",
    "Sin respuesta", "NR"
}
def _is_missing_label(x: str) -> bool:
    return str(x).strip() in MISSING_LABELS

# ---------- Helpers ----------
def clean_label(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip()
    rep = {"√≠":"í","√≥":"ó","√±":"ñ","√©":"é","√í":"á","√∫":"ú","###":""}
    for k,v in rep.items():
        s = s.replace(k,v)
    return s

def _make_unique_columns(cols):
    seen, out = {}, []
    for c in cols:
        base = str(c)
        if base not in seen:
            seen[base] = 1; out.append(base)
        else:
            seen[base] += 1; out.append(f"{base} ({seen[base]})")
    return out

def _cat(s: pd.Series) -> pd.Series:
    # convierte a object, rellena NaN a "(Sin dato)" y fuerza str
    return s.astype("object").where(s.notna(), "(Sin dato)").astype(str)

def vc_percent(df, col, by=None):
    if col not in df.columns: return pd.DataFrame(columns=[col, "n", "%"])
    if by is not None and by not in df.columns: by = None

    if by is None:
        s = _cat(df[col])
        s = s[~s.isin(MISSING_LABELS)]
        if s.empty: return pd.DataFrame(columns=[col, "n", "%"])
        t = s.value_counts(dropna=False).rename_axis(col).reset_index(name="n")
        total = int(t["n"].sum())
        t["%"] = (t["n"] / total * 100).round(1) if total else 0
        return t

    tmp = pd.DataFrame({by: _cat(df[by]), col: _cat(df[col])})
    tmp = tmp[~tmp[col].isin(MISSING_LABELS)]
    if tmp.empty: return pd.DataFrame(columns=[by, col, "n", "%"])
    t = tmp.groupby([by, col], dropna=False).size().rename("n").reset_index()
    t["%"] = t.groupby(by)["n"].transform(lambda s: (s/s.sum()*100).round(1))
    return t

def crosstab_pct(df, r, c, by=None):
    if (r not in df.columns) or (c not in df.columns):
        return pd.DataFrame()

    if by is None:
        rr, cc = _cat(df[r]), _cat(df[c])
        mask = (~rr.isin(MISSING_LABELS)) & (~cc.isin(MISSING_LABELS))
        rr, cc = rr[mask], cc[mask]
        if rr.empty or cc.empty: return pd.DataFrame()
        tab = pd.crosstab(rr, cc, dropna=False)
        tab.columns = tab.columns.astype(str)
        tab["n_fila"] = tab.sum(axis=1)
        pct = (tab.div(tab["n_fila"].replace(0, np.nan), axis=0)*100).round(1)
        tab = tab.drop(columns=["n_fila"])
        tab["__tipo__"] = "n"; pct["__tipo__"] = "%"
        return pd.concat(
            [tab.reset_index().rename(columns={"index": r}),
             pct.reset_index().rename(columns={"index": r})],
            ignore_index=True
        )

    # con 'by': iterar grupos
    out = []
    for g, sub in df.groupby(by):
        rr, cc = _cat(sub[r]), _cat(sub[c])
        mask = (~rr.isin(MISSING_LABELS)) & (~cc.isin(MISSING_LABELS))
        rr, cc = rr[mask], cc[mask]
        if rr.empty or cc.empty: continue
        tab = pd.crosstab(rr, cc, dropna=False)
        tab.columns = tab.columns.astype(str)
        tab["n_fila"] = tab.sum(axis=1)
        pct = (tab.div(tab["n_fila"].replace(0, np.nan), axis=0)*100).round(1)
        tab = tab.drop(columns=["n_fila"])
        tab["__grupo__"] = str(g); tab["__tipo__"] = "n"
        pct["__grupo__"] = str(g); pct["__tipo__"] = "%"
        out.append(tab.reset_index().rename(columns={"index": r}))
        out.append(pct.reset_index().rename(columns={"index": r}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

# ====== NUEVO: Render bonito para cruces (separa n/% y ordena) ======
def _render_crosstab_pretty(out: pd.DataFrame, r: str):
    """Recibe la salida de crosstab_pct() y la muestra en dos tablas (n y %),
    ocultando columnas técnicas y ordenando filas por el total (desc)."""

    if out is None or out.empty:
        st.info("Sin datos para cruzar.")
        return

    def _order_rows(n_df: pd.DataFrame) -> list:
        cols = [x for x in n_df.columns if x != r]
        if not cols:
            return list(range(len(n_df)))
        tot = n_df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        return list(tot.sort_values(ascending=False).index)

    # Caso SIN desagregación por grupo
    if "__grupo__" not in out.columns:
        n   = out[out["__tipo__"] == "n"] \
                .drop(columns=["__tipo__", "n_fila"], errors="ignore") \
                .reset_index(drop=True)
        pct = out[out["__tipo__"] == "%"] \
                .drop(columns=["__tipo__", "n_fila"], errors="ignore") \
                .reset_index(drop=True)

        order = _order_rows(n)
        n   = n.loc[order].reset_index(drop=True)
        pct = pct.loc[order].reset_index(drop=True)

        t1, t2 = st.tabs(["Conteos (n)", "Porcentajes (%)"])
        with t1:
            st.dataframe(n, use_container_width=True)
        with t2:
            st.dataframe(pct, use_container_width=True)
        return

    # Caso CON desagregación por grupo
    for g, sub in out.groupby("__grupo__"):
        n   = sub[sub["__tipo__"] == "n"] \
                .drop(columns=["__tipo__", "n_fila", "__grupo__"], errors="ignore") \
                .reset_index(drop=True)
        pct = sub[sub["__tipo__"] == "%"] \
                .drop(columns=["__tipo__", "n_fila", "__grupo__"], errors="ignore") \
                .reset_index(drop=True)

        order = _order_rows(n)
        n   = n.loc[order].reset_index(drop=True)
        pct = pct.loc[order].reset_index(drop=True)

        with st.expander(f"Sector: {g}", expanded=False):
            t1, t2 = st.tabs(["Conteos (n)", "Porcentajes (%)"])
            with t1:
                st.dataframe(n, use_container_width=True)
            with t2:
                st.dataframe(pct, use_container_width=True)

# ---------- Export a Excel ----------
def export_xlsx(sheets_dict):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet, df in sheets_dict.items():
            if isinstance(df, dict):
                startrow = 0
                for name, sub in df.items():
                    sub.to_excel(writer, index=False, sheet_name=sheet, startrow=startrow)
                    startrow += len(sub) + 3
            else:
                df.to_excel(writer, index=False, sheet_name=sheet)
    return output.getvalue()

# ---------- Carga de datos ----------
st.sidebar.title("⚙️ Datos")
uploaded = st.sidebar.file_uploader("Sube CSV/Excel (opcional)", type=["csv","xlsx"])
DATA_PATH_XLSX = "data/respuestas.xlsx"
DATA_PATH_CSV  = "data/respuestas.csv"
CODEBOOK_PATH  = "data/Codebook.xlsx"

if uploaded is None:
    if os.path.exists(DATA_PATH_XLSX):
        try:
            df = pd.read_excel(DATA_PATH_XLSX, engine="openpyxl")
        except Exception as e:
            st.error(f"No se pudo leer {DATA_PATH_XLSX} con openpyxl. Detalle: {e}")
            st.stop()
    elif os.path.exists(DATA_PATH_CSV):
        df = pd.read_csv(DATA_PATH_CSV)
    else:
        st.error("No se encontró data/respuestas.xlsx ni data/respuestas.csv.")
        st.stop()
else:
    if uploaded.name.endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        try:
            df = pd.read_excel(uploaded, engine="openpyxl")
        except Exception as e:
            st.error(f"No se pudo leer el Excel subido con openpyxl. Detalle: {e}")
            st.stop()

codebook = None
if os.path.exists(CODEBOOK_PATH):
    try:
        codebook = pd.read_excel(CODEBOOK_PATH, engine="openpyxl")
    except Exception as e:
        st.warning(f"No se pudo leer Codebook en {CODEBOOK_PATH}. Detalle: {e}")

df = df.rename(columns={c: clean_label(c) for c in df.columns})
df.columns = _make_unique_columns(df.columns)

# ---------- Mapeo de variables ----------
st.sidebar.header("🧭 Mapeo de variables")
def pick(label, default_candidates):
    options = ["<ninguna>"] + list(df.columns)
    default = 0
    for cand in default_candidates:
        for i, col in enumerate(options):
            if col.lower() == cand.lower():
                default = i; break
        if default: break
    return st.sidebar.selectbox(label, options=options, index=default, key=f"pick_{label}")

sector = pick("SECTOR", ["sector","zona","bloque"])

# B
p004 = pick("p004 Uso de estructura", ["p004","Uso de la estructura"])
p005 = pick("p005 Estado físico", ["p005"])
p006 = pick("p006 Material techo", ["p006","Material del techo"])
p007 = pick("p007 Material paredes", ["p007","Material de las paredes"])
p008 = pick("p008 Material piso", ["p008","Material del piso"])
# C
nviv = pick("nvivienda Nº de hogares", ["nvivienda","n_hogares","hogares"])
p009a = pick("p009a Espacios habitables", ["p009a","espacios habitables"])
p009b = pick("p009b Niveles", ["p009b","niveles del hogar","niveles del hogsar"])
p010 = pick("p010 Tenencia", ["p010","Tenencia del inmueble"])
sexoj = pick("Sexo jefatura", ["sexo_jefe_hogar1","sexo_jefe_hogar","sexo jefatura","sexo_jefatura"])
p011 = pick("p011 Tamaño del hogar", ["p011","personas en el hogar"])
sexom = pick("Mujeres adultas", ["sexom"])
sexoh = pick("Hombres adultos", ["sexoh"])
sexonh = pick("Niños", ["sexonh"])
sexonm = pick("Niñas", ["sexonm"])
# D
p012 = pick("p012 Años de residencia", ["p012","yearsresidencia","años residencia"])
p013 = pick("p013 Personas con ingresos", ["p013","personas con ingresos"])
p014 = pick("p014 Fuente principal de ingreso", ["p014","fuente principal de ingresos","Fuente principal de ingreso"])
p022 = pick("p022 Activos del hogar", ["p022","activos hogar"])
# E
p015 = pick("p015 Servicios básicos", ["p015","Servicios básicos disponibles","Servicio: Agua"])
p016 = pick("p016 Frecuencia agua", ["p016","Frecuencia acceso agua"])
p017 = pick("p017 Fuente de agua", ["p017","Fuente de agua"])
p018 = pick("p018 Tipo sanitario", ["p018","Tipo de sanitario"])
p019 = pick("p019 Uso sanitario", ["p019","Uso sanitario"])
p020 = pick("p020 Aguas grises", ["p020","Eliminación aguas grises"])
p021 = pick("p021 Basura", ["p021","Eliminación basura"])
# F
p025 = pick("p025 Actividad negocio", ["p025","Actividad principal"])
p026 = pick("p026 Tiempo operación", ["p026","Tiempo de operación"])
p027 = pick("p027 Permisos", ["p027","Permisos de operación"])
p028 = pick("p028 Tenencia local", ["p028","Tenencia local"])
p029 = pick("p029 Nº trabajadores", ["p029","Nº trabajadores"])
p030 = pick("p030 Nº formales", ["p030","Nº empleados formales"])
p031 = pick("p031 Ingreso mensual", ["p031","Ingreso mensual empleados"])
p032 = pick("p032 Activos negocio", ["p032","Activos negocio"])
# G
p035 = pick("p035 Condiciones del espacio", ["p035","Condiciones del espacio"])
p035tx = pick("p035tx Problemas (texto/cod)", ["p035tx","Problemas identificados"])
p036 = pick("p036 Percepción seguridad", ["p036","Percepción de seguridad"])
# GPS
lat_col = pick("LATITUD (GPS)", ["lat","latitude","y","gps_lat","Latitud"])
lon_col = pick("LONGITUD (GPS)", ["lon","longitude","x","lng","long","gps_lon","Longitud"])
# Abiertas
p040 = pick("p040 (abierta)", ["p040"])
p041 = pick("p041 (abierta)", ["p041"])
p38tx = pick("p38tx (abierta)", ["p38tx","p038tx","p38"])
p024  = pick("p024 (abierta)",  ["p024"])

# ---------- Filtro general por sector (multiselect) ----------
st.sidebar.header("Filtros")
work = df.copy()
if sector != "<ninguna>":
    vals = sorted([v for v in work[sector].dropna().unique()])
    sel  = st.sidebar.multiselect("Sector (filtro base)", options=vals, default=vals, key="flt_sector")
    if sel: work = work[work[sector].isin(sel)]
    else:   work = work.iloc[0:0]

# ---------- Vista Totales vs. Sólo un sector (drill-down) ----------
st.sidebar.header("👁️ Vista de tabulados")
vista = st.sidebar.radio(
    "Modo de vista",
    ["Totales (toda la muestra)", "Sólo un sector"],
    index=0, key="vista_tablas"
)
sector_focus = None
if (vista == "Sólo un sector") and (sector != "<ninguna>"):
    opciones_sector = ["<elige>"] + sorted([v for v in work[sector].dropna().unique()])
    sector_focus = st.sidebar.selectbox("Sector a mostrar", opciones_sector, index=0, key="sector_focus")

if (vista == "Sólo un sector") and (sector_focus not in [None, "<elige>"]) and (sector != "<ninguna>"):
    view_df = work[work[sector] == sector_focus].copy()
    ambito_txt = f"**{sector_focus}**"
else:
    view_df = work.copy()
    ambito_txt = "**Totales**"

# ---------- Utilidades de render ----------
def show_vc(label_var_tuple):
    col, label = label_var_tuple
    if col == "<ninguna>": return
    st.markdown(f"**{label}**")
    st.dataframe(vc_percent(view_df, col, by=None), use_container_width=True)

# ====== NUEVO: usamos el render bonito para cruces
def show_xtab(r, c, titulo=None):
    if (r == "<ninguna>") or (c == "<ninguna>"):
        return
    if titulo:
        st.markdown(f"**{titulo}**")
    _out = crosstab_pct(view_df, r, c, by=None)
    _render_crosstab_pretty(_out, r)

# ---------- Header & KPIs ----------
st.title("📊 Plan de Tabulados y Cruces — Anexo Estadístico")
st.caption(f"Ámbito actual: {ambito_txt}")
c1,c2,c3,c4 = st.columns(4)
c1.metric("Observaciones", f"{len(view_df):,}")
if sector != "<ninguna>":
    c2.metric("Sectores (en filtro base)", int(work[sector].nunique()))
else:
    c2.metric("Sectores", "—")
if p011 != "<ninguna>":
    with np.errstate(all='ignore'):
        c3.metric("Tamaño hogar (media)", f"{pd.to_numeric(view_df[p011], errors='coerce').mean():.1f}")
else:
    c3.metric("Tamaño hogar (media)", "—")
if p029 != "<ninguna>":
    with np.errstate(all='ignore'):
        c4.metric("Trabajadores (media)", f"{pd.to_numeric(view_df[p029], errors='coerce').mean():.1f}")
else:
    c4.metric("Trabajadores (media)", "—")

st.markdown("---")

# ---------- Tabs ----------
tabB, tabC, tabD, tabE, tabF, tabG, tabI, tabMAP, tabTXT, tabMANUAL, tabEXPORT = st.tabs([
    "B — Estructura", "C — Hogares", "D — Socioeconómico", "E — Servicios",
    "F — Negocios", "G — Espacios/Percepción", "I — Indicadores",
    "Mapa GPS", "Texto (abiertas)", "Manual", "Exportar"
])

# ---- B
with tabB:
    st.subheader("BLOQUE B – Características físicas de la estructura")
    st.markdown("**Tabulados simples**")
    for par in [
        (p004,"Uso de estructura (p004)"),
        (p005,"Estado físico (p005)"),
        (p006,"Material del techo (p006)"),
        (p007,"Material de las paredes (p007)"),
        (p008,"Material del piso (p008)")
    ]: show_vc(par)

    st.markdown("**Cruces clave**")
    show_xtab(p004, p005, "p004 × p005 — Estado físico por uso de estructura")
    show_xtab(p005, p006, "p005 × Material techo")
    show_xtab(p005, p007, "p005 × Material paredes")
    show_xtab(p005, p008, "p005 × Material piso")
    show_xtab(p004, p006, "p004 × Material techo")
    show_xtab(p004, p007, "p004 × Material paredes")
    show_xtab(p004, p008, "p004 × Material piso")

# ---- C
def is_vivienda_or_mixto(v):
    if v is None: return False
    s = str(v).strip().lower()
    return ("vivienda" in s) or ("mixto" in s) or ("vivienda–negocio" in s) or ("vivienda-negocio" in s)

with tabC:
    st.subheader("BLOQUE C – Hogares (p004 = vivienda o mixto)")
    sub = view_df.copy()
    if p004 != "<ninguna>":
        sub = sub[[True if is_vivienda_or_mixto(v) else False for v in sub[p004]]]

    st.markdown("**Tabulados simples y descriptivos**")
    for col,label in [(nviv,"Nº de hogares (nvivienda)"),
                      (p009a,"Nº de espacios habitables (p009a)"),
                      (p009b,"Nº de niveles (p009b)")]:
        if col!="<ninguna>":
            x = pd.to_numeric(sub[col], errors='coerce')
            desc = x.describe()[["count","mean","50%","min","max"]].rename({"50%":"median"})
            st.markdown(f"**{label} — media/mediana/min/max**")
            st.write(desc.to_frame().T)

    for col,label in [(p010,"Tenencia (p010)"), (sexoj,"Sexo jefatura"), (p011,"Tamaño del hogar (p011) desagregado")]:
        show_vc((col,label))

    st.markdown("**Cruces clave**")
    for r,c,t in [
        (sexoj,p010,"Sexo jefatura × Tenencia"),
        (sexoj,p015,"Sexo jefatura × Servicios básicos"),
        (sexoj,p005,"Sexo jefatura × Estado físico"),
        (sexoj,p014,"Sexo jefatura × Fuente de ingreso"),
        (sexoj,p011,"Sexo jefatura × Tamaño del hogar"),
        (p010,p015,"Tenencia × Servicios básicos"),
        (p010,p005,"Tenencia × Estado físico"),
    ]: show_xtab(r,c,t)

# ---- D
with tabD:
    st.subheader("BLOQUE D – Socioeconómico (p004 = vivienda o mixto)")
    sub = view_df.copy()
    if p004 != "<ninguna>":
        sub = sub[[True if is_vivienda_or_mixto(v) else False for v in sub[p004]]]

    for col,label in [(p012,"Años de residencia (p012)"), (p013,"Nº personas con ingresos (p013)")]:
        if col!="<ninguna>":
            x = pd.to_numeric(sub[col], errors='coerce')
            desc = x.describe()[["count","mean","50%","min","max"]].rename({"50%":"median"})
            st.markdown(f"**{label} — media/mediana/min/max**")
            st.write(desc.to_frame().T)

    for par in [(p014,"Fuente principal de ingreso (p014)"), (p022,"Activos del hogar (p022)")]:
        show_vc(par)

    st.markdown("**Cruces clave**")
    for r,c,t in [
        (p014, sexoj, "Fuente de ingreso × Sexo jefatura"),
        (p013, p011, "Nº personas con ingresos × Tamaño del hogar"),
        (p022, p010, "Activos × Tenencia"),
        (p022, p015, "Activos × Servicios básicos"),
    ]: show_xtab(r,c,t)

# ---- E
with tabE:
    st.subheader("BLOQUE E – Servicios (p004 = vivienda o mixto)")
    sub = view_df.copy()
    if p004 != "<ninguna>":
        sub = sub[[True if is_vivienda_or_mixto(v) else False for v in sub[p004]]]

    for par in [
        (p015,"Servicios básicos (p015)"), (p016,"Frecuencia acceso agua (p016)"),
        (p017,"Fuente de agua (p017)"), (p018,"Tipo de sanitario (p018)"),
        (p019,"Uso sanitario (p019)"), (p020,"Eliminación aguas grises (p020)"),
        (p021,"Eliminación basura (p021)")
    ]: show_vc(par)

    st.markdown("**Cruces clave**")
    for r,c,t in [
        (p015, p010, "Servicios básicos × Tenencia"),
        (p015, sexoj, "Servicios básicos × Sexo jefatura"),
        (p015, p005, "Servicios básicos × Estado físico"),
        (p016, p017, "Frecuencia agua × Fuente de agua"),
        (p018, p019, "Tipo sanitario × Uso sanitario"),
        (p020, p021, "Aguas grises × Eliminación basura"),
    ]: show_xtab(r,c,t)

# ---- F
def is_negocio_or_mixto(v):
    if v is None: return False
    s = str(v).strip().lower()
    return ("negocio" in s) or ("mixto" in s) or ("vivienda–negocio" in s) or ("vivienda-negocio" in s)

with tabF:
    st.subheader("BLOQUE F – Negocios (p004 = negocio o mixto)")
    sub = view_df.copy()
    if p004 != "<ninguna>":
        sub = sub[[True if is_negocio_or_mixto(v) else False for v in sub[p004]]]

    for col,label in [
        (p025,"Actividad principal (p025)"), (p026,"Tiempo de operación (p026)"),
        (p027,"Permisos de operación (p027)"), (p028,"Tenencia local (p028)"),
        (p029,"Nº trabajadores (p029)"), (p030,"Nº empleados formales (p030)"),
        (p031,"Ingreso mensual empleados (p031)"), (p032,"Activos negocio (p032)")
    ]:
        if col in [p026,p029,p030,p031] and col!="<ninguna>":
            x = pd.to_numeric(sub[col], errors='coerce')
            desc = x.describe()[["count","mean","50%","min","max"]].rename({"50%":"median"})
            st.markdown(f"**{label} — media/mediana/min/max**")
            st.write(desc.to_frame().T)
        else:
            show_vc((col,label))

    st.markdown("**Cruces clave**")
    for r,c,t in [
        (p025, p027, "Actividad × Permisos"),
        (p027, p028, "Permisos × Tenencia local"),
        (p030, p029, "Nº formales × Total trabajadores"),
        (p026, p027, "Tiempo de operación × Permisos"),
        (p031, p027, "Ingreso mensual × Permisos"),
    ]: show_xtab(r,c,t)

# ---- G
with tabG:
    st.subheader("BLOQUE G – Espacios públicos y percepción")
    for par in [(p036,"Percepción de seguridad (p036)"),
                (p035,"Condiciones del espacio (p035)"),
                (p035tx,"Problemas identificados (p035tx)")]:
        show_vc(par)

    st.markdown("**Cruces clave**")
    for r,c,t in [
        (p036, p004, "Percepción seguridad × Uso de estructura"),
        (p036, sexoj, "Percepción seguridad × Sexo jefatura"),
        (p035, p035tx, "Condiciones del espacio × Problemas identificados"),
    ]: show_xtab(r,c,t)

# ---- I (Indicadores)
with tabI:
    st.subheader("BLOQUE I – Indicadores (resumen)")
    base = view_df.copy()
    ind = {}

    if p005!="<ninguna>":
        s = base[p005].astype(str).str.lower()
        ind["% estructuras en mal estado"] = (s.str.contains("malo") | s.str.contains("mal")).mean()*100 if len(s)>0 else np.nan
    if sexoj!="<ninguna>":
        s = base[sexoj].astype(str).str.lower()
        ind["% hogares con jefatura femenina"] = (s.str.contains("mujer") | s.str.contains("femen")).mean()*100 if len(s)>0 else np.nan
    if p010!="<ninguna>":
        s = base[p010].astype(str).str.lower()
        prec = s.str_contains("prest") | s.str.contains("invad") | s.str.contains("alquil.*sin") | s.str.contains("sin.*titul")
        ind["% hogares con tenencia precaria"] = prec.mean()*100 if len(s)>0 else np.nan
    if p015!="<ninguna>":
        s = base[p015].astype(str).str.lower()
        ind["% hogares sin acceso a agua potable"] = (~(s.str.contains("agua") | s.str.contains("acued"))).mean()*100 if len(s)>0 else np.nan
    if p018!="<ninguna>":
        s = base[p018].astype(str).str.lower()
        ind["% hogares con saneamiento inadecuado"] = (s.str.contains("letrin") | s.str.contains("ninguno") | s.str.contains("compart")).mean()*100 if len(s)>0 else np.nan
    if p027!="<ninguna>":
        s = base[p027].astype(str).str.lower()
        ind["% negocios sin permisos"] = (s.str.contains("no") | s.str.contains("ninguno")).mean()*100 if len(s)>0 else np.nan
    if p022!="<ninguna>":
        ind["Promedio activos por hogar"] = pd.to_numeric(base[p022], errors='coerce').mean()
    if p032!="<ninguna>":
        ind["Promedio activos por negocio"] = pd.to_numeric(base[p032], errors='coerce').mean()
    if p030!="<ninguna>" and p029!="<ninguna>":
        num = pd.to_numeric(base[p030], errors='coerce')
        den = pd.to_numeric(base[p029], errors='coerce').replace(0, np.nan)
        ind["% negocios con personal formalizado"] = ((num/den).mean()*100) if den.notna().any() else np.nan

    st.dataframe(pd.DataFrame({"Indicador": list(ind.keys()), "Valor": list(ind.values())}), use_container_width=True)
    st.caption("Las reglas son heurísticas; ajusta a tu codificación final.")

# ---- MAPA
with tabMAP:
    st.subheader("Mapa de coordenadas GPS")
    if lat_col != "<ninguna>" and lon_col != "<ninguna>":
        m = view_df.copy()
        m["_lat"] = pd.to_numeric(m[lat_col], errors="coerce")
        m["_lon"] = pd.to_numeric(m[lon_col], errors="coerce")
        m = m.dropna(subset=["_lat","_lon"])
        m = m[(m["_lat"].between(-90,90)) & (m["_lon"].between(-180,180))]
        if m.empty:
            st.info("No hay coordenadas válidas después de la limpieza.")
        else:
            map_df = m.rename(columns={"_lat":"lat","_lon":"lon"})[["lat","lon"]]
            st.map(map_df, use_container_width=True)
            st.caption(f"{len(map_df):,} puntos mostrados (vista: {ambito_txt.strip('*')}).")
    else:
        st.info("Selecciona LATITUD y LONGITUD en la barra lateral.")

# ---- TEXTO (abiertas)
with tabTXT:
    st.subheader("Análisis de preguntas abiertas")
    activar_texto = st.toggle("Activar análisis de texto (abiertas)", value=False, key="txt_toggle",
                              help="Activa para calcular frecuencias y generar nubes de palabras")
    if not activar_texto:
        st.info("Activa el análisis para calcular frecuencias y nubes.")
    else:
        import nltk
        from sklearn.feature_extraction.text import CountVectorizer
        from wordcloud import WordCloud
        from unidecode import unidecode

        # stopwords ES
        try:
            from nltk.corpus import stopwords
            _ = stopwords.words("spanish")
        except:
            nltk.download("stopwords")
            from nltk.corpus import stopwords

        stop_es = set(stopwords.words("spanish")) | {
            "si","no","sì","sí","mas","más","tambien","también","pues","porque",
            "q","que","ya","solo","sólo","alli","allí","ahi","ahí","aqui","aquí"
        }
        MISSING_TEXT_PATTERNS = (
            r"^no\s*contesta.?$|^no\s*respond[eió].?$|^ns/?nr$|^no\s*sabe\s*/?\s*no\s*responde$|^sin\s*respuesta$|^na$|^n/?a$",
        )
        def is_missing_text(s: str) -> bool:
            s = str(s or "").strip().lower()
            if s in {m.lower() for m in MISSING_LABELS}: return True
            for pat in MISSING_TEXT_PATTERNS:
                if re.match(pat, s, flags=re.I): return True
            return False

        def norm(s):
            if pd.isna(s): return ""
            s = str(s).replace("\n"," ").lower()
            s = re.sub(r"\s+", " ", s).strip()
            return unidecode(s)

        text_cols = [c for c in [p040, p041, p38tx, p024] if c != "<ninguna>" and c in view_df.columns]
        if not text_cols:
            st.warning("Selecciona al menos una columna abierta (p040, p041, p38tx, p024).")
        else:
            st.caption("Columnas analizadas: " + ", ".join(text_cols))
            corpora = {}
            for col in text_cols:
                raw = view_df[col].astype(str)
                raw = raw[~raw.map(is_missing_text)]
                txt = raw.map(norm)
                txt = txt[txt.str.len() > 0]
                corpora[col] = txt

            st.markdown("### Frecuencias")
            n_top = st.slider("Top términos a mostrar", 10, 50, 20, key="txt_topn")

            def top_ngrams(series, n=1, top=20):
                series = series[series.str.len() > 0]
                if series.empty: return pd.DataFrame(columns=["término","frecuencia"])
                vect = CountVectorizer(ngram_range=(n,n), stop_words=list(stop_es), min_df=2)
                try:
                    X = vect.fit_transform(series)
                except ValueError:
                    return pd.DataFrame(columns=["término","frecuencia"])
                if X.shape[1] == 0:
                    return pd.DataFrame(columns=["término","frecuencia"])
                freqs = np.asarray(X.sum(axis=0)).ravel()
                vocab = np.array(vect.get_feature_names_out())
                order = freqs.argsort()[::-1][:top]
                return pd.DataFrame({"término": vocab[order], "frecuencia": freqs[order]})

            for col in text_cols:
                st.markdown(f"**{col}**")
                s = corpora[col]
                if s.empty:
                    st.info("Sin texto utilizable (vacíos o no-respuestas)."); continue
                c1,c2 = st.columns(2)
                with c1:
                    st.write("Unigramas (palabras)")
                    st.dataframe(top_ngrams(s, 1, n_top), use_container_width=True)
                with c2:
                    st.write("Bigramas (parejas de palabras)")
                    st.dataframe(top_ngrams(s, 2, n_top), use_container_width=True)

            st.markdown("### Nube de palabras")
            col_wc = st.selectbox("Selecciona columna para la nube", options=text_cols, index=0, key="sel_wc")
            txt_series = corpora.get(col_wc, pd.Series(dtype=str))
            txt_wc = " ".join(txt_series.tolist()).strip()
            if len(txt_wc) < 3:
                st.info("No hay texto suficiente para generar la nube.")
            else:
                try:
                    wc = WordCloud(width=1000, height=400, background_color="white",
                                   stopwords=stop_es, collocations=False).generate(txt_wc)
                    st.image(wc.to_array(), use_column_width=True)
                except Exception as e:
                    st.warning(f"No se pudo generar la nube: {e}")

# ---- MANUAL
# ---- MANUAL (robusto; sin use_container_width y con fallback de encoding)
with tabMANUAL:
    st.subheader("Manual de Usuario")

    DEFAULT_MD = """# Manual de Usuario – Dashboard
Este es un manual de respaldo. Para mostrar tu manual propio:
- crea un archivo **MANUAL.md** en la raíz del repo o en `data/MANUAL.md`,
- o usa `Manual_Usuario_Dashboard.md` (raíz o `data/`),
- o `Manual_Usuario_Dashboard-2.md` (raíz o `data/`),
- y realiza *Rerun/Reboot* en Streamlit.

## Contenido sugerido
1. Requisitos e instalación
2. Estructura del repo /data
3. Carga de datos y Codebook
4. Mapeo de variables y Filtros
5. Pestañas (B–G, Indicadores, Mapa GPS, Texto)
6. Exportación (Excel)
7. Solución de problemas
"""

    import pathlib

    def _read_text_safe(p: pathlib.Path) -> str:
        """Lee texto con fallback de encoding para evitar AttributeError durante render."""
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            # Fallback común para archivos guardados con ANSI/Windows-Latin
            return p.read_text(encoding="latin-1", errors="ignore")

    # Orden de búsqueda (incluye tu -2)
    candidates = [
        pathlib.Path("MANUAL.md"),
        pathlib.Path("data/MANUAL.md"),
        pathlib.Path("Manual_Usuario_Dashboard.md"),
        pathlib.Path("data/Manual_Usuario_Dashboard.md"),
        pathlib.Path("Manual_Usuario_Dashboard-2.md"),
        pathlib.Path("data/Manual_Usuario_Dashboard-2.md"),
    ]

    manual_path = next((p for p in candidates if p.exists()), None)

    if manual_path is None:
        md = DEFAULT_MD
        st.caption("Mostrando manual de respaldo (no se encontró un archivo de manual en el repositorio).")
        file_name = "MANUAL.md"
    else:
        try:
            md = _read_text_safe(manual_path)
            st.caption(f"Mostrando: `{manual_path}`")
        except Exception as e:
            # Si algo falla leyendo el archivo, mostramos respaldo para no romper la app
            st.warning(f"No se pudo leer el manual `{manual_path.name}` ({e}). Se mostrará el manual de respaldo.")
            md = DEFAULT_MD
        file_name = manual_path.name

    # Render seguro: si Markdown fallara por contenido extraño, mostramos en <textarea> como respaldo
    try:
        st.markdown(md, unsafe_allow_html=False)
    except Exception as e:
        st.error(f"No se pudo renderizar el manual como Markdown: {e}")
        st.text_area("Contenido del manual (vista de texto)", value=md, height=360)

    # Descarga: SIN use_container_width (para compatibilidad)
    st.download_button(
        label="⬇️ Descargar manual mostrado",
        data=md.encode("utf-8"),
        file_name=file_name,
        mime="text/markdown",
        key="dl_manual_btn"
    )



# ---- EXPORTAR
with tabEXPORT:
    st.subheader("Exportar anexos a Excel (según vista actual)")
    sheets = {}
    # B
    if p004!="<ninguna>": sheets["B_p004"] = vc_percent(view_df, p004, by=None)
    if p005!="<ninguna>": sheets["B_p005"] = vc_percent(view_df, p005, by=None)
    if p006!="<ninguna>": sheets["B_p006"] = vc_percent(view_df, p006, by=None)
    if p007!="<ninguna>": sheets["B_p007"] = vc_percent(view_df, p007, by=None)
    if p008!="<ninguna>": sheets["B_p008"] = vc_percent(view_df, p008, by=None)
    if p004!="<ninguna>" and p005!="<ninguna>": sheets["B_p004x_p005"] = crosstab_pct(view_df, p004, p005, by=None)
    for other, key in [(p006,"p005x_p006"),(p007,"p005x_p007"),(p008,"p005x_p008")]:
        if p005!="<ninguna>" and other!="<ninguna>":
            sheets[f"B_{key}"] = crosstab_pct(view_df, p005, other, by=None)
    for other, key in [(p006,"p004x_p006"),(p007,"p004x_p007"),(p008,"p004x_p008")]:
        if p004!="<ninguna>" and other!="<ninguna>":
            sheets[f"B_{key}"] = crosstab_pct(view_df, p004, other, by=None)

    if sheets:
        data = export_xlsx(sheets)
        st.download_button("⬇️ Descargar Anexo Estadístico (Excel)", data=data,
                           file_name="anexo_estadistico.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Configura mapeo de variables para habilitar la exportación.")
