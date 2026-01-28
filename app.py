import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path

st.set_page_config(page_title="Bitácora — KPI + Problemas", layout="wide")
st.title("Bitácora - Reparaciones")

# =========================
# CONFIG COLUMNAS (TU EXCEL)
# =========================
COL_VIN = "VIN CON PROBLEMAS"
COL_FECHA = "Fecha reparación"
COL_ESTADO = "Unidad revisada/Operativa"
COL_PROB = "Tipo de problema"

# =========================
# RUTAS
# =========================
BASE_DIR = Path(__file__).resolve().parent
XLSX_PATH = BASE_DIR / "data" / "bitacora.xlsx"
CSV_PATH = BASE_DIR / "data" / "bitacora.csv"

@st.cache_data
def load_df():
    if XLSX_PATH.exists():
        df = pd.read_excel(XLSX_PATH)
    else:
        df = pd.read_csv(CSV_PATH, sep=";", encoding="latin1")
        df = df.loc[:, ~df.columns.str.contains(r"^Unnamed")]
    return df

df = load_df()

# =========================
# VALIDACIONES
# =========================
need = [COL_VIN, COL_ESTADO, COL_FECHA]
missing = [c for c in need if c not in df.columns]
if missing:
    st.error(f"Faltan columnas en el archivo: {missing}")
    st.write("Columnas disponibles:", list(df.columns))
    st.stop()

# =========================
# NORMALIZACIÓN
# =========================
df = df.dropna(subset=[COL_VIN]).copy()
df["UNIDAD_ID"] = df[COL_VIN].astype(str).str.strip()

df["ESTADO_RAW"] = df[COL_ESTADO].fillna("").astype(str).str.strip()
df["ESTADO"] = df["ESTADO_RAW"].str.lower()

df["ES_REVISADO"] = df["ESTADO"].str.contains(r"\brevisad", na=False)         # Revisado/Revisada
df["ES_NO_REVISADO"] = df["ESTADO"].str.contains(r"\bno\s*revis", na=False)   # No revisada
df["ES_DE_BAJA"] = df["ESTADO"].str.contains("de baja", na=False)

df["FECHA_TRABAJO"] = pd.to_datetime(df[COL_FECHA], dayfirst=True, errors="coerce")
df["TIENE_FECHA_REP"] = df["FECHA_TRABAJO"].notna()

# =========================
# FILTROS
# =========================
with st.sidebar:
    st.header("Filtros")
    show_active_only = st.checkbox("Excluir 'De Baja' de los KPIs", value=True)

base = df.copy()
if show_active_only:
    base = base[~base["ES_DE_BAJA"]].copy()

# =========================
# KPI PRINCIPAL: VIN únicos vs VIN reparados (con fecha)
# =========================
vin_total_unicos = int(base["UNIDAD_ID"].nunique())
vin_reparados_unicos = int(base.loc[base["ES_REVISADO"] & base["TIENE_FECHA_REP"], "UNIDAD_ID"].nunique())

pct_reparados = (vin_reparados_unicos / vin_total_unicos * 100) if vin_total_unicos else 0
pct_no_reparados = 100 - pct_reparados if vin_total_unicos else 0

st.subheader("KPIs")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total VIN únicos", f"{vin_total_unicos:,}".replace(",", "."))
k2.metric("VIN reparados (únicos)", f"{vin_reparados_unicos:,}".replace(",", "."))
k3.metric("% VIN reparados", f"{pct_reparados:.1f}%")
k4.metric("% VIN no reparados", f"{pct_no_reparados:.1f}%")

# =========================
# SEMANA ACTUAL — Reparados esta semana (según fecha)
# =========================
st.subheader("Semana actual")

today = pd.Timestamp(date.today())
year_now = int(today.isocalendar().year)
week_now = int(today.isocalendar().week)

rep_only = base[base["TIENE_FECHA_REP"]].copy()
if rep_only.empty:
    st.info("No hay filas con Fecha reparación para calcular la semana actual.")
else:
    iso = rep_only["FECHA_TRABAJO"].dt.isocalendar()
    rep_only["_YEAR"] = iso["year"].astype(int)
    rep_only["_WEEK"] = iso["week"].astype(int)

    w = rep_only[(rep_only["_YEAR"] == year_now) & (rep_only["_WEEK"] == week_now)].copy()

    w_vin_reparados = int(w.loc[w["ES_REVISADO"], "UNIDAD_ID"].nunique())

    s1, s2 = st.columns(2)
    s1.metric("VIN reparados (únicos) — semana", f"{w_vin_reparados:,}".replace(",", "."))

# =========================
# REPARACIONES POR DÍA (solo filas con fecha)
# =========================
st.subheader("Reparaciones por día")

rep_only2 = base[base["TIENE_FECHA_REP"]].copy()
if rep_only2.empty:
    st.info("No hay filas con Fecha reparación para graficar por día.")
else:
    rep_only2 = rep_only2.assign(DIA=rep_only2["FECHA_TRABAJO"].dt.date)

    # Registros por día
    by_day = (
        rep_only2.groupby("DIA")
        .agg(
            registros_con_fecha=("UNIDAD_ID", "count"),
            registros_revisados=("ES_REVISADO", "sum"),
        )
        .reset_index()
        .sort_values("DIA")
    )

    # VIN reparados únicos por día (solo Revisado)
    by_day_units = (
        rep_only2.loc[rep_only2["ES_REVISADO"]]
        .groupby("DIA")["UNIDAD_ID"]
        .nunique()
        .rename("vin_reparados_unicos")
        .reset_index()
        .sort_values("DIA")
    )

    # Unimos para graficar / mostrar
    by_day_full = by_day.merge(by_day_units, on="DIA", how="left").fillna({"vin_reparados_unicos": 0})

    # ✅ ARREGLADO: nombres correctos (con underscore)
    st.line_chart(by_day_full.set_index("DIA")[["registros_con_fecha", "registros_revisados"]])

    st.subheader("VIN reparados (únicos por día)")
    st.dataframe(by_day_full[["DIA", "vin_reparados_unicos"]], use_container_width=True)

# =========================
# PROBLEMAS MÁS TÍPICOS
# =========================
st.subheader("Problemas más típicos")

tmp = base.copy()
tmp["PROBLEMA"] = tmp[COL_PROB].fillna("Sin clasificar").astype(str).str.strip()

st.caption("Top problemas — todos los registros")
top_all = tmp["PROBLEMA"].value_counts().head(10)
st.bar_chart(top_all)

with st.expander("Ver tabla top problemas"):
    tab = pd.DataFrame({"Tipo de problema": top_all.index, "Registros": top_all.values})
    st.dataframe(tab, use_container_width=True)
