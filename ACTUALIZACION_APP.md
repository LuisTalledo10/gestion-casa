# 🔄 Guía de Actualización de app.py para Google Sheets

## ⚠️ IMPORTANTE

Este documento explica cómo actualizar `app.py` para usar Google Sheets.
El cambio completo es extenso (3000+ líneas de código). 

**Recomendaciones:**
1. Lee esta guía completa primero
2. Haz backup de `app.py` actual
3. Considera probar con una versión simplificada primero
4. O solicita una versión completamente adaptada

---

## 📋 Cambios Necesarios

### 1. Cambios en las Importaciones ✅ (Ya hecho)

```python
# ANTES:
import sqlite3

# AHORA:
from google_sheets_db import GoogleSheetsDB
```

### 2. Cambios en la Conexión ✅ (Ya hecho)

```python
# ANTES:
conn = sqlite3.connect('contabilidad.db')

# AHORA:
db = get_database()  # Retorna GoogleSheetsDB con cache
```

### 3. Cambios en Funciones CRUD ⚠️ (Parcialmente hecho)

Hay **23 funciones** que necesitan actualización. Las principales ya están actualizadas:

✅ `crear_gasto_mensual()` - Actualizada
✅ `leer_gastos_mensuales()` - Actualizada
✅ `actualizar_gasto_mensual()` - Actualizada
✅ `desactivar_gasto_mensual()` - Actualizada

⚠️ Funciones pendientes:
- `obtener_monto_del_mes()`
- `establecer_monto_del_mes()`
- `obtener_montos_configurados()`
- `registrar_pago()`
- `obtener_pagos_del_mes()`
- `calcular_tabla_mensual()`
- `calcular_saldo_neto()`
- ... y otras 16 más

### 4. Patrón de Conversión

Para cada función que use SQLite, aplica este patrón:

```python
# ANTES (SQLite):
def mi_funcion(conn, ...):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tabla WHERE ...")
    resultado = cursor.fetchall()
    return resultado

# DESPUÉS (Google Sheets):
def mi_funcion(db, ...):
    try:
        df = db.obtener_gastos_mensuales()  # o el método correspondiente
        # Filtrar df según necesites
        return df
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()
```

---

## 🚀 Opciones de Implementación

### Opción A: Actualización Manual Gradual

**Pros:** Control total, entiendes cada cambio
**Contras:** Toma tiempo (2-4 horas)

**Pasos:**
1. Haz backup de `app.py`
2. Actualiza una función a la vez
3. Prueba después de cada cambio
4. Continúa con la siguiente

### Opción B: Usar Adapter Pattern (Recomendado)

Crear un archivo `db_adapter.py` que traduzca llamadas SQL a Google Sheets:

```python
class DBAdapter:
    def __init__(self, gs_db):
        self.db = gs_db
    
    def cursor(self):
        return self
    
    def execute(self, query, params=()):
        # Traducir SQL a llamadas de Google Sheets
        # Ejemplo simplificado
        if "SELECT * FROM gastos_mensuales" in query:
            df = self.db.obtener_gastos_mensuales()
            return df
        # ... más traducciones
    
    def fetchall(self):
        # Retornar resultados
        pass
```

Luego en `app.py`:
```python
db = get_database()
conn = DBAdapter(db)  # conn funciona igual que antes
```

**Pros:** Cambios mínimos en app.py
**Contras:** Requiere crear adapter completo

### Opción C: Versión Simplificada Nueva ⭐

Crear `app_v2.py` con solo las funciones esenciales adaptadas a Google Sheets:

- ✅ Tabla mensual de gastos
- ✅ Registro de pagos
- ✅ Resumen de saldos
- ✅ Reportes PDF
- ❌ (Sin) Grupos de distribución complejos
- ❌ (Sin) Montos variables por mes

**Pros:** Funciona inmediatamente, código limpio
**Contras:** Pierdes algunas funciones avanzadas

---

## 🛠️ Implementación Recomendada

Te recomiendo **Opción C** para empezar:

1. Crear `app_simple.py` con funciones básicas
2. Probar que funciona con Google Sheets
3. Migrar tus datos
4. Una vez estable, agregar funciones avanzadas

---

## 📝 Lista de Verificación

Antes de desplegar:

- [ ] Configuraste Google Cloud y API
- [ ] Creaste el spreadsheet
- [ ] Compartiste con cuenta de servicio
- [ ] Configuraste `.streamlit/secrets.toml` localmente
- [ ] Probaste la conexión: `streamlit run migrate_to_sheets.py`
- [ ] Migraste los datos existentes
- [ ] Probaste crear/leer/actualizar gastos
- [ ] Configuraste secrets en Streamlit Cloud
- [ ] Hiciste commit y push
- [ ] Verificaste que funciona en producción

---

## 🆘 ¿Necesitas Ayuda?

### Opción 1: Quiero que actualices TODO app.py ahora
- Toma ~30-60 minutos
- Genera archivo completo con ~3000 líneas
- Requiere pruebas extensivas

### Opción 2: Quiero versión simplificada (app_simple.py)
- Toma ~10 minutos
- Solo funciones esenciales
- Funciona inmediatamente

### Opción 3: Ayúdame a crear el adapter
- Toma ~15 minutos
- Cambios mínimos en app.py
- Mantiene todas las funciones

**¿Qué opción prefieres?** 🤔

---

## 💡 Recomendación Personal

Para tu caso (problema de pérdida de datos en Streamlit Cloud), te recomiendo:

1. **Crear `app_simple.py`** con funciones básicas
2. **Probar localmente** que funciona
3. **Desplegar en Streamlit Cloud** con secrets configurados
4. **Usar por unos días** para verificar que los datos persisten
5. **Luego migrar funciones avanzadas** gradualmente

Esto te permite:
- ✅ Resolver el problema AHORA (datos que se pierden)
- ✅ Tener algo funcionando rápido
- ✅ Ir agregando features gradualmente
- ✅ Menos riesgo de bugs

¿Procedo con crear `app_simple.py`? 🚀
