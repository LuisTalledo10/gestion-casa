# 🎯 GUÍA RÁPIDA: Migrar a Google Sheets

## ¿Por qué migrar?

Tu app en Streamlit Cloud pierde los datos porque usa SQLite (archivo local) y los contenedores se reinician. Con Google Sheets, **tus datos estarán siempre en la nube** y nunca se perderán. ✅

---

## 📋 PASOS PARA MIGRAR (Resumen)

### 1️⃣ Configurar Google Cloud (10 minutos)

1. Ve a https://console.cloud.google.com/
2. Crea un proyecto nuevo
3. Habilita: **Google Sheets API** y **Google Drive API**
4. Crea una **Cuenta de Servicio**
5. Descarga las credenciales en formato **JSON**

**📖 Guía detallada:** `GOOGLE_SHEETS_SETUP.md`

---

### 2️⃣ Crear el Google Sheet (2 minutos)

1. Ve a https://sheets.google.com
2. Crea un nuevo spreadsheet
3. Nómbralo: **"Gestión Casa - Base de Datos"**
4. **Compártelo** con el email de la cuenta de servicio (está en el JSON)
5. Dale permisos de **Editor**
6. Copia la URL del spreadsheet

---

### 3️⃣ Configurar Secrets localmente (5 minutos)

1. Crea la carpeta `.streamlit` en tu proyecto:
```powershell
New-Item -Path ".streamlit" -ItemType Directory -Force
```

2. Crea el archivo `secrets.toml`:
```powershell
New-Item -Path ".streamlit\secrets.toml" -ItemType File
```

3. Copia el contenido de `secrets.toml.example`
4. Reemplaza con tus valores reales del JSON de Google Cloud
5. Pega la URL de tu spreadsheet

---

### 4️⃣ Instalar dependencias (1 minuto)

```powershell
pip install gspread oauth2client
```

O usa el `requirements.txt` actualizado:
```powershell
pip install -r requirements.txt
```

---

### 5️⃣ Probar la conexión (2 minutos)

Ejecuta este comando para verificar que todo funciona:

```powershell
streamlit run migrate_to_sheets.py
```

Si ves "✅ Conectado a Google Sheets", ¡todo está bien!

---

### 6️⃣ Migrar tus datos (5 minutos)

Si ya tienes datos en `contabilidad.db`:

1. Haz un backup:
```powershell
Copy-Item contabilidad.db contabilidad.db.backup
```

2. Ejecuta el script de migración:
```powershell
streamlit run migrate_to_sheets.py
```

3. Haz clic en "🚀 Iniciar Migración"
4. Espera a que termine
5. Verifica los datos en tu Google Sheet

---

### 7️⃣ Actualizar app.py (PENDIENTE)

Necesitarás modificar `app.py` para que use Google Sheets en lugar de SQLite.

**Cambios principales:**
- Importar `GoogleSheetsDB` en lugar de `sqlite3`
- Reemplazar todas las queries SQL con métodos de la clase
- Probar localmente

**¿Quieres que te ayude con esto?** Es el paso más importante.

---

### 8️⃣ Configurar Streamlit Cloud (3 minutos)

1. Ve a tu app en https://share.streamlit.io/
2. Haz clic en **⚙️ Settings > Secrets**
3. Copia TODO el contenido de `.streamlit/secrets.toml`
4. Pégalo en el editor de Streamlit Cloud
5. Haz clic en **Save**
6. La app se reiniciará automáticamente

---

### 9️⃣ Desplegar cambios (2 minutos)

1. Haz commit de los cambios:
```powershell
git add .
git commit -m "Migración a Google Sheets para persistencia de datos"
git push origin main
```

2. Streamlit Cloud detectará los cambios y redesplegará automáticamente

---

### 🔟 Verificar que funciona

1. Abre tu app desplegada
2. Crea un gasto de prueba
3. Cierra la pestaña
4. Espera unos minutos
5. Vuelve a abrir la app
6. **¡Los datos deberían seguir ahí!** 🎉

---

## 🆘 ¿Problemas?

### "Could not find credentials"
- Verifica que `.streamlit/secrets.toml` existe
- Verifica que el formato es correcto (copia de `secrets.toml.example`)

### "Permission denied"
- Comparte el spreadsheet con el `client_email` del JSON
- Dale permisos de **Editor**

### "API not enabled"
- Ve a Google Cloud Console
- Habilita Google Sheets API y Google Drive API

### La app funciona local pero no en Streamlit Cloud
- Verifica que copiaste los secrets correctamente en Streamlit Cloud
- No debe haber espacios extras ni saltos de línea

---

## 📊 Ventajas de Google Sheets

✅ **Nunca pierdes datos** (incluso si la app duerme por días)
✅ **Puedes ver los datos** directamente en Google Sheets
✅ **Editar manualmente** si necesitas corregir algo
✅ **Gratis** para uso personal
✅ **Backups automáticos** por Google
✅ **Acceso desde cualquier lugar**

---

## 📁 Archivos del proyecto

```
gestion_casa/
├── app.py                      # App principal (pendiente actualizar)
├── google_sheets_db.py         # ✅ Clase para manejar Google Sheets
├── migrate_to_sheets.py        # ✅ Script de migración
├── GOOGLE_SHEETS_SETUP.md      # ✅ Guía detallada
├── secrets.toml.example        # ✅ Plantilla de secrets
├── requirements.txt            # ✅ Actualizado con gspread
├── .streamlit/
│   └── secrets.toml           # ⚠️ TUS CREDENCIALES (no subir a GitHub)
└── contabilidad.db            # SQLite antiguo (hacer backup)
```

---

## 🚀 Siguiente paso

**¿Quieres que actualice `app.py` para usar Google Sheets?**

Esto implica:
1. Reemplazar todas las conexiones SQLite
2. Adaptar las queries a los métodos de la clase
3. Probar que todo funciona
4. Mantener la misma funcionalidad

Es un cambio grande pero necesario. ¿Procedemos? 🤔
