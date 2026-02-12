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
        
        # Última fecha disponible para métricas "de hoy"
        last_date = df['fecha'].max()
        df_last_day = df[df['fecha'] == last_date]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Posición Promedio", f"{df_last_day['posicion'].mean():.1f}")
        c2.metric("Total Keywords", df['keyword'].nunique())
        
        # Contamos cuántas keywords tienen conflicto HOY (o en la última fecha)
        conflict_count = df_last_day[df_last_day['es_canibalizacion'] == True]['keyword'].nunique()
        c3.metric("Conflictos Activos- Canibalizaciones hoy", conflict_count, delta_color="inverse")
        
        # Gráfico de Tendencia
        daily_avg = df.groupby('fecha')['posicion'].mean().reset_index()
        fig = px.line(daily_avg, x='fecha', y='posicion', markers=True, line_shape='spline', title="Evolución del Ranking Promedio")
        fig.update_yaxes(autorange="reversed")
        fig.update_traces(line_color='#00CC96', line_width=3)
        st.plotly_chart(fig, use_container_width=True)

    # === PESTAÑA 2: ANÁLISIS DETALLADO ===
    # === PESTAÑA 2: ANÁLISIS DETALLADO ===
    with tab2:
        st.header("Dashboard Jerárquico de Keywords")
        
        # --- FILTROS DE FECHA Y CANIBALIZACIÓN ---
        with st.container():
            c_date, c_warn = st.columns([2, 1])
            min_d, max_d = df['fecha'].min().date(), df['fecha'].max().date()
            d_range = c_date.date_input("Rango de Fechas", [min_d, max_d])
            show_conflict = c_warn.checkbox("Ver solo Canibalizaciones ⚠️")

        st.divider() # Línea separadora visual

        # --- FILTROS EN CASCADA (NIVELES 1 -> 4) ---
        # Usamos 4 columnas para que se vea ordenado
        col1, col2, col3, col4 = st.columns(4)

        def get_mask(df_target, col_name, selection_list):
            """Crea una máscara booleana basada en una selección múltiple, manejando vacíos."""
            if not selection_list:
                # Si la lista está vacía, seleccionamos TODO
                return pd.Series(True, index=df_target.index)
            else:
                # Separamos los valores normales de la etiqueta especial "(Sin Categoría)"
                query_vals = [x for x in selection_list if x != '(Sin Categoría)']
                include_blanks = '(Sin Categoría)' in selection_list
                
                # Máscara para valores normales
                mask_vals = df_target[col_name].isin(query_vals)
                # Máscara para vacíos (si se seleccionó la opción)
                mask_blanks = (df_target[col_name] == "") if include_blanks else pd.Series(False, index=df_target.index)
                
                # Combinamos ambas condiciones con OR (|)
                return mask_vals | mask_blanks

        # --- NIVEL 1 ---
        # Obtenemos valores únicos reales
        opts_1_raw = sorted(df[df['categoria_1'] != ""]['categoria_1'].unique().tolist())
        # Si existen vacíos en los datos, agregamos la opción visual
        has_empty_1 = "" in df['categoria_1'].unique()
        opts_1_display = opts_1_raw + (['(Sin Categoría)'] if has_empty_1 else [])
        
        # Usamos multiselect
        sel_1 = col1.multiselect("Nivel 1", opts_1_display, placeholder="Elige opciones...")
        
        # Calculamos la máscara del Nivel 1
        mask_1 = get_mask(df, 'categoria_1', sel_1)

        # --- NIVEL 2 (Depende de Nivel 1) ---
        df_l2 = df[mask_1] # Filtramos los datos disponibles
        
        opts_2_raw = sorted(df_l2[df_l2['categoria_2'] != ""]['categoria_2'].unique().tolist())
        has_empty_2 = "" in df_l2['categoria_2'].unique()
        opts_2_display = opts_2_raw + (['(Sin Categoría)'] if has_empty_2 else [])
        
        # Deshabilitamos si no hay opciones reales disponibles
        disabled_2 = len(opts_2_display) == 0 or (len(opts_2_display) == 1 and opts_2_display[0] == '(Sin Categoría)' and not has_empty_2)
        
        sel_2 = col2.multiselect("Nivel 2", opts_2_display, disabled=disabled_2, placeholder="Elige opciones...")
        mask_2 = get_mask(df, 'categoria_2', sel_2)

        # --- NIVEL 3 (Depende de Nivel 1 y 2) ---
        df_l3 = df[mask_1 & mask_2]
        
        opts_3_raw = sorted(df_l3[df_l3['categoria_3'] != ""]['categoria_3'].unique().tolist())
        has_empty_3 = "" in df_l3['categoria_3'].unique()
        opts_3_display = opts_3_raw + (['(Sin Categoría)'] if has_empty_3 else [])
        
        disabled_3 = len(opts_3_display) == 0
        sel_3 = col3.multiselect("Nivel 3", opts_3_display, disabled=disabled_3, placeholder="Elige opciones...")
        mask_3 = get_mask(df, 'categoria_3', sel_3)

        # --- NIVEL 4 (Depende de Nivel 1, 2 y 3) ---
        df_l4 = df[mask_1 & mask_2 & mask_3]
        
        opts_4_raw = sorted(df_l4[df_l4['categoria_4'] != ""]['categoria_4'].unique().tolist())
        has_empty_4 = "" in df_l4['categoria_4'].unique()
        opts_4_display = opts_4_raw + (['(Sin Categoría)'] if has_empty_4 else [])
        
        disabled_4 = len(opts_4_display) == 0
        sel_4 = col4.multiselect("Nivel 4", opts_4_display, disabled=disabled_4, placeholder="Elige opciones...")
        mask_4 = get_mask(df, 'categoria_4', sel_4)


        # --- APLICACIÓN FINAL DE TODOS LOS FILTROS ---
        # 1. Filtro de Fecha
        if len(d_range) == 2:
            start_date, end_date = d_range
            final_mask = (df['fecha'].dt.date >= start_date) & (df['fecha'].dt.date <= end_date)
        else:
            final_mask = pd.Series(True, index=df.index)

        # 2. Combinamos las máscaras de categorías (AND)
        final_mask &= mask_1 & mask_2 & mask_3 & mask_4
        
        # 3. Filtro de Canibalización
        if show_conflict: final_mask &= (df['es_canibalizacion'] == True)
            
        filtered_df = df[final_mask].copy()

        # --- RESULTADOS (Esto sigue igual que antes, o con el cambio del switch si lo aplicaste) ---
        if not filtered_df.empty:
            st.info(f"Se encontraron {len(filtered_df)} registros.")
            
            # === NUEVO CONTROL: SWITCH PARA AGRUPAR ===
            # Creamos columnas para poner el switch a la derecha o izquierda
            col_graph, col_toggle = st.columns([4, 1])
            
            with col_toggle:
                st.write("") # Espacio para alinear verticalmente
                st.write("") 
                agrupar = st.toggle("📉 Ver Promedio", value=False, help="Fusiona todas las keywords en una sola línea promedio")

            # === LÓGICA DEL GRÁFICO ===
            if agrupar:
                # 1. MODO PROMEDIO: Agrupamos por fecha y calculamos la media de la posición
                df_chart = filtered_df.groupby('fecha')['posicion'].mean().reset_index()
                
                # Le ponemos un nombre genérico para que la leyenda se vea bien
                # Si hay una categoría seleccionada, usamos ese nombre, si no "Promedio General"
                nombre_linea = sel_2 if sel_2 != 'Todos' else (sel_1 if sel_1 != 'Todos' else "Promedio Global")
                df_chart['keyword'] = f"Promedio: {nombre_linea}"
                
                titulo_grafico = "Evolución Promedio (Agrupado)"
                color_discrete = ['#FF4B4B'] # Color rojo/destacado para el promedio
            else:
                # 2. MODO DETALLADO: Usamos los datos tal cual
                df_chart = filtered_df
                titulo_grafico = "Evolución por Keyword (Detallado)"
                color_discrete = None # Que Plotly asigne colores automáticos

            # Crear el gráfico con los datos preparados (df_chart)
            fig_detail = px.line(
                df_chart, 
                x='fecha', 
                y='posicion', 
                color='keyword', # Ahora color depende de si agrupamos o no
                line_shape='spline', 
                markers=True, 
                color_discrete_sequence=color_discrete,
                height=500,
                title=titulo_grafico
            )
            
            # Configuraciones visuales del gráfico
            fig_detail.update_yaxes(autorange="reversed", title="Posición (1 es Top)")
            fig_detail.update_layout(hovermode="x unified") # Muestra info de todas las líneas al pasar el mouse
            
            st.plotly_chart(fig_detail, use_container_width=True)
            
            st.divider()
            
            # 2. TABLA INTELIGENTE (Esta la dejamos siempre detallada para que puedas auditar)
            st.subheader("📋 Detalle de Datos (Raw Data)")

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

            tabla_final = filtered_df.copy() # Usamos siempre el DF original para la tabla
            
            if show_conflict:
                st.warning("Mostrando detalles de conflictos de canibalización.")
                tabla_final['Conflicto Detectado'] = tabla_final['detalle_canibalizacion'].apply(limpiar_canibalizacion)
                cols_to_show = ['fecha', 'keyword', 'posicion', 'url_encontrada', 'Conflicto Detectado']
            else:
                cols_to_show = ['fecha', 'keyword', 'posicion', 'url_encontrada', 'categoria_1', 'categoria_2']

            tabla_final['fecha'] = tabla_final['fecha'].dt.date
            
            st.dataframe(
                tabla_final[cols_to_show], 
                use_container_width=True,
                hide_index=True
            )
                
        else:
            st.warning("No hay datos para esta combinación de filtros.")
else:
    st.warning("No hay datos cargados.")