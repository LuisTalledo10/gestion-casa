"""
Aplicación de Gestión de Contabilidad Doméstica
Sistema de gastos compartidos entre Ricardo y Wendy

Instalación de dependencias:
pip install streamlit plotly pandas

Para ejecutar la aplicación:
streamlit run app.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import calendar
from math import ceil
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import io

# ==================== CONFIGURACIÓN DE LA BASE DE DATOS ====================

def conectar_db():
    """
    Conecta a la base de datos SQLite y crea las tablas si no existen.
    Returns:
        conn: Objeto de conexión a la base de datos
    """
    conn = sqlite3.connect('contabilidad.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Crear tabla de gastos mensuales (solo concepto y frecuencia)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos_mensuales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto TEXT NOT NULL,
            monto_total REAL NOT NULL,
            frecuencia TEXT NOT NULL,
            tipo_monto TEXT DEFAULT 'fijo',
            tipo_distribucion TEXT DEFAULT '50/50',
            monto_fijo_ricardo REAL DEFAULT NULL,
            monto_fijo_wendy REAL DEFAULT NULL,
            porcentaje_ricardo REAL DEFAULT 50.0,
            grupo TEXT DEFAULT NULL,
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT NOT NULL
        )
    ''')
    
    # Crear tabla de montos por mes (para gastos que varían)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS montos_mensuales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gasto_id INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            anio INTEGER NOT NULL,
            monto_total REAL NOT NULL,
            fecha_registro TEXT NOT NULL,
            FOREIGN KEY (gasto_id) REFERENCES gastos_mensuales(id),
            UNIQUE(gasto_id, mes, anio)
        )
    ''')
    
    # Crear tabla de pagos individuales
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gasto_id INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            anio INTEGER NOT NULL,
            quien_pago TEXT NOT NULL,
            monto_pagado REAL NOT NULL,
            fecha_pago TEXT NOT NULL,
            semana INTEGER DEFAULT NULL,
            FOREIGN KEY (gasto_id) REFERENCES gastos_mensuales(id)
        )
    ''')
    
    # Crear tabla de grupos de distribución
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grupos_distribucion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            monto_fijo_ricardo REAL DEFAULT NULL,
            monto_fijo_wendy REAL DEFAULT NULL,
            quien_paga_fijo TEXT NOT NULL,
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Crear tabla de gastos en grupo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos_en_grupo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupo_id INTEGER NOT NULL,
            gasto_id INTEGER NOT NULL,
            FOREIGN KEY (grupo_id) REFERENCES grupos_distribucion(id),
            FOREIGN KEY (gasto_id) REFERENCES gastos_mensuales(id),
            UNIQUE(grupo_id, gasto_id)
        )
    ''')
    
    conn.commit()
    return conn

# ==================== FUNCIONES CRUD GASTOS MENSUALES ====================

def crear_gasto_mensual(conn, concepto, monto_total, frecuencia, tipo_monto='fijo',
                       tipo_distribucion='50/50', monto_fijo_ricardo=None, monto_fijo_wendy=None,
                       porcentaje_ricardo=50.0, grupo=None):
    """
    Crea un nuevo gasto mensual recurrente con distribución personalizada.
    tipo_monto: 'fijo' o 'variable'
    tipo_distribucion: '50/50', 'fijo_ricardo', 'fijo_wendy', 'personalizado'
    """
    cursor = conn.cursor()
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO gastos_mensuales (concepto, monto_total, frecuencia, tipo_monto,
                                      tipo_distribucion, monto_fijo_ricardo, monto_fijo_wendy,
                                      porcentaje_ricardo, grupo, fecha_creacion)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (concepto, monto_total, frecuencia, tipo_monto, tipo_distribucion,
          monto_fijo_ricardo, monto_fijo_wendy, porcentaje_ricardo, grupo, fecha_actual))
    conn.commit()
    return True

def leer_gastos_mensuales(conn, solo_activos=True):
    """
    Lee todos los gastos mensuales.
    """
    if solo_activos:
        query = "SELECT * FROM gastos_mensuales WHERE activo = 1 ORDER BY concepto"
    else:
        query = "SELECT * FROM gastos_mensuales ORDER BY concepto"
    df = pd.read_sql_query(query, conn)
    return df

def actualizar_gasto_mensual(conn, id_gasto, concepto, monto_total, frecuencia, tipo_monto,
                            tipo_distribucion='50/50', monto_fijo_ricardo=None, monto_fijo_wendy=None,
                            porcentaje_ricardo=50.0, grupo=None):
    """
    Actualiza un gasto mensual con distribución personalizada.
    """
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE gastos_mensuales
        SET concepto = ?, monto_total = ?, frecuencia = ?, tipo_monto = ?,
            tipo_distribucion = ?, monto_fijo_ricardo = ?, monto_fijo_wendy = ?,
            porcentaje_ricardo = ?, grupo = ?
        WHERE id = ?
    ''', (concepto, monto_total, frecuencia, tipo_monto, tipo_distribucion,
          monto_fijo_ricardo, monto_fijo_wendy, porcentaje_ricardo, grupo, id_gasto))
    conn.commit()
    return cursor.rowcount > 0

def desactivar_gasto_mensual(conn, id_gasto):
    """
    Desactiva un gasto mensual (no lo borra, solo lo marca como inactivo).
    """
    cursor = conn.cursor()
    cursor.execute('UPDATE gastos_mensuales SET activo = 0 WHERE id = ?', (id_gasto,))
    conn.commit()
    return cursor.rowcount > 0

# ==================== FUNCIONES DE MONTOS MENSUALES ====================

def obtener_monto_del_mes(conn, gasto_id, mes, anio):
    """
    Obtiene el monto específico de un gasto para un mes.
    Si no existe, devuelve el monto base del gasto.
    """
    cursor = conn.cursor()
    
    # Primero buscar si hay un monto específico para este mes
    cursor.execute('''
        SELECT monto_total FROM montos_mensuales
        WHERE gasto_id = ? AND mes = ? AND anio = ?
    ''', (gasto_id, mes, anio))
    
    resultado = cursor.fetchone()
    
    if resultado:
        return resultado[0]
    else:
        # Si no existe, devolver el monto base
        cursor.execute('SELECT monto_total FROM gastos_mensuales WHERE id = ?', (gasto_id,))
        resultado_base = cursor.fetchone()
        return resultado_base[0] if resultado_base else 0.0

def establecer_monto_del_mes(conn, gasto_id, mes, anio, monto):
    """
    Establece un monto específico para un gasto en un mes determinado.
    Si ya existe, lo actualiza; si no existe, lo crea.
    """
    cursor = conn.cursor()
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # Verificar si ya existe un registro para este gasto en este mes
        cursor.execute('''
            SELECT id FROM montos_mensuales
            WHERE gasto_id = ? AND mes = ? AND anio = ?
        ''', (gasto_id, mes, anio))
        
        existe = cursor.fetchone()
        
        if existe:
            # Actualizar el registro existente
            cursor.execute('''
                UPDATE montos_mensuales
                SET monto_total = ?, fecha_registro = ?
                WHERE gasto_id = ? AND mes = ? AND anio = ?
            ''', (monto, fecha_actual, gasto_id, mes, anio))
        else:
            # Insertar nuevo registro
            cursor.execute('''
                INSERT INTO montos_mensuales (gasto_id, mes, anio, monto_total, fecha_registro)
                VALUES (?, ?, ?, ?, ?)
            ''', (gasto_id, mes, anio, monto, fecha_actual))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error al establecer monto del mes: {e}")
        return False

def obtener_montos_configurados(conn, mes, anio):
    """
    Obtiene todos los gastos con sus montos para un mes específico.
    Si el gasto es 'variable', busca el monto personalizado del mes.
    Si el gasto es 'fijo', siempre usa el monto base.
    Incluye información de distribución personalizada.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT g.id, g.concepto, g.frecuencia, g.tipo_monto,
               CASE 
                   WHEN g.tipo_monto = 'variable' THEN COALESCE(m.monto_total, g.monto_total)
                   ELSE g.monto_total
               END as monto_total,
               CASE WHEN m.id IS NOT NULL THEN 1 ELSE 0 END as personalizado,
               g.tipo_distribucion, g.monto_fijo_ricardo, g.monto_fijo_wendy,
               g.porcentaje_ricardo, g.grupo
        FROM gastos_mensuales g
        LEFT JOIN montos_mensuales m ON g.id = m.gasto_id AND m.mes = ? AND m.anio = ?
        WHERE g.activo = 1
        ORDER BY g.grupo, g.concepto
    """, (mes, anio))
    
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=columns)
    return df

# ==================== FUNCIONES AUXILIARES PARA FRECUENCIAS ====================

def calcular_distribucion_pago(gasto, monto_total_mes):
    """
    Calcula cuánto debe pagar cada persona según el tipo de distribución.
    Returns: (monto_ricardo, monto_wendy)
    """
    tipo_dist = gasto.get('tipo_distribucion', '50/50')
    
    if tipo_dist == 'fijo_ricardo':
        # Ricardo paga monto fijo, Wendy paga la diferencia
        monto_ricardo = gasto.get('monto_fijo_ricardo', 0) or 0
        monto_wendy = max(0, monto_total_mes - monto_ricardo)
    elif tipo_dist == 'fijo_wendy':
        # Wendy paga monto fijo, Ricardo paga la diferencia
        monto_wendy = gasto.get('monto_fijo_wendy', 0) or 0
        monto_ricardo = max(0, monto_total_mes - monto_wendy)
    elif tipo_dist == 'personalizado':
        # Porcentaje personalizado
        porcentaje_r = gasto.get('porcentaje_ricardo', 50.0) or 50.0
        monto_ricardo = monto_total_mes * (porcentaje_r / 100)
        monto_wendy = monto_total_mes - monto_ricardo
    else:  # '50/50' (por defecto)
        monto_ricardo = monto_total_mes / 2
        monto_wendy = monto_total_mes / 2
    
    return (monto_ricardo, monto_wendy)

# ==================== FUNCIONES DE GRUPOS DE DISTRIBUCIÓN ====================

def crear_grupo_distribucion(conn, nombre, descripcion, quien_paga_fijo, monto_fijo, gastos_ids):
    """
    Crea un grupo de distribución y asocia gastos a él.
    quien_paga_fijo: 'Ricardo' o 'Wendy'
    monto_fijo: el monto fijo que paga esa persona
    gastos_ids: lista de IDs de gastos a agrupar
    """
    cursor = conn.cursor()
    
    try:
        # Crear el grupo
        monto_r = monto_fijo if quien_paga_fijo == 'Ricardo' else None
        monto_w = monto_fijo if quien_paga_fijo == 'Wendy' else None
        
        cursor.execute('''
            INSERT INTO grupos_distribucion 
            (nombre, descripcion, monto_fijo_ricardo, monto_fijo_wendy, quien_paga_fijo)
            VALUES (?, ?, ?, ?, ?)
        ''', (nombre, descripcion, monto_r, monto_w, quien_paga_fijo))
        
        grupo_id = cursor.lastrowid
        
        # Asociar gastos al grupo
        for gasto_id in gastos_ids:
            cursor.execute('''
                INSERT INTO gastos_en_grupo (grupo_id, gasto_id)
                VALUES (?, ?)
            ''', (grupo_id, gasto_id))
            
            # Actualizar el tipo de distribución del gasto a 'agrupado'
            cursor.execute('''
                UPDATE gastos_mensuales 
                SET tipo_distribucion = 'agrupado'
                WHERE id = ?
            ''', (gasto_id,))
        
        conn.commit()
        return grupo_id
    except Exception as e:
        conn.rollback()
        print(f"Error al crear grupo: {e}")
        return None

def obtener_grupos_distribucion(conn):
    """
    Obtiene todos los grupos de distribución activos con sus gastos.
    """
    cursor = conn.cursor()
    cursor.execute('''
        SELECT gd.id, gd.nombre, gd.descripcion, gd.monto_fijo_ricardo, 
               gd.monto_fijo_wendy, gd.quien_paga_fijo
        FROM grupos_distribucion gd
        WHERE gd.activo = 1
        ORDER BY gd.nombre
    ''')
    
    grupos = []
    for row in cursor.fetchall():
        grupo_id, nombre, desc, monto_r, monto_w, quien_paga = row
        
        # Obtener gastos del grupo
        cursor.execute('''
            SELECT g.id, g.concepto, g.monto_total
            FROM gastos_mensuales g
            INNER JOIN gastos_en_grupo ge ON g.id = ge.gasto_id
            WHERE ge.grupo_id = ? AND g.activo = 1
        ''', (grupo_id,))
        
        gastos = cursor.fetchall()
        
        grupos.append({
            'id': grupo_id,
            'nombre': nombre,
            'descripcion': desc,
            'monto_fijo_ricardo': monto_r,
            'monto_fijo_wendy': monto_w,
            'quien_paga_fijo': quien_paga,
            'gastos': gastos
        })
    
    return grupos

def obtener_gastos_de_grupo(conn, grupo_id):
    """
    Obtiene los gastos que pertenecen a un grupo.
    """
    cursor = conn.cursor()
    cursor.execute('''
        SELECT g.id, g.concepto, g.monto_total, g.tipo_monto
        FROM gastos_mensuales g
        INNER JOIN gastos_en_grupo ge ON g.id = ge.gasto_id
        WHERE ge.grupo_id = ? AND g.activo = 1
    ''', (grupo_id,))
    
    return cursor.fetchall()

def actualizar_grupo_distribucion(conn, grupo_id, nombre, descripcion, quien_paga_fijo, monto_fijo):
    """
    Actualiza un grupo de distribución.
    """
    cursor = conn.cursor()
    
    monto_r = monto_fijo if quien_paga_fijo == 'Ricardo' else None
    monto_w = monto_fijo if quien_paga_fijo == 'Wendy' else None
    
    cursor.execute('''
        UPDATE grupos_distribucion
        SET nombre = ?, descripcion = ?, monto_fijo_ricardo = ?, 
            monto_fijo_wendy = ?, quien_paga_fijo = ?
        WHERE id = ?
    ''', (nombre, descripcion, monto_r, monto_w, quien_paga_fijo, grupo_id))
    
    conn.commit()
    return cursor.rowcount > 0

def agregar_gasto_a_grupo(conn, grupo_id, gasto_id):
    """
    Agrega un gasto existente a un grupo.
    """
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO gastos_en_grupo (grupo_id, gasto_id)
            VALUES (?, ?)
        ''', (grupo_id, gasto_id))
        
        # Actualizar tipo_distribucion a 'agrupado'
        cursor.execute('''
            UPDATE gastos_mensuales 
            SET tipo_distribucion = 'agrupado'
            WHERE id = ?
        ''', (gasto_id,))
        
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def remover_gasto_de_grupo(conn, grupo_id, gasto_id):
    """
    Remueve un gasto de un grupo.
    """
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM gastos_en_grupo
        WHERE grupo_id = ? AND gasto_id = ?
    ''', (grupo_id, gasto_id))
    
    # Cambiar tipo_distribucion a '50/50' por defecto
    cursor.execute('''
        UPDATE gastos_mensuales 
        SET tipo_distribucion = '50/50'
        WHERE id = ?
    ''', (gasto_id,))
    
    conn.commit()
    return cursor.rowcount > 0

def eliminar_grupo_distribucion(conn, grupo_id):
    """
    Elimina un grupo de distribución (lo marca como inactivo).
    """
    cursor = conn.cursor()
    
    # Cambiar todos los gastos del grupo a tipo '50/50'
    cursor.execute('''
        UPDATE gastos_mensuales 
        SET tipo_distribucion = '50/50'
        WHERE id IN (
            SELECT gasto_id FROM gastos_en_grupo WHERE grupo_id = ?
        )
    ''', (grupo_id,))
    
    # Marcar grupo como inactivo
    cursor.execute('''
        UPDATE grupos_distribucion
        SET activo = 0
        WHERE id = ?
    ''', (grupo_id,))
    
    conn.commit()
    return cursor.rowcount > 0

def calcular_semanas_del_mes(mes, anio):
    """
    Calcula cuántas semanas (lunes a domingo) hay en un mes.
    Solo cuenta semanas que comienzan (lunes) dentro del mes.
    """
    # Primer y último día del mes
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])
    
    # Encontrar el primer lunes del mes (dentro del mes, no antes)
    if primer_dia.weekday() == 0:  # Ya es lunes
        primer_lunes = primer_dia
    else:
        # Avanzar al siguiente lunes dentro del mes
        dias_hasta_lunes = (7 - primer_dia.weekday()) % 7
        if dias_hasta_lunes == 0:
            dias_hasta_lunes = 7
        primer_lunes = primer_dia + timedelta(days=dias_hasta_lunes)
    
    # Si el primer lunes está fuera del mes, no hay semanas completas
    if primer_lunes > ultimo_dia:
        return 0
    
    # Contar semanas desde el primer lunes hasta el último día del mes
    semanas = 0
    fecha_actual = primer_lunes
    while fecha_actual <= ultimo_dia:
        semanas += 1
        fecha_actual += timedelta(days=7)
    
    return semanas

def obtener_rango_semana(mes, anio, numero_semana):
    """
    Obtiene el rango de fechas de una semana específica del mes.
    Las semanas van de lunes a domingo.
    Retorna el rango solo para semanas que empiezan dentro del mes.
    Returns: (fecha_inicio, fecha_fin) como strings 'dd/mm'
    """
    # Primer día del mes
    primer_dia = date(anio, mes, 1)
    
    # Encontrar el primer lunes dentro del mes
    if primer_dia.weekday() == 0:  # Ya es lunes
        primer_lunes = primer_dia
    else:
        # Avanzar al siguiente lunes dentro del mes
        dias_hasta_lunes = (7 - primer_dia.weekday()) % 7
        if dias_hasta_lunes == 0:
            dias_hasta_lunes = 7
        primer_lunes = primer_dia + timedelta(days=dias_hasta_lunes)
    
    # Calcular inicio de la semana solicitada (lunes)
    fecha_inicio = primer_lunes + timedelta(days=(numero_semana - 1) * 7)
    
    # Fin de la semana es siempre 6 días después (domingo)
    fecha_fin = fecha_inicio + timedelta(days=6)
    
    return fecha_inicio.strftime('%d/%m'), fecha_fin.strftime('%d/%m')

def calcular_monto_mensual_segun_frecuencia(monto_base, frecuencia, mes, anio):
    """
    Calcula el monto total del mes según la frecuencia del gasto.
    - Mensual: monto_base
    - Semanal: monto_base * número de semanas del mes
    - Quincenal: monto_base * 2
    - Anual: monto_base / 12
    """
    if frecuencia == "Semanal":
        semanas = calcular_semanas_del_mes(mes, anio)
        return monto_base * semanas
    elif frecuencia == "Quincenal":
        return monto_base * 2
    elif frecuencia == "Anual":
        return monto_base / 12
    else:  # Mensual
        return monto_base

# ==================== FUNCIONES DE PAGOS ====================

def registrar_pago(conn, gasto_id, mes, anio, quien_pago, monto_pagado, semana=None):
    """
    Registra un pago realizado por Ricardo o Wendy.
    Para gastos semanales, incluye el número de semana.
    """
    cursor = conn.cursor()
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO pagos (gasto_id, mes, anio, quien_pago, monto_pagado, fecha_pago, semana)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (gasto_id, mes, anio, quien_pago, monto_pagado, fecha_actual, semana))
    conn.commit()
    return True

def obtener_pagos_del_mes(conn, mes, anio):
    """
    Obtiene todos los pagos de un mes específico.
    """
    query = """
        SELECT p.*, g.concepto, g.monto_total, g.frecuencia
        FROM pagos p
        JOIN gastos_mensuales g ON p.gasto_id = g.id
        WHERE p.mes = ? AND p.anio = ?
        ORDER BY p.fecha_pago DESC
    """
    df = pd.read_sql_query(query, conn, params=(mes, anio))
    return df

def verificar_pago_existente(conn, gasto_id, mes, anio, quien_pago, semana=None):
    """
    Verifica si ya existe un pago para un gasto específico en un mes.
    Para gastos semanales, verifica la semana específica.
    """
    cursor = conn.cursor()
    if semana is not None:
        cursor.execute('''
            SELECT COUNT(*) FROM pagos
            WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = ? AND semana = ?
        ''', (gasto_id, mes, anio, quien_pago, semana))
    else:
        cursor.execute('''
            SELECT COUNT(*) FROM pagos
            WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = ?
        ''', (gasto_id, mes, anio, quien_pago))
    count = cursor.fetchone()[0]
    return count > 0

def obtener_semanas_pagadas(conn, gasto_id, mes, anio, quien_pago):
    """
    Obtiene las semanas ya pagadas de un gasto semanal.
    Returns: lista de números de semana
    """
    cursor = conn.cursor()
    cursor.execute('''
        SELECT semana FROM pagos
        WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = ? AND semana IS NOT NULL
        ORDER BY semana
    ''', (gasto_id, mes, anio, quien_pago))
    semanas = [row[0] for row in cursor.fetchall()]
    return semanas

def eliminar_pago(conn, pago_id):
    """
    Elimina un pago específico de la base de datos.
    """
    cursor = conn.cursor()
    cursor.execute('DELETE FROM pagos WHERE id = ?', (pago_id,))
    conn.commit()
    return cursor.rowcount > 0

def eliminar_pago_por_criterios(conn, gasto_id, mes, anio, quien_pago):
    """
    Elimina un pago específico basado en los criterios.
    """
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM pagos
        WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = ?
    ''', (gasto_id, mes, anio, quien_pago))
    conn.commit()
    return cursor.rowcount > 0

# ==================== CÁLCULO DE TABLA MENSUAL ====================

def calcular_tabla_mensual(conn, mes, anio):
    """
    Calcula la tabla de gastos del mes con los pagos realizados.
    Usa los montos específicos del mes si existen.
    Para gastos semanales, calcula el monto total del mes (semanas * monto_base).
    Soporta distribución personalizada de pagos y grupos de distribución.
    Returns:
        DataFrame con los gastos, montos y quién ha pagado
    """
    gastos_df = obtener_montos_configurados(conn, mes, anio)
    
    if gastos_df.empty:
        return pd.DataFrame()
    
    # Crear lista para almacenar los resultados
    resultados = []
    gastos_procesados = set()  # Para evitar duplicar gastos agrupados
    
    # Obtener todos los grupos activos
    grupos = obtener_grupos_distribucion(conn)
    
    # Procesar grupos primero
    for grupo in grupos:
        grupo_id = grupo['id']
        nombre_grupo = grupo['nombre']
        gastos_grupo = grupo['gastos']
        
        if not gastos_grupo:
            continue
        
        # Calcular monto total del grupo
        monto_total_grupo = 0
        conceptos_grupo = []
        
        for gasto_id, concepto, monto_base in gastos_grupo:
            # Obtener el monto actualizado del mes (considerando ediciones)
            monto_mes_actualizado = obtener_monto_del_mes(conn, gasto_id, mes, anio)
            
            # Buscar frecuencia del gasto
            gasto_info = gastos_df[gastos_df['id'] == gasto_id]
            if not gasto_info.empty:
                gasto_row = gasto_info.iloc[0]
                frecuencia = gasto_row['frecuencia']
                
                # Calcular monto según frecuencia
                monto_mes = calcular_monto_mensual_segun_frecuencia(
                    monto_mes_actualizado, 
                    frecuencia, 
                    mes, 
                    anio
                )
                monto_total_grupo += monto_mes
                conceptos_grupo.append(concepto)
                gastos_procesados.add(gasto_id)
        
        # Calcular distribución del grupo
        quien_paga = grupo['quien_paga_fijo']
        if quien_paga == 'Ricardo':
            monto_fijo = grupo['monto_fijo_ricardo'] or 0
            monto_ricardo = monto_fijo
            monto_wendy = max(0, monto_total_grupo - monto_fijo)
        elif quien_paga == 'Wendy':
            monto_fijo = grupo['monto_fijo_wendy'] or 0
            monto_wendy = monto_fijo
            monto_ricardo = max(0, monto_total_grupo - monto_fijo)
        else:
            # Por defecto 50/50
            monto_ricardo = monto_total_grupo / 2
            monto_wendy = monto_total_grupo / 2
        
        # Verificar si todos los gastos del grupo están pagados
        ricardo_pago = all(
            verificar_pago_existente(conn, g_id, mes, anio, 'Ricardo')
            for g_id, _, _ in gastos_grupo
        )
        wendy_pago = all(
            verificar_pago_existente(conn, g_id, mes, anio, 'Wendy')
            for g_id, _, _ in gastos_grupo
        )
        
        concepto_grupo = f"📦 {nombre_grupo} ({' + '.join(conceptos_grupo)})"
        
        resultados.append({
            'id': f"grupo_{grupo_id}",
            'Concepto': concepto_grupo + " 💰" + quien_paga[0],  # 💰R o 💰W
            'Monto Total': monto_total_grupo,
            'Frecuencia': 'Grupo',
            'Asignado Ricardo': monto_ricardo,
            'Asignado Wendy': monto_wendy,
            'Ricardo Pagó': '✅' if ricardo_pago else '❌',
            'Wendy Pagó': '✅' if wendy_pago else '❌'
        })
    
    # Procesar gastos individuales (no agrupados)
    for _, gasto in gastos_df.iterrows():
        gasto_id = gasto['id']
        
        # Saltar si ya fue procesado como parte de un grupo
        if gasto_id in gastos_procesados:
            continue
        
        # Saltar si tiene tipo_distribucion 'agrupado' pero no encontramos el grupo
        # (esto no debería pasar, pero por seguridad)
        if gasto.get('tipo_distribucion') == 'agrupado':
            continue
        
        concepto = gasto['concepto']
        monto_base = gasto['monto_total']
        frecuencia = gasto['frecuencia']
        tipo_monto = gasto['tipo_monto']
        personalizado = gasto['personalizado']
        
        # Calcular el monto total del mes según la frecuencia
        monto_total = calcular_monto_mensual_segun_frecuencia(monto_base, frecuencia, mes, anio)
        
        # Calcular cuánto debe cada persona según distribución
        monto_ricardo, monto_wendy = calcular_distribucion_pago(gasto, monto_total)
        
        # Para gastos semanales, verificar si todas las semanas están pagadas
        if frecuencia == "Semanal":
            semanas_del_mes = calcular_semanas_del_mes(mes, anio)
            ricardo_semanas = obtener_semanas_pagadas(conn, gasto_id, mes, anio, 'Ricardo')
            wendy_semanas = obtener_semanas_pagadas(conn, gasto_id, mes, anio, 'Wendy')
            
            ricardo_pago = len(ricardo_semanas) == semanas_del_mes
            wendy_pago = len(wendy_semanas) == semanas_del_mes
            
            # Agregar info de semanas al concepto
            concepto_con_info = f"{concepto} ({len(ricardo_semanas)}/{semanas_del_mes} sem)"
        else:
            # Para gastos no semanales, verificar pago normal
            ricardo_pago = verificar_pago_existente(conn, gasto_id, mes, anio, 'Ricardo')
            wendy_pago = verificar_pago_existente(conn, gasto_id, mes, anio, 'Wendy')
            concepto_con_info = concepto
        
        # Indicador de monto
        if tipo_monto == 'variable' and personalizado:
            indicador = " 📝"  # Variable y editado
        elif tipo_monto == 'variable':
            indicador = " 🔄"  # Variable pero no editado
        else:
            indicador = ""  # Fijo
        
        # Indicador de distribución
        tipo_dist = gasto.get('tipo_distribucion', '50/50')
        if tipo_dist == 'fijo_ricardo':
            dist_tag = " 💰R"  # Ricardo paga fijo
        elif tipo_dist == 'fijo_wendy':
            dist_tag = " 💰W"  # Wendy paga fijo
        elif tipo_dist == 'personalizado':
            dist_tag = " ⚖️"  # Porcentaje personalizado
        else:
            dist_tag = ""  # 50/50 normal
        
        resultados.append({
            'id': gasto_id,
            'Concepto': concepto_con_info + indicador + dist_tag,
            'Monto Total': monto_total,
            'Frecuencia': frecuencia,
            'Asignado Ricardo': monto_ricardo,
            'Asignado Wendy': monto_wendy,
            'Ricardo Pagó': '✅' if ricardo_pago else '❌',
            'Wendy Pagó': '✅' if wendy_pago else '❌'
        })
    
    return pd.DataFrame(resultados)

def calcular_saldo_neto(conn, mes, anio):
    """
    Calcula el saldo neto de deuda entre Ricardo y Wendy para un mes específico.
    Usa la misma lógica que la tabla mensual: calcula lo pagado vs lo que debe cada uno.
    """
    # Obtener la tabla mensual con los montos que debe cada uno
    tabla_df = calcular_tabla_mensual(conn, mes, anio)
    
    if tabla_df.empty:
        return {
            'total_debe_cada_uno': 0.0,
            'pagado_ricardo': 0.0,
            'pagado_wendy': 0.0,
            'saldo_ricardo': 0.0,
            'saldo_wendy': 0.0,
            'mensaje': "No hay gastos configurados para este mes"
        }
    
    # Calcular el total que debe pagar cada uno (suma de todos sus gastos)
    total_debe_ricardo = tabla_df['Asignado Ricardo'].sum()
    total_debe_wendy = tabla_df['Asignado Wendy'].sum()
    
    # Calcular cuánto ha pagado cada uno usando la misma lógica de la tabla
    cursor = conn.cursor()
    
    pagado_ricardo_total = 0.0
    pagado_wendy_total = 0.0
    
    for _, row in tabla_df.iterrows():
        gasto_id = row['id']
        
        # Calcular pagado por Ricardo
        try:
            if str(gasto_id).startswith('grupo_'):
                grupo_id = int(str(gasto_id).replace('grupo_', ''))
                query = """
                    SELECT COALESCE(SUM(p.monto_pagado), 0) as total_pagado
                    FROM pagos p
                    INNER JOIN gastos_en_grupo geg ON p.gasto_id = geg.gasto_id
                    WHERE geg.grupo_id = ? AND p.mes = ? AND p.anio = ? AND p.quien_pago = 'Ricardo'
                """
                cursor.execute(query, (grupo_id, mes, anio))
            else:
                query = """
                    SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                    FROM pagos
                    WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = 'Ricardo'
                """
                cursor.execute(query, (gasto_id, mes, anio))
            
            result = cursor.fetchone()
            pagado_ricardo_total += result[0] if result else 0.0
        except:
            pass
        
        # Calcular pagado por Wendy
        try:
            if str(gasto_id).startswith('grupo_'):
                grupo_id = int(str(gasto_id).replace('grupo_', ''))
                query = """
                    SELECT COALESCE(SUM(p.monto_pagado), 0) as total_pagado
                    FROM pagos p
                    INNER JOIN gastos_en_grupo geg ON p.gasto_id = geg.gasto_id
                    WHERE geg.grupo_id = ? AND p.mes = ? AND p.anio = ? AND p.quien_pago = 'Wendy'
                """
                cursor.execute(query, (grupo_id, mes, anio))
            else:
                query = """
                    SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                    FROM pagos
                    WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = 'Wendy'
                """
                cursor.execute(query, (gasto_id, mes, anio))
            
            result = cursor.fetchone()
            pagado_wendy_total += result[0] if result else 0.0
        except:
            pass
    
    # Calcular saldo (pendiente)
    saldo_ricardo = max(0, total_debe_ricardo - pagado_ricardo_total)
    saldo_wendy = max(0, total_debe_wendy - pagado_wendy_total)
    
    # Determinar mensaje
    if saldo_ricardo > 0.01 and saldo_wendy > 0.01:
        mensaje = f"Ricardo debe ${saldo_ricardo:.2f} y Wendy debe ${saldo_wendy:.2f}"
    elif saldo_ricardo > 0.01:
        mensaje = f"Ricardo debe pagar ${saldo_ricardo:.2f}"
    elif saldo_wendy > 0.01:
        mensaje = f"Wendy debe pagar ${saldo_wendy:.2f}"
    else:
        mensaje = "Todo pagado este mes ✅"
    
    # Para mantener compatibilidad con el código existente, devolvemos total_debe_cada_uno
    # como el promedio (aunque ahora cada uno puede deber diferente)
    total_debe_cada_uno = (total_debe_ricardo + total_debe_wendy) / 2
    
    return {
        'total_debe_cada_uno': total_debe_cada_uno,
        'total_debe_ricardo': total_debe_ricardo,
        'total_debe_wendy': total_debe_wendy,
        'pagado_ricardo': pagado_ricardo_total,
        'pagado_wendy': pagado_wendy_total,
        'saldo_ricardo': saldo_ricardo,
        'saldo_wendy': saldo_wendy,
        'mensaje': mensaje
    }

# ==================== FUNCIONES DE GRÁFICOS ====================

def crear_grafico_gastos_tiempo(conn):
    """
    Crea un gráfico de gastos en el tiempo con indicador de fecha actual.
    """
    query = """
        SELECT 
            p.anio || '-' || printf('%02d', p.mes) || '-01' as periodo,
            SUM(p.monto_pagado) as total,
            p.quien_pago
        FROM pagos p
        GROUP BY p.anio, p.mes, p.quien_pago
        ORDER BY p.anio, p.mes
    """
    df = pd.read_sql_query(query, conn)
    
    if df.empty:
        return None
    
    # Convertir periodo a datetime para ordenamiento correcto
    df['periodo'] = pd.to_datetime(df['periodo'])
    
    # Obtener fecha actual
    fecha_actual = datetime.now()
    # Crear timestamp para la fecha actual
    periodo_actual = pd.to_datetime(f"{fecha_actual.year}-{fecha_actual.month:02d}-{fecha_actual.day:02d}")
    
    # Crear gráfico
    fig = px.line(df, x='periodo', y='total', color='quien_pago',
                  title=f'Gastos en el Tiempo (Hoy: {fecha_actual.day}/{fecha_actual.month}/{fecha_actual.year})',
                  labels={'periodo': 'Mes', 'total': 'Monto ($)', 'quien_pago': 'Persona'},
                  markers=True)
    
    # Marcar la fecha actual con una línea vertical usando add_shape
    fig.add_shape(
        type="line",
        x0=periodo_actual,
        x1=periodo_actual,
        y0=0,
        y1=1,
        yref="paper",
        line=dict(color="red", width=2, dash="dash")
    )
    
    # Agregar anotación para la fecha actual
    fig.add_annotation(
        x=periodo_actual,
        y=1,
        yref="paper",
        text=f"📅 Hoy ({fecha_actual.day}/{fecha_actual.month})",
        showarrow=False,
        yshift=10
    )
    
    fig.update_xaxes(
        title="Fecha",
        tickformat="%b %Y"  # Formato: Oct 2025
    )
    
    fig.update_layout(
        hovermode='x unified',
        yaxis_title="Monto ($)",
        showlegend=True
    )
    
    return fig

def crear_grafico_distribucion(conn, mes, anio):
    """
    Crea un gráfico de distribución de gastos por categoría.
    Agrupa los gastos que pertenecen a grupos de distribución.
    """
    # Obtener la tabla calculada que ya agrupa correctamente
    tabla_df = calcular_tabla_mensual(conn, mes, anio)
    
    if tabla_df.empty:
        return None
    
    # Usar el concepto y monto total de la tabla calculada
    df_grafico = tabla_df[['Concepto', 'Monto Total']].copy()
    df_grafico.columns = ['concepto', 'total']
    
    fig = px.pie(df_grafico, values='total', names='concepto',
                 title=f'Distribución de Gastos - {calendar.month_name[mes]} {anio}',
                 hole=0.3)  # Agregar hole para hacerlo tipo donut
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    return fig

# ==================== GENERACIÓN DE REPORTES PDF ====================

def generar_pdf_reporte_general(conn, mes, anio):
    """
    Genera un reporte PDF general del mes con todos los detalles.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#34495E'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Título
    mes_nombre = calendar.month_name[mes]
    titulo = Paragraph(f"REPORTE DE CONTABILIDAD DOMÉSTICA<br/>{mes_nombre.upper()} {anio}", title_style)
    elements.append(titulo)
    elements.append(Spacer(1, 0.3*inch))
    
    # Fecha de generación
    fecha_gen = Paragraph(f"<b>Fecha de generación:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal'])
    elements.append(fecha_gen)
    elements.append(Spacer(1, 0.3*inch))
    
    # Resumen Financiero
    elements.append(Paragraph("RESUMEN FINANCIERO", heading_style))
    
    saldo = calcular_saldo_neto(conn, mes, anio)
    
    # Calcular porcentajes basados en lo que cada uno debe pagar
    total_debe_ricardo = saldo.get('total_debe_ricardo', saldo['total_debe_cada_uno'])
    total_debe_wendy = saldo.get('total_debe_wendy', saldo['total_debe_cada_uno'])
    
    ricardo_porcentaje = (saldo['pagado_ricardo'] / total_debe_ricardo * 100) if total_debe_ricardo > 0 else 0
    wendy_porcentaje = (saldo['pagado_wendy'] / total_debe_wendy * 100) if total_debe_wendy > 0 else 0
    
    data_resumen = [
        ['Concepto', 'Monto'],
        ['Total de Gastos Mensuales', f"${(total_debe_ricardo + total_debe_wendy):.2f}"],
        ['', ''],
        ['Ricardo - Debe Pagar', f"${total_debe_ricardo:.2f}"],
        ['Ricardo - Ya Pagó', f"${saldo['pagado_ricardo']:.2f}"],
        ['Ricardo - Pendiente', f"${saldo['saldo_ricardo']:.2f}"],
        ['Ricardo - Progreso', f"{ricardo_porcentaje:.0f}%"],
        ['', ''],
        ['Wendy - Debe Pagar', f"${total_debe_wendy:.2f}"],
        ['Wendy - Ya Pagó', f"${saldo['pagado_wendy']:.2f}"],
        ['Wendy - Pendiente', f"${saldo['saldo_wendy']:.2f}"],
        ['Wendy - Progreso', f"{wendy_porcentaje:.0f}%"],
    ]
    
    tabla_resumen = Table(data_resumen, colWidths=[4*inch, 2*inch])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),  # Línea vacía
        ('FONTNAME', (0, 7), (-1, 7), 'Helvetica-Bold'),  # Línea vacía
        ('BACKGROUND', (0, 3), (0, 6), colors.HexColor('#D6EAF8')),  # Ricardo - azul claro
        ('BACKGROUND', (0, 8), (0, 11), colors.HexColor('#FCE4EC')),  # Wendy - rosa claro
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),  # Debe Ricardo
        ('FONTNAME', (0, 8), (-1, 8), 'Helvetica-Bold'),  # Debe Wendy
        ('FONTNAME', (0, 6), (-1, 6), 'Helvetica-Bold'),  # Progreso Ricardo
        ('FONTNAME', (0, 11), (-1, 11), 'Helvetica-Bold'),  # Progreso Wendy
    ]))
    
    elements.append(tabla_resumen)
    elements.append(Spacer(1, 0.3*inch))
    
    # Estado del Mes
    elements.append(Paragraph("ESTADO DEL MES", heading_style))
    estado_texto = Paragraph(f"<b>{saldo['mensaje']}</b>", styles['Normal'])
    elements.append(estado_texto)
    elements.append(Spacer(1, 0.3*inch))
    
    # Detalle de Gastos - TABLA DE RICARDO
    elements.append(Paragraph("TABLA DE RICARDO", heading_style))
    
    tabla_df = calcular_tabla_mensual(conn, mes, anio)
    
    if not tabla_df.empty:
        # Agregar columnas de monto pagado y pendiente
        cursor = conn.cursor()
        
        tabla_df['Ricardo Pagado'] = 0.0
        tabla_df['Ricardo Pendiente'] = 0.0
        tabla_df['Ricardo %'] = 0.0
        
        for idx, row in tabla_df.iterrows():
            gasto_id = row['id']
            debe_ricardo = row['Asignado Ricardo']
            
            # Calcular para Ricardo
            try:
                if str(gasto_id).startswith('grupo_'):
                    grupo_id = int(str(gasto_id).replace('grupo_', ''))
                    query = """
                        SELECT COALESCE(SUM(p.monto_pagado), 0) as total_pagado
                        FROM pagos p
                        INNER JOIN gastos_en_grupo geg ON p.gasto_id = geg.gasto_id
                        WHERE geg.grupo_id = ? AND p.mes = ? AND p.anio = ? AND p.quien_pago = 'Ricardo'
                    """
                    cursor.execute(query, (grupo_id, mes, anio))
                else:
                    query = """
                        SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                        FROM pagos
                        WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = 'Ricardo'
                    """
                    cursor.execute(query, (gasto_id, mes, anio))
                
                result = cursor.fetchone()
                ricardo_pagado = result[0] if result else 0.0
                ricardo_pendiente = max(0, debe_ricardo - ricardo_pagado)
                ricardo_porcentaje = (ricardo_pagado / debe_ricardo * 100) if debe_ricardo > 0 else 0
                
                tabla_df.at[idx, 'Ricardo Pagado'] = ricardo_pagado
                tabla_df.at[idx, 'Ricardo Pendiente'] = ricardo_pendiente
                tabla_df.at[idx, 'Ricardo %'] = ricardo_porcentaje
            except:
                pass
        
        # Tabla Ricardo
        data_ricardo = [['Gasto', 'Asignado', 'Pagado', 'Pendiente', 'Progreso']]
        
        for _, row in tabla_df.iterrows():
            data_ricardo.append([
                row['Concepto'],
                f"${row['Asignado Ricardo']:.2f}",
                f"${row['Ricardo Pagado']:.2f}",
                f"${row['Ricardo Pendiente']:.2f}",
                f"{row['Ricardo %']:.0f}%"
            ])
        
        tabla_ricardo = Table(data_ricardo, colWidths=[2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1*inch])
        tabla_ricardo.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        
        elements.append(tabla_ricardo)
        elements.append(Spacer(1, 0.3*inch))
        
        # TABLA DE WENDY
        elements.append(Paragraph("TABLA DE WENDY", heading_style))
        
        # Calcular para Wendy
        tabla_df['Wendy Pagado'] = 0.0
        tabla_df['Wendy Pendiente'] = 0.0
        tabla_df['Wendy %'] = 0.0
        
        for idx, row in tabla_df.iterrows():
            gasto_id = row['id']
            debe_wendy = row['Asignado Wendy']
            
            try:
                if str(gasto_id).startswith('grupo_'):
                    grupo_id = int(str(gasto_id).replace('grupo_', ''))
                    query = """
                        SELECT COALESCE(SUM(p.monto_pagado), 0) as total_pagado
                        FROM pagos p
                        INNER JOIN gastos_en_grupo geg ON p.gasto_id = geg.gasto_id
                        WHERE geg.grupo_id = ? AND p.mes = ? AND p.anio = ? AND p.quien_pago = 'Wendy'
                    """
                    cursor.execute(query, (grupo_id, mes, anio))
                else:
                    query = """
                        SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                        FROM pagos
                        WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = 'Wendy'
                    """
                    cursor.execute(query, (gasto_id, mes, anio))
                
                result = cursor.fetchone()
                wendy_pagado = result[0] if result else 0.0
                wendy_pendiente = max(0, debe_wendy - wendy_pagado)
                wendy_porcentaje = (wendy_pagado / debe_wendy * 100) if debe_wendy > 0 else 0
                
                tabla_df.at[idx, 'Wendy Pagado'] = wendy_pagado
                tabla_df.at[idx, 'Wendy Pendiente'] = wendy_pendiente
                tabla_df.at[idx, 'Wendy %'] = wendy_porcentaje
            except:
                pass
        
        # Tabla Wendy
        data_wendy = [['Gasto', 'Asignado', 'Pagado', 'Pendiente', 'Progreso']]
        
        for _, row in tabla_df.iterrows():
            data_wendy.append([
                row['Concepto'],
                f"${row['Asignado Wendy']:.2f}",
                f"${row['Wendy Pagado']:.2f}",
                f"${row['Wendy Pendiente']:.2f}",
                f"{row['Wendy %']:.0f}%"
            ])
        
        tabla_wendy = Table(data_wendy, colWidths=[2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1*inch])
        tabla_wendy.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E91E63')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        
        elements.append(tabla_wendy)
    else:
        elements.append(Paragraph("No hay gastos registrados para este mes.", styles['Normal']))
    
    elements.append(Spacer(1, 0.3*inch))
    
    # Historial de Pagos
    elements.append(Paragraph("HISTORIAL DE PAGOS REALIZADOS", heading_style))
    
    pagos_df = obtener_pagos_del_mes(conn, mes, anio)
    
    if not pagos_df.empty:
        data_pagos = [['Fecha', 'Concepto', 'Quien Pagó', 'Monto']]
        
        for _, pago in pagos_df.iterrows():
            data_pagos.append([
                pago['fecha_pago'],
                pago['concepto'],
                pago['quien_pago'],
                f"${pago['monto_pagado']:.2f}"
            ])
        
        tabla_pagos = Table(data_pagos, colWidths=[1.5*inch, 2*inch, 1.5*inch, 1.5*inch])
        tabla_pagos.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E74C3C')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        
        elements.append(tabla_pagos)
    else:
        elements.append(Paragraph("No se han realizado pagos en este mes.", styles['Normal']))
    
    # Generar PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generar_pdf_reporte_individual(conn, mes, anio, persona):
    """
    Genera un reporte PDF individual para Ricardo o Wendy.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#34495E'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Título
    mes_nombre = calendar.month_name[mes]
    icono = "👨" if persona == "Ricardo" else "👩"
    titulo = Paragraph(f"REPORTE INDIVIDUAL - {persona.upper()}<br/>{mes_nombre.upper()} {anio}", title_style)
    elements.append(titulo)
    elements.append(Spacer(1, 0.3*inch))
    
    # Fecha de generación
    fecha_gen = Paragraph(f"<b>Fecha de generación:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal'])
    elements.append(fecha_gen)
    elements.append(Spacer(1, 0.3*inch))
    
    # Resumen Personal
    elements.append(Paragraph(f"RESUMEN DE {persona.upper()}", heading_style))
    
    saldo = calcular_saldo_neto(conn, mes, anio)
    
    # Obtener el total específico que debe esta persona
    if persona == 'Ricardo':
        total_debe = saldo.get('total_debe_ricardo', saldo['total_debe_cada_uno'])
        pagado = saldo['pagado_ricardo']
        pendiente = saldo['saldo_ricardo']
    else:
        total_debe = saldo.get('total_debe_wendy', saldo['total_debe_cada_uno'])
        pagado = saldo['pagado_wendy']
        pendiente = saldo['saldo_wendy']
    
    porcentaje = (pagado / total_debe * 100) if total_debe > 0 else 0
    
    data_personal = [
        ['Concepto', 'Monto'],
        ['Total a pagar este mes', f"${total_debe:.2f}"],
        ['Ya pagado', f"${pagado:.2f}"],
        ['Pendiente por pagar', f"${pendiente:.2f}"],
        ['Progreso de pago', f"{porcentaje:.0f}%"],
    ]
    
    tabla_personal = Table(data_personal, colWidths=[4*inch, 2*inch])
    tabla_personal.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9B59B6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, -2), (-1, -2), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor('#FFE5CC')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#D5F4E6')),
    ]))
    
    elements.append(tabla_personal)
    elements.append(Spacer(1, 0.3*inch))
    
    # Estado de Pagos por Gasto
    elements.append(Paragraph(f"GASTOS ASIGNADOS A {persona.upper()}", heading_style))
    
    tabla_df = calcular_tabla_mensual(conn, mes, anio)
    
    if not tabla_df.empty:
        # Calcular pagado y pendiente para cada gasto
        cursor = conn.cursor()
        
        columna_asignado = f'Asignado {persona}'
        data_gastos = [['Gasto', 'Asignado', 'Ya Pagó', 'Pendiente', 'Progreso']]
        
        for _, row in tabla_df.iterrows():
            gasto_id = row['id']
            asignado = row[columna_asignado]
            
            # Calcular monto pagado
            pagado = 0.0
            try:
                if str(gasto_id).startswith('grupo_'):
                    grupo_id = int(str(gasto_id).replace('grupo_', ''))
                    query = """
                        SELECT COALESCE(SUM(p.monto_pagado), 0) as total_pagado
                        FROM pagos p
                        INNER JOIN gastos_en_grupo geg ON p.gasto_id = geg.gasto_id
                        WHERE geg.grupo_id = ? AND p.mes = ? AND p.anio = ? AND p.quien_pago = ?
                    """
                    cursor.execute(query, (grupo_id, mes, anio, persona))
                else:
                    query = """
                        SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                        FROM pagos
                        WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = ?
                    """
                    cursor.execute(query, (gasto_id, mes, anio, persona))
                
                result = cursor.fetchone()
                pagado = result[0] if result else 0.0
            except:
                pass
            
            pendiente = max(0, asignado - pagado)
            porcentaje = (pagado / asignado * 100) if asignado > 0 else 0
            
            data_gastos.append([
                row['Concepto'],
                f"${asignado:.2f}",
                f"${pagado:.2f}",
                f"${pendiente:.2f}",
                f"{porcentaje:.0f}%"
            ])
        
        tabla_gastos = Table(data_gastos, colWidths=[2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1*inch])
        tabla_gastos.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16A085')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        
        elements.append(tabla_gastos)
    else:
        elements.append(Paragraph("No hay gastos registrados para este mes.", styles['Normal']))
    
    elements.append(Spacer(1, 0.3*inch))
    
    # Pagos Realizados
    elements.append(Paragraph(f"PAGOS REALIZADOS POR {persona.upper()}", heading_style))
    
    pagos_df = obtener_pagos_del_mes(conn, mes, anio)
    pagos_persona = pagos_df[pagos_df['quien_pago'] == persona] if not pagos_df.empty else pd.DataFrame()
    
    if not pagos_persona.empty:
        data_pagos = [['Fecha', 'Concepto', 'Monto Pagado']]
        
        for _, pago in pagos_persona.iterrows():
            data_pagos.append([
                pago['fecha_pago'],
                pago['concepto'],
                f"${pago['monto_pagado']:.2f}"
            ])
        
        # Total pagado
        total_pagado = pagos_persona['monto_pagado'].sum()
        data_pagos.append(['', 'TOTAL PAGADO', f"${total_pagado:.2f}"])
        
        tabla_pagos = Table(data_pagos, colWidths=[2*inch, 3*inch, 1.5*inch])
        tabla_pagos.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E67E22')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F39C12')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        
        elements.append(tabla_pagos)
    else:
        elements.append(Paragraph(f"{persona} no ha realizado pagos en este mes.", styles['Normal']))
    
    elements.append(Spacer(1, 0.5*inch))
    
    # Mensaje final
    if pendiente > 0.01:
        mensaje = Paragraph(
            f"<b>IMPORTANTE:</b> {persona} aún tiene <b>${pendiente:.2f}</b> pendientes por pagar este mes.",
            styles['Normal']
        )
    else:
        mensaje = Paragraph(
            f"<b>¡FELICITACIONES!</b> {persona} ha completado todos sus pagos del mes.",
            styles['Normal']
        )
    
    elements.append(mensaje)
    
    # Generar PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==================== INTERFAZ STREAMLIT ====================

def main():
    st.set_page_config(
        page_title="Contabilidad Ricardo y Wendy",
        page_icon="🏠",
        layout="wide"
    )
    
    st.title("🏠 Contabilidad Doméstica - Ricardo y Wendy")
    
    # Explicación del sistema
    with st.expander("ℹ️ ¿Cómo funciona el sistema?"):
        st.markdown("""
        ### 📋 Sistema de Gastos Mensuales
        
        1. **Gastos Recurrentes**: En la pestaña "Gestionar Gastos" defines gastos que se repiten cada mes 
           (Luz, Agua, Casa, etc.). Estos son los **mismos para todos los meses**.
        
        2. **Pagos Mensuales**: Cada mes, Ricardo y Wendy deben pagar su parte (50%) de cada gasto. 
           Los pagos **se resetean cada mes**.
        
        3. **Ejemplo**:
           - **Octubre 2025**: Ricardo paga Luz ✅, Wendy paga Agua ✅
           - **Noviembre 2025**: Nuevos pagos, todo empieza en ❌ (nadie ha pagado aún)
        
        4. **Selector de Mes**: Arriba puedes cambiar el mes para ver:
           - Qué gastos había ese mes
           - Quién pagó qué ese mes
           - Cuánto falta por pagar ese mes
        
        **💡 Los gastos son iguales cada mes, pero los pagos cambian.**
        """)
    
    st.markdown("---")
    
    # Conectar a la base de datos
    conn = conectar_db()
    
    # Selector de mes
    col_mes1, col_mes2 = st.columns([3, 1])
    with col_mes1:
        fecha_actual = datetime.now()
        mes_actual = fecha_actual.month
        anio_actual = fecha_actual.year
        
        meses = {i: calendar.month_name[i] for i in range(1, 13)}
        mes_seleccionado = st.selectbox(
            "📅 Mes",
            options=list(meses.keys()),
            format_func=lambda x: meses[x],
            index=mes_actual - 1
        )
    
    with col_mes2:
        anio_seleccionado = st.number_input(
            "Año",
            min_value=2020,
            max_value=2030,
            value=anio_actual
        )
    
    # Crear tabs para diferentes funcionalidades
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "📊 Tabla Mensual", 
        "💳 Pagar Gastos",
        "⚙️ Gestionar Gastos", 
        "🗑️ Eliminar Pagos",
        "📄 Reportes PDF",
        "📈 Estadísticas",
        "💰 Resumen",
        "👨 Ricardo",
        "👩 Wendy"
    ])
    
    # ========== TAB 1: TABLA MENSUAL ==========
    with tab1:
        st.header(f"📊 Tabla de Gastos - {meses[mes_seleccionado]} {anio_seleccionado}")
        
        # Mensaje informativo
        if mes_seleccionado == fecha_actual.month and anio_seleccionado == fecha_actual.year:
            st.info(f"📅 Estás viendo el mes **actual** ({meses[mes_seleccionado]} {anio_seleccionado})")
        else:
            st.warning(f"📅 Estás viendo un mes **diferente** ({meses[mes_seleccionado]} {anio_seleccionado}). Los gastos son los mismos cada mes, pero los pagos varían.")
        
        # Sección para editar montos del mes
        with st.expander("✏️ Editar Montos de este Mes (Luz, Agua, Internet, etc.)"):
            st.write("**Los gastos como luz, agua e internet varían cada mes. Aquí puedes ajustar sus montos.**")
            st.caption("📝 Los montos editados solo afectarán a este mes, no a los meses anteriores o futuros.")
            st.caption("ℹ️ Solo se muestran gastos con monto **variable**. Los gastos fijos no se pueden editar aquí.")
            
            gastos_config = obtener_montos_configurados(conn, mes_seleccionado, anio_seleccionado)
            
            # Filtrar solo los gastos VARIABLES
            if not gastos_config.empty:
                gastos_config = gastos_config[gastos_config['tipo_monto'] == 'variable']
            
            if not gastos_config.empty:
                for idx, gasto in gastos_config.iterrows():
                    es_grupo = gasto.get('grupo') is not None and gasto.get('grupo') != '' and gasto.get('grupo') != None
                    
                    # Si es un grupo, mostrar edición expandida
                    if es_grupo:
                        with st.container():
                            col_header1, col_header2 = st.columns([3, 1])
                            
                            with col_header1:
                                st.write(f"**📦 {gasto['grupo']}** ({gasto['concepto']})")
                                if gasto['personalizado']:
                                    st.caption("📝 Montos personalizados para este mes")
                                else:
                                    st.caption(f"📋 Monto base total: ${gasto['monto_total']:.2f}")
                            
                            with col_header2:
                                mostrar_grupo = st.checkbox(
                                    "Editar",
                                    key=f"toggle_grupo_{gasto['id']}",
                                    help="Editar gastos individuales del grupo"
                                )
                            
                            if mostrar_grupo:
                                st.markdown("---")
                                st.write("**Gastos individuales del grupo:**")
                                
                                # Parsear los gastos individuales
                                gastos_individuales = [g.strip() for g in gasto['concepto'].split('+')]
                                
                                # Calcular monto por gasto (distribución equitativa por defecto)
                                monto_por_gasto = gasto['monto_total'] / len(gastos_individuales)
                                
                                montos_individuales = []
                                
                                for i, nombre_gasto in enumerate(gastos_individuales):
                                    col1, col2 = st.columns([2, 2])
                                    
                                    with col1:
                                        st.write(f"  • **{nombre_gasto}**")
                                    
                                    with col2:
                                        monto_individual = st.number_input(
                                            f"Monto {nombre_gasto}",
                                            min_value=0.0,
                                            value=float(monto_por_gasto),
                                            step=0.01,
                                            format="%.2f",
                                            key=f"monto_individual_{gasto['id']}_{i}",
                                            label_visibility="collapsed",
                                            help=f"Monto específico para {nombre_gasto} en {meses[mes_seleccionado]}"
                                        )
                                        montos_individuales.append(monto_individual)
                                
                                # Mostrar total calculado
                                total_calculado = sum(montos_individuales)
                                st.info(f"💰 **Total del grupo:** ${total_calculado:.2f}")
                                
                                # Botón para guardar
                                if st.button("💾 Guardar montos del grupo", key=f"guardar_grupo_{gasto['id']}", type="primary"):
                                    resultado = establecer_monto_del_mes(conn, gasto['id'], mes_seleccionado, anio_seleccionado, total_calculado)
                                    if resultado:
                                        st.success(f"✅ Montos actualizados para {gasto['grupo']}")
                                        st.caption(f"Desglose guardado: {' | '.join([f'{g}: ${m:.2f}' for g, m in zip(gastos_individuales, montos_individuales)])}")
                                        st.rerun()
                                    else:
                                        st.error("❌ Error al guardar los montos del grupo")
                            
                            st.markdown("---")
                    
                    # Gasto simple (no es grupo)
                    else:
                        col1, col2, col3 = st.columns([2, 2, 1])
                        
                        with col1:
                            st.write(f"**{gasto['concepto']}**")
                            if gasto['personalizado']:
                                st.caption("📝 Monto personalizado para este mes")
                            else:
                                st.caption("📋 Usando monto base")
                        
                        with col2:
                            nuevo_monto = st.number_input(
                                f"Monto para {meses[mes_seleccionado]}",
                                min_value=0.0,
                                value=float(gasto['monto_total']),
                                step=0.01,
                                format="%.2f",
                                key=f"monto_{gasto['id']}",
                                label_visibility="collapsed"
                            )
                        
                        with col3:
                            if st.button("💾", key=f"guardar_monto_{gasto['id']}", help="Guardar monto"):
                                resultado = establecer_monto_del_mes(conn, gasto['id'], mes_seleccionado, anio_seleccionado, nuevo_monto)
                                if resultado:
                                    st.success("✅ Guardado")
                                    st.rerun()
                                else:
                                    st.error("❌ Error al guardar")
                        
                        st.markdown("---")
            else:
                st.info("ℹ️ No hay gastos **variables** configurados en este momento. Los gastos con montos fijos no se muestran aquí.")
        
        st.markdown("---")
        
        tabla_df = calcular_tabla_mensual(conn, mes_seleccionado, anio_seleccionado)
        
        if not tabla_df.empty:
            # Agregar columnas de monto pagado y pendiente
            cursor = conn.cursor()
            
            tabla_df['Ricardo Pagado'] = 0.0
            tabla_df['Ricardo Pendiente'] = 0.0
            tabla_df['Ricardo %'] = 0.0
            tabla_df['Wendy Pagado'] = 0.0
            tabla_df['Wendy Pendiente'] = 0.0
            tabla_df['Wendy %'] = 0.0
            
            for idx, row in tabla_df.iterrows():
                gasto_id = row['id']
                asignado_ricardo = row['Asignado Ricardo']
                asignado_wendy = row['Asignado Wendy']
                
                # Calcular para Ricardo
                try:
                    if str(gasto_id).startswith('grupo_'):
                        grupo_id = int(str(gasto_id).replace('grupo_', ''))
                        query = """
                            SELECT COALESCE(SUM(p.monto_pagado), 0) as total_pagado
                            FROM pagos p
                            INNER JOIN gastos_en_grupo geg ON p.gasto_id = geg.gasto_id
                            WHERE geg.grupo_id = ? AND p.mes = ? AND p.anio = ? AND p.quien_pago = 'Ricardo'
                        """
                        cursor.execute(query, (grupo_id, mes_seleccionado, anio_seleccionado))
                    else:
                        query = """
                            SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                            FROM pagos
                            WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = 'Ricardo'
                        """
                        cursor.execute(query, (gasto_id, mes_seleccionado, anio_seleccionado))
                    
                    result = cursor.fetchone()
                    ricardo_pagado = result[0] if result else 0.0
                    ricardo_pendiente = max(0, asignado_ricardo - ricardo_pagado)
                    ricardo_porcentaje = (ricardo_pagado / asignado_ricardo * 100) if asignado_ricardo > 0 else 0
                    
                    tabla_df.at[idx, 'Ricardo Pagado'] = ricardo_pagado
                    tabla_df.at[idx, 'Ricardo Pendiente'] = ricardo_pendiente
                    tabla_df.at[idx, 'Ricardo %'] = ricardo_porcentaje
                except:
                    pass
                
                # Calcular para Wendy
                try:
                    if str(gasto_id).startswith('grupo_'):
                        grupo_id = int(str(gasto_id).replace('grupo_', ''))
                        query = """
                            SELECT COALESCE(SUM(p.monto_pagado), 0) as total_pagado
                            FROM pagos p
                            INNER JOIN gastos_en_grupo geg ON p.gasto_id = geg.gasto_id
                            WHERE geg.grupo_id = ? AND p.mes = ? AND p.anio = ? AND p.quien_pago = 'Wendy'
                        """
                        cursor.execute(query, (grupo_id, mes_seleccionado, anio_seleccionado))
                    else:
                        query = """
                            SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                            FROM pagos
                            WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = 'Wendy'
                        """
                        cursor.execute(query, (gasto_id, mes_seleccionado, anio_seleccionado))
                    
                    result = cursor.fetchone()
                    wendy_pagado = result[0] if result else 0.0
                    wendy_pendiente = max(0, asignado_wendy - wendy_pagado)
                    wendy_porcentaje = (wendy_pagado / asignado_wendy * 100) if asignado_wendy > 0 else 0
                    
                    tabla_df.at[idx, 'Wendy Pagado'] = wendy_pagado
                    tabla_df.at[idx, 'Wendy Pendiente'] = wendy_pendiente
                    tabla_df.at[idx, 'Wendy %'] = wendy_porcentaje
                except:
                    pass
            
            # Crear dos tablas separadas: una para Ricardo y otra para Wendy
            st.subheader("👨 Tabla de Ricardo")
            
            # Tabla de Ricardo
            columnas_ricardo = ['Concepto', 'Monto Total', 'Frecuencia', 'Asignado Ricardo',
                               'Ricardo Pagado', 'Ricardo Pendiente', 'Ricardo %']
            tabla_ricardo = tabla_df[columnas_ricardo].copy()
            
            st.dataframe(
                tabla_ricardo,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Concepto": st.column_config.TextColumn(
                        "Concepto",
                        width="medium",
                        help="Nombre del gasto"
                    ),
                    "Monto Total": st.column_config.NumberColumn(
                        "💰 Total",
                        format="$%.2f",
                        width="small"
                    ),
                    "Frecuencia": st.column_config.TextColumn(
                        "📅 Frecuencia",
                        width="small"
                    ),
                    "Asignado Ricardo": st.column_config.NumberColumn(
                        "💵 Asignado",
                        format="$%.2f",
                        width="small",
                        help="Monto asignado a Ricardo"
                    ),
                    "Ricardo Pagado": st.column_config.NumberColumn(
                        "✅ Pagado",
                        format="$%.2f",
                        width="small",
                        help="Monto que Ricardo ya pagó"
                    ),
                    "Ricardo Pendiente": st.column_config.NumberColumn(
                        "⏳ Pendiente",
                        format="$%.2f",
                        width="small",
                        help="Monto que le falta pagar a Ricardo"
                    ),
                    "Ricardo %": st.column_config.NumberColumn(
                        "📊 Progreso",
                        format="%.0f%%",
                        width="small",
                        help="Porcentaje pagado por Ricardo"
                    )
                }
            )
            
            # Resumen de Ricardo
            col1, col2, col3 = st.columns(3)
            with col1:
                ricardo_asignado_total = tabla_df['Asignado Ricardo'].sum()
                st.metric("💵 Asignado Total", f"${ricardo_asignado_total:.2f}")
            with col2:
                ricardo_pagado_total = tabla_df['Ricardo Pagado'].sum()
                st.metric("✅ Ya Pagó", f"${ricardo_pagado_total:.2f}")
            with col3:
                ricardo_pendiente_total = tabla_df['Ricardo Pendiente'].sum()
                progreso_ricardo = (ricardo_pagado_total / ricardo_asignado_total * 100) if ricardo_asignado_total > 0 else 0
                st.metric("⏳ Pendiente", f"${ricardo_pendiente_total:.2f}", 
                         delta=f"{progreso_ricardo:.0f}% pagado", delta_color="normal")
            
            st.markdown("---")
            
            # Tabla de Wendy
            st.subheader("👩 Tabla de Wendy")
            
            columnas_wendy = ['Concepto', 'Monto Total', 'Frecuencia', 'Asignado Wendy',
                             'Wendy Pagado', 'Wendy Pendiente', 'Wendy %']
            tabla_wendy = tabla_df[columnas_wendy].copy()
            
            st.dataframe(
                tabla_wendy,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Concepto": st.column_config.TextColumn(
                        "Concepto",
                        width="medium",
                        help="Nombre del gasto"
                    ),
                    "Monto Total": st.column_config.NumberColumn(
                        "💰 Total",
                        format="$%.2f",
                        width="small"
                    ),
                    "Frecuencia": st.column_config.TextColumn(
                        "📅 Frecuencia",
                        width="small"
                    ),
                    "Asignado Wendy": st.column_config.NumberColumn(
                        "💵 Asignado",
                        format="$%.2f",
                        width="small",
                        help="Monto asignado a Wendy"
                    ),
                    "Wendy Pagado": st.column_config.NumberColumn(
                        "✅ Pagado",
                        format="$%.2f",
                        width="small",
                        help="Monto que Wendy ya pagó"
                    ),
                    "Wendy Pendiente": st.column_config.NumberColumn(
                        "⏳ Pendiente",
                        format="$%.2f",
                        width="small",
                        help="Monto que le falta pagar a Wendy"
                    ),
                    "Wendy %": st.column_config.NumberColumn(
                        "📊 Progreso",
                        format="%.0f%%",
                        width="small",
                        help="Porcentaje pagado por Wendy"
                    )
                }
            )
            
            # Resumen de Wendy
            col1, col2, col3 = st.columns(3)
            with col1:
                wendy_asignado_total = tabla_df['Asignado Wendy'].sum()
                st.metric("💵 Asignado Total", f"${wendy_asignado_total:.2f}")
            with col2:
                wendy_pagado_total = tabla_df['Wendy Pagado'].sum()
                st.metric("✅ Ya Pagó", f"${wendy_pagado_total:.2f}")
            with col3:
                wendy_pendiente_total = tabla_df['Wendy Pendiente'].sum()
                progreso_wendy = (wendy_pagado_total / wendy_asignado_total * 100) if wendy_asignado_total > 0 else 0
                st.metric("⏳ Pendiente", f"${wendy_pendiente_total:.2f}",
                         delta=f"{progreso_wendy:.0f}% pagado", delta_color="normal")
        else:
            st.warning("⚠️ No hay gastos mensuales configurados. Ve a la pestaña 'Gestionar Gastos' para agregar.")
    
    # ========== TAB 2: PAGAR GASTOS ==========
    with tab2:
        st.header(f"💳 Registrar Pago de Gastos - {meses[mes_seleccionado]} {anio_seleccionado}")
        
        # Verificar si es el mes actual
        if mes_seleccionado != fecha_actual.month or anio_seleccionado != fecha_actual.year:
            st.warning(f"⚠️ Atención: Estás registrando pagos para **{meses[mes_seleccionado]} {anio_seleccionado}** (no es el mes actual)")
        
        # Selector de persona
        persona = st.radio(
            "¿Quién está pagando?",
            options=["Ricardo", "Wendy"],
            horizontal=True
        )
        
        st.markdown("---")
        
        # Obtener configuración de gastos
        gastos_config = obtener_montos_configurados(conn, mes_seleccionado, anio_seleccionado)
        
        if not gastos_config.empty:
            st.subheader(f"Gastos de {persona}")
            
            for idx, gasto in gastos_config.iterrows():
                gasto_id = gasto['id']
                concepto = gasto['concepto']
                monto_base = gasto['monto_total']
                frecuencia = gasto['frecuencia']
                grupo = gasto.get('grupo', '')
                
                # Calcular el monto total del mes según frecuencia
                monto_total_mes = calcular_monto_mensual_segun_frecuencia(monto_base, frecuencia, mes_seleccionado, anio_seleccionado)
                
                # Calcular cuánto debe pagar esta persona según distribución
                monto_ricardo, monto_wendy = calcular_distribucion_pago(gasto, monto_total_mes)
                monto_pagar = monto_ricardo if persona == "Ricardo" else monto_wendy
                
                # Información de distribución
                tipo_dist = gasto.get('tipo_distribucion', '50/50')
                if tipo_dist == 'fijo_ricardo':
                    dist_info = f"💰 Ricardo paga ${monto_ricardo:.2f} fijo, Wendy ${monto_wendy:.2f}"
                elif tipo_dist == 'fijo_wendy':
                    dist_info = f"💰 Wendy paga ${monto_wendy:.2f} fijo, Ricardo ${monto_ricardo:.2f}"
                elif tipo_dist == 'personalizado':
                    porc_r = gasto.get('porcentaje_ricardo', 50.0)
                    porc_w = 100 - porc_r
                    dist_info = f"⚖️ Ricardo {porc_r:.0f}% (${monto_ricardo:.2f}), Wendy {porc_w:.0f}% (${monto_wendy:.2f})"
                else:
                    dist_info = f"⚖️ 50/50 - ${monto_pagar:.2f} cada uno"
                
                # ====== MANEJO ESPECIAL PARA GASTOS SEMANALES ======
                if frecuencia == "Semanal":
                    semanas_mes = calcular_semanas_del_mes(mes_seleccionado, anio_seleccionado)
                    semanas_pagadas = obtener_semanas_pagadas(conn, gasto_id, mes_seleccionado, anio_seleccionado, persona)
                    semanas_pendientes = [s for s in range(1, semanas_mes + 1) if s not in semanas_pagadas]
                    
                    monto_semanal_persona = monto_pagar / semanas_mes
                    
                    titulo = f"📅 **{concepto}**"
                    if grupo:
                        titulo += f" [{grupo}]"
                    titulo += f" - ${monto_semanal_persona:.2f}/semana ({len(semanas_pagadas)}/{semanas_mes} pagadas)"
                    
                    with st.expander(titulo, expanded=len(semanas_pendientes) > 0):
                        st.caption(dist_info)
                        
                        if semanas_pendientes:
                            st.write(f"**Semanas pendientes:** {len(semanas_pendientes)}")
                            
                            for num_semana in semanas_pendientes:
                                rango = obtener_rango_semana(mes_seleccionado, anio_seleccionado, num_semana)
                                col1, col2, col3 = st.columns([3, 2, 1])
                                
                                with col1:
                                    st.write(f"**Semana {num_semana}** ({rango[0]} - {rango[1]})")
                                
                                with col2:
                                    st.metric("A pagar", f"${monto_semanal_persona:.2f}")
                                
                                with col3:
                                    if st.button("✅ Pagar", key=f"pagar_sem_{gasto_id}_{num_semana}_{persona}"):
                                        if registrar_pago(conn, gasto_id, mes_seleccionado, 
                                                        anio_seleccionado, persona, monto_semanal_persona, num_semana):
                                            st.success(f"✅ Pagada semana {num_semana}")
                                            st.rerun()
                        else:
                            st.success(f"✅ Todas las semanas pagadas!")
                            st.info(f"Total pagado: ${monto_pagar:.2f} ({semanas_mes} semanas × ${monto_semanal_persona:.2f})")
                
                # ====== GASTOS NO SEMANALES (MENSUAL, QUINCENAL, ANUAL) ======
                else:
                    monto_pagar = monto_total_mes / 2  # 50% cada uno
                    
                    # Verificar si ya pagó
                    ya_pago = verificar_pago_existente(conn, gasto_id, mes_seleccionado, anio_seleccionado, persona)
                    
                    with st.container():
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            titulo_gasto = f"**{concepto}**"
                            if grupo:
                                titulo_gasto += f" [{grupo}]"
                            st.write(titulo_gasto)
                            
                            # Información de frecuencia
                            if frecuencia == "Quincenal":
                                st.caption(f"Quincenal: ${monto_base:.2f} × 2 = ${monto_total_mes:.2f}")
                            elif frecuencia == "Anual":
                                st.caption(f"Anual: ${monto_base:.2f} ÷ 12 = ${monto_total_mes:.2f}/mes")
                            else:
                                st.caption(f"Frecuencia: {frecuencia}")
                            
                            # Información de distribución
                            st.caption(dist_info)
                        
                        with col2:
                            if ya_pago:
                                st.success(f"✅ Pagado: ${monto_pagar:.2f}")
                            else:
                                st.metric("A pagar", f"${monto_pagar:.2f}")
                        
                        with col3:
                            if not ya_pago:
                                if st.button("✅ Pagar", key=f"pagar_{gasto_id}_{persona}"):
                                    if registrar_pago(conn, gasto_id, mes_seleccionado, 
                                                    anio_seleccionado, persona, monto_pagar):
                                        st.success(f"✅ Pago registrado")
                                        st.rerun()
                            else:
                                st.write("✓ Listo")
                        
                        st.markdown("---")
        else:
            st.warning("⚠️ No hay gastos configurados para este mes.")
    
    # ========== TAB 3: GESTIONAR GASTOS MENSUALES ==========
    with tab3:
        st.header("⚙️ Gestionar Gastos Mensuales")
        
        # 3 Subtabs: Agregar Gasto (simplificado), Lista de Gastos, Grupos de Distribución
        subtab1, subtab2, subtab3 = st.tabs([
            "➕ Agregar Gasto", 
            "📋 Lista de Gastos",
            "📦 Grupos de Distribución"
        ])
        
        # ========== SUBTAB 1: AGREGAR NUEVO GASTO (SIMPLIFICADO) ==========
        with subtab1:
            st.subheader("➕ Agregar Nuevo Gasto Mensual")
            st.info("💡 **Nuevo diseño:** Cada gasto es independiente. Luego puedes agruparlos en 'Grupos de Distribución'.")
            
            with st.form("form_agregar_gasto", clear_on_submit=True):
                st.markdown("### 📝 Información del Gasto")
                
                concepto = st.text_input(
                    "Concepto",
                    placeholder="Ej: Luz, Agua, Renta, Internet",
                    help="Nombre del gasto (cada uno por separado)"
                )
                
                col1, col2 = st.columns(2)
                
                with col1:
                    monto_total = st.number_input(
                        "💰 Monto Base ($)",
                        min_value=0.0,
                        step=0.01,
                        format="%.2f",
                        help="Monto del gasto"
                    )
                
                with col2:
                    frecuencia = st.selectbox(
                        "📅 Frecuencia",
                        options=["Mensual", "Semanal", "Quincenal", "Anual"],
                        help="Con qué frecuencia se paga"
                    )
                
                st.markdown("---")
                st.markdown("### 🔒/🔄 Tipo de Monto")
                
                tipo_monto = st.radio(
                    "Selecciona el tipo:",
                    options=["fijo", "variable"],
                    format_func=lambda x: "🔒 Fijo (siempre el mismo monto)" if x == "fijo" else "🔄 Variable (puede cambiar cada mes)",
                    horizontal=True
                )
                
                if tipo_monto == "fijo":
                    st.caption("🔒 Este gasto siempre costará lo mismo")
                else:
                    st.caption("🔄 Podrás ajustar el monto cada mes")
                
                st.markdown("---")
                st.markdown("### ⚖️ Distribución del Pago")
                st.caption("💡 Puedes cambiar esto después o agrupar gastos en la pestaña 'Grupos de Distribución'")
                
                tipo_distribucion = st.radio(
                    "¿Cómo se divide el pago?",
                    options=["50/50", "fijo_ricardo", "fijo_wendy", "personalizado"],
                    format_func=lambda x: {
                        "50/50": "⚖️ 50/50 (mitad cada uno)",
                        "fijo_ricardo": "💰 Ricardo paga monto fijo",
                        "fijo_wendy": "💰 Wendy paga monto fijo",
                        "personalizado": "⚙️ Porcentaje personalizado"
                    }[x],
                    index=0,
                    key="dist_nuevo_gasto"
                )
                
                monto_fijo_ricardo = None
                monto_fijo_wendy = None
                porcentaje_ricardo = 50.0
                
                if tipo_distribucion == "fijo_ricardo":
                    st.info("💰 Ricardo paga un monto fijo, Wendy paga la diferencia")
                    monto_fijo_ricardo = st.number_input(
                        "¿Cuánto paga Ricardo? ($)",
                        min_value=0.0,
                        value=min(100.0, float(monto_total) if monto_total > 0 else 100.0),
                        step=0.01,
                        format="%.2f",
                        key="monto_r_nuevo"
                    )
                    if monto_total > 0:
                        diferencia = max(0, monto_total - monto_fijo_ricardo)
                        st.success(f"✅ Ricardo: ${monto_fijo_ricardo:.2f} | Wendy: ${diferencia:.2f}")
                
                elif tipo_distribucion == "fijo_wendy":
                    st.info("💰 Wendy paga un monto fijo, Ricardo paga la diferencia")
                    monto_fijo_wendy = st.number_input(
                        "¿Cuánto paga Wendy? ($)",
                        min_value=0.0,
                        value=min(100.0, float(monto_total) if monto_total > 0 else 100.0),
                        step=0.01,
                        format="%.2f",
                        key="monto_w_nuevo"
                    )
                    if monto_total > 0:
                        diferencia = max(0, monto_total - monto_fijo_wendy)
                        st.success(f"✅ Wendy: ${monto_fijo_wendy:.2f} | Ricardo: ${diferencia:.2f}")
                
                elif tipo_distribucion == "personalizado":
                    st.info("⚙️ Define el porcentaje de cada uno")
                    porcentaje_ricardo = st.slider(
                        "Porcentaje que paga Ricardo (%)",
                        0.0, 100.0, 50.0, 1.0,
                        key="porc_r_nuevo"
                    )
                    if monto_total > 0:
                        monto_r = monto_total * (porcentaje_ricardo / 100)
                        monto_w = monto_total * ((100 - porcentaje_ricardo) / 100)
                        st.success(f"✅ Ricardo: {porcentaje_ricardo:.0f}% (${monto_r:.2f}) | Wendy: {100-porcentaje_ricardo:.0f}% (${monto_w:.2f})")
                else:
                    if monto_total > 0:
                        mitad = monto_total / 2
                        st.success(f"✅ Ricardo: ${mitad:.2f} | Wendy: ${mitad:.2f}")
                
                st.markdown("---")
                
                submit_agregar = st.form_submit_button("💾 Agregar Gasto", type="primary", use_container_width=True)
                
                if submit_agregar:
                    if concepto and monto_total > 0:
                        # Validaciones
                        if tipo_distribucion == "fijo_ricardo" and monto_fijo_ricardo and monto_fijo_ricardo > monto_total:
                            st.error("❌ El monto fijo de Ricardo no puede ser mayor al monto total")
                        elif tipo_distribucion == "fijo_wendy" and monto_fijo_wendy and monto_fijo_wendy > monto_total:
                            st.error("❌ El monto fijo de Wendy no puede ser mayor al monto total")
                        else:
                            # Crear gasto sin grupo
                            if crear_gasto_mensual(conn, concepto, monto_total, frecuencia, tipo_monto,
                                                  tipo_distribucion, monto_fijo_ricardo, monto_fijo_wendy,
                                                  porcentaje_ricardo, None):  # grupo=None
                                tipo_texto = "Fijo" if tipo_monto == "fijo" else "Variable"
                                st.success(f"✅ Gasto '{concepto}' agregado: ${monto_total:.2f} ({tipo_texto})")
                                st.info("💡 Ve a la pestaña 'Grupos de Distribución' si quieres agrupar este gasto con otros")
                                st.rerun()
                    else:
                        st.error("⚠️ Completa todos los campos correctamente.")
        
        # ========== SUBTAB 2: LISTA Y EDICIÓN DE GASTOS ==========
        with subtab2:
            st.subheader("📋 Gastos Mensuales Actuales")
            
            gastos_df = leer_gastos_mensuales(conn)
            
            if not gastos_df.empty:
                # Botón para mostrar/ocultar el editor
                if 'gasto_editar_id' not in st.session_state:
                    st.session_state.gasto_editar_id = None
                
                for _, gasto in gastos_df.iterrows():
                    # Verificar si el gasto está en algún grupo
                    cursor = conn.cursor()
                    query_grupo = """
                        SELECT gd.nombre 
                        FROM grupos_distribucion gd
                        INNER JOIN gastos_en_grupo ge ON gd.id = ge.grupo_id
                        WHERE ge.gasto_id = ? AND gd.activo = 1
                    """
                    cursor.execute(query_grupo, (gasto['id'],))
                    grupo_info = cursor.fetchone()
                    grupo_nombre = grupo_info[0] if grupo_info else None
                    
                    with st.container():
                        # Mostrar información del gasto
                        col1, col2, col3, col4 = st.columns([3, 2, 1.5, 1.5])
                        
                        with col1:
                            icono_tipo = "🔒" if gasto['tipo_monto'] == 'fijo' else "🔄"
                            icono_grupo = "📦 " if grupo_nombre else ""
                            st.write(f"**{icono_grupo}{icono_tipo} {gasto['concepto']}**")
                            if grupo_nombre:
                                st.caption(f"En grupo: {grupo_nombre} | {gasto['frecuencia']}")
                            else:
                                st.caption(f"{gasto['frecuencia']}")
                        
                        with col2:
                            # Mostrar distribución
                            tipo_dist = gasto.get('tipo_distribucion', '50/50')
                            if tipo_dist == 'agrupado':
                                st.write(f"💰 ${gasto['monto_total']:.2f}")
                                st.caption(f"📦 Ver grupo")
                            elif tipo_dist == '50/50':
                                st.write(f"💰 ${gasto['monto_total']:.2f}")
                                st.caption(f"⚖️ c/u: ${gasto['monto_total']/2:.2f}")
                            elif tipo_dist == 'fijo_ricardo':
                                monto_r = gasto.get('monto_fijo_ricardo', 0) or 0
                                monto_w = max(0, gasto['monto_total'] - monto_r)
                                st.write(f"💰 ${gasto['monto_total']:.2f}")
                                st.caption(f"💰R ${monto_r:.2f} | W ${monto_w:.2f}")
                            elif tipo_dist == 'fijo_wendy':
                                monto_w = gasto.get('monto_fijo_wendy', 0) or 0
                                monto_r = max(0, gasto['monto_total'] - monto_w)
                                st.write(f"💰 ${gasto['monto_total']:.2f}")
                                st.caption(f"R ${monto_r:.2f} | 💰W ${monto_w:.2f}")
                            elif tipo_dist == 'personalizado':
                                porc = gasto.get('porcentaje_ricardo', 50) or 50
                                monto_r = gasto['monto_total'] * (porc / 100)
                                monto_w = gasto['monto_total'] * ((100 - porc) / 100)
                                st.write(f"💰 ${gasto['monto_total']:.2f}")
                                st.caption(f"⚙️ R {porc:.0f}% | W {100-porc:.0f}%")
                        
                        with col3:
                            tipo_texto = "Fijo" if gasto['tipo_monto'] == 'fijo' else "Variable"
                            st.caption(f"Tipo: {tipo_texto}")
                        
                        with col4:
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                # No permitir editar si está en un grupo
                                if grupo_nombre:
                                    st.button("✏️", key=f"edit_{gasto['id']}", disabled=True, help="No se puede editar: está en un grupo")
                                else:
                                    if st.button("✏️", key=f"edit_{gasto['id']}", help="Editar"):
                                        st.session_state.gasto_editar_id = gasto['id']
                                        st.rerun()
                            with col_btn2:
                                if st.button("🗑️", key=f"del_{gasto['id']}", help="Eliminar"):
                                    if desactivar_gasto_mensual(conn, gasto['id']):
                                        st.success("✅ Eliminado")
                                        st.rerun()
                        
                        # Formulario de edición (solo si no está en grupo)
                        if st.session_state.gasto_editar_id == gasto['id'] and not grupo_nombre:
                            with st.expander("✏️ Editar Gasto", expanded=True):
                                with st.form(f"form_editar_{gasto['id']}"):
                                    st.write("**Editando:** " + gasto['concepto'])
                                    
                                    nuevo_concepto = st.text_input(
                                        "Concepto",
                                        value=gasto['concepto'],
                                        key=f"concepto_edit_{gasto['id']}"
                                    )
                                    
                                    col_edit1, col_edit2 = st.columns(2)
                                    
                                    with col_edit1:
                                        nuevo_monto = st.number_input(
                                            "Monto Base ($)",
                                            min_value=0.0,
                                            value=float(gasto['monto_total']),
                                            step=0.01,
                                            format="%.2f",
                                            key=f"monto_edit_{gasto['id']}"
                                        )
                                    
                                    with col_edit2:
                                        nueva_frecuencia = st.selectbox(
                                            "Frecuencia",
                                            options=["Mensual", "Semanal", "Quincenal", "Anual"],
                                            index=["Mensual", "Semanal", "Quincenal", "Anual"].index(gasto['frecuencia']),
                                            key=f"frecuencia_edit_{gasto['id']}"
                                        )
                                    
                                    nuevo_tipo = st.radio(
                                        "Tipo de Monto",
                                        options=["fijo", "variable"],
                                        format_func=lambda x: "🔒 Fijo" if x == "fijo" else "🔄 Variable",
                                        index=0 if gasto['tipo_monto'] == 'fijo' else 1,
                                        horizontal=True,
                                        key=f"tipo_edit_{gasto['id']}"
                                    )
                                    
                                    st.markdown("---")
                                    st.markdown("**Distribución:**")
                                    
                                    tipo_dist_actual = gasto.get('tipo_distribucion', '50/50')
                                    opciones_dist = ["50/50", "fijo_ricardo", "fijo_wendy", "personalizado"]
                                    idx_dist = opciones_dist.index(tipo_dist_actual) if tipo_dist_actual in opciones_dist else 0
                                    
                                    nuevo_tipo_dist = st.radio(
                                        "Tipo distribución",
                                        options=opciones_dist,
                                        format_func=lambda x: {
                                            "50/50": "⚖️ 50/50",
                                            "fijo_ricardo": "💰R fijo",
                                            "fijo_wendy": "💰W fijo",
                                            "personalizado": "⚙️ Personalizado"
                                        }[x],
                                        index=idx_dist,
                                        horizontal=True,
                                        key=f"dist_edit_{gasto['id']}"
                                    )
                                    
                                    nuevo_monto_fijo_r = None
                                    nuevo_monto_fijo_w = None
                                    nuevo_porc_r = 50.0
                                    
                                    if nuevo_tipo_dist == "fijo_ricardo":
                                        val_actual = float(gasto.get('monto_fijo_ricardo', 0)) if gasto.get('monto_fijo_ricardo') else 0.0
                                        nuevo_monto_fijo_r = st.number_input(
                                            "Monto fijo Ricardo ($)",
                                            min_value=0.0,
                                            value=val_actual,
                                            step=0.01,
                                            format="%.2f",
                                            key=f"monto_r_edit_{gasto['id']}"
                                        )
                                    elif nuevo_tipo_dist == "fijo_wendy":
                                        val_actual = float(gasto.get('monto_fijo_wendy', 0)) if gasto.get('monto_fijo_wendy') else 0.0
                                        nuevo_monto_fijo_w = st.number_input(
                                            "Monto fijo Wendy ($)",
                                            min_value=0.0,
                                            value=val_actual,
                                            step=0.01,
                                            format="%.2f",
                                            key=f"monto_w_edit_{gasto['id']}"
                                        )
                                    elif nuevo_tipo_dist == "personalizado":
                                        val_actual = float(gasto.get('porcentaje_ricardo', 50)) if gasto.get('porcentaje_ricardo') else 50.0
                                        nuevo_porc_r = st.slider(
                                            "% Ricardo",
                                            0.0, 100.0, val_actual, 1.0,
                                            key=f"porc_r_edit_{gasto['id']}"
                                        )
                                    
                                    col_btn_edit1, col_btn_edit2 = st.columns(2)
                                    
                                    with col_btn_edit1:
                                        submit_editar = st.form_submit_button("💾 Guardar", type="primary", use_container_width=True)
                                    
                                    with col_btn_edit2:
                                        cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)
                                    
                                    if submit_editar:
                                        if actualizar_gasto_mensual(conn, gasto['id'], nuevo_concepto, nuevo_monto, 
                                                                   nueva_frecuencia, nuevo_tipo, nuevo_tipo_dist,
                                                                   nuevo_monto_fijo_r, nuevo_monto_fijo_w,
                                                                   nuevo_porc_r, None):
                                            st.success("✅ Actualizado")
                                            st.session_state.gasto_editar_id = None
                                            st.rerun()
                                    
                                    if cancelar:
                                        st.session_state.gasto_editar_id = None
                                        st.rerun()
                        
                        st.markdown("---")
            else:
                st.info("No hay gastos configurados. Agrega uno en 'Agregar Gasto'.")
        
        # ========== SUBTAB 3: GRUPOS DE DISTRIBUCIÓN (NUEVO) ==========
        with subtab3:
            st.subheader("📦 Grupos de Distribución")
            st.info("💡 Aquí puedes agrupar varios gastos para que una persona pague un monto fijo por todos.")
            
            # Obtener grupos existentes
            grupos = obtener_grupos_distribucion(conn)
            
            if grupos:
                st.markdown("### Grupos Activos")
                
                for grupo in grupos:
                    with st.expander(f"📦 {grupo['nombre']}", expanded=False):
                        st.write(f"**Descripción:** {grupo['descripcion'] or 'Sin descripción'}")
                        
                        quien_paga = grupo['quien_paga_fijo']
                        monto_fijo = grupo['monto_fijo_ricardo'] if quien_paga == 'Ricardo' else grupo['monto_fijo_wendy']
                        
                        st.write(f"**💰 {quien_paga} paga:** ${monto_fijo:.2f} fijo")
                        
                        # Calcular total del grupo
                        total_grupo = sum(g[2] for g in grupo['gastos'])
                        monto_otro = max(0, total_grupo - monto_fijo)
                        otro = "Wendy" if quien_paga == "Ricardo" else "Ricardo"
                        
                        st.write(f"**{otro} paga:** ${monto_otro:.2f} (diferencia)")
                        st.write(f"**Total del grupo:** ${total_grupo:.2f}")
                        
                        st.markdown("**Gastos incluidos:**")
                        for gasto_id, concepto, monto in grupo['gastos']:
                            st.caption(f"  • {concepto}: ${monto:.2f}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✏️ Editar", key=f"edit_grupo_{grupo['id']}"):
                                st.session_state[f"editando_grupo_{grupo['id']}"] = True
                                st.rerun()
                        with col2:
                            if st.button("🗑️ Eliminar", key=f"del_grupo_{grupo['id']}"):
                                if eliminar_grupo_distribucion(conn, grupo['id']):
                                    st.success("✅ Grupo eliminado. Los gastos vuelven a distribución individual.")
                                    st.rerun()
                
                st.markdown("---")
            
            # Formulario para crear nuevo grupo
            st.markdown("### ➕ Crear Nuevo Grupo")
            
            with st.form("form_nuevo_grupo"):
                nombre_grupo = st.text_input(
                    "Nombre del Grupo",
                    placeholder="Ej: Servicios Básicos, Alimentación",
                    help="Nombre que identifica este grupo"
                )
                
                descripcion_grupo = st.text_area(
                    "Descripción (opcional)",
                    placeholder="Ej: Servicios de luz, agua y gas del hogar",
                    max_chars=200
                )
                
                st.markdown("### 💰 Distribución del Grupo")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    quien_paga_fijo = st.radio(
                        "¿Quién paga monto fijo?",
                        options=["Ricardo", "Wendy"],
                        horizontal=True
                    )
                
                with col2:
                    monto_fijo_grupo = st.number_input(
                        f"Monto fijo que paga {quien_paga_fijo} ($)",
                        min_value=0.0,
                        value=100.0,
                        step=0.01,
                        format="%.2f"
                    )
                
                st.markdown("### 📋 Selecciona Gastos")
                st.caption("Elige los gastos que deseas agrupar")
                
                # Obtener gastos disponibles (no agrupados)
                gastos_disponibles = gastos_df[
                    (gastos_df['tipo_distribucion'] != 'agrupado') & 
                    (gastos_df['activo'] == 1)
                ].copy()
                
                if gastos_disponibles.empty:
                    st.warning("⚠️ No hay gastos disponibles para agrupar. Crea gastos primero en 'Agregar Gasto'.")
                    gastos_seleccionados = []
                else:
                    gastos_seleccionados = []
                    total_seleccionado = 0
                    
                    for _, gasto in gastos_disponibles.iterrows():
                        col_check, col_info = st.columns([1, 4])
                        
                        with col_check:
                            if st.checkbox(
                                "",
                                key=f"sel_gasto_{gasto['id']}",
                                label_visibility="collapsed"
                            ):
                                gastos_seleccionados.append(gasto['id'])
                                total_seleccionado += gasto['monto_total']
                        
                        with col_info:
                            st.write(f"**{gasto['concepto']}** - ${gasto['monto_total']:.2f}")
                    
                    if gastos_seleccionados:
                        st.info(f"💰 **Total de gastos seleccionados:** ${total_seleccionado:.2f}")
                        st.success(f"✅ {quien_paga_fijo}: ${monto_fijo_grupo:.2f} | {('Wendy' if quien_paga_fijo == 'Ricardo' else 'Ricardo')}: ${max(0, total_seleccionado - monto_fijo_grupo):.2f}")
                
                submit_grupo = st.form_submit_button("💾 Crear Grupo de Distribución", type="primary", use_container_width=True)
                
                if submit_grupo:
                    if not nombre_grupo:
                        st.error("❌ Ingresa un nombre para el grupo")
                    elif len(gastos_seleccionados) < 2:
                        st.error("❌ Selecciona al menos 2 gastos para crear un grupo")
                    else:
                        grupo_id = crear_grupo_distribucion(
                            conn, 
                            nombre_grupo, 
                            descripcion_grupo,
                            quien_paga_fijo,
                            monto_fijo_grupo,
                            gastos_seleccionados
                        )
                        if grupo_id:
                            st.success(f"✅ Grupo '{nombre_grupo}' creado correctamente")
                            st.info(f"Los {len(gastos_seleccionados)} gastos ahora están agrupados con distribución fija.")
                            st.rerun()
                        else:
                            st.error("❌ Error al crear el grupo")
    
    # ========== TAB 4: ELIMINAR PAGOS ==========
    with tab4:
        st.header(f"🗑️ Eliminar Pagos - {meses[mes_seleccionado]} {anio_seleccionado}")
        
        st.warning("⚠️ Esta sección te permite corregir errores eliminando pagos que se registraron por equivocación.")
        
        # Obtener pagos del mes
        pagos_df = obtener_pagos_del_mes(conn, mes_seleccionado, anio_seleccionado)
        
        if not pagos_df.empty:
            st.subheader(f"Pagos registrados en {meses[mes_seleccionado]} {anio_seleccionado}")
            
            # Mostrar cada pago con opción de eliminar
            for idx, pago in pagos_df.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
                    
                    with col1:
                        # Mostrar el concepto y si es semanal, el número de semana
                        if pago['frecuencia'] == 'Semanal' and pago['semana'] is not None:
                            rango = obtener_rango_semana(mes_seleccionado, anio_seleccionado, int(pago['semana']))
                            st.write(f"**{pago['concepto']}** 📅 Semana {int(pago['semana'])} ({rango[0]}-{rango[1]})")
                        else:
                            st.write(f"**{pago['concepto']}**")
                    
                    with col2:
                        st.write(f"💵 ${pago['monto_pagado']:.2f}")
                    
                    with col3:
                        icono = "👨" if pago['quien_pago'] == 'Ricardo' else "👩"
                        st.write(f"{icono} {pago['quien_pago']}")
                    
                    with col4:
                        st.caption(pago['fecha_pago'])
                    
                    with col5:
                        if st.button("🗑️", key=f"eliminar_pago_{pago['id']}", help="Eliminar este pago"):
                            if eliminar_pago(conn, pago['id']):
                                st.success("✅ Pago eliminado")
                                st.rerun()
                    
                    st.markdown("---")
            
            # Opción de limpiar todos los pagos del mes
            st.markdown("---")
            st.subheader("⚠️ Zona Peligrosa")
            
            col_danger1, col_danger2 = st.columns([3, 1])
            
            with col_danger1:
                st.error(f"**Eliminar TODOS los pagos de {meses[mes_seleccionado]} {anio_seleccionado}**")
                st.caption("Esta acción no se puede deshacer. Se eliminarán todos los pagos de este mes.")
            
            with col_danger2:
                if st.button("🗑️ Eliminar Todos", type="primary", key="eliminar_todos"):
                    # Confirmación adicional
                    if 'confirmar_eliminar_todos' not in st.session_state:
                        st.session_state.confirmar_eliminar_todos = True
                        st.warning("⚠️ Haz clic nuevamente para confirmar")
                    else:
                        cursor = conn.cursor()
                        cursor.execute('''
                            DELETE FROM pagos
                            WHERE mes = ? AND anio = ?
                        ''', (mes_seleccionado, anio_seleccionado))
                        conn.commit()
                        eliminados = cursor.rowcount
                        st.success(f"✅ Se eliminaron {eliminados} pagos")
                        del st.session_state.confirmar_eliminar_todos
                        st.rerun()
        else:
            st.info("No hay pagos registrados en este mes para eliminar.")
    
    # ========== TAB 5: REPORTES PDF ==========
    with tab5:
        st.header(f"📄 Generar Reportes PDF - {meses[mes_seleccionado]} {anio_seleccionado}")
        
        st.info("📋 Genera reportes detallados en formato PDF para imprimir o compartir")
        
        col1, col2, col3 = st.columns(3)
        
        # Reporte General
        with col1:
            st.subheader("📊 Reporte General")
            st.write("Incluye:")
            st.write("✅ Resumen financiero completo")
            st.write("✅ Estado de todos los gastos")
            st.write("✅ Pagos de Ricardo y Wendy")
            st.write("✅ Historial completo del mes")
            
            if st.button("📥 Descargar Reporte General", key="btn_general", type="primary"):
                with st.spinner("Generando PDF..."):
                    pdf_buffer = generar_pdf_reporte_general(conn, mes_seleccionado, anio_seleccionado)
                    
                    st.download_button(
                        label="💾 Descargar PDF General",
                        data=pdf_buffer,
                        file_name=f"Reporte_General_{meses[mes_seleccionado]}_{anio_seleccionado}.pdf",
                        mime="application/pdf",
                        key="download_general"
                    )
                    st.success("✅ PDF generado correctamente")
        
        # Reporte Ricardo
        with col2:
            st.subheader("👨 Reporte Ricardo")
            st.write("Incluye:")
            st.write("✅ Resumen personal de Ricardo")
            st.write("✅ Cuánto debe pagar")
            st.write("✅ Qué ha pagado")
            st.write("✅ Qué le falta pagar")
            
            if st.button("📥 Descargar Reporte Ricardo", key="btn_ricardo", type="primary"):
                with st.spinner("Generando PDF..."):
                    pdf_buffer = generar_pdf_reporte_individual(conn, mes_seleccionado, anio_seleccionado, "Ricardo")
                    
                    st.download_button(
                        label="💾 Descargar PDF Ricardo",
                        data=pdf_buffer,
                        file_name=f"Reporte_Ricardo_{meses[mes_seleccionado]}_{anio_seleccionado}.pdf",
                        mime="application/pdf",
                        key="download_ricardo"
                    )
                    st.success("✅ PDF generado correctamente")
        
        # Reporte Wendy
        with col3:
            st.subheader("👩 Reporte Wendy")
            st.write("Incluye:")
            st.write("✅ Resumen personal de Wendy")
            st.write("✅ Cuánto debe pagar")
            st.write("✅ Qué ha pagado")
            st.write("✅ Qué le falta pagar")
            
            if st.button("📥 Descargar Reporte Wendy", key="btn_wendy", type="primary"):
                with st.spinner("Generando PDF..."):
                    pdf_buffer = generar_pdf_reporte_individual(conn, mes_seleccionado, anio_seleccionado, "Wendy")
                    
                    st.download_button(
                        label="💾 Descargar PDF Wendy",
                        data=pdf_buffer,
                        file_name=f"Reporte_Wendy_{meses[mes_seleccionado]}_{anio_seleccionado}.pdf",
                        mime="application/pdf",
                        key="download_wendy"
                    )
                    st.success("✅ PDF generado correctamente")
        
        st.markdown("---")
        
        # Vista previa de contenido
        st.subheader("👁️ Vista Previa del Contenido")
        
        tabla_df = calcular_tabla_mensual(conn, mes_seleccionado, anio_seleccionado)
        saldo = calcular_saldo_neto(conn, mes_seleccionado, anio_seleccionado)
        
        # Obtener totales específicos de cada persona
        total_debe_ricardo = saldo.get('total_debe_ricardo', saldo['total_debe_cada_uno'])
        total_debe_wendy = saldo.get('total_debe_wendy', saldo['total_debe_cada_uno'])
        total_gastos = total_debe_ricardo + total_debe_wendy
        
        col_prev1, col_prev2 = st.columns(2)
        
        with col_prev1:
            st.write("**👨 Ricardo:**")
            st.write(f"- Debe pagar: ${total_debe_ricardo:.2f}")
            st.write(f"- Ya pagó: ${saldo['pagado_ricardo']:.2f}")
            st.write(f"- Pendiente: ${saldo['saldo_ricardo']:.2f}")
            ricardo_prog = (saldo['pagado_ricardo'] / total_debe_ricardo * 100) if total_debe_ricardo > 0 else 0
            st.write(f"- Progreso: {ricardo_prog:.0f}%")
        
        with col_prev2:
            st.write("**👩 Wendy:**")
            st.write(f"- Debe pagar: ${total_debe_wendy:.2f}")
            st.write(f"- Ya pagó: ${saldo['pagado_wendy']:.2f}")
            st.write(f"- Pendiente: ${saldo['saldo_wendy']:.2f}")
            wendy_prog = (saldo['pagado_wendy'] / total_debe_wendy * 100) if total_debe_wendy > 0 else 0
            st.write(f"- Progreso: {wendy_prog:.0f}%")
        
        st.markdown("---")
        st.write(f"**💰 Total Gastos del Mes:** ${total_gastos:.2f}")
        st.write(f"**📊 Estado:** {saldo['mensaje']}")
        
        if not tabla_df.empty:
            st.write("**Detalle de Gastos:**")
            st.dataframe(
                tabla_df.drop('id', axis=1), 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Concepto": st.column_config.TextColumn(
                        "Concepto",
                        width="medium"
                    ),
                    "Monto Total": st.column_config.NumberColumn(
                        "Monto Total",
                        format="$%.2f",
                        width="small"
                    ),
                    "Frecuencia": st.column_config.TextColumn(
                        "Frecuencia",
                        width="small"
                    ),
                    "Asignado Ricardo": st.column_config.NumberColumn(
                        "Asignado Ricardo",
                        format="$%.2f",
                        width="small"
                    ),
                    "Asignado Wendy": st.column_config.NumberColumn(
                        "Asignado Wendy",
                        format="$%.2f",
                        width="small"
                    ),
                    "Ricardo Pagó": st.column_config.TextColumn(
                        "Ricardo Pagó",
                        width="small"
                    ),
                    "Wendy Pagó": st.column_config.TextColumn(
                        "Wendy Pagó",
                        width="small"
                    )
                }
            )
    
    # ========== TAB 6: ESTADÍSTICAS ==========
    with tab6:
        st.header("� Estadísticas y Gráficos")
        
        # Gráfico de gastos en el tiempo
        st.subheader("📊 Gastos en el Tiempo")
        fig_tiempo = crear_grafico_gastos_tiempo(conn)
        
        if fig_tiempo:
            st.plotly_chart(fig_tiempo, use_container_width=True)
        else:
            st.info("No hay datos suficientes para mostrar el gráfico de tiempo.")
        
        st.markdown("---")
        
        # Gráfico de distribución del mes actual
        st.subheader(f"🥧 Distribución de Gastos - {meses[mes_seleccionado]} {anio_seleccionado}")
        fig_distribucion = crear_grafico_distribucion(conn, mes_seleccionado, anio_seleccionado)
        
        if fig_distribucion:
            st.plotly_chart(fig_distribucion, use_container_width=True)
        else:
            st.info("No hay pagos registrados para este mes.")
        
        st.markdown("---")
        
        # Tabla de historial de pagos
        st.subheader("📋 Historial de Pagos")
        pagos_df = obtener_pagos_del_mes(conn, mes_seleccionado, anio_seleccionado)
        
        if not pagos_df.empty:
            # Formatear para mostrar
            pagos_display = pagos_df[['concepto', 'quien_pago', 'monto_pagado', 'fecha_pago']].copy()
            pagos_display.columns = ['Concepto', 'Quien Pagó', 'Monto', 'Fecha']
            pagos_display['Monto'] = pagos_display['Monto'].apply(lambda x: f"${x:.2f}")
            
            st.dataframe(
                pagos_display, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Concepto": st.column_config.TextColumn(
                        "Concepto",
                        width="medium"
                    ),
                    "Quien Pagó": st.column_config.TextColumn(
                        "Quien Pagó",
                        width="small"
                    ),
                    "Monto": st.column_config.TextColumn(
                        "Monto",
                        width="small"
                    ),
                    "Fecha": st.column_config.TextColumn(
                        "Fecha",
                        width="small"
                    )
                }
            )
        else:
            st.info("No hay pagos registrados para este mes.")
    
    # ========== TAB 7: RESUMEN ==========
    with tab7:
        st.header(f"💰 Resumen - {meses[mes_seleccionado]} {anio_seleccionado}")
        
        # Indicador de mes
        if mes_seleccionado == fecha_actual.month and anio_seleccionado == fecha_actual.year:
            st.success(f"✅ Resumen del mes **actual**: {meses[mes_seleccionado]} {anio_seleccionado}")
        else:
            st.info(f"📅 Resumen de: {meses[mes_seleccionado]} {anio_seleccionado}")
        
        saldo = calcular_saldo_neto(conn, mes_seleccionado, anio_seleccionado)
        
        # Mostrar resumen en tarjetas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="💰 Total Debe Cada Uno",
                value=f"${saldo['total_debe_cada_uno']:.2f}"
            )
        
        with col2:
            st.metric(
                label="� Ha Pagado Ricardo",
                value=f"${saldo['pagado_ricardo']:.2f}"
            )
        
        with col3:
            st.metric(
                label="� Ha Pagado Wendy",
                value=f"${saldo['pagado_wendy']:.2f}"
            )
        
        st.markdown("---")
        
        # Pendientes
        col4, col5 = st.columns(2)
        
        with col4:
            color_ricardo = "off" if saldo['saldo_ricardo'] <= 0 else "normal"
            st.metric(
                label="📊 Pendiente Ricardo",
                value=f"${saldo['saldo_ricardo']:.2f}",
                delta=f"-${saldo['pagado_ricardo']:.2f}" if saldo['pagado_ricardo'] > 0 else None,
                delta_color=color_ricardo
            )
        
        with col5:
            color_wendy = "off" if saldo['saldo_wendy'] <= 0 else "normal"
            st.metric(
                label="📊 Pendiente Wendy",
                value=f"${saldo['saldo_wendy']:.2f}",
                delta=f"-${saldo['pagado_wendy']:.2f}" if saldo['pagado_wendy'] > 0 else None,
                delta_color=color_wendy
            )
        
        st.markdown("---")
        
        # Mostrar el mensaje del saldo neto
        if "pagado" in saldo['mensaje'].lower():
            st.success(f"✅ **{saldo['mensaje']}**")
        else:
            st.warning(f"⚠️ **{saldo['mensaje']}**")
        
        # Barra de progreso
        st.subheader("📊 Progreso de Pagos")
        
        col_prog1, col_prog2 = st.columns(2)
        
        with col_prog1:
            st.write("**Ricardo**")
            if saldo['total_debe_cada_uno'] > 0:
                progreso_ricardo = min(saldo['pagado_ricardo'] / saldo['total_debe_cada_uno'], 1.0)
                st.progress(progreso_ricardo)
                st.caption(f"{progreso_ricardo*100:.1f}% pagado")
        
        with col_prog2:
            st.write("**Wendy**")
            if saldo['total_debe_cada_uno'] > 0:
                progreso_wendy = min(saldo['pagado_wendy'] / saldo['total_debe_cada_uno'], 1.0)
                st.progress(progreso_wendy)
                st.caption(f"{progreso_wendy*100:.1f}% pagado")
    
    # ========== TAB 8: INTERFAZ RICARDO ==========
    with tab8:
        st.header(f"👨 Interfaz de Ricardo - {meses[mes_seleccionado]} {anio_seleccionado}")
        
        # Obtener la tabla mensual completa
        tabla_df = calcular_tabla_mensual(conn, mes_seleccionado, anio_seleccionado)
        
        if not tabla_df.empty:
            # Calcular pagos realizados por Ricardo para cada gasto
            gastos_con_info = []
            cursor = conn.cursor()
            
            for _, gasto in tabla_df.iterrows():
                gasto_id = gasto['id']
                concepto = gasto['Concepto']
                monto_total = gasto['Monto Total']
                frecuencia = gasto['Frecuencia']
                debe_pagar_total = gasto['Asignado Ricardo']
                
                # Obtener cuánto ya pagó Ricardo para este gasto
                ya_pago = 0
                
                try:
                    # Si es un grupo, necesitamos sumar los pagos de todos los gastos del grupo
                    if str(gasto_id).startswith('grupo_'):
                        grupo_id = int(str(gasto_id).replace('grupo_', ''))
                        query = """
                            SELECT COALESCE(SUM(p.monto_pagado), 0) as total_pagado
                            FROM pagos p
                            INNER JOIN gastos_en_grupo geg ON p.gasto_id = geg.gasto_id
                            WHERE geg.grupo_id = ? AND p.mes = ? AND p.anio = ? AND p.quien_pago = 'Ricardo'
                        """
                        cursor.execute(query, (grupo_id, mes_seleccionado, anio_seleccionado))
                        result = cursor.fetchone()
                        ya_pago = result[0] if result else 0
                    else:
                        query = """
                            SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                            FROM pagos
                            WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = 'Ricardo'
                        """
                        cursor.execute(query, (gasto_id, mes_seleccionado, anio_seleccionado))
                        result = cursor.fetchone()
                        ya_pago = result[0] if result else 0
                except Exception as e:
                    # Si hay error en la consulta, asumir que no ha pagado nada
                    ya_pago = 0
                
                pendiente = debe_pagar_total - ya_pago
                
                # Solo agregar si hay algo pendiente (incluso si ya pagó algo parcialmente)
                if pendiente > 0:
                    gastos_con_info.append({
                        'concepto': concepto,
                        'monto_total': monto_total,
                        'frecuencia': frecuencia,
                        'debe_pagar_total': debe_pagar_total,
                        'ya_pago': ya_pago,
                        'pendiente': pendiente
                    })
            
            if gastos_con_info:
                st.info(f"💡 Tienes **{len(gastos_con_info)}** gastos pendientes por pagar")
                
                total_pendiente = 0
                
                for gasto_info in gastos_con_info:
                    total_pendiente += gasto_info['pendiente']
                    
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            st.markdown(f"**{gasto_info['concepto']}**")
                            st.caption(f"Frecuencia: {gasto_info['frecuencia']} | Total: ${gasto_info['monto_total']:.2f}")
                        
                        with col2:
                            st.metric("Debes Pagar", f"${gasto_info['debe_pagar_total']:.2f}")
                            if gasto_info['ya_pago'] > 0:
                                st.caption(f"✅ Pagaste: ${gasto_info['ya_pago']:.2f}")
                        
                        with col3:
                            st.metric("Pendiente", f"${gasto_info['pendiente']:.2f}")
                        
                        st.markdown("---")
                
                # Resumen total
                st.subheader("📊 Resumen Total")
                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.metric("Total Pendiente", f"${total_pendiente:.2f}")
                with col_res2:
                    saldo = calcular_saldo_neto(conn, mes_seleccionado, anio_seleccionado)
                    st.metric("Total Pagado", f"${saldo['pagado_ricardo']:.2f}")
            else:
                st.success("🎉 ¡Excelente! No tienes gastos pendientes por pagar este mes.")
                saldo = calcular_saldo_neto(conn, mes_seleccionado, anio_seleccionado)
                st.metric("Total Pagado", f"${saldo['pagado_ricardo']:.2f}")
        else:
            st.info("No hay gastos registrados para este mes.")
    
    # ========== TAB 9: INTERFAZ WENDY ==========
    with tab9:
        st.header(f"👩 Interfaz de Wendy - {meses[mes_seleccionado]} {anio_seleccionado}")
        
        # Obtener la tabla mensual completa
        tabla_df = calcular_tabla_mensual(conn, mes_seleccionado, anio_seleccionado)
        
        if not tabla_df.empty:
            # Calcular pagos realizados por Wendy para cada gasto
            gastos_con_info = []
            cursor = conn.cursor()
            
            for _, gasto in tabla_df.iterrows():
                gasto_id = gasto['id']
                concepto = gasto['Concepto']
                monto_total = gasto['Monto Total']
                frecuencia = gasto['Frecuencia']
                debe_pagar_total = gasto['Asignado Wendy']
                
                # Obtener cuánto ya pagó Wendy para este gasto
                ya_pago = 0
                
                try:
                    # Si es un grupo, necesitamos sumar los pagos de todos los gastos del grupo
                    if str(gasto_id).startswith('grupo_'):
                        grupo_id = int(str(gasto_id).replace('grupo_', ''))
                        query = """
                            SELECT COALESCE(SUM(p.monto_pagado), 0) as total_pagado
                            FROM pagos p
                            INNER JOIN gastos_en_grupo geg ON p.gasto_id = geg.gasto_id
                            WHERE geg.grupo_id = ? AND p.mes = ? AND p.anio = ? AND p.quien_pago = 'Wendy'
                        """
                        cursor.execute(query, (grupo_id, mes_seleccionado, anio_seleccionado))
                        result = cursor.fetchone()
                        ya_pago = result[0] if result else 0
                    else:
                        query = """
                            SELECT COALESCE(SUM(monto_pagado), 0) as total_pagado
                            FROM pagos
                            WHERE gasto_id = ? AND mes = ? AND anio = ? AND quien_pago = 'Wendy'
                        """
                        cursor.execute(query, (gasto_id, mes_seleccionado, anio_seleccionado))
                        result = cursor.fetchone()
                        ya_pago = result[0] if result else 0
                except Exception as e:
                    # Si hay error en la consulta, asumir que no ha pagado nada
                    ya_pago = 0
                
                pendiente = debe_pagar_total - ya_pago
                
                # Solo agregar si hay algo pendiente (incluso si ya pagó algo parcialmente)
                if pendiente > 0:
                    gastos_con_info.append({
                        'concepto': concepto,
                        'monto_total': monto_total,
                        'frecuencia': frecuencia,
                        'debe_pagar_total': debe_pagar_total,
                        'ya_pago': ya_pago,
                        'pendiente': pendiente
                    })
            
            if gastos_con_info:
                st.info(f"💡 Tienes **{len(gastos_con_info)}** gastos pendientes por pagar")
                
                total_pendiente = 0
                
                for gasto_info in gastos_con_info:
                    total_pendiente += gasto_info['pendiente']
                    
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            st.markdown(f"**{gasto_info['concepto']}**")
                            st.caption(f"Frecuencia: {gasto_info['frecuencia']} | Total: ${gasto_info['monto_total']:.2f}")
                        
                        with col2:
                            st.metric("Debes Pagar", f"${gasto_info['debe_pagar_total']:.2f}")
                            if gasto_info['ya_pago'] > 0:
                                st.caption(f"✅ Pagaste: ${gasto_info['ya_pago']:.2f}")
                        
                        with col3:
                            st.metric("Pendiente", f"${gasto_info['pendiente']:.2f}")
                        
                        st.markdown("---")
                
                # Resumen total
                st.subheader("📊 Resumen Total")
                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.metric("Total Pendiente", f"${total_pendiente:.2f}")
                with col_res2:
                    saldo = calcular_saldo_neto(conn, mes_seleccionado, anio_seleccionado)
                    st.metric("Total Pagado", f"${saldo['pagado_wendy']:.2f}")
            else:
                st.success("🎉 ¡Excelente! No tienes gastos pendientes por pagar este mes.")
                saldo = calcular_saldo_neto(conn, mes_seleccionado, anio_seleccionado)
                st.metric("Total Pagado", f"${saldo['pagado_wendy']:.2f}")
        else:
            st.info("No hay gastos registrados para este mes.")

if __name__ == "__main__":
    main()
