# 📊 Configuración de Google Sheets como Base de Datos

## Paso 1: Crear un Proyecto en Google Cloud

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Dale un nombre como "Gestion Casa DB"

## Paso 2: Habilitar las APIs necesarias

1. En el menú lateral, ve a **"APIs y servicios" > "Biblioteca"**
2. Busca y habilita estas APIs:
   - ✅ **Google Sheets API**
   - ✅ **Google Drive API**

## Paso 3: Crear una Cuenta de Servicio

1. Ve a **"APIs y servicios" > "Credenciales"**
2. Haz clic en **"Crear credenciales" > "Cuenta de servicio"**
3. Dale un nombre (ejemplo: "gestion-casa-service")
4. Haz clic en **"Crear y continuar"**
5. En "Rol", selecciona **"Editor"** (o "Propietario" para más permisos)
6. Haz clic en **"Continuar"** y luego **"Listo"**

## Paso 4: Generar la Clave JSON

1. En la lista de cuentas de servicio, encuentra la que acabas de crear
2. Haz clic en ella para ver los detalles
3. Ve a la pestaña **"Claves"**
4. Haz clic en **"Agregar clave" > "Crear nueva clave"**
5. Selecciona formato **JSON**
6. Se descargará un archivo JSON con las credenciales

**⚠️ IMPORTANTE:** Guarda este archivo de forma segura. Contiene las credenciales privadas.

El archivo JSON se verá así:
```json
{
  "type": "service_account",
  "project_id": "tu-proyecto-12345",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "gestion-casa-service@tu-proyecto.iam.gserviceaccount.com",
  "client_id": "123456789...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

## Paso 5: Crear el Google Sheet

1. Ve a [Google Sheets](https://sheets.google.com)
2. Crea un nuevo spreadsheet
3. Dale un nombre como **"Gestión Casa - Base de Datos"**
4. Copia la URL del spreadsheet (algo como: `https://docs.google.com/spreadsheets/d/1ABC...XYZ/edit`)
5. Haz clic en **"Compartir"** (botón verde arriba a la derecha)
6. Pega el email de la cuenta de servicio (lo encuentras en el JSON como `client_email`)
7. Dale permisos de **Editor**
8. Desmarca "Notificar a las personas" si aparece
9. Haz clic en **"Compartir"** o **"Enviar"**

## Paso 6: Configurar Secrets en Streamlit Cloud

### Para desarrollo local (.streamlit/secrets.toml):

1. Crea una carpeta `.streamlit` en tu proyecto:
```bash
mkdir .streamlit
```

2. Crea el archivo `secrets.toml` dentro:
```bash
New-Item -Path ".streamlit\secrets.toml" -ItemType File
```

3. Pega este contenido (reemplaza con tus valores):

```toml
# URL de tu Google Sheet
spreadsheet_url = "https://docs.google.com/spreadsheets/d/TU_SPREADSHEET_ID_AQUI/edit"

# Credenciales de Google Cloud (del archivo JSON que descargaste)
[gcp_service_account]
type = "service_account"
project_id = "tu-proyecto-12345"
private_key_id = "abc123..."
private_key = "-----BEGIN PRIVATE KEY-----\nTU_PRIVATE_KEY_AQUI\n-----END PRIVATE KEY-----\n"
client_email = "gestion-casa-service@tu-proyecto.iam.gserviceaccount.com"
client_id = "123456789..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
```

**⚠️ IMPORTANTE:** Asegúrate de que `.streamlit/` esté en tu `.gitignore` para no subir las credenciales a GitHub.

### Para Streamlit Cloud (deployment):

1. Ve a tu app en [Streamlit Cloud](https://share.streamlit.io/)
2. Haz clic en **"Settings"** (⚙️) > **"Secrets"**
3. Pega el mismo contenido del archivo `secrets.toml`
4. Haz clic en **"Save"**

## Paso 7: Actualizar el .gitignore

Asegúrate de que estos archivos NO se suban a GitHub:

```gitignore
# Secrets de Streamlit
.streamlit/secrets.toml
.streamlit/config.toml

# Credenciales de Google
*.json
!requirements.txt
```

## Paso 8: Probar la conexión

Ejecuta la app localmente:
```bash
streamlit run app.py
```

Si todo está configurado correctamente:
- ✅ Verás "✅ Conectado a Google Sheets"
- ✅ Se crearán automáticamente las hojas necesarias en tu spreadsheet
- ✅ Los datos se guardarán en la nube y nunca se perderán

## Estructura del Spreadsheet

Después de la primera ejecución, tu Google Sheet tendrá estas pestañas:

1. **gastos_mensuales** - Gastos configurados
2. **montos_mensuales** - Montos específicos por mes
3. **pagos** - Registro de pagos realizados
4. **grupos_distribucion** - Grupos de gastos
5. **gastos_en_grupo** - Relación gastos-grupos

## Solución de Problemas

### Error: "Could not find credentials"
- Verifica que el archivo `secrets.toml` existe en `.streamlit/`
- Verifica que el formato del TOML es correcto

### Error: "Permission denied"
- Verifica que compartiste el spreadsheet con el `client_email`
- Dale permisos de **Editor**

### Error: "API not enabled"
- Ve a Google Cloud Console
- Habilita Google Sheets API y Google Drive API

### Error en Streamlit Cloud
- Verifica que pegaste los secrets correctamente
- Asegúrate de que no hay espacios extras o saltos de línea incorrectos

## Migración desde SQLite

Si ya tienes datos en `contabilidad.db`, puedes exportarlos:

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('contabilidad.db')

# Exportar cada tabla
gastos = pd.read_sql_query("SELECT * FROM gastos_mensuales", conn)
gastos.to_csv('gastos_mensuales.csv', index=False)

# Repetir para cada tabla...
```

Luego importarlos en Google Sheets manualmente o con un script.

## Ventajas de usar Google Sheets

✅ **Persistencia**: Los datos nunca se pierden
✅ **Accesibilidad**: Puedes ver/editar datos directamente en Sheets
✅ **Gratis**: Sin límites para uso personal
✅ **Backup**: Google hace backups automáticos
✅ **Colaboración**: Múltiples personas pueden acceder
✅ **Sin servidor**: No necesitas mantener una base de datos

## Desventajas

❌ **Límites**: 10 millones de celdas por spreadsheet
❌ **Velocidad**: Más lento que una base de datos real
❌ **Concurrencia**: No ideal para muchos usuarios simultáneos

Para tu caso de uso (gestión personal de gastos), Google Sheets es perfecto. 🎉
