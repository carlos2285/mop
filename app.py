import os, re, io
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Plan de Tabulados — Encuesta", layout="wide")

# -------- Helpers --------
def clean_label(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip()
    rep = {"√≠":"í","√≥":"ó","√±":"ñ","√©":"é","√í":"á","√∫":"ú","###":""}
    for k,v in rep.items():
        s = s.replace(k,v)
    return s

def _make_unique_columns(cols):
    seen = {}
    new_cols = []
    for c in cols:
        base = str(c)
        if base not in seen:
            seen[base] = 1
            new_cols.append(base)
        else:
            seen[base] += 1
            new_cols.append(f"{base} ({seen[base]})")
    return new_cols

def vc_percent(df, col, by=None):
    # Reemplaza NaN por texto y fuerza str (para que JSON no reciba NaN)
    def cat(s):
        return s.astype("object").where(s.notna(), "(Sin dato)").astype(str)

    if by is not None:
        tmp = pd.DataFrame({by: cat(df[by]), col: cat(df[col])})
        t = tmp.groupby([by, col], dropna=False).size().rename("n").reset_index()
        t["%"] = t.groupby(by)["n"].transform(lambda s: (s/s.sum()*100).round(1))
        return t
    else:
        s = cat(df[col])
        t = s.value_counts(dropna=False).rename_axis(col).reset_index(name="n")
        total = t["n"].sum()
        t["%"] = (t["n"]/total*100).round(1) if total else 0
        return t


def crosstab_pct(df, r, c, by=None):
    # Reemplaza NaN por "(Sin dato)" y fuerza str
    def cat(s):
        return s.astype("object").where(s.notna(), "(Sin dato)").astype(str)

    if by is not None:
        out = []
        for g, sub in df.groupby(by):
            rr = cat(sub[r]); cc = cat(sub[c])
            tab = pd.crosstab(rr, cc, dropna=False)
            tab.columns = tab.columns.astype(str)  # evita NaN como nombre de columna
            tab["n_fila"] = tab.sum(axis=1)

            pct = tab.div(tab["n_fila"].replace(0, np.nan), axis=0)*100
            pct = pct.round(1)

            tab = tab.drop(columns=["n_fila"])
            tab["__grupo__"] = str(g)
            tab["__tipo__"] = "n"
            pct["__grupo__"] = str(g)
            pct["__tipo__"] = "%"

            out.append(tab.reset_index().rename(columns={"index": r}))
            out.append(pct.reset_index().rename(columns={"index": r}))
        return pd.concat(out, ignore_index=True)
    else:
        rr = cat(df[r]); cc = cat(df[c])
        tab = pd.crosstab(rr, cc, dropna=False)
        tab.columns = tab.columns.astype(str)
        tab["n_fila"] = tab.sum(axis=1)

        pct = tab.div(tab["n_fila"].replace(0, np.nan), axis=0)*100
        pct = pct.round(1)

        tab = tab.drop(columns=["n_fila"])
        tab["__tipo__"] = "n"
        pct["__tipo__"] = "%"

        return pd.concat(
            [
                tab.reset_index().rename(columns={"index": r}),
                pct.reset_index().rename(columns={"index": r}),
            ],
            ignore_index=True,
        )


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

# -------- Data load (fixed /data + engine=openpyxl) --------
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

# -------- Variable mapper --------
st.sidebar.header("🧭 Mapeo de variables")
def pick(label, default_candidates):
    options = ["<ninguna>"] + list(df.columns)
    default = 0
    for cand in default_candidates:
        for i, col in enumerate(options):
            if col.lower() == cand.lower():
                default = i; break
        if default: break
    return st.sidebar.selectbox(label, options=options, index=default)

sector = pick("SECTOR", ["sector","zona","bloque"])

# Bloque B
p004 = pick("p004 Uso de estructura", ["p004","Uso de la estructura"])
p005 = pick("p005 Estado físico", ["p005"])
p006 = pick("p006 Material techo", ["p006","Material del techo"])
p007 = pick("p007 Material paredes", ["p007","Material de las paredes"])
p008 = pick("p008 Material piso", ["p008","Material del piso"])

# Bloque C
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

# Bloque D
p012 = pick("p012 Años de residencia", ["p012","yearsresidencia","años residencia"])
p013 = pick("p013 Personas con ingresos", ["p013","personas con ingresos"])
p014 = pick("p014 Fuente principal de ingreso", ["p014","fuente principal de ingresos","Fuente principal de ingreso"])
p022 = pick("p022 Activos del hogar", ["p022","activos hogar"])

# Bloque E
p015 = pick("p015 Servicios básicos", ["p015","Servicios básicos disponibles","Servicio: Agua"])
p016 = pick("p016 Frecuencia agua", ["p016","Frecuencia acceso agua"])
p017 = pick("p017 Fuente de agua", ["p017","Fuente de agua"])
p018 = pick("p018 Tipo sanitario", ["p018","Tipo de sanitario"])
p019 = pick("p019 Uso sanitario", ["p019","Uso sanitario"])
p020 = pick("p020 Aguas grises", ["p020","Eliminación aguas grises"])
p021 = pick("p021 Basura", ["p021","Eliminación basura"])

# Bloque F
p025 = pick("p025 Actividad negocio", ["p025","Actividad principal"])
p026 = pick("p026 Tiempo operación", ["p026","Tiempo de operación"])
p027 = pick("p027 Permisos", ["p027","Permisos de operación"])
p028 = pick("p028 Tenencia local", ["p028","Tenencia local"])
p029 = pick("p029 Nº trabajadores", ["p029","Nº trabajadores"])
p030 = pick("p030 Nº formales", ["p030","Nº empleados formales"])
p031 = pick("p031 Ingreso mensual", ["p031","Ingreso mensual empleados"])
p032 = pick("p032 Activos negocio", ["p032","Activos negocio"])

# Bloque G
p035 = pick("p035 Condiciones del espacio", ["p035","Condiciones del espacio"])
p035tx = pick("p035tx Problemas (texto/cod)", ["p035tx","Problemas identificados"])
p036 = pick("p036 Percepción seguridad", ["p036","Percepción de seguridad"])
# --- GPS ---
lat_col = pick("LATITUD (GPS)", ["lat","latitude","y","gps_lat","Latitud"])
lon_col = pick("LONGITUD (GPS)", ["lon","longitude","x","lng","long","gps_lon","Longitud"])


# -------- Filtros --------
st.sidebar.header("Filtros")
work = df.copy()
if sector != "<ninguna>":
    vals = sorted([v for v in work[sector].dropna().unique()])
    sel = st.sidebar.multiselect("Sector", options=vals, default=vals)
    if sel: work = work[sector].isin(sel)
    else: work = df.index == -1
work = df[work] if isinstance(work, pd.Series) else df

def is_vivienda_or_mixto(v):
    if v is None: return False
    s = str(v).strip().lower()
    return ("vivienda" in s) or ("mixto" in s) or ("vivienda–negocio" in s) or ("vivienda-negocio" in s)

def is_negocio_or_mixto(v):
    if v is None: return False
    s = str(v).strip().lower()
    return ("negocio" in s) or ("mixto" in s) or ("vivienda–negocio" in s) or ("vivienda-negocio" in s)

# -------- Header & KPIs --------
st.title("📊 Plan de Tabulados y Cruces — Anexo Estadístico")
c1,c2,c3,c4 = st.columns(4)
c1.metric("Observaciones", f"{len(work):,}")
if sector != "<ninguna>":
    c2.metric("Sectores", int(work[sector].nunique()))
else:
    c2.metric("Sectores", "—")
if p011 != "<ninguna>":
    with np.errstate(all='ignore'):
        c3.metric("Tamaño hogar (media)", f"{pd.to_numeric(work[p011], errors='coerce').mean():.1f}")
else:
    c3.metric("Tamaño hogar (media)", "—")
if p029 != "<ninguna>":
    with np.errstate(all='ignore'):
        c4.metric("Trabajadores (media)", f"{pd.to_numeric(work[p029], errors='coerce').mean():.1f}")
else:
    c4.metric("Trabajadores (media)", "—")

st.markdown("---")

tabB, tabC, tabD, tabE, tabF, tabG, tabI, tabMAP, tabEXPORT = st.tabs([
    "B — Estructura", "C — Hogares", "D — Socioeconómico", "E — Servicios",
    "F — Negocios", "G — Espacios/Percepción", "I — Indicadores", "Mapa GPS", "Exportar"
])


with tabB:
    st.subheader("BLOQUE B – Características físicas de la estructura")
    st.markdown("**Tabulados simples**")
    cols_simple = [(p004, "Uso de estructura (p004)"), (p005, "Estado físico (p005)"),
                   (p006, "Material del techo (p006)"), (p007, "Material de las paredes (p007)"), (p008, "Material del piso (p008)")]
    for col, label in cols_simple:
        if col != "<ninguna>":
            st.markdown(f"**{label}**")
            t = vc_percent(work, col, by=sector if sector != '<ninguna>' else None)
            st.dataframe(t, use_container_width=True)

    st.markdown("**Cruces clave**")
    if p004 != "<ninguna>" and p005 != "<ninguna>":
        st.markdown("**p004 × p005 — Estado físico por uso de estructura**")
        st.dataframe(crosstab_pct(work, p004, p005, by=sector if sector!='<ninguna>' else None), use_container_width=True)
    for other, label in [(p006,"Material techo"), (p007,"Material paredes"), (p008,"Material piso")]:
        if p005 != "<ninguna>" and other != "<ninguna>":
            st.markdown(f"**p005 × {label}**")
            st.dataframe(crosstab_pct(work, p005, other, by=sector if sector!='<ninguna>' else None), use_container_width=True)
    for other, label in [(p006,"Material techo"), (p007,"Material paredes"), (p008,"Material piso")]:
        if p004 != "<ninguna>" and other != "<ninguna>":
            st.markdown(f"**p004 × {label}**")
            st.dataframe(crosstab_pct(work, p004, other, by=sector if sector!='<ninguna>' else None), use_container_width=True)

with tabC:
    st.subheader("BLOQUE C – Hogares dentro de la estructura (p004 = vivienda o mixto)")
    sub = work.copy()
    if p004 != "<ninguna>":
        sub = sub[[True if is_vivienda_or_mixto(v) else False for v in sub[p004]]]
    st.markdown("**Tabulados simples**")
    for col, label in [(nviv,"Nº de hogares (nvivienda)"),
                       (p009a,"Nº de espacios habitables (p009a)"),
                       (p009b,"Nº de niveles (p009b)")]:
        if col != "<ninguna>":
            x = pd.to_numeric(sub[col], errors='coerce')
            desc = x.describe()[["count","mean","50%","min","max"]].rename({"50%":"median"})
            st.markdown(f"**{label} — media/mediana/min/max**")
            st.write(desc.to_frame().T)
    for col, label in [(p010,"Tenencia del inmueble (p010)"),
                       (sexoj,"Sexo jefatura"),
                       (p011,"Tamaño del hogar (p011) desagregado")]:
        if col != "<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(vc_percent(sub, col, by=sector if sector!='<ninguna>' else None), use_container_width=True)

    comp_cols = [(sexom,"Mujeres adultas"),(sexoh,"Hombres adultos"),(sexonh,"Niños"),(sexonm,"Niñas")]
    comp_available = [(c,lbl) for c,lbl in comp_cols if c!="<ninguna>"]
    if comp_available:
        st.markdown("**Componentes del hogar (conteos)**")
        table = pd.DataFrame({lbl: pd.to_numeric(sub[c], errors='coerce').sum() for c,lbl in comp_available}, index=["Total"]
        )
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
    for r,c,label in cr_pairs:
        if r!="<ninguna>" and c!="<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(crosstab_pct(sub, r, c, by=sector if sector!='<ninguna>' else None), use_container_width=True)

with tabD:
    st.subheader("BLOQUE D – Situación socioeconómica (p004 = vivienda o mixto)")
    sub = work.copy()
    if p004 != "<ninguna>":
        sub = sub[[True if is_vivienda_or_mixto(v) else False for v in sub[p004]]]
    st.markdown("**Tabulados simples**")
    for col, label in [(p012,"Año de residencia (p012)"), (p013,"Nº de personas con ingresos (p013)")]:
        if col!="<ninguna>":
            x = pd.to_numeric(sub[col], errors='coerce')
            desc = x.describe()[["count","mean","50%","min","max"]].rename({"50%":"median"})
            st.markdown(f"**{label} — media/mediana/min/max**")
            st.write(desc.to_frame().T)
    for col, label in [(p014,"Fuente principal de ingreso (p014)"), (p022,"Activos del hogar (p022)")]:
        if col!="<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(vc_percent(sub, col, by=sector if sector!='<ninguna>' else None), use_container_width=True)

    st.markdown("**Cruces clave**")
    pairs = [
        (p014, sexoj, "Fuente de ingreso × Sexo jefatura"),
        (p013, p011, "Nº personas con ingresos × Tamaño del hogar"),
        (p022, p010, "Activos × Tenencia"),
        (p022, p015, "Activos × Servicios básicos"),
    ]
    for r,c,label in pairs:
        if r!="<ninguna>" and c!="<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(crosstab_pct(sub, r, c, by=sector if sector!='<ninguna>' else None), use_container_width=True)

with tabE:
    st.subheader("BLOQUE E – Acceso a servicios y saneamiento (p004 = vivienda o mixto)")
    sub = work.copy()
    if p004 != "<ninguna>":
        sub = sub[[True if is_vivienda_or_mixto(v) else False for v in sub[p004]]]
    st.markdown("**Tabulados simples**")
    for col, label in [(p015,"Servicios básicos (p015)"), (p016,"Frecuencia acceso agua (p016)"),
                       (p017,"Fuente de agua (p017)"), (p018,"Tipo de sanitario (p018)"),
                       (p019,"Uso sanitario (p019)"), (p020,"Eliminación aguas grises (p020)"),
                       (p021,"Eliminación basura (p021)")]:
        if col!="<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(vc_percent(sub, col, by=sector if sector!='<ninguna>' else None), use_container_width=True)
    st.markdown("**Cruces clave**")
    for r,c,label in [
        (p015, p010, "Servicios básicos × Tenencia"),
        (p015, sexoj, "Servicios básicos × Sexo jefatura"),
        (p015, p005, "Servicios básicos × Estado físico"),
        (p016, p017, "Frecuencia acceso agua × Fuente de agua"),
        (p018, p019, "Tipo sanitario × Uso sanitario"),
        (p020, p021, "Eliminación aguas grises × Eliminación basura"),
    ]:
        if r!="<ninguna>" and c!="<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(crosstab_pct(sub, r, c, by=sector if sector!='<ninguna>' else None), use_container_width=True)

with tabF:
    st.subheader("BLOQUE F – Negocios (p004 = negocio o mixto)")
    sub = work.copy()
    if p004 != "<ninguna>":
        sub = sub[[True if is_negocio_or_mixto(v) else False for v in sub[p004]]]
    st.markdown("**Tabulados simples**")
    for col, label in [(p025,"Actividad principal (p025)"), (p026,"Tiempo de operación (p026)"),
                       (p027,"Permisos de operación (p027)"), (p028,"Tenencia local (p028)"),
                       (p029,"Nº trabajadores (p029)"), (p030,"Nº empleados formales (p030)"),
                       (p031,"Ingreso mensual empleados (p031)"), (p032,"Activos negocio (p032)")]:
        if col!="<ninguna>":
            if col in [p026, p029, p030, p031]:
                x = pd.to_numeric(sub[col], errors='coerce')
                desc = x.describe()[["count","mean","50%","min","max"]].rename({"50%":"median"})
                st.markdown(f"**{label} — media/mediana/min/max**")
                st.write(desc.to_frame().T)
            else:
                st.markdown(f"**{label}**")
                st.dataframe(vc_percent(sub, col, by=sector if sector!='<ninguna>' else None), use_container_width=True)
    st.markdown("**Cruces clave**")
    for r,c,label in [
        (p025, p027, "Actividad × Permisos"),
        (p027, p028, "Permisos × Tenencia local"),
        (p030, p029, "Nº formales × Total trabajadores"),
        (p026, p027, "Tiempo de operación × Permisos"),
        (p031, p027, "Ingreso mensual × Permisos"),
    ]:
        if r!="<ninguna>" and c!="<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(crosstab_pct(sub, r, c, by=sector if sector!='<ninguna>' else None), use_container_width=True)

with tabG:
    st.subheader("BLOQUE G – Espacios públicos y percepción (todos los registros)")
    st.markdown("**Tabulados simples**")
    for col, label in [(p036,"Percepción de seguridad (p036)"),
                       (p035,"Condiciones del espacio (p035)"),
                       (p035tx,"Problemas identificados (p035tx)")]:
        if col!="<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(vc_percent(work, col, by=sector if sector!='<ninguna>' else None), use_container_width=True)
    st.markdown("**Cruces clave**")
    for r,c,label in [
        (p036, p004, "Percepción seguridad × Uso de estructura"),
        (p036, sexoj, "Percepción seguridad × Sexo jefatura"),
        (p035, p035tx, "Condiciones del espacio × Problemas identificados"),
    ]:
        if r!="<ninguna>" and c!="<ninguna>":
            st.markdown(f"**{label}**")
            st.dataframe(crosstab_pct(work, r, c, by=sector if sector!='<ninguna>' else None), use_container_width=True)

with tabI:
    st.subheader("BLOQUE I – Indicadores clave (resumen ejecutivo)")
    ind_tables = {}
    base = work.copy()
    if p005!="<ninguna>":
        s = base[p005].astype(str).str.lower()
        ind_bad = (s.str.contains("malo") | s.str.contains("mal")).mean()*100 if len(s)>0 else np.nan
        ind_tables["% estructuras en mal estado"] = ind_bad
    if sexoj!="<ninguna>":
        s = base[sexoj].astype(str).str.lower()
        fem = s.str.contains("mujer") | s.str.contains("femen")
        ind_tables["% hogares con jefatura femenina"] = fem.mean()*100 if len(s)>0 else np.nan
    if p010!="<ninguna>":
        s = base[p010].astype(str).str.lower()
        prec = s.str.contains("prest") | s.str.contains("invad") | s.str.contains("alquil.*sin") | s.str.contains("sin.*titul")
        ind_tables["% hogares con tenencia precaria"] = prec.mean()*100 if len(s)>0 else np.nan
    if p015!="<ninguna>":
        s = base[p015].astype(str).str.lower()
        sin_agua = ~(s.str.contains("agua") | s.str.contains("acued"))
        ind_tables["% hogares sin acceso a agua potable"] = sin_agua.mean()*100 if len(s)>0 else np.nan
    if p018!="<ninguna>":
        s = base[p018].astype(str).str.lower()
        inade = s.str.contains("letrin") | s.str.contains("ninguno") | s.str.contains("compart")
        ind_tables["% hogares con saneamiento inadecuado"] = inade.mean()*100 if len(s)>0 else np.nan
    if p027!="<ninguna>":
        s = base[p027].astype(str).str.lower()
        noperm = s.str.contains("no") | s.str.contains("ninguno")
        ind_tables["% negocios sin permisos"] = noperm.mean()*100 if len(s)>0 else np.nan
    if p022!="<ninguna>":
        ind_tables["Promedio activos por hogar"] = pd.to_numeric(base[p022], errors='coerce').mean()
    if p032!="<ninguna>":
        ind_tables["Promedio activos por negocio"] = pd.to_numeric(base[p032], errors='coerce').mean()
    if p030!="<ninguna>" and p029!="<ninguna>":
        num = pd.to_numeric(base[p030], errors='coerce')
        den = pd.to_numeric(base[p029], errors='coerce').replace(0, np.nan)
        ind_tables["% negocios con personal formalizado"] = ((num/den).mean()*100) if den.notna().any() else np.nan
    ind_df = pd.DataFrame({"Indicador": list(ind_tables.keys()), "Valor": list(ind_tables.values())})
    st.dataframe(ind_df, use_container_width=True)
    st.caption("Las reglas de indicadores son heurísticas; ajustables a tu codificación exacta.")

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
        if p005!="<ninguna>" and other!="<ninguna>":
            sheets[f"B_{key}"] = crosstab_pct(work, p005, other, by=sector if sector!='<ninguna>' else None)
    for other, key in [(p006,"p004x_p006"),(p007,"p004x_p007"),(p008,"p004x_p008")]:
        if p004!="<ninguna>" and other!="<ninguna>":
            sheets[f"B_{key}"] = crosstab_pct(work, p004, other, by=sector if sector!='<ninguna>' else None)
# ---- MAPA GPS ----
with tabMAP:
    st.subheader("Mapa de coordenadas GPS")

    if lat_col != "<ninguna>" and lon_col != "<ninguna>":
        m = work.copy()

        # Convertir a numérico y limpiar
        m["_lat"] = pd.to_numeric(m[lat_col], errors="coerce")
        m["_lon"] = pd.to_numeric(m[lon_col], errors="coerce")
        m = m.dropna(subset=["_lat", "_lon"])
        m = m[(m["_lat"].between(-90, 90)) & (m["_lon"].between(-180, 180))]

        if m.empty:
            st.info("No hay coordenadas válidas después de la limpieza.")
        else:
            # st.map requiere columnas 'lat' y 'lon'
            map_df = m.rename(columns={"_lat": "lat", "_lon": "lon"})[["lat", "lon"]]
            st.map(map_df, use_container_width=True)
            st.caption(f"{len(map_df):,} puntos mostrados.")
    else:
        st.info("Selecciona las columnas de LATITUD y LONGITUD en la barra lateral.")

    subC = work.copy()
    if p004!="<ninguna>":
        subC = subC[[True if is_vivienda_or_mixto(v) else False for v in subC[p004]]]
    for col, key in [(nviv,"C_nvivienda"),(p009a,"C_p009a"),(p009b,"C_p009b"),(p010,"C_p010"),(sexoj,"C_sexoj"),(p011,"C_p011")]:
        if col!="<ninguna>": sheets[key] = vc_percent(subC, col, by=sector if sector!='<ninguna>' else None)
    for r,c,key in [(sexoj,p010,"C_sexoj_x_p010"),(sexoj,p015,"C_sexoj_x_p015"),(sexoj,p005,"C_sexoj_x_p005"),
                    (sexoj,p014,"C_sexoj_x_p014"),(sexoj,p011,"C_sexoj_x_p011"),(p010,p015,"C_p010_x_p015"),
                    (p010,p005,"C_p010_x_p005")]:
        if r!="<ninguna>" and c!="<ninguna>": sheets[key] = crosstab_pct(subC, r, c, by=sector if sector!='<ninguna>' else None)

    subD = subC
    for col, key in [(p012,"D_p012"),(p013,"D_p013"),(p014,"D_p014"),(p022,"D_p022")]:
        if col!="<ninguna>": sheets[key] = vc_percent(subD, col, by=sector if sector!='<ninguna>' else None)
    for r,c,key in [(p014,sexoj,"D_p014_x_sexoj"),(p013,p011,"D_p013_x_p011"),(p022,p010,"D_p022_x_p010"),(p022,p015,"D_p022_x_p015")]:
        if r!="<ninguna>" and c!="<ninguna>": sheets[key] = crosstab_pct(subD, r, c, by=sector if sector!='<ninguna>' else None)

    subE = subC
    for col, key in [(p015,"E_p015"),(p016,"E_p016"),(p017,"E_p017"),(p018,"E_p018"),(p019,"E_p019"),(p020,"E_p020"),(p021,"E_p021")]:
        if col!="<ninguna>": sheets[key] = vc_percent(subE, col, by=sector if sector!='<ninguna>' else None)
    for r,c,key in [(p015,p010,"E_p015_x_p010"),(p015,sexoj,"E_p015_x_sexoj"),(p015,p005,"E_p015_x_p005"),
                    (p016,p017,"E_p016_x_p017"),(p018,p019,"E_p018_x_p019"),(p020,p021,"E_p020_x_p021")]:
        if r!="<ninguna>" and c!="<ninguna>": sheets[key] = crosstab_pct(subE, r, c, by=sector if sector!='<ninguna>' else None)

    subF = work.copy()
    if p004!="<ninguna>":
        subF = subF[[True if is_negocio_or_mixto(v) else False for v in subF[p004]]]
    for col, key in [(p025,"F_p025"),(p026,"F_p026"),(p027,"F_p027"),(p028,"F_p028"),(p029,"F_p029"),(p030,"F_p030"),(p031,"F_p031"),(p032,"F_p032")]:
        if col!="<ninguna>": sheets[key] = vc_percent(subF, col, by=sector if sector!='<ninguna>' else None)
    for r,c,key in [(p025,p027,"F_p025_x_p027"),(p027,p028,"F_p027_x_p028"),(p030,p029,"F_p030_x_p029"),(p026,p027,"F_p026_x_p027"),(p031,p027,"F_p031_x_p027")]:
        if r!="<ninguna>" and c!="<ninguna>": sheets[key] = crosstab_pct(subF, r, c, by=sector if sector!='<ninguna>' else None)

    for col, key in [(p036,"G_p036"),(p035,"G_p035"),(p035tx,"G_p035tx")]:
        if col!="<ninguna>": sheets[key] = vc_percent(work, col, by=sector if sector!='<ninguna>' else None)
    for r,c,key in [(p036,p004,"G_p036_x_p004"),(p036,sexoj,"G_p036_x_sexoj"),(p035,p035tx,"G_p035_x_p035tx")]:
        if r!="<ninguna>" and c!="<ninguna>": sheets[key] = crosstab_pct(work, r, c, by=sector if sector!='<ninguna>' else None)

    if sheets:
        data = export_xlsx(sheets)
        st.download_button("⬇️ Descargar Anexo Estadístico (Excel)", data=data, file_name="anexo_estadistico.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Configura el mapeo de variables para habilitar la exportación.")
