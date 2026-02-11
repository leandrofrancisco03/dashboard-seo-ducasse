import streamlit as st
import pandas as pd
import sqlalchemy
import plotly.express as px
import json

st.set_page_config(page_title="SEO Dashboard", layout="wide")

@st.cache_data(ttl=600)
def load_data():
    try:
        # Construimos la URL usando st.secrets
        db_user = st.secrets["DB_USER"]
        db_pass = st.secrets["DB_PASS"]
        db_host = st.secrets["DB_HOST"]
        db_name = st.secrets["DB_NAME"]

        engine = sqlalchemy.create_engine(f'postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:5432/{db_name}')

        # ... el resto de tu código de la query ...
        query = """
        SELECT fecha, keyword, posicion, categoria_1, categoria_2, categoria_3, categoria_4, 
               url_encontrada, es_canibalizacion, detalle_canibalizacion
        FROM rankings_historico ORDER BY fecha ASC
        """
        df = pd.read_sql(query, engine)
        # ... resto de tu lógica ...
        return df
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame()

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

        # 1. NIVEL 1 (Padre)
        opts_1 = ['Todos'] + sorted(df[df['categoria_1'] != ""]['categoria_1'].unique().tolist()) + ['(Sin Categoría)']
        sel_1 = col1.selectbox("Nivel 1", opts_1)

        # 2. NIVEL 2 (Hijo de 1)
        # Filtramos los datos disponibles según lo elegido en Nivel 1
        mask_1 = pd.Series(True, index=df.index)
        if sel_1 == '(Sin Categoría)': mask_1 = df['categoria_1'] == ""
        elif sel_1 != 'Todos': mask_1 = df['categoria_1'] == sel_1
        
        df_l2 = df[mask_1]
        opts_2 = ['Todos'] + sorted(df_l2[df_l2['categoria_2'] != ""]['categoria_2'].unique().tolist())
        # Si el usuario eligió Nivel 1, habilitamos Nivel 2, si no hay opciones, deshabilitamos
        sel_2 = col2.selectbox("Nivel 2", opts_2, disabled=(len(opts_2)==1))

        # 3. NIVEL 3 (Hijo de 2)
        mask_2 = pd.Series(True, index=df.index)
        if sel_2 != 'Todos': mask_2 = df['categoria_2'] == sel_2
        
        df_l3 = df[mask_1 & mask_2]
        opts_3 = ['Todos'] + sorted(df_l3[df_l3['categoria_3'] != ""]['categoria_3'].unique().tolist())
        sel_3 = col3.selectbox("Nivel 3", opts_3, disabled=(len(opts_3)==1))

        # 4. NIVEL 4 (Hijo de 3)
        mask_3 = pd.Series(True, index=df.index)
        if sel_3 != 'Todos': mask_3 = df['categoria_3'] == sel_3
        
        df_l4 = df[mask_1 & mask_2 & mask_3]
        opts_4 = ['Todos'] + sorted(df_l4[df_l4['categoria_4'] != ""]['categoria_4'].unique().tolist())
        sel_4 = col4.selectbox("Nivel 4", opts_4, disabled=(len(opts_4)==1))


        # --- APLICACIÓN FINAL DE FILTROS ---
        # Empezamos con el filtro de fecha
        final_mask = (df['fecha'].dt.date >= d_range[0]) & (df['fecha'].dt.date <= d_range[1])
        
        # Aplicamos la cascada de categorías
        if sel_1 == '(Sin Categoría)': final_mask &= (df['categoria_1'] == "")
        elif sel_1 != 'Todos': final_mask &= (df['categoria_1'] == sel_1)
        
        if sel_2 != 'Todos': final_mask &= (df['categoria_2'] == sel_2)
        if sel_3 != 'Todos': final_mask &= (df['categoria_3'] == sel_3)
        if sel_4 != 'Todos': final_mask &= (df['categoria_4'] == sel_4)
        
        if show_conflict: final_mask &= (df['es_canibalizacion'] == True)
            
        filtered_df = df[final_mask].copy()

        # --- MOSTRAR RESULTADOS ---
        if not filtered_df.empty:
            st.info(f"Se encontraron {len(filtered_df)} registros.")
            
            # 1. GRÁFICO (Siempre visible)
            fig_detail = px.line(
                filtered_df, x='fecha', y='posicion', color='keyword',
                line_shape='spline', markers=True, 
                hover_data=['url_encontrada'],
                height=500,
                title="Evolución de Posiciones"
            )
            fig_detail.update_yaxes(autorange="reversed", title="Posición (1 es Top)")
            st.plotly_chart(fig_detail, use_container_width=True)
            
            st.divider() # Separador visual
            
            # 2. TABLA INTELIGENTE
            st.subheader("📋 Detalle de Datos")

            # Función para limpiar el JSON de canibalización
            def limpiar_canibalizacion(row):
                if not row or row == {}: return ""
                try:
                    # Si viene como texto, convertir a dict
                    data = row if isinstance(row, dict) else json.loads(row)
                    items = data.get('data', [])
                    if not items: return ""
                    
                    # Formatear bonito: "Pos 7: url..."
                    conflictos = []
                    for item in items:
                        url_corta = item['url'].replace('https://', '').replace('http://', '')
                        conflictos.append(f" Pos {item['pos']}: {url_corta}")
                    return " | ".join(conflictos)
                except:
                    return "Error formato"

            # Preparamos los datos para la tabla
            tabla_final = filtered_df.copy()
            
            # Solo si el usuario quiere ver conflictos, procesamos esa columna pesada
            if show_conflict:
                st.warning("Mostrando detalles de conflictos de canibalización.")
                tabla_final['Conflicto Detectado'] = tabla_final['detalle_canibalizacion'].apply(limpiar_canibalizacion)
                
                # Columnas a mostrar en modo conflicto
                cols_to_show = ['fecha', 'keyword', 'posicion', 'url_encontrada', 'Conflicto Detectado']
            else:
                # Columnas a mostrar en modo normal (Limpio)
                cols_to_show = ['fecha', 'keyword', 'posicion', 'url_encontrada', 'categoria_1', 'categoria_2', 'categoria_3']

            # Formatear la fecha para que no salga la hora (00:00:00)
            tabla_final['fecha'] = tabla_final['fecha'].dt.date
            
            # Mostrar la tabla final limpia
            st.dataframe(
                tabla_final[cols_to_show], 
                use_container_width=True,
                hide_index=True # Ocultar el índice numérico feo (0, 1, 2...)
            )
                
        else:
            st.warning("No hay datos para esta combinación de filtros.")
else:
    st.warning("No hay datos cargados.")