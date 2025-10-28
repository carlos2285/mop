import os, io, re
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

# --------------------- Config & Estilos ---------------------
st.set_page_config(page_title="Plan de Tabulados — Encuesta", layout="wide")

st.markdown("""
<style>
/* Tabs con espacio y wrap */
.stTabs [data-baseweb="tab-list"]{
  gap: .75rem;
  flex-wrap: wrap;
}
.stTabs [data-baseweb="tab"]{
  padding: 8px 14px;
  border-radius: 10px;
  background: rgba(255,255,255,.05);
  color: #ddd;
}
.stTabs [aria-selected="true"]{
  background: rgba(255,255,255,.14);
  color: #fff;
  font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# --------------------- Constantes / Helpers ---------------------
MISSING_LABELS = {
    "", "(Sin dato)", "No contestó", "No contesto", "No respondió", "No responde",
    "No sabe/No responde", "NS/NR", "Ns/Nr", "NSNR", "No aplica", "NA", "N/A",
    "Sin respuesta", "NR", "nan", "NaN"
}

def _is_missing_label(x) -> bool:
    return str(x).strip() in MISSING_LABELS

def clean_label(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip()
    rep = {"√≠":"í","√≥":"ó","√±":"ñ","√©":"é","√í":"á","√∫":"ú","###":""}
    for k, v in rep.items():
        s = s.replace(k, v)
    return s

def _make_unique_columns(cols):
    seen, out = {}, []
    for c in cols:
        c = str(c)
        if c not in seen:
            seen[c] = 1
            out.append(c)
        else:
            seen[c] += 1
            out.append(f"{c} ({seen[c]})")
    return out

def _cat_series(s: pd.Series) -> pd.Series:
    """Etiquetas como texto; NaN -> '(Sin dato)' (solo para mostrar)."""
    s = s.astype("object")
    s = s.where(s.notna(), "(Sin dato)")
    s = s.replace({"nan": "(Sin dato)", "NaN": "(Sin dato)"})
    return s.astype(str)

def vc_percent(df: pd.DataFrame, col: str, by: str | None = None) -> pd.DataFrame:
    if by:
        tmp = pd.DataFrame({by: _cat_series(df[by]), col: _cat_series(df[col])})
        tmp = tmp[~tmp[col].isin(MISSING_LABELS)]
        if tmp.empty:
            return pd.DataFrame(columns=[by, col, "n", "%"])
        t = tmp.groupby([by, col], dropna=False).size().rename("n").reset_index()
        t["%"] = t.groupby(by)["n"].transform(lambda s: (s / s.sum() * 100).round(1))
        return t
    else:
        s = _cat_series(df[col])
        s = s[~s.isin(MISSING_LABELS)]
        if s.empty:
            return pd.DataFrame(columns=[col, "n", "%"])
        t = s.value_counts(dropna=False).rename_axis(col).reset_index(name="n")
        total = t["n"].sum()
        t["%"] = (t["n"] / total * 100).round(1) if total else 0
        return t

def crosstab_pct(df: pd.DataFrame, r: str, c: str, by: str | None = None) -> pd.DataFrame:
    def _prep(x): return _cat_series(x)
    def _one(sub):
        rr, cc = _prep(sub[r]), _prep(sub[c])
        mask = (~rr.isin(MISSING_LABELS)) & (~cc.isin(MISSING_LABELS))
        rr, cc = rr[mask], cc[mask]
        if rr.empty or cc.empty:
            return pd.DataFrame()
        tab = pd.crosstab(rr, cc, dropna=False)
        tab.columns = tab.columns.astype(str)
        tab["n_fila"] = tab.sum(axis=1)
        pct = (tab.div(tab["n_fila"].replace(0, np.nan), axis=0) * 100).round(1)
        tab = tab.drop(columns=["n_fila"])
        tab["__tipo__"] = "n"
        pct["__tipo__"] = "%"
        return pd.concat(
            [tab.reset_index().rename(columns={"index": r}),
             pct.reset_index().rename(columns={"index": r})],
            ignore_index=True
        )

    if by:
        out = []
        for g, sub in df.groupby(by):
            t = _one(sub)
            if not t.empty:
                t["__grupo__"] = str(g)
                out.append(t)
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    return _one(df)

def export_xlsx(sheets_dict: dict) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet, data in sheets_dict.items():
            if isinstance(data, dict):
                startrow = 0
                for _, subdf in data.items():
                    subdf.to_excel(writer, index=False, sheet_name=sheet, startrow=startrow)
                    startrow += len(subdf) + 3
            else:
                data.to_excel(writer, index=False, sheet_name=sheet)
    return output.getvalue()

# --------------------- Data load ---------------------
st.sidebar.title("⚙️ Datos")
uploaded = st.sidebar.file_uploader("Sube CSV/Excel (opcional)", type=["csv","xlsx"])

DATA_PATH_XLSX = "data/respuestas.xlsx"
DATA_PATH_CSV  = "data/respuestas.csv"
CODEBOOK_PATH  = "data/Codebook.xlsx"  # opcional

if uploaded is None:
    if os.path.exists(DATA_PATH_XLSX):
        df = pd.read_excel(DATA_PATH_XLSX, engine="openpyxl")
    elif os.path.exists(DATA_PATH_CSV):
        df = pd.read_csv(DATA_PATH_CSV)
    else:
        st.error("No se encontró data/respuestas.xlsx ni data/respuestas.csv.")
        st.stop()
else:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded, engine="openpyxl")

# Limpieza general de encabezados
df = df.rename(columns={c: clean_label(c) for c in df.columns})
df.columns = _make_unique_columns(df.columns)

# --------------------- Mapeo Variables ---------------------
st.sidebar.header("🧭 Mapeo de variables")

def pick(label, candidates):
    options = ["<ninguna>"] + list(df.columns)
    default = 0
    for cand in candidates:
        for i, col in enumerate(options):
            if col.lower() == cand.lower():
                default = i; break
        if default: break
    return st.sidebar.selectbox(label, options=options, index=default)

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
lat_col = pick("LATITUD (GPS)", ["lat","latitude","y","gps_lat","Latitud","p002__Latitude"])
lon_col = pick("LONGITUD (GPS)", ["lon","longitude","x","lng","long","gps_lon","Longitud","p002__Longitude"])
# Abiertas
p040 = pick("p040 (abierta)", ["p040"])
p041 = pick("p041 (abierta)", ["p041"])
p38tx = pick("p38tx (abierta)", ["p38tx","p038tx","p38"])
p024  = pick("p024 (abierta)",  ["p024"])

# --------------------- Filtros ---------------------
st.sidebar.header("Filtros")
work = df.copy()
if sector != "<ninguna>":
    vals = sorted([v for v in work[sector].dropna().unique()])
    sel = st.sidebar.multiselect("Sector", options=vals, default=vals)
    mask = work[sector].isin(sel) if sel else (work.index == -1)
    work = work[mask]

# Helpers para subsets por uso
def is_vivienda_or_mixto(v):
    s = str(v or "").strip().lower()
    return ("vivienda" in s) or ("mixto" in s) or ("vivienda–negocio" in s) or ("vivienda-negocio" in s)

def is_negocio_or_mixto(v):
    s = str(v or "").strip().lower()
    return ("negocio" in s) or ("mixto" in s) or ("vivienda–negocio" in s) or ("vivienda-negocio" in s)

# --------------------- UI ---------------------
st.title("📊 Plan de Tabulados y Cruces — Anexo Estadístico")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Observaciones", f"{len(work):,}")
c2.metric("Sectores", int(work[sector].nunique()) if sector != "<ninguna>" else "—")
with np.errstate(all='ignore'):
    c3.metric("Tamaño hogar (media)", f"{pd.to_numeric(work[p011], errors='coerce').mean():.1f}" if p011 != "<ninguna>" else "—")
with np.errstate(all='ignore'):
    c4.metric("Trabajadores (media)", f"{pd.to_numeric(work[p029], errors='coerce').mean():.1f}" if p029 != "<ninguna>" else "—")
st.markdown("---")

tabB, tabC, tabD, tabE, tabF, tabG, tabI, tabMAP, tabTXT, tabMANUAL, tabEXPORT = st.tabs([
    "B — Estructura", "C — Hogares", "D — Socioeconómico", "E — Servicios",
    "F — Negocios", "G — Espacios/Percepción", "I — Indicadores",
    "Mapa GPS", "Texto (abiertas)", "Manual", "Exportar"
])

# --------------------- BLOQUE B ---------------------
with tabB:
    st.subheader("BLOQUE B – Características físicas de la estructura")
    st.markdown("**Tabulados simples**")
    for col, label in [
        (p004, "Uso de estructura (p004)"), (p005, "Estado físico (p005)"),
        (p006, "Material del techo (p006)"), (p007, "Material de las paredes (p007)"),
        (p008, "Material del piso (p008)")
    ]:
        if col != "<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(vc_percent(work, col, by=sector if sector != "<ninguna>" else None), use_container_width=True)

    st.markdown("**Cruces clave**")
    if p004 != "<ninguna>" and p005 != "<ninguna>":
        st.markdown("**p004 × p005 — Estado físico por uso de estructura**")
        st.dataframe(crosstab_pct(work, p004, p005, by=sector if sector != "<ninguna>" else None), use_container_width=True)
    for other, label in [(p006, "Material techo"), (p007, "Material paredes"), (p008, "Material piso")]:
        if p005 != "<ninguna>" and other != "<ninguna>":
            st.markdown(f"**p005 × {label}**")
            st.dataframe(crosstab_pct(work, p005, other, by=sector if sector != "<ninguna>" else None), use_container_width=True)
    for other, label in [(p006, "Material techo"), (p007, "Material paredes"), (p008, "Material piso")]:
        if p004 != "<ninguna>" and other != "<ninguna>":
            st.markdown(f"**p004 × {label}**")
            st.dataframe(crosstab_pct(work, p004, other, by=sector if sector != "<ninguna>" else None), use_container_width=True)

# --------------------- BLOQUE C ---------------------
with tabC:
    st.subheader("BLOQUE C – Hogares (p004 = vivienda o mixto)")
    sub = work.copy()
    if p004 != "<ninguna>":
        sub = sub[[is_vivienda_or_mixto(v) for v in sub[p004]]]

    st.markdown("**Tabulados numéricos**")
    for col, label in [(nviv, "Nº de hogares (nvivienda)"), (p009a, "Nº de espacios habitables (p009a)"), (p009b, "Nº de niveles (p009b)")]:
        if col != "<ninguna>":
            x = pd.to_numeric(sub[col], errors='coerce')
            desc = x.describe()[["count", "mean", "50%", "min", "max"]].rename({"50%": "median"})
            st.markdown(f"**{label} — media/mediana/min/max**")
            st.write(desc.to_frame().T)

    for col, label in [(p010, "Tenencia del inmueble (p010)"), (sexoj, "Sexo jefatura"), (p011, "Tamaño del hogar (p011) desagregado")]:
        if col != "<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(vc_percent(sub, col, by=sector if sector != "<ninguna>" else None), use_container_width=True)

    comp_cols = [(sexom, "Mujeres adultas"), (sexoh, "Hombres adultos"), (sexonh, "Niños"), (sexonm, "Niñas")]
    comp_available = [(c, lbl) for c, lbl in comp_cols if c != "<ninguna>"]
    if comp_available:
        st.markdown("**Componentes del hogar (conteos)**")
        table = pd.DataFrame({lbl: pd.to_numeric(sub[c], errors='coerce').sum() for c, lbl in comp_available}, index=["Total"])
        st.dataframe(table, use_container_width=True)

    st.markdown("**Cruces clave**")
    cr_pairs = [
        (sexoj, p010, "Sexo jefatura × Tenencia (p010)"),
        (sexoj, p015, "Sexo jefatura × Servicios básicos (p015)"),
        (sexoj, p005, "Sexo jefatura × Estado físico (p005)"),
        (sexoj, p014, "Sexo jefatura × Fuente de ingreso (p014)"),
        (sexoj, p011, "Sexo jefatura × Tamaño del hogar (p011)"),
        (p010, p015, "Tenencia × Servicios básicos"),
        (p010, p005, "Tenencia × Estado físico"),
    ]
    for r, c, label in cr_pairs:
        if r != "<ninguna>" and c != "<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(crosstab_pct(sub, r, c, by=sector if sector != "<ninguna>" else None), use_container_width=True)

# --------------------- BLOQUE D ---------------------
with tabD:
    st.subheader("BLOQUE D – Situación socioeconómica (p004 = vivienda o mixto)")
    sub = work.copy()
    if p004 != "<ninguna>":
        sub = sub[[is_vivienda_or_mixto(v) for v in sub[p004]]]

    for col, label in [(p012, "Año de residencia (p012)"), (p013, "Nº de personas con ingresos (p013)")]:
        if col != "<ninguna>":
            x = pd.to_numeric(sub[col], errors='coerce')
            desc = x.describe()[["count","mean","50%","min","max"]].rename({"50%":"median"})
            st.markdown(f"**{label} — media/mediana/min/max**")
            st.write(desc.to_frame().T)

    for col, label in [(p014, "Fuente principal de ingreso (p014)"), (p022, "Activos del hogar (p022)")]:
        if col != "<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(vc_percent(sub, col, by=sector if sector != "<ninguna>" else None), use_container_width=True)

    st.markdown("**Cruces clave**")
    pairs = [
        (p014, sexoj, "Fuente de ingreso × Sexo jefatura"),
        (p013, p011, "Nº personas con ingresos × Tamaño del hogar"),
        (p022, p010, "Activos × Tenencia"),
        (p022, p015, "Activos × Servicios básicos"),
    ]
    for r, c, label in pairs:
        if r != "<ninguna>" and c != "<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(crosstab_pct(sub, r, c, by=sector if sector != "<ninguna>" else None), use_container_width=True)

# --------------------- BLOQUE E ---------------------
with tabE:
    st.subheader("BLOQUE E – Acceso a servicios y saneamiento (p004 = vivienda o mixto)")
    sub = work.copy()
    if p004 != "<ninguna>":
        sub = sub[[is_vivienda_or_mixto(v) for v in sub[p004]]]

    for col, label in [
        (p015,"Servicios básicos (p015)"), (p016,"Frecuencia acceso agua (p016)"),
        (p017,"Fuente de agua (p017)"), (p018,"Tipo de sanitario (p018)"),
        (p019,"Uso sanitario (p019)"), (p020,"Eliminación aguas grises (p020)"),
        (p021,"Eliminación basura (p021)")
    ]:
        if col != "<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(vc_percent(sub, col, by=sector if sector != "<ninguna>" else None), use_container_width=True)

    st.markdown("**Cruces clave**")
    for r, c, label in [
        (p015, p010, "Servicios básicos × Tenencia"),
        (p015, sexoj, "Servicios básicos × Sexo jefatura"),
        (p015, p005, "Servicios básicos × Estado físico"),
        (p016, p017, "Frecuencia acceso agua × Fuente de agua"),
        (p018, p019, "Tipo sanitario × Uso sanitario"),
        (p020, p021, "Eliminación aguas grises × Eliminación basura"),
    ]:
        if r != "<ninguna>" and c != "<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(crosstab_pct(sub, r, c, by=sector if sector != "<ninguna>" else None), use_container_width=True)

# --------------------- BLOQUE F ---------------------
with tabF:
    st.subheader("BLOQUE F – Negocios (p004 = negocio o mixto)")
    sub = work.copy()
    if p004 != "<ninguna>":
        sub = sub[[is_negocio_or_mixto(v) for v in sub[p004]]]

    for col, label in [
        (p025,"Actividad principal (p025)"), (p026,"Tiempo de operación (p026)"),
        (p027,"Permisos de operación (p027)"), (p028,"Tenencia local (p028)"),
        (p029,"Nº trabajadores (p029)"), (p030,"Nº empleados formales (p030)"),
        (p031,"Ingreso mensual empleados (p031)"), (p032,"Activos negocio (p032)")
    ]:
        if col != "<ninguna>":
            if col in [p026, p029, p030, p031]:
                x = pd.to_numeric(sub[col], errors='coerce')
                desc = x.describe()[["count","mean","50%","min","max"]].rename({"50%":"median"})
                st.markdown(f"**{label} — media/mediana/min/max**")
                st.write(desc.to_frame().T)
            else:
                st.markdown(f"**{label}**")
                st.dataframe(vc_percent(sub, col, by=sector if sector != "<ninguna>" else None), use_container_width=True)

    st.markdown("**Cruces clave**")
    for r, c, label in [
        (p025, p027, "Actividad × Permisos"),
        (p027, p028, "Permisos × Tenencia local"),
        (p030, p029, "Nº formales × Total trabajadores"),
        (p026, p027, "Tiempo de operación × Permisos"),
        (p031, p027, "Ingreso mensual × Permisos"),
    ]:
        if r != "<ninguna>" and c != "<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(crosstab_pct(sub, r, c, by=sector if sector != "<ninguna>" else None), use_container_width=True)

# --------------------- BLOQUE G ---------------------
with tabG:
    st.subheader("BLOQUE G – Espacios públicos y percepción (todos los registros)")
    for col, label in [(p036,"Percepción de seguridad (p036)"),
                       (p035,"Condiciones del espacio (p035)"),
                       (p035tx,"Problemas identificados (p035tx)")]:
        if col != "<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(vc_percent(work, col, by=sector if sector != "<ninguna>" else None), use_container_width=True)

    st.markdown("**Cruces clave**")
    for r, c, label in [
        (p036, p004, "Percepción seguridad × Uso de estructura"),
        (p036, sexoj, "Percepción seguridad × Sexo jefatura"),
        (p035, p035tx, "Condiciones del espacio × Problemas identificados"),
    ]:
        if r != "<ninguna>" and c != "<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(crosstab_pct(work, r, c, by=sector if sector != "<ninguna>" else None), use_container_width=True)

# --------------------- INDICADORES ---------------------
with tabI:
    st.subheader("BLOQUE I – Indicadores (resumen)")
    ind = {}
    base = work.copy()
    if p005 != "<ninguna>":
        s = base[p005].astype(str).str.lower()
        ind["% estructuras en mal estado"] = (s.str.contains("malo|mal")).mean() * 100 if len(s) else np.nan
    if sexoj != "<ninguna>":
        s = base[sexoj].astype(str).str.lower()
        ind["% hogares con jefatura femenina"] = (s.str.contains("mujer|femen")).mean() * 100 if len(s) else np.nan
    if p010 != "<ninguna>":
        s = base[p010].astype(str).str.lower()
        ind["% tenencia precaria"] = (s.str.contains("prest|invad|alquil.*sin|sin.*titul")).mean() * 100 if len(s) else np.nan
    if p015 != "<ninguna>":
        s = base[p015].astype(str).str.lower()
        ind["% hogares sin agua potable"] = (~(s.str.contains("agua|acued"))).mean() * 100 if len(s) else np.nan
    if p018 != "<ninguna>":
        s = base[p018].astype(str).str.lower()
        ind["% saneamiento inadecuado"] = (s.str.contains("letrin|ninguno|compart")).mean() * 100 if len(s) else np.nan
    if p027 != "<ninguna>":
        s = base[p027].astype(str).str.lower()
        ind["% negocios sin permisos"] = (s.str.contains("no|ninguno")).mean() * 100 if len(s) else np.nan
    if p022 != "<ninguna>":
        ind["Promedio activos por hogar"] = pd.to_numeric(base[p022], errors='coerce').mean()
    if p032 != "<ninguna>":
        ind["Promedio activos por negocio"] = pd.to_numeric(base[p032], errors='coerce').mean()
    if p030 != "<ninguna>" and p029 != "<ninguna>":
        num = pd.to_numeric(base[p030], errors='coerce')
        den = pd.to_numeric(base[p029], errors='coerce').replace(0, np.nan)
        ind["% negocios con personal formalizado"] = (num / den).mean() * 100 if den.notna().any() else np.nan
    st.dataframe(pd.DataFrame({"Indicador": list(ind.keys()), "Valor": list(ind.values())}), use_container_width=True)
    st.caption("Heurísticos; ajusta reglas a tu codificación si lo necesitas.")

# --------------------- MAPA ---------------------
with tabMAP:
    st.subheader("Mapa de coordenadas GPS")
    if lat_col != "<ninguna>" and lon_col != "<ninguna>":
        m = work.copy()
        m["_lat"] = pd.to_numeric(m[lat_col], errors="coerce")
        m["_lon"] = pd.to_numeric(m[lon_col], errors="coerce")

        # Autocorrección de escala si vienen en microgrados (muy grandes en valor absoluto)
        def fix_scale(s: pd.Series, is_lon=False):
            s2 = s.copy()
            # si la mediana está fuera de rango típico, intentamos dividir
            med = np.nanmedian(s2)
            if np.isfinite(med):
                if abs(med) > 10000:        # ej. -893155664
                    s2 = s2 / 1e7
                elif abs(med) > 1000:
                    s2 = s2 / 1e6
            return s2

        m["_lat"] = fix_scale(m["_lat"])
        m["_lon"] = fix_scale(m["_lon"], is_lon=True)

        m = m.dropna(subset=["_lat", "_lon"])
        m = m[(m["_lat"].between(-90, 90)) & (m["_lon"].between(-180, 180))]

        if m.empty:
            st.info("No hay coordenadas válidas después de la limpieza.")
        else:
            map_df = m.rename(columns={"_lat": "lat", "_lon": "lon"})[["lat", "lon"]]
            st.map(map_df, use_container_width=True)
            st.caption(f"{len(map_df):,} puntos mostrados.")
    else:
        st.info("Selecciona las columnas de LATITUD y LONGITUD en la barra lateral.")

# --------------------- TEXTO (ABIERTAS) ---------------------
with tabTXT:
    st.subheader("Análisis de preguntas abiertas")
    activar_texto = st.toggle("Activar análisis de texto (abiertas)", value=False,
                              help="Activa para calcular frecuencias y nubes")

    if activar_texto:
        import nltk, re
        from sklearn.feature_extraction.text import CountVectorizer
        from wordcloud import WordCloud
        from unidecode import unidecode

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
            s = str(s).replace("\n", " ").lower()
            s = re.sub(r"\s+", " ", s).strip()
            return unidecode(s)

        text_cols = [c for c in [p040, p041, p38tx, p024] if c != "<ninguna>" and c in work.columns]
        if not text_cols:
            st.warning("Selecciona al menos una columna abierta en la barra lateral.")
        else:
            st.caption("Columnas analizadas: " + ", ".join(text_cols))

            corpora = {}
            for col in text_cols:
                raw = work[col].astype(str)
                raw = raw[~raw.map(is_missing_text)]
                txt = raw.map(norm)
                txt = txt[txt.str.len() > 0]
                corpora[col] = txt

            st.markdown("### Frecuencias")
            n_top = st.slider("Top términos a mostrar", 10, 50, 20, key="txt_topn_unique")

            def top_ngrams(series, n=1, top=20):
                series = series[series.str.len() > 0]
                if series.empty:
                    return pd.DataFrame(columns=["término","frecuencia"])
                vect = CountVectorizer(ngram_range=(n, n), stop_words=list(stop_es), min_df=2)
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
                    st.info("Sin texto utilizable (todo fue vacío o no-respuesta).")
                    continue
                c1, c2 = st.columns(2)
                with c1:
                    st.write("Unigramas (palabras)")
                    st.dataframe(top_ngrams(s, 1, n_top), use_container_width=True)
                with c2:
                    st.write("Bigramas (parejas de palabras)")
                    st.dataframe(top_ngrams(s, 2, n_top), use_container_width=True)

            st.markdown("### Nube de palabras")
            col_wc = st.selectbox("Selecciona columna para la nube", options=text_cols, index=0, key="sel_wc_unique")
            txt_series = corpora.get(col_wc, pd.Series(dtype=str))
            txt_wc = " ".join(txt_series.tolist()).strip()

            if len(txt_wc) < 3:
                st.info("No hay texto suficiente para generar la nube (se excluyeron vacíos / No contestó).")
            else:
                wc = WordCloud(width=1000, height=400, background_color="white",
                               stopwords=stop_es, collocations=False).generate(txt_wc)
                img = wc.to_array()
                st.image(img, use_column_width=True)

            st.markdown("### Codificación automática (diccionario)")
            sample_dict = """salud: clinica|hospital|medico|enfermera|centro de salud|farmacia
seguridad: robo|asalto|pandilla|violencia|iluminacion|policia
vialidad: calle|bache|pavimento|trafico|semaforo|pasarela
agua: agua|tuberia|acueducto|pozo|lluvia
residuos: basura|desecho|aseo|relleno|recoleccion|reciclaje
otro: otro|varios|misc"""
            dict_text = st.text_area("Diccionario (categoria: palabra1|palabra2|...)", value=sample_dict, height=150, key="dict_text_unique")

            rules = []
            for line in dict_text.splitlines():
                if ":" in line:
                    cat, kw = line.split(":", 1)
                    cat = cat.strip()
                    kws = [w.strip() for w in kw.split("|") if w.strip()]
                    if cat and kws: rules.append((cat, kws))

            col_to_code = st.selectbox("Columna a codificar", options=text_cols, index=0, key="sel_code_col_unique")

            def auto_code(text):
                t = norm(text)
                for cat, kws in rules:
                    for w in kws:
                        if w and re.search(rf"\b{re.escape(unidecode(w.lower()))}\b", t):
                            return cat
                return "No clasificado"

            if st.button("Aplicar codificación", use_container_width=True, key="btn_code_unique"):
                coded = work[[col_to_code]].copy()
                coded["categoria_auto"] = work[col_to_code].apply(auto_code)
                st.success("Codificación aplicada.")
                st.dataframe(coded.head(50), use_container_width=True)

                resumen = coded["categoria_auto"].value_counts(dropna=False).rename_axis("categoria").reset_index(name="n")
                total = resumen["n"].sum()
                resumen["%"] = (resumen["n"]/total*100).round(1) if total else 0
                st.markdown("**Resumen de categorías (auto)**")
                st.dataframe(resumen, use_container_width=True)

                st.download_button(
                    "⬇️ Descargar codificación (CSV)",
                    data=coded.to_csv(index=False).encode("utf-8"),
                    file_name=f"codificacion_{col_to_code}.csv",
                    mime="text/csv"
                )
    else:
        st.info("Activa el switch para calcular frecuencias, nube y codificación.")

# --------------------- MANUAL ---------------------
with tabMANUAL:
    st.subheader("Manual de Usuario")
    DEFAULT_MD = """# Manual de Usuario – Dashboard
Este es un manual de respaldo. Para mostrar tu manual propio:
- crea un archivo **MANUAL.md** en la raíz del repo **o** en `data/MANUAL.md`,
- o usa **Manual_Usuario_Dashboard.md** (raíz o `data/`).
- Haz *Rerun/Reboot* en Streamlit.
"""
    import pathlib
    candidates = [
        pathlib.Path("MANUAL.md"),
        pathlib.Path("data/MANUAL.md"),
        pathlib.Path("Manual_Usuario_Dashboard.md"),
        pathlib.Path("data/Manual_Usuario_Dashboard.md"),
    ]
    manual_path = next((p for p in candidates if p.exists()), None)
    if manual_path is not None:
        md = manual_path.read_text(encoding="utf-8", errors="ignore")
        source = f"Mostrando: `{manual_path}`"
    else:
        md = DEFAULT_MD
        source = "Mostrando manual de respaldo (no se encontró MANUAL.md)."
    st.caption(source)
    st.markdown(md, unsafe_allow_html=False)
    st.download_button("⬇️ Descargar manual mostrado", data=md.encode("utf-8"),
                       file_name=(manual_path.name if manual_path else "MANUAL.md"),
                       mime="text/markdown", use_container_width=True)

# --------------------- EXPORTAR ---------------------
with tabEXPORT:
    st.subheader("Exportar anexos a Excel (tabulados y cruces)")
    sheets = {}
    if p004!="<ninguna>": sheets["B_p004"] = vc_percent(work, p004, by=sector if sector!='<ninguna>' else None)
    if p005!="<ninguna>": sheets["B_p005"] = vc_percent(work, p005, by=sector if sector!='<ninguna>' else None)
    if p006!="<ninguna>": sheets["B_p006"] = vc_percent(work, p006, by=sector if sector!='<ninguna>' else None)
    if p007!="<ninguna>": sheets["B_p007"] = vc_percent(work, p007, by=sector if sector!='<ninguna>' else None)
    if p008!="<ninguna>": sheets["B_p008"] = vc_percent(work, p008, by=sector if sector!='<ninguna>' else None)
    if p004!="<ninguna>" and p005!="<ninguna>": sheets["B_p004x_p005"] = crosstab_pct(work, p004, p005, by=sector if sector!='<ninguna>' else None)
    for other, key in [(p006,"p005x_p006"),(p007,"p005x_p007"),(p008,"p005x_p008")]:
        if p005!="<ninguna>" and other!="<ninguna>": sheets[f"B_{key}"] = crosstab_pct(work, p005, other, by=sector if sector!='<ninguna>' else None)
    for other, key in [(p006,"p004x_p006"),(p007,"p004x_p007"),(p008,"p004x_p008")]:
        if p004!="<ninguna>" and other!="<ninguna>": sheets[f"B_{key}"] = crosstab_pct(work, p004, other, by=sector if sector!='<ninguna>' else None)

    # (También agregas aquí C, D, E, F, G si lo deseas como en tu versión anterior)

    if sheets:
        st.download_button("⬇️ Descargar Anexo Estadístico (Excel)",
                           data=export_xlsx(sheets),
                           file_name="anexo_estadistico.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Configura el mapeo de variables para habilitar la exportación.")
