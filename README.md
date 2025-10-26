# 🏠 Contabilidad Doméstica - Ricardo y Wendy

Aplicación de escritorio en Python para gestionar gastos compartidos mensuales entre Ricardo y Wendy, con sistema de pagos individuales y estadísticas detalladas.

## 🚀 Características Principales

- ✅ **Gastos mensuales recurrentes**: Configura gastos fijos (luz, agua, casa, comida, etc.)
- 💳 **Sistema de pagos individual**: Cada persona paga su parte (50%) de cada gasto
- 📊 **Tabla mensual**: Visualiza qué gastos están pagados y cuáles están pendientes
- 📈 **Gráficos estadísticos**: Visualiza gastos en el tiempo y distribución por categoría
- � **Cálculo automático**: Saldo pendiente de cada persona
- 📱 **Reporte por WhatsApp**: Envío automático del estado de cuentas

## 🎯 Cómo Funciona

1. **Configura tus gastos mensuales** (Ej: Luz $120, Agua $60, Casa $600, Comida semanal $100)
2. **Cada persona paga su parte**: Ricardo y Wendy pagan independientemente el 50% de cada gasto
3. **Visualiza el progreso**: La tabla muestra con ✅ o ❌ qué está pagado
4. **Revisa estadísticas**: Gráficos de gastos en el tiempo
5. **Reporte automático**: Envía el resumen por WhatsApp

## 📋 Requisitos

- Python 3.x
- SQLite3 (incluido en Python)

## 🔧 Instalación

1. **Instalar dependencias**:
```bash
pip install -r requirements.txt
```

O instalar manualmente:
```bash
pip install streamlit pywhatkit pandas plotly
```

## 📂 Estructura del Proyecto

```
gestion_casa/
│
├── app.py              # Interfaz principal con Streamlit
├── reporte.py          # Script de automatización para WhatsApp
├── requirements.txt    # Dependencias del proyecto
├── contabilidad.db     # Base de datos SQLite (se crea automáticamente)
└── README.md          # Este archivo
```

## 🎯 Uso de la Aplicación

### 1. Iniciar la Aplicación

```bash
streamlit run app.py
```

La aplicación se abrirá en tu navegador con 5 pestañas:

#### 📊 Tabla Mensual
- Visualiza todos los gastos del mes seleccionado
- Muestra el monto que debe pagar cada persona (50% del total)
- Indica con ✅ o ❌ si cada persona ya pagó su parte
- Resumen de totales y pendientes

#### � Pagar Gastos
- Selecciona quién está pagando (Ricardo o Wendy)
- Lista de gastos pendientes de pago
- Muestra el monto exacto a pagar (50% del total)
- Botón "Pagar" para registrar el pago

**Ejemplo**: Si la luz cuesta $120 mensuales, Wendy debe pagar $60. Al dar clic en "Pagar", se registra su pago y aparece ✅ en la tabla.

#### ⚙️ Gestionar Gastos
- **Agregar gastos mensuales**: Concepto, monto total y frecuencia
- **Ver gastos actuales**: Lista de todos los gastos configurados
- **Eliminar gastos**: Desactiva gastos que ya no aplican

**Ejemplos de gastos**:
- Luz: $120 - Mensual
- Agua: $60 - Mensual  
- Casa: $600 - Mensual
- Comida: $100 - Semanal

#### 📈 Estadísticas
- **Gráfico de línea**: Gastos en el tiempo por persona
- **Gráfico de pastel**: Distribución de gastos del mes
- **Historial de pagos**: Tabla detallada de todos los pagos

#### 💰 Resumen
- Total que debe pagar cada uno (50/50)
- Cuánto ha pagado cada persona
- Cuánto falta por pagar
- Barra de progreso de pagos
- Mensaje claro de quién debe pagar

### 2. Script de Reporte Automático

#### Configuración inicial:

1. Abre el archivo `reporte.py`
2. Verifica o modifica los números de teléfono:

```python
TELEFONO_RICARDO = '+51939597167'  # Número de Ricardo
TELEFONO_WENDY = '+51936250157'    # Número de Wendy
```

**Formato del número**: `+[código_país][número]` (Ejemplo: `+51987654321` para Perú)

#### Ejecución manual:

```bash
python reporte.py
```

**Requisitos importantes:**
- Debes tener WhatsApp Web configurado en tu navegador predeterminado
- Debes tener sesión activa en WhatsApp Web
- El script abrirá automáticamente el navegador

### 3. Automatización con Programador de Tareas (Windows)

Para ejecutar el reporte automáticamente cada mes:

1. Abre **Programador de Tareas** de Windows
2. Clic en **Crear Tarea Básica**
3. Nombre: "Reporte Contabilidad Mensual"
4. Desencadenador: **Mensual** (elige el día, ej: día 1 de cada mes)
5. Acción: **Iniciar un programa**
   - Programa: `D:\proyectos\gestion_casa\.venv\Scripts\python.exe`
   - Argumentos: `D:\proyectos\gestion_casa\reporte.py`
   - Iniciar en: `D:\proyectos\gestion_casa`
6. Finalizar y guardar

## 📊 Base de Datos

### Tabla: gastos_mensuales

| Campo           | Tipo    | Descripción                              |
|-----------------|---------|------------------------------------------|
| id              | INTEGER | Clave primaria, autoincremental          |
| concepto        | TEXT    | Nombre del gasto (Luz, Agua, etc.)       |
| monto_total     | REAL    | Monto total del gasto                    |
| frecuencia      | TEXT    | Mensual, Semanal, Quincenal              |
| activo          | INTEGER | 1 = activo, 0 = inactivo                 |
| fecha_creacion  | TEXT    | Fecha de creación                        |

### Tabla: pagos

| Campo         | Tipo    | Descripción                          |
|---------------|---------|--------------------------------------|
| id            | INTEGER | Clave primaria, autoincremental      |
| gasto_id      | INTEGER | Referencia al gasto mensual          |
| mes           | INTEGER | Mes del pago (1-12)                  |
| anio          | INTEGER | Año del pago                         |
| quien_pago    | TEXT    | 'Ricardo' o 'Wendy'                  |
| monto_pagado  | REAL    | Monto pagado                         |
| fecha_pago    | TEXT    | Fecha del registro del pago          |

## 💡 Lógica del Sistema

### División de Gastos (50/50)

1. **Total Mensual**: Suma de todos los gastos activos
2. **Debe pagar cada uno**: Total ÷ 2
3. **Monto por gasto**: Cada gasto se divide en 2 automáticamente
4. **Pagos independientes**: Cada persona paga su parte cuando puede
5. **Saldo**: Diferencia entre lo que debe y lo que ha pagado

**Ejemplo práctico**:
- Gastos mensuales: Luz $120 + Agua $60 + Casa $600 = $780
- Debe pagar cada uno: $780 ÷ 2 = $390
- Ricardo paga luz ($60) y agua ($30) = $90 pagados, $300 pendientes
- Wendy paga casa ($300) y luz ($60) = $360 pagados, $30 pendientes

## 🛠️ Stack Tecnológico

- **Backend/Lógica**: Python 3.x
- **Base de Datos**: SQLite3
- **Frontend**: Streamlit
- **Gráficos**: Plotly
- **Automatización**: pywhatkit

## 📱 Ejemplo de Reporte por WhatsApp

```
🏠 REPORTE DE CONTABILIDAD DOMÉSTICA
📅 Fecha: 25/10/2025 10:30
📆 Mes: Octubre 2025

━━━━━━━━━━━━━━━━━━━━
💰 RESUMEN FINANCIERO
━━━━━━━━━━━━━━━━━━━━

📊 Total de Gastos Mensuales: $780.00
📌 Debe pagar cada uno (50/50): $390.00

👨 Ha pagado Ricardo: $90.00
👩 Ha pagado Wendy: $360.00

━━━━━━━━━━━━━━━━━━━━
💳 SALDO PENDIENTE
━━━━━━━━━━━━━━━━━━━━

Ricardo debe pagar $300.00

━━━━━━━━━━━━━━━━━━━━
Generado automáticamente
```

## ⚠️ Notas Importantes

- La base de datos `contabilidad.db` se crea automáticamente en la primera ejecución
- Los gastos se gestionan de forma mensual
- Cada persona registra sus pagos independientemente
- Los números de teléfono deben incluir el código de país
- Para usar el envío por WhatsApp, debes tener WhatsApp Web activo

## 🐛 Solución de Problemas

### Error al enviar WhatsApp:
- Verifica que tienes sesión activa en WhatsApp Web
- Asegúrate de que el navegador predeterminado esté configurado
- Verifica que los números tengan el formato correcto (+código_país + número)

### No aparecen los gastos:
- Verifica que hayas agregado gastos en la pestaña "Gestionar Gastos"
- Asegúrate de que los gastos estén marcados como activos

### Los pagos no se registran:
- Verifica que no hayas pagado ya ese gasto en el mes actual
- Cada persona solo puede pagar una vez su parte por mes

## 📝 Licencia

Este proyecto es de uso libre para fines personales.

---

Creado con ❤️ para Ricardo y Wendy
