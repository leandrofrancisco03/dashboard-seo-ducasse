import streamlit as st
import pandas as pd
import sqlalchemy
import plotly.express as px
import json

# 1. Configuración de página (SIEMPRE PRIMERO)
st.set_page_config(page_title="SEO Dashboard", layout="wide")

# ==========================================
# 🔐 SISTEMA DE LOGIN (CANDADO DE SEGURIDAD)
# ==========================================
def check_password():
    """Retorna True si el usuario ingresó la clave correcta."""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.text_input(
        "🔐 Ingrese la contraseña de acceso", 
        type="password", 
        on_change=password_entered, 
        key="password_input"
    )
    return False

def password_entered():
    # --- CONTRASEÑA ---
    if st.session_state["password_input"] == st.secrets["DASHBOARD_PASS"]:
        st.session_state.password_correct = True
        del st.session_state["password_input"]  # Borramos la clave de memoria por seguridad
    else:
        st.error("Contraseña incorrecta")

if not check_password():
    st.stop()  # DETENERSE SI NO HAY CLAVE

# ==========================================
# APLICACIÓN PRINCIPAL (Solo carga si pasó el login)
# ==========================================

# --- CONEXIÓN A LA BASE DE DATOS ---
@st.cache_data(ttl=600)
def load_data():
    try:
        # Recuperamos variables de streamlit
        db_user = st.secrets["DB_USER"]
        db_pass = st.secrets["DB_PASS"]
        db_host = st.secrets["DB_HOST"]
        db_name = st.secrets["DB_NAME"]

        # Conexión
        engine = sqlalchemy.create_engine(f'postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:5432/{db_name}')

        query = """
        SELECT fecha, keyword, posicion, categoria_1, categoria_2, categoria_3, categoria_4, 
               url_encontrada, es_canibalizacion, detalle_canibalizacion
        FROM rankings_historico ORDER BY fecha ASC
        """
        df = pd.read_sql(query, engine)
        
        # Convertir fecha a datetime
        df['fecha'] = pd.to_datetime(df['fecha'])
        
        # Limpieza visual de nulos para los filtros
        cols_cat = ['categoria_1', 'categoria_2', 'categoria_3', 'categoria_4']
        for col in cols_cat:
            df[col] = df[col].fillna("")
            
        return df
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame()

# Cargamos datos
df = load_data()

st.title("🔎 Monitoreo de Posicionamiento Ducasse")

if not df.empty:
    tab1, tab2 = st.tabs(["🌎 Visión General", "🔬 Análisis Detallado"])

    # === PESTAÑA 1: VISIÓN GLOBAL ===
    with tab1:
        st.header("Salud del Proyecto")
        
        last_date = df['fecha'].max()
        df_last_day = df[df['fecha'] == last_date]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Posición Promedio", f"{df_last_day['posicion'].mean():.1f}")
        c2.metric("Total Keywords", df['keyword'].nunique())
        
        conflict_count = df_last_day[df_last_day['es_canibalizacion'] == True]['keyword'].nunique()
        c3.metric("Conflictos Activos Hoy", conflict_count, delta_color="inverse")
        
        daily_avg = df.groupby('fecha')['posicion'].mean().reset_index()
        fig = px.line(daily_avg, x='fecha', y='posicion', markers=True, line_shape='spline', title="Evolución del Ranking Promedio")
        fig.update_yaxes(autorange="reversed")
        fig.update_traces(line_color='#00CC96', line_width=3)
        st.plotly_chart(fig, use_container_width=True)

    # === PESTAÑA 2: ANÁLISIS DETALLADO ===
    with tab2:
        st.header("Dashboard Jerárquico de Keywords")
        
        with st.container():
            c_date, c_warn = st.columns([2, 1])
            min_d, max_d = df['fecha'].min().date(), df['fecha'].max().date()
            
            # Selector de rango de fechas
            d_range = c_date.date_input("Rango de Fechas", [min_d, max_d])
            show_conflict = c_warn.checkbox("Ver solo Canibalizaciones ⚠️")

        st.divider()

        # --- FILTROS EN CASCADA ---
        col1, col2, col3, col4 = st.columns(4)

        # Nivel 1
        opts_1 = ['Todos'] + sorted(df[df['categoria_1'] != ""]['categoria_1'].unique().tolist()) + ['(Sin Categoría)']
        sel_1 = col1.selectbox("Nivel 1", opts_1)

        # Nivel 2
        mask_1 = pd.Series(True, index=df.index)
        if sel_1 == '(Sin Categoría)': mask_1 = df['categoria_1'] == ""
        elif sel_1 != 'Todos': mask_1 = df['categoria_1'] == sel_1
        
        df_l2 = df[mask_1]
        opts_2 = ['Todos'] + sorted(df_l2[df_l2['categoria_2'] != ""]['categoria_2'].unique().tolist())
        sel_2 = col2.selectbox("Nivel 2", opts_2, disabled=(len(opts_2)==1))

        # Nivel 3
        mask_2 = pd.Series(True, index=df.index)
        if sel_2 != 'Todos': mask_2 = df['categoria_2'] == sel_2
        
        df_l3 = df[mask_1 & mask_2]
        opts_3 = ['Todos'] + sorted(df_l3[df_l3['categoria_3'] != ""]['categoria_3'].unique().tolist())
        sel_3 = col3.selectbox("Nivel 3", opts_3, disabled=(len(opts_3)==1))

        # Nivel 4
        mask_3 = pd.Series(True, index=df.index)
        if sel_3 != 'Todos': mask_3 = df['categoria_3'] == sel_3
        
        df_l4 = df[mask_1 & mask_2 & mask_3]
        opts_4 = ['Todos'] + sorted(df_l4[df_l4['categoria_4'] != ""]['categoria_4'].unique().tolist())
        sel_4 = col4.selectbox("Nivel 4", opts_4, disabled=(len(opts_4)==1))

        # --- APLICACIÓN DE FILTROS ---
        if len(d_range) == 2:
            start_date, end_date = d_range
            final_mask = (df['fecha'].dt.date >= start_date) & (df['fecha'].dt.date <= end_date)
        else:
            final_mask = pd.Series(True, index=df.index)

        # Aplicar cascada
        if sel_1 == '(Sin Categoría)': final_mask &= (df['categoria_1'] == "")
        elif sel_1 != 'Todos': final_mask &= (df['categoria_1'] == sel_1)
        
        if sel_2 != 'Todos': final_mask &= (df['categoria_2'] == sel_2)
        if sel_3 != 'Todos': final_mask &= (df['categoria_3'] == sel_3)
        if sel_4 != 'Todos': final_mask &= (df['categoria_4'] == sel_4)
        
        if show_conflict: final_mask &= (df['es_canibalizacion'] == True)
            
        filtered_df = df[final_mask].copy()

        # --- RESULTADOS ---
        if not filtered_df.empty:
            st.info(f"Se encontraron {len(filtered_df)} registros.")
            
            # Gráfico
            fig_detail = px.line(
                filtered_df, x='fecha', y='posicion', color='keyword',
                line_shape='spline', markers=True, 
                hover_data=['url_encontrada'],
                height=500,
                title="Evolución de Posiciones"
            )
            fig_detail.update_yaxes(autorange="reversed", title="Posición (1 es Top)")
            st.plotly_chart(fig_detail, use_container_width=True)
            
            st.divider()
            
            # Tabla
            st.subheader("📋 Detalle de Datos")

            def limpiar_canibalizacion(row):
                if not row or row == {}: return ""
                try:
                    data = row if isinstance(row, dict) else json.loads(row)
                    items = data.get('data', [])
                    if not items: return ""
                    
                    conflictos = []
                    for item in items:
                        url_corta = item.get('url', '').replace('https://', '').replace('http://', '')
                        conflictos.append(f"Pos {item.get('pos', '?')}: {url_corta}")
                    return " | ".join(conflictos)
                except:
                    return "Error formato"

            tabla_final = filtered_df.copy()
            
            if show_conflict:
                st.warning("Mostrando detalles de conflictos de canibalización.")
                tabla_final['Conflicto Detectado'] = tabla_final['detalle_canibalizacion'].apply(limpiar_canibalizacion)
                cols_to_show = ['fecha', 'keyword', 'posicion', 'url_encontrada', 'Conflicto Detectado']
            else:
                cols_to_show = ['fecha', 'keyword', 'posicion', 'url_encontrada', 'categoria_1', 'categoria_2', 'categoria_3']

            tabla_final['fecha'] = tabla_final['fecha'].dt.date
            
            st.dataframe(
                tabla_final[cols_to_show], 
                use_container_width=True,
                hide_index=True
            )
                
        else:
            st.warning("No hay datos para esta combinación de filtros.")
else:
    st.warning("No se pudieron cargar datos. Verifica la conexión a la base de datos.")