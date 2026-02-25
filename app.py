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

# Función global para rangos de posiciones
def clasificar_rango(pos):
    if pd.isna(pos): return '> 100'
    if pos <= 3: return 'TOP 1-3'
    elif pos <= 10: return 'TOP 4-10'
    elif pos <= 20: return 'TOP 11-20'
    elif pos <= 100: return 'TOP 21-100'
    else: return '> 100'

st.title("🔎 Monitoreo de Posicionamiento Ducasse")

if not df.empty:
    tab1, tab2 = st.tabs(["🌎 Visión General", "🔬 Análisis Detallado"])

    # === PESTAÑA 1: VISIÓN GLOBAL ===
    with tab1:
        st.header("Salud del Proyecto")
        
        # Última fecha disponible para métricas "de hoy"
        last_date = df['fecha'].max()
        df_last_day = df[df['fecha'] == last_date].copy()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Posición Promedio", f"{df_last_day['posicion'].mean():.1f}")
        c2.metric("Total Keywords", df['keyword'].nunique())
        
        # Contamos cuántas keywords tienen conflicto HOY (o en la última fecha)
        conflict_count = df_last_day[df_last_day['es_canibalizacion'] == True]['keyword'].nunique()
        c3.metric("Conflictos Activos- Canibalizaciones hoy", conflict_count, delta_color="inverse")
        
        st.divider()
        
        # Gráfico de Tendencia General
        st.subheader("Evolución del Ranking Promedio Global")
        daily_avg = df.groupby('fecha')['posicion'].mean().reset_index()
        fig = px.line(daily_avg, x='fecha', y='posicion', markers=True, line_shape='spline')
        fig.update_yaxes(autorange="reversed", title="Posición Promedio (1 es mejor)")
        fig.update_traces(line_color='#00CC96', line_width=3)
        st.plotly_chart(fig, use_container_width=True)


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
        col1, col2, col3, col4 = st.columns(4)

        def get_mask(df_target, col_name, selection_list):
            if not selection_list:
                return pd.Series(True, index=df_target.index)
            else:
                query_vals = [x for x in selection_list if x != '(Sin Categoría)']
                include_blanks = '(Sin Categoría)' in selection_list
                mask_vals = df_target[col_name].isin(query_vals)
                mask_blanks = (df_target[col_name] == "") if include_blanks else pd.Series(False, index=df_target.index)
                return mask_vals | mask_blanks

        # --- NIVEL 1 ---
        opts_1_raw = sorted(df[df['categoria_1'] != ""]['categoria_1'].unique().tolist())
        has_empty_1 = "" in df['categoria_1'].unique()
        opts_1_display = opts_1_raw + (['(Sin Categoría)'] if has_empty_1 else [])
        sel_1 = col1.multiselect("Nivel 1", opts_1_display, placeholder="Elige opciones...")
        mask_1 = get_mask(df, 'categoria_1', sel_1)

        # --- NIVEL 2 ---
        df_l2 = df[mask_1]
        opts_2_raw = sorted(df_l2[df_l2['categoria_2'] != ""]['categoria_2'].unique().tolist())
        has_empty_2 = "" in df_l2['categoria_2'].unique()
        opts_2_display = opts_2_raw + (['(Sin Categoría)'] if has_empty_2 else [])
        disabled_2 = len(opts_2_display) == 0 or (len(opts_2_display) == 1 and opts_2_display[0] == '(Sin Categoría)' and not has_empty_2)
        sel_2 = col2.multiselect("Nivel 2", opts_2_display, disabled=disabled_2, placeholder="Elige opciones...")
        mask_2 = get_mask(df, 'categoria_2', sel_2)

        # --- NIVEL 3 ---
        df_l3 = df[mask_1 & mask_2]
        opts_3_raw = sorted(df_l3[df_l3['categoria_3'] != ""]['categoria_3'].unique().tolist())
        has_empty_3 = "" in df_l3['categoria_3'].unique()
        opts_3_display = opts_3_raw + (['(Sin Categoría)'] if has_empty_3 else [])
        disabled_3 = len(opts_3_display) == 0
        sel_3 = col3.multiselect("Nivel 3", opts_3_display, disabled=disabled_3, placeholder="Elige opciones...")
        mask_3 = get_mask(df, 'categoria_3', sel_3)

        # --- NIVEL 4 ---
        df_l4 = df[mask_1 & mask_2 & mask_3]
        opts_4_raw = sorted(df_l4[df_l4['categoria_4'] != ""]['categoria_4'].unique().tolist())
        has_empty_4 = "" in df_l4['categoria_4'].unique()
        opts_4_display = opts_4_raw + (['(Sin Categoría)'] if has_empty_4 else [])
        disabled_4 = len(opts_4_display) == 0
        sel_4 = col4.multiselect("Nivel 4", opts_4_display, disabled=disabled_4, placeholder="Elige opciones...")
        mask_4 = get_mask(df, 'categoria_4', sel_4)


        # --- APLICACIÓN FINAL DE FILTROS ---
        if len(d_range) == 2:
            start_date, end_date = d_range
            final_mask = (df['fecha'].dt.date >= start_date) & (df['fecha'].dt.date <= end_date)
        else:
            final_mask = pd.Series(True, index=df.index)

        final_mask &= mask_1 & mask_2 & mask_3 & mask_4
        if show_conflict: final_mask &= (df['es_canibalizacion'] == True)
            
        filtered_df = df[final_mask].copy()

        # --- RESULTADOS ---
        if not filtered_df.empty:
            st.info(f"Se encontraron {len(filtered_df)} registros para esta selección.")

            # ==========================================
            # 📊 MOVIDO AQUÍ: DISTRIBUCIÓN DE POSICIONES INTERACTIVA
            # ==========================================
            st.subheader("Distribución de Posiciones (Segmentado)")

            filtered_df['rango'] = filtered_df['posicion'].apply(clasificar_rango)
            
            fechas_ordenadas = sorted(filtered_df['fecha'].unique())
            last_date_filt = fechas_ordenadas[-1]
            fecha_anterior_filt = fechas_ordenadas[-2] if len(fechas_ordenadas) > 1 else last_date_filt
            
            df_last_day_filt = filtered_df[filtered_df['fecha'] == last_date_filt]
            df_prev_day_filt = filtered_df[filtered_df['fecha'] == fecha_anterior_filt]

            orden_rangos = ['TOP 1-3', 'TOP 4-10', 'TOP 11-20', 'TOP 21-100']
            colores_rangos = {
                'TOP 1-3': '#F4D03F',   # Amarillo
                'TOP 4-10': '#AED6F1',  # Celeste claro
                'TOP 11-20': '#85C1E9', # Azul intermedio
                'TOP 21-100': '#5DADE2' # Azul más oscuro
            }

            distribucion_hoy = df_last_day_filt['rango'].value_counts().reindex(orden_rangos).reset_index()
            distribucion_hoy.columns = ['Rango', 'Total']
            distribucion_hoy = distribucion_hoy.fillna(0)

            fig_donut = px.pie(
                distribucion_hoy, 
                values='Total', 
                names='Rango', 
                hole=0.55,
                color='Rango',
                color_discrete_map=colores_rangos
            )
            fig_donut.update_traces(textinfo='none', hovertemplate='<b>%{label}</b><br>Distribución de palabras clave: %{percent}')
            fig_donut.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=250)

            tendencias = filtered_df.groupby(['rango', 'fecha']).size().unstack(fill_value=0)

            datos_tabla = []
            for rango in orden_rangos:
                tendencia_historica = tendencias.loc[rango].tolist() if rango in tendencias.index else [0]
                kw_hoy = set(df_last_day_filt[df_last_day_filt['rango'] == rango]['keyword'])
                kw_ayer = set(df_prev_day_filt[df_prev_day_filt['rango'] == rango]['keyword'])
                
                nuevas = len(kw_hoy - kw_ayer)
                perdidas = len(kw_ayer - kw_hoy)

                datos_tabla.append({
                    "Rango": f"🟢 {rango}" if rango == 'TOP 1-3' else f"🔵 {rango}",
                    "Total": len(kw_hoy),
                    "Nuevas": f"+{nuevas}" if nuevas > 0 else "0",
                    "Perdidas": f"-{perdidas}" if perdidas > 0 else "0",
                    "Tendencia": tendencia_historica
                })

            df_tabla_final = pd.DataFrame(datos_tabla)

            col_donut, col_tabla = st.columns([1, 2.5], gap="medium")

            with col_donut:
                st.plotly_chart(fig_donut, use_container_width=True)

            with col_tabla:
                st.write("") 
                st.dataframe(
                    df_tabla_final,
                    column_config={
                        "Rango": st.column_config.TextColumn("Distribución de posiciones"),
                        "Total": st.column_config.NumberColumn("Total"),
                        "Nuevas": st.column_config.TextColumn("Nuevas"),
                        "Perdidas": st.column_config.TextColumn("Perdidas"),
                        "Tendencia": st.column_config.AreaChartColumn("Tendencia", y_min=0)
                    },
                    hide_index=True,
                    use_container_width=True
                )

            st.divider()
            
            # === CONTROL DE VISTA (SWITCH PARA LINE CHART) ===
            col_graph, col_toggle = st.columns([4, 1])
            with col_toggle:
                st.write("") 
                st.write("") 
                ver_detalle = st.toggle("📈 Ver Detalle Keywords", value=False, help="Activa para ver línea por línea")

            # === LÓGICA DEL GRÁFICO (Líneas) ===
            if not ver_detalle:
                df_chart = filtered_df.groupby('fecha')['posicion'].mean().reset_index()
                
                if sel_4: nombre = f"Promedio: {', '.join(sel_4)}"
                elif sel_3: nombre = f"Promedio: {', '.join(sel_3)}"
                elif sel_2: nombre = f"Promedio: {', '.join(sel_2)}"
                elif sel_1: nombre = f"Promedio: {', '.join(sel_1)}"
                else: nombre = "Promedio General Segmentado"
                
                df_chart['keyword'] = nombre
                titulo_grafico = "Evolución Promedio (Vista Resumida)"
                color_map = None 
            else:
                df_chart = filtered_df
                titulo_grafico = "Evolución Detallada por Keyword"
                color_map = None

            fig_detail = px.line(
                df_chart, 
                x='fecha', 
                y='posicion', 
                color='keyword', 
                line_shape='spline', 
                markers=True, 
                color_discrete_sequence=color_map,
                height=500,
                title=titulo_grafico
            )
            
            fig_detail.update_yaxes(autorange="reversed", title="Posición (1 es Top)")
            fig_detail.update_layout(hovermode="x unified")
            
            st.plotly_chart(fig_detail, use_container_width=True)
            
            st.divider()
            
            # 2. TABLA DE DATOS (Raw Data)
            st.subheader("📋 Detalle de Datos Raw")

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
                st.warning("⚠️ Mostrando detalles de conflictos de canibalización.")
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