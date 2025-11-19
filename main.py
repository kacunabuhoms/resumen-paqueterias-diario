import streamlit as st
import requests
import pandas as pd
from datetime import date, timedelta

# ==========================
# CONFIG DE PÁGINA (WIDE)
# ==========================
st.set_page_config(
    page_title="Resumen de entregas por fecha",
    layout="wide",
)

# ==========================
# CONFIGURACIÓN BÁSICA
# ==========================

LOCAL_TZ = "America/Monterrey"

API_URL = st.secrets["api"]["url"]
API_KEY = st.secrets["api"]["key"]

# Inicializar dataset en sesión
if "raw_dataset" not in st.session_state:
    st.session_state["raw_dataset"] = None

# ==========================
# UI - STREAMLIT
# ==========================

st.title("📦 Resumen de entregas por fecha de entrega")

st.markdown(
    """
    1. Presiona **"Cargar datos desde API"** para obtener el dataset completo.  
    2. Luego selecciona la fecha de entrega para ver la tabla y los resúmenes.
    """
)

# --------- BOTÓN PARA CARGAR DATOS DESDE EL API ---------
if st.button("1️⃣ Cargar datos desde API"):
    headers = {
        "api-key": API_KEY
    }

    with st.spinner("Llamando al API y cargando datos..."):
        try:
            response = requests.get(API_URL, headers=headers, timeout=60)
            response.raise_for_status()
        except requests.RequestException as e:
            st.error(f"❌ Error al llamar al servicio: {e}")
        else:
            data = response.json()

            # Normalizar a lista
            if isinstance(data, list):
                dataset = data
            elif isinstance(data, dict):
                # Si la API viene como {"data": [...]}, ajusta aquí si aplica
                dataset = data.get("data", [])
            else:
                dataset = []
                st.error("La respuesta del API no es una lista ni un dict con 'data'.")

            st.session_state["raw_dataset"] = dataset

    if st.session_state["raw_dataset"] is not None:
        st.success(f"✅ Datos cargados. Registros totales: {len(st.session_state['raw_dataset'])}")

# --------- SELECCIÓN DE FECHA PARA FILTRAR ---------

default_date = date.today() - timedelta(days=1)

selected_date = st.date_input(
    "Selecciona la fecha de entrega a filtrar",
    value=default_date,
)

if st.session_state["raw_dataset"] is None:
    st.info("Primero presiona **\"Cargar datos desde API\"** para obtener la información.")
else:
    # ==========================
    # DATAFRAME COMPLETO
    # ==========================
    df_all = pd.DataFrame(st.session_state["raw_dataset"])

    # --- Incidence -> bool (en todo el dataset) ---
    def to_bool(x):
        if pd.isna(x):
            return False
        if isinstance(x, bool):
            return x
        try:
            return float(x) != 0
        except Exception:
            return False

    if "incidence" in df_all.columns:
        df_all["incidence"] = df_all["incidence"].apply(to_bool)

    # --- Parseo y normalización de fechas a America/Monterrey ---
    # Se asume que el API manda timestamptz en UTC
    if "start_date" in df_all.columns:
        start_utc = pd.to_datetime(df_all["start_date"], utc=True, errors="coerce")
        df_all["_start_local"] = start_utc.dt.tz_convert(LOCAL_TZ)
    else:
        df_all["_start_local"] = pd.NaT

    if "delivery_date" in df_all.columns:
        delivery_utc = pd.to_datetime(df_all["delivery_date"], utc=True, errors="coerce")
        df_all["_delivery_local"] = delivery_utc.dt.tz_convert(LOCAL_TZ)
    else:
        df_all["_delivery_local"] = pd.NaT

    # Fecha (solo día) en zona local para filtrar
    df_all["_delivery_local_date"] = df_all["_delivery_local"].dt.date

    # Horas de entrega (en base a datetimes locales)
    df_all["_horas_entrega"] = (
        df_all["_delivery_local"] - df_all["_start_local"]
    ).dt.total_seconds() / 3600.0

    # ==========================
    # FILTRO POR FECHA SELECCIONADA (zona local)
    # ==========================
    mask_fecha = df_all["_delivery_local_date"] == selected_date
    df_fecha = df_all.loc[mask_fecha].copy()

    # ==========================
    # TABLA DETALLE (SOLO FECHA SELECCIONADA)
    # ==========================

    st.subheader("📋 Detalle de envíos para la fecha seleccionada")

    if not df_fecha.empty:
        # Sobrescribir columnas de fecha con la versión en horario de Monterrey
        if "start_date" in df_fecha.columns:
            df_fecha["start_date"] = df_fecha["_start_local"].dt.strftime("%Y-%m-%d %H:%M")

        if "delivery_date" in df_fecha.columns:
            df_fecha["delivery_date"] = df_fecha["_delivery_local"].dt.strftime("%Y-%m-%d %H:%M")

        cols = [
            "client",
            "carrier",
            "service",
            "dest_state",
            "start_date",
            "delivery_date",
            "incidence",
            "extended_zone",
            "service_mode",
        ]
        cols_presentes = [c for c in cols if c in df_fecha.columns]

        rename_map = {
            "client": "Cliente",
            "carrier": "Paquetería",
            "service": "Servicio",
            "dest_state": "Estado destino",
            "start_date": "Fecha inicio (Monterrey)",
            "delivery_date": "Fecha entrega (Monterrey)",
            "incidence": "Incidencia",
            "extended_zone": "Zona extendida",
            "service_mode": "Modo de servicio",
        }

        df_display = df_fecha[cols_presentes].rename(columns=rename_map)

        st.dataframe(df_display, width="stretch")
    else:
        st.info("No se encontraron registros para esa fecha en horario de Monterrey.")

    # ==========================
    # RESUMEN GENERAL + ÚLTIMOS N DÍAS
    # ==========================

    st.subheader("📊 Resumen general")

    n_dias = st.number_input(
        "Número de días hacia atrás (incluyendo la fecha seleccionada)",
        min_value=1,
        value=3,
        step=1,
    )

    # ---------- Resumen SOLO delivery_date seleccionado ----------
    total_entregado_fecha = len(df_fecha)

    horas_validas_fecha = df_fecha["_horas_entrega"].dropna()
    if len(horas_validas_fecha) > 0:
        promedio_horas_fecha = horas_validas_fecha.mean()
        promedio_dias_fecha = promedio_horas_fecha / 24.0
        tiempo_promedio_fecha_str = f"{promedio_horas_fecha:.2f} h (~{promedio_dias_fecha:.2f} días)"
    else:
        tiempo_promedio_fecha_str = "N/D"

    if "incidence" in df_fecha.columns:
        total_incidencias_fecha = int(df_fecha["incidence"].sum())
    else:
        total_incidencias_fecha = 0

    if total_entregado_fecha > 0:
        porcentaje_incidencias_fecha = (total_incidencias_fecha / total_entregado_fecha) * 100
    else:
        porcentaje_incidencias_fecha = 0.0

    porcentaje_incidencias_fecha_str = f"{porcentaje_incidencias_fecha:.2f}%"

    # ---------- Resumen ÚLTIMOS N DÍAS (incluyendo delivery_date seleccionado) ----------

    fecha_min = selected_date - timedelta(days=n_dias - 1)
    mask_rango = (
        (df_all["_delivery_local_date"] >= fecha_min)
        & (df_all["_delivery_local_date"] <= selected_date)
    )
    df_rango = df_all.loc[mask_rango].copy()

    total_entregado_rango = len(df_rango)

    horas_validas_rango = df_rango["_horas_entrega"].dropna()
    if len(horas_validas_rango) > 0:
        promedio_horas_rango = horas_validas_rango.mean()
        promedio_dias_rango = promedio_horas_rango / 24.0
        tiempo_promedio_rango_str = f"{promedio_horas_rango:.2f} h (~{promedio_dias_rango:.2f} días)"
    else:
        tiempo_promedio_rango_str = "N/D"

    if "incidence" in df_rango.columns:
        total_incidencias_rango = int(df_rango["incidence"].sum())
    else:
        total_incidencias_rango = 0

    if total_entregado_rango > 0:
        porcentaje_incidencias_rango = (total_incidencias_rango / total_entregado_rango) * 100
    else:
        porcentaje_incidencias_rango = 0.0

    porcentaje_incidencias_rango_str = f"{porcentaje_incidencias_rango:.2f}%"

    # ---------- HEADERS CENTRADOS (2 COLUMNAS SOBRE LAS 4) ----------
    header_col1, header_col2 = st.columns([1, 1])

    with header_col1:
        st.markdown(
            f"<h4 style='text-align:center'>Resumen {selected_date.strftime('%Y-%m-%d')}</h4>",
            unsafe_allow_html=True,
        )

    with header_col2:
        st.markdown(
            f"<h4 style='text-align:center'>Resumen últimos {n_dias} días</h4>",
            unsafe_allow_html=True,
        )

    # ---------- RESÚMENES EN 4 COLUMNAS (MISMO NIVEL) ----------
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    # Resumen {delivery_date}
    with col1:
        st.markdown("**Cantidad entregada**")
        st.markdown("**Tiempo promedio de entrega**")
        st.markdown("**Total de incidencias**")
        st.markdown("**Porcentaje de incidencias**")

    with col2:
        st.markdown(f"**{total_entregado_fecha}**")
        st.markdown(f"**{tiempo_promedio_fecha_str}**")
        st.markdown(f"**{total_incidencias_fecha}**")
        st.markdown(f"**{porcentaje_incidencias_fecha_str}**")

    # Resumen últimos N días
    with col3:
        st.markdown("**Cantidad entregada**")
        st.markdown("**Tiempo promedio de entrega**")
        st.markdown("**Total de incidencias**")
        st.markdown("**Porcentaje de incidencias**")

    with col4:
        st.markdown(f"**{total_entregado_rango}**")
        st.markdown(f"**{tiempo_promedio_rango_str}**")
        st.markdown(f"**{total_incidencias_rango}**")
        st.markdown(f"**{porcentaje_incidencias_rango_str}**")

    # ==========================
    # REGISTROS SIN delivery_date
    # (JUSTO ANTES DEL SUBHEADER DE PAQUETERÍAS)
    # ==========================

    if "delivery_date" in df_all.columns:
        # Consideramos nulos y strings vacíos
        mask_delivery_na = df_all["delivery_date"].isna() | (
            df_all["delivery_date"].astype(str).str.strip() == ""
        )
        total_sin_delivery = int(mask_delivery_na.sum())
        st.markdown(f"**Registros sin `delivery_date` (vacío o nulo) en todo el dataset:** {total_sin_delivery}")
    else:
        st.markdown("**Registros sin `delivery_date`:** la columna `delivery_date` no existe en el dataset.")

    # ==========================
    # RESUMEN AGRUPADO POR CARRIER - FECHA SELECCIONADA
    # ==========================

    st.subheader("🚚 Resumen por paquetería (carrier) - fecha seleccionada")

    if not df_fecha.empty and "carrier" in df_fecha.columns:
        df_group_fecha = df_fecha.copy()

        # Carrier en mayúsculas antes de agrupar
        df_group_fecha["carrier_upper"] = df_group_fecha["carrier"].astype(str).str.upper()

        group_fecha = df_group_fecha.groupby("carrier_upper").agg(
            Cantidad_entregas=("carrier_upper", "size"),
            Tiempo_promedio_horas=("_horas_entrega", "mean"),
            Incidencias=("incidence", "sum"),
        )

        group_fecha["Tiempo_promedio_dias"] = group_fecha["Tiempo_promedio_horas"] / 24.0
        group_fecha["Porcentaje_incidencias"] = (
            group_fecha["Incidencias"] / group_fecha["Cantidad_entregas"] * 100
        )

        group_fecha = group_fecha.reset_index().rename(columns={"carrier_upper": "PAQUETERIA"})

        group_fecha["Tiempo_promedio_horas"] = group_fecha["Tiempo_promedio_horas"].round(2)
        group_fecha["Tiempo_promedio_dias"] = group_fecha["Tiempo_promedio_dias"].round(2)
        group_fecha["Porcentaje_incidencias"] = group_fecha["Porcentaje_incidencias"].round(2)

        st.dataframe(group_fecha, width="stretch")
    else:
        st.info("No hay datos para agrupar por paquetería en la fecha seleccionada.")

    # ==========================
    # RESUMEN AGRUPADO POR CARRIER - ÚLTIMOS N DÍAS
    # ==========================

    st.subheader(f"🚚 Resumen por paquetería (carrier) - últimos {n_dias} días")

    if not df_rango.empty and "carrier" in df_rango.columns:
        df_group_rango = df_rango.copy()

        # Carrier en mayúsculas antes de agrupar
        df_group_rango["carrier_upper"] = df_group_rango["carrier"].astype(str).str.upper()

        group_rango = df_group_rango.groupby("carrier_upper").agg(
            Cantidad_entregas=("carrier_upper", "size"),
            Tiempo_promedio_horas=("_horas_entrega", "mean"),
            Incidencias=("incidence", "sum"),
        )

        group_rango["Tiempo_promedio_dias"] = group_rango["Tiempo_promedio_horas"] / 24.0
        group_rango["Porcentaje_incidencias"] = (
            group_rango["Incidencias"] / group_rango["Cantidad_entregas"] * 100
        )

        group_rango = group_rango.reset_index().rename(columns={"carrier_upper": "PAQUETERIA"})

        group_rango["Tiempo_promedio_horas"] = group_rango["Tiempo_promedio_horas"].round(2)
        group_rango["Tiempo_promedio_dias"] = group_rango["Tiempo_promedio_dias"].round(2)
        group_rango["Porcentaje_incidencias"] = group_rango["Porcentaje_incidencias"].round(2)

        st.dataframe(group_rango, width="stretch")
    else:
        st.info(f"No hay datos para agrupar por paquetería en los últimos {n_dias} días.")
