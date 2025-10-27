"""
Módulo para manejar Google Sheets como base de datos
Reemplaza SQLite con Google Sheets para persistencia en la nube
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
from datetime import datetime

class GoogleSheetsDB:
    """Clase para manejar la conexión y operaciones con Google Sheets"""
    
    def __init__(self):
        """Inicializar conexión con Google Sheets usando secrets de Streamlit"""
        self.client = None
        self.spreadsheet = None
        self._connect()
    
    def _connect(self):
        """Establecer conexión con Google Sheets"""
        try:
            # Configurar las credenciales desde st.secrets
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Cargar credenciales desde secrets
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self.client = gspread.authorize(creds)
            
            # Abrir el spreadsheet
            spreadsheet_url = st.secrets["spreadsheet_url"]
            self.spreadsheet = self.client.open_by_url(spreadsheet_url)
            
        except Exception as e:
            st.error(f"❌ Error conectando con Google Sheets: {str(e)}")
            st.info("Asegúrate de configurar los secrets en Streamlit Cloud")
    
    def _get_worksheet(self, sheet_name, create_if_missing=True):
        """Obtener o crear una hoja específica"""
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            if create_if_missing:
                return self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
            return None
    
    def _ensure_table_exists(self, table_name, columns):
        """Asegurar que la tabla (hoja) existe con sus columnas"""
        worksheet = self._get_worksheet(table_name)
        
        # Si la hoja está vacía, agregar encabezados
        if worksheet.row_count == 0 or not worksheet.row_values(1):
            worksheet.insert_row(columns, 1)
        
        return worksheet
    
    # ==================== GASTOS MENSUALES ====================
    
    def crear_tabla_gastos_mensuales(self):
        """Crear tabla de gastos mensuales"""
        columns = ['id', 'concepto', 'monto', 'frecuencia', 'distribucion_ricardo', 'distribucion_wendy']
        self._ensure_table_exists('gastos_mensuales', columns)
    
    def insertar_gasto_mensual(self, concepto, monto, frecuencia, dist_ricardo, dist_wendy):
        """Insertar un nuevo gasto mensual"""
        worksheet = self._get_worksheet('gastos_mensuales')
        
        # Obtener el siguiente ID
        all_values = worksheet.get_all_values()
        next_id = len(all_values)  # Incluye el header
        
        # Insertar fila
        row = [next_id, concepto, monto, frecuencia, dist_ricardo, dist_wendy]
        worksheet.append_row(row)
        
        return next_id
    
    def obtener_gastos_mensuales(self):
        """Obtener todos los gastos mensuales como DataFrame"""
        worksheet = self._get_worksheet('gastos_mensuales')
        data = worksheet.get_all_records()
        
        if not data:
            return pd.DataFrame(columns=['id', 'concepto', 'monto', 'frecuencia', 
                                        'distribucion_ricardo', 'distribucion_wendy'])
        
        df = pd.DataFrame(data)
        # Convertir tipos de datos
        df['monto'] = pd.to_numeric(df['monto'], errors='coerce')
        df['distribucion_ricardo'] = pd.to_numeric(df['distribucion_ricardo'], errors='coerce')
        df['distribucion_wendy'] = pd.to_numeric(df['distribucion_wendy'], errors='coerce')
        
        return df
    
    def actualizar_gasto_mensual(self, gasto_id, concepto, monto, frecuencia, dist_ricardo, dist_wendy):
        """Actualizar un gasto mensual existente"""
        worksheet = self._get_worksheet('gastos_mensuales')
        
        # Buscar la fila con el ID
        cell = worksheet.find(str(gasto_id))
        if cell:
            row_num = cell.row
            worksheet.update(f'A{row_num}:F{row_num}', 
                           [[gasto_id, concepto, monto, frecuencia, dist_ricardo, dist_wendy]])
    
    def eliminar_gasto_mensual(self, gasto_id):
        """Eliminar un gasto mensual"""
        worksheet = self._get_worksheet('gastos_mensuales')
        
        # Buscar y eliminar la fila
        cell = worksheet.find(str(gasto_id))
        if cell:
            worksheet.delete_rows(cell.row)
    
    # ==================== MONTOS MENSUALES ====================
    
    def crear_tabla_montos_mensuales(self):
        """Crear tabla de montos mensuales"""
        columns = ['id', 'gasto_id', 'mes', 'anio', 'monto_ricardo', 'monto_wendy']
        self._ensure_table_exists('montos_mensuales', columns)
    
    def obtener_montos_mensuales(self, mes, anio):
        """Obtener montos mensuales para un mes/año específico"""
        worksheet = self._get_worksheet('montos_mensuales')
        data = worksheet.get_all_records()
        
        if not data:
            return pd.DataFrame(columns=['id', 'gasto_id', 'mes', 'anio', 'monto_ricardo', 'monto_wendy'])
        
        df = pd.DataFrame(data)
        df = df[(df['mes'] == mes) & (df['anio'] == anio)]
        
        # Convertir tipos
        df['monto_ricardo'] = pd.to_numeric(df['monto_ricardo'], errors='coerce')
        df['monto_wendy'] = pd.to_numeric(df['monto_wendy'], errors='coerce')
        
        return df
    
    def actualizar_monto_mensual(self, gasto_id, mes, anio, monto_ricardo, monto_wendy):
        """Actualizar o insertar monto mensual"""
        worksheet = self._get_worksheet('montos_mensuales')
        all_values = worksheet.get_all_records()
        
        # Buscar si existe
        found = False
        for idx, row in enumerate(all_values, start=2):  # Start at 2 (skip header)
            if (row['gasto_id'] == gasto_id and 
                row['mes'] == mes and 
                row['anio'] == anio):
                # Actualizar
                worksheet.update(f'A{idx}:F{idx}', 
                               [[row['id'], gasto_id, mes, anio, monto_ricardo, monto_wendy]])
                found = True
                break
        
        if not found:
            # Insertar nuevo
            next_id = len(all_values) + 1
            worksheet.append_row([next_id, gasto_id, mes, anio, monto_ricardo, monto_wendy])
    
    # ==================== PAGOS ====================
    
    def crear_tabla_pagos(self):
        """Crear tabla de pagos"""
        columns = ['id', 'gasto_id', 'mes', 'anio', 'quien_pago', 'monto_pagado', 'fecha_pago']
        self._ensure_table_exists('pagos', columns)
    
    def insertar_pago(self, gasto_id, mes, anio, quien_pago, monto_pagado):
        """Insertar un nuevo pago"""
        worksheet = self._get_worksheet('pagos')
        
        all_values = worksheet.get_all_values()
        next_id = len(all_values)
        
        fecha_pago = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        row = [next_id, gasto_id, mes, anio, quien_pago, monto_pagado, fecha_pago]
        worksheet.append_row(row)
        
        return next_id
    
    def obtener_pagos(self, mes, anio):
        """Obtener pagos de un mes/año específico"""
        worksheet = self._get_worksheet('pagos')
        data = worksheet.get_all_records()
        
        if not data:
            return pd.DataFrame(columns=['id', 'gasto_id', 'mes', 'anio', 
                                        'quien_pago', 'monto_pagado', 'fecha_pago'])
        
        df = pd.DataFrame(data)
        df = df[(df['mes'] == mes) & (df['anio'] == anio)]
        
        df['monto_pagado'] = pd.to_numeric(df['monto_pagado'], errors='coerce')
        
        return df
    
    def obtener_total_pagado(self, gasto_id, mes, anio, quien):
        """Obtener el total pagado por una persona para un gasto específico"""
        worksheet = self._get_worksheet('pagos')
        data = worksheet.get_all_records()
        
        if not data:
            return 0
        
        df = pd.DataFrame(data)
        df = df[(df['gasto_id'] == gasto_id) & 
                (df['mes'] == mes) & 
                (df['anio'] == anio) & 
                (df['quien_pago'] == quien)]
        
        if df.empty:
            return 0
        
        df['monto_pagado'] = pd.to_numeric(df['monto_pagado'], errors='coerce')
        return df['monto_pagado'].sum()
    
    # ==================== GRUPOS DE DISTRIBUCIÓN ====================
    
    def crear_tabla_grupos_distribucion(self):
        """Crear tabla de grupos de distribución"""
        columns = ['id', 'nombre_grupo', 'distribucion_ricardo', 'distribucion_wendy']
        self._ensure_table_exists('grupos_distribucion', columns)
    
    def obtener_grupos_distribucion(self):
        """Obtener todos los grupos de distribución"""
        worksheet = self._get_worksheet('grupos_distribucion')
        data = worksheet.get_all_records()
        
        if not data:
            return pd.DataFrame(columns=['id', 'nombre_grupo', 'distribucion_ricardo', 'distribucion_wendy'])
        
        df = pd.DataFrame(data)
        df['distribucion_ricardo'] = pd.to_numeric(df['distribucion_ricardo'], errors='coerce')
        df['distribucion_wendy'] = pd.to_numeric(df['distribucion_wendy'], errors='coerce')
        
        return df
    
    # ==================== GASTOS EN GRUPO ====================
    
    def crear_tabla_gastos_en_grupo(self):
        """Crear tabla de gastos en grupo"""
        columns = ['id', 'grupo_id', 'gasto_id']
        self._ensure_table_exists('gastos_en_grupo', columns)
    
    def obtener_gastos_en_grupo(self, grupo_id):
        """Obtener todos los gastos de un grupo"""
        worksheet = self._get_worksheet('gastos_en_grupo')
        data = worksheet.get_all_records()
        
        if not data:
            return []
        
        df = pd.DataFrame(data)
        df = df[df['grupo_id'] == grupo_id]
        
        return df['gasto_id'].tolist()
    
    # ==================== INICIALIZACIÓN ====================
    
    def inicializar_todas_las_tablas(self):
        """Crear todas las tablas necesarias"""
        self.crear_tabla_gastos_mensuales()
        self.crear_tabla_montos_mensuales()
        self.crear_tabla_pagos()
        self.crear_tabla_grupos_distribucion()
        self.crear_tabla_gastos_en_grupo()
        st.success("✅ Todas las tablas de Google Sheets han sido inicializadas")
