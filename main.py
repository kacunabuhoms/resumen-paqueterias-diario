import streamlit as st
import requests
import pandas as pd
from io import StringIO

# -------------------------------------------------
# Configuración básica de la página
# -------------------------------------------------
st.set_page_config(page_title="Dataset Info", layout="wide")

st.title("📊 Dataset Info desde API de Wing")

# -------------------------------------------------
# Función para obtener y procesar los datos
# -------------------------------------------------
def get_dataset():
    url = "https://wapi.wing.buhologistics.com/getDatasetInfo"
    headers = {
        "api-key": "0DJB9c_xpbQbprsg7iZLaUR"
    }

    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()  # lanza error si el status != 200

    # Intentar primero como JSON
    try:
        data = response.json()
        # Ajusta esto si tu JSON viene en otra estructura
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            records = data["data"]
        elif isinstance(data, list):
            records = data
        else:
            # Si es un dict raro, lo metemos en una lista
            records = [data]

        df = pd.DataFrame(records)
        # Generamos un CSV a partir del DataFrame
        csv_text = df.to_csv(index=False)
        return df, csv_text

    except ValueError:
        # Si NO es JSON, asumimos que ya viene como CSV
        text = response.text
        # Creamos el DataFrame a partir del CSV crudo
        df = pd.read_csv(StringIO(text))
        # Regresamos el texto tal cual "como viene"
        return df, text


# -------------------------------------------------
# Cuerpo principal de la app
# -------------------------------------------------
with st.spinner("Obteniendo datos de la API..."):
    try:
        df, csv_text = get_dataset()
    except Exception as e:
        st.error(f"Error al obtener los datos: {e}")
        st.stop()

st.subheader("Vista de datos en tabla")
st.dataframe(df, use_container_width=True)

st.subheader("Descargar datos")
st.download_button(
    label="⬇️ Descargar CSV (completo)",
    data=csv_text,
    file_name="dataset_info.csv",
    mime="text/csv",
)
