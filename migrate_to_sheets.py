"""
Script de migración de SQLite a Google Sheets
Ejecuta este script UNA VEZ para migrar tus datos existentes
"""

import sqlite3
import pandas as pd
from google_sheets_db import GoogleSheetsDB
import streamlit as st

def migrar_sqlite_a_google_sheets(db_path='contabilidad.db'):
    """
    Migrar todos los datos de SQLite a Google Sheets
    
    Args:
        db_path: Ruta al archivo de base de datos SQLite
    """
    
    st.title("🔄 Migración de SQLite a Google Sheets")
    
    # Verificar que existe el archivo SQLite
    import os
    if not os.path.exists(db_path):
        st.error(f"❌ No se encontró el archivo {db_path}")
        st.info("Si no tienes datos que migrar, puedes inicializar Google Sheets directamente.")
        return
    
    st.info("📊 Conectando con SQLite...")
    conn = sqlite3.connect(db_path)
    
    st.info("☁️ Conectando con Google Sheets...")
    gs_db = GoogleSheetsDB()
    
    # Inicializar las tablas en Google Sheets
    st.info("🔨 Creando estructura de tablas...")
    gs_db.inicializar_todas_las_tablas()
    
    try:
        # ==================== MIGRAR GASTOS MENSUALES ====================
        st.subheader("1️⃣ Migrando gastos mensuales...")
        gastos_df = pd.read_sql_query("SELECT * FROM gastos_mensuales", conn)
        
        if not gastos_df.empty:
            worksheet = gs_db._get_worksheet('gastos_mensuales')
            
            # Limpiar datos existentes (excepto header)
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
            
            # Convertir DataFrame a lista de listas
            data_to_insert = gastos_df.values.tolist()
            
            # Insertar por lotes
            if data_to_insert:
                worksheet.append_rows(data_to_insert)
            
            st.success(f"✅ Migrados {len(gastos_df)} gastos mensuales")
        else:
            st.warning("⚠️ No hay gastos mensuales para migrar")
        
        # ==================== MIGRAR MONTOS MENSUALES ====================
        st.subheader("2️⃣ Migrando montos mensuales...")
        try:
            montos_df = pd.read_sql_query("SELECT * FROM montos_mensuales", conn)
            
            if not montos_df.empty:
                worksheet = gs_db._get_worksheet('montos_mensuales')
                
                if worksheet.row_count > 1:
                    worksheet.delete_rows(2, worksheet.row_count)
                
                data_to_insert = montos_df.values.tolist()
                
                if data_to_insert:
                    worksheet.append_rows(data_to_insert)
                
                st.success(f"✅ Migrados {len(montos_df)} montos mensuales")
            else:
                st.warning("⚠️ No hay montos mensuales para migrar")
        except Exception as e:
            st.warning(f"⚠️ Tabla montos_mensuales no existe o está vacía: {e}")
        
        # ==================== MIGRAR PAGOS ====================
        st.subheader("3️⃣ Migrando pagos...")
        try:
            pagos_df = pd.read_sql_query("SELECT * FROM pagos", conn)
            
            if not pagos_df.empty:
                worksheet = gs_db._get_worksheet('pagos')
                
                if worksheet.row_count > 1:
                    worksheet.delete_rows(2, worksheet.row_count)
                
                data_to_insert = pagos_df.values.tolist()
                
                if data_to_insert:
                    worksheet.append_rows(data_to_insert)
                
                st.success(f"✅ Migrados {len(pagos_df)} pagos")
            else:
                st.warning("⚠️ No hay pagos para migrar")
        except Exception as e:
            st.warning(f"⚠️ Tabla pagos no existe o está vacía: {e}")
        
        # ==================== MIGRAR GRUPOS DE DISTRIBUCIÓN ====================
        st.subheader("4️⃣ Migrando grupos de distribución...")
        try:
            grupos_df = pd.read_sql_query("SELECT * FROM grupos_distribucion", conn)
            
            if not grupos_df.empty:
                worksheet = gs_db._get_worksheet('grupos_distribucion')
                
                if worksheet.row_count > 1:
                    worksheet.delete_rows(2, worksheet.row_count)
                
                data_to_insert = grupos_df.values.tolist()
                
                if data_to_insert:
                    worksheet.append_rows(data_to_insert)
                
                st.success(f"✅ Migrados {len(grupos_df)} grupos")
            else:
                st.warning("⚠️ No hay grupos para migrar")
        except Exception as e:
            st.warning(f"⚠️ Tabla grupos_distribucion no existe o está vacía: {e}")
        
        # ==================== MIGRAR GASTOS EN GRUPO ====================
        st.subheader("5️⃣ Migrando gastos en grupo...")
        try:
            gastos_grupo_df = pd.read_sql_query("SELECT * FROM gastos_en_grupo", conn)
            
            if not gastos_grupo_df.empty:
                worksheet = gs_db._get_worksheet('gastos_en_grupo')
                
                if worksheet.row_count > 1:
                    worksheet.delete_rows(2, worksheet.row_count)
                
                data_to_insert = gastos_grupo_df.values.tolist()
                
                if data_to_insert:
                    worksheet.append_rows(data_to_insert)
                
                st.success(f"✅ Migrados {len(gastos_grupo_df)} registros de gastos en grupo")
            else:
                st.warning("⚠️ No hay gastos en grupo para migrar")
        except Exception as e:
            st.warning(f"⚠️ Tabla gastos_en_grupo no existe o está vacía: {e}")
        
        # ==================== RESUMEN ====================
        st.success("🎉 ¡Migración completada exitosamente!")
        st.balloons()
        
        st.info("""
        ### ✅ Próximos pasos:
        
        1. **Verifica los datos** en tu Google Sheet
        2. **Prueba la aplicación** para asegurarte de que todo funciona
        3. **Haz backup** del archivo `contabilidad.db` original
        4. **Elimina** el archivo SQLite si ya no lo necesitas
        5. **Actualiza** la aplicación principal para usar Google Sheets
        """)
        
    except Exception as e:
        st.error(f"❌ Error durante la migración: {str(e)}")
        st.exception(e)
    
    finally:
        conn.close()

def main():
    """Función principal"""
    
    st.set_page_config(
        page_title="Migración a Google Sheets",
        page_icon="🔄",
        layout="wide"
    )
    
    st.title("🔄 Migración de SQLite a Google Sheets")
    
    st.markdown("""
    Este script migrará todos tus datos existentes de SQLite a Google Sheets.
    
    ### ⚠️ Antes de comenzar:
    
    1. ✅ Configura Google Sheets siguiendo las instrucciones en `GOOGLE_SHEETS_SETUP.md`
    2. ✅ Crea el archivo `.streamlit/secrets.toml` con tus credenciales
    3. ✅ Asegúrate de que el archivo `contabilidad.db` existe
    4. ✅ Haz un backup de tu base de datos SQLite
    
    ### 📋 Este script:
    
    - Lee todos los datos de tu base de datos SQLite
    - Crea las tablas necesarias en Google Sheets
    - Copia todos los datos a Google Sheets
    - NO modifica ni elimina tu base de datos SQLite original
    
    ---
    """)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        if st.button("🚀 Iniciar Migración", type="primary", use_container_width=True):
            migrar_sqlite_a_google_sheets()

if __name__ == "__main__":
    main()
