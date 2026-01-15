# Meeting Analyzer – Farmer Mass

Sistema automatizado de análisis de reuniones para evaluar calidad de handoffs entre Farmers y restaurantes usando Airflow, Google Drive y LLM.

[![Airflow](https://img.shields.io/badge/orchestration-airflow-orange)](dags/)
[![Google Drive](https://img.shields.io/badge/source-google_drive-green)](utils/)
[![Python](https://img.shields.io/badge/python-3.11-blue)]()

---

## Tabla de Contenidos

- [Descripción](#descripción)
- [Arquitectura](#arquitectura)
- [Instalación y Deploy](#instalación-y-deploy)
  - [1. Preparar Archivos](#1-preparar-archivos)
  - [2. Configurar Google Service Account](#2-configurar-google-service-account)
  - [3. Configurar Airflow Variables](#3-configurar-airflow-variables)
  - [4. Compartir Carpeta de Drive](#4-compartir-carpeta-de-drive)
  - [5. Activar DAG](#5-activar-dag)
- [Configuración](#configuración)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Monitoreo y Logs](#monitoreo-y-logs)
- [Testing Local](#testing-local)
- [Troubleshooting](#troubleshooting)
- [Notas sobre Snowflake](#notas-sobre-snowflake)

---

## Descripción

Sistema para **Farmer Mass** (156 integrantes) que automatiza:

1. Escaneo de documentos en Google Drive
2. Lectura de transcripciones de reuniones (Gemini)
3. Análisis con LLM (evaluación de hitos y habilidades)
4. Escritura de análisis estructurado en Google Drive

**Valor:** Estandariza medición de calidad, identifica hitos críticos, genera scoring de desempeño.

**Estado actual:** Snowflake temporalmente deshabilitado. El análisis se escribe únicamente en Google Drive.

---

## Arquitectura

```
┌─────────────────┐
│  Google Drive   │  Carpeta con subcarpetas de reuniones
│  (Documentos)   │  Cada carpeta tiene "Notas - ..."
└────────┬────────┘
         │
         │ Cada 4 horas
         ↓
┌─────────────────┐
│  Airflow DAG    │  3 tasks:
│                 │  1. Setup environment
│                 │  2. Scan Drive folders
│                 │  3. Process documents
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   LLM API       │  gpt-4o-mini (default)
│  (Rappi LiteLLM)│  Análisis estructurado
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Google Drive   │  Escribe análisis en documento
│   (Output)      │  Sección "Análisis - Farmer"
└─────────────────┘
```

**Flujo:**
- **Trigger:** Cada 4 horas (configurable)
- **Input:** Documentos "Notas - ..." en subcarpetas de Drive
- **Procesamiento:** LLM analiza transcripción y genera JSON estructurado
- **Output:** JSON escrito como nueva sección en el mismo documento

---

## Instalación y Deploy

### 1. Preparar Archivos

Copiar el proyecto a la carpeta de DAGs de Airflow:

```bash
cd /path/to/gemini-notes

# Copiar archivos necesarios
cp dags/farmer_mass_meeting_analysis_dag.py $AIRFLOW_HOME/dags/
cp analyzer.py $AIRFLOW_HOME/dags/
cp config.py $AIRFLOW_HOME/dags/
cp -r prompts $AIRFLOW_HOME/dags/
cp -r utils $AIRFLOW_HOME/dags/
```

### 2. Configurar Google Service Account

#### Opción A: Crear nueva cuenta de servicio

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Selecciona tu proyecto
3. **IAM & Admin** → **Service Accounts** → **Create Service Account**
4. Nombre: `farmer-mass-analyzer`
5. Grant roles:
   - **Google Drive API** → Editor
   - **Google Docs API** → Editor
6. **Create Key** → **JSON** → Download
7. Guarda el contenido del JSON

#### Opción B: Usar cuenta existente

Si ya tienes una cuenta de servicio con permisos de Drive/Docs, usa ese JSON.

### 3. Configurar Airflow Variables

#### Variables Obligatorias

**Via UI:**
1. Airflow UI → **Admin** → **Variables**
2. Click en **"+"**
3. Agregar cada variable:

| Key | Value | Descripción |
|-----|-------|-------------|
| `google_sheet_creds_upload_v2` | `{JSON completo}` | Service Account JSON de Google |

**Via CLI:**
```bash
# Google Service Account
airflow variables set google_sheet_creds_upload_v2 '{
  "type": "service_account",
  "project_id": "your-project",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "farmer-mass-analyzer@your-project.iam.gserviceaccount.com",
  ...
}'
```

#### Variables Opcionales (con defaults)

```bash
# URL de carpeta de Drive (opcional)
airflow variables set farmer_mass_drive_folder_url "https://drive.google.com/drive/folders/YOUR_FOLDER_ID"

# Las siguientes variables son opcionales - Core LLM Proxy ya tiene defaults correctos
# Solo configúralas si necesitas cambiar país o modelo

# Base URL de API (default: CO - Colombia)
airflow variables set llm_base_url "https://core-llm-proxy-external.security.rappi.com/api/core-llm-proxy/openai/v1"

# API Key (default: dummykey - el proxy no requiere key real)
airflow variables set llm_api_key "dummykey"

# Modelo LLM (default: gpt-4o-mini)
airflow variables set llm_model "gpt-4o-mini"
```

**Nota:** El Core LLM Proxy de Rappi inyecta automáticamente las credenciales de OpenAI. No necesitas API key real.

### 4. Compartir Carpeta de Drive

La carpeta de Google Drive debe ser compartida con la cuenta de servicio:

1. Abre la carpeta en Drive:
   ```
   https://drive.google.com/drive/folders/1iLJ8xFfYlRSbwaAtmthFQD8PT7AQsJzC
   ```

2. Click derecho → **Share**
3. Agrega el email de la cuenta de servicio:
   ```
   farmer-mass-analyzer@your-project.iam.gserviceaccount.com
   ```
   (Este email está en el JSON del Service Account)

4. Permisos: **Editor** (para poder escribir el análisis de vuelta)

### 5. Activar DAG

1. En Airflow UI → **DAGs**
2. Busca `farmer_mass_meeting_analysis`
3. Toggle el switch a **ON**
4. (Opcional) Click en **"Trigger DAG"** para ejecutar manualmente

**El DAG se ejecutará automáticamente cada 4 horas.**

---

## Configuración

### Variables de Airflow

| Variable | Requerida | Default | Descripción |
|----------|-----------|---------|-------------|
| `google_sheet_creds_upload_v2` | ✅ Sí | - | JSON de Service Account de Google |
| `farmer_mass_drive_folder_url` | ❌ No | URL predefinida | Carpeta raíz de Drive |
| `llm_api_key` | ❌ No | `dummykey` | API Key (el proxy no requiere real) |
| `llm_base_url` | ❌ No | Core LLM Proxy CO | Base URL de API (Core LLM Proxy) |
| `llm_model` | ❌ No | `gpt-4o-mini` | Modelo OpenAI a usar |

**Nota:** El proyecto usa el **Core LLM Proxy de Rappi** que inyecta automáticamente credenciales de OpenAI. Ver [documentación del proxy](https://confluence.rappi.com/display/TECH/Core+LLM+Proxy).

### Estructura de Carpetas en Drive

```
Farmer Mass Reuniones (carpeta principal)
├── Reunión 1 - Aliado X
│   ├── Notas - Reunión Aliado X    ← Este archivo se procesa
│   └── Otros archivos...
├── Reunión 2 - Aliado Y
│   ├── Notas - Reunión Aliado Y    ← Este archivo se procesa
│   └── Otros archivos...
└── ...
```

**Criterio de búsqueda:** Documentos que contienen "Notas" en el nombre.

---

## Estructura del Proyecto

```
gemini-notes/
├── dags/
│   └── farmer_mass_meeting_analysis_dag.py  # DAG principal (225 líneas)
├── utils/
│   ├── __init__.py
│   ├── google_drive_manager.py              # Google Drive API (215 líneas)
│   └── snowflake_manager.py                 # Snowflake (241 líneas, comentado)
├── prompts/
│   └── system_prompt.txt                    # Prompt del LLM
├── analyzer.py                              # Lógica de análisis (121 líneas)
├── config.py                                # Configuración (21 líneas)
├── requirements.txt                         # Dependencias Python
├── verify_setup.py                          # Script de verificación
├── variables.txt                            # Comandos de configuración
├── snowflake_schema.sql                     # Schema DB (futuro)
└── README.md                                # Esta documentación
```

**Total:** 831 líneas de código Python

---

## Monitoreo y Logs

### Ver Logs en Airflow

**Via UI:**
1. DAG → Graph View
2. Click en la task (ej: `process_documents`)
3. **Log** tab

**Via CLI:**
```bash
airflow tasks logs farmer_mass_meeting_analysis process_documents 2026-01-15
```

### Métricas del DAG

El resumen de cada ejecución muestra:
- Total de documentos encontrados
- Documentos procesados exitosamente
- Documentos omitidos (transcripción vacía)
- Errores durante el procesamiento

Ejemplo:
```
==================================================
RESUMEN DE PROCESAMIENTO
==================================================
Total documentos: 12
Procesados: 10
Omitidos: 1
Errores: 1
==================================================
```

---

## Testing Local

Para probar el sistema localmente antes de deployar en Airflow:

```bash
# 1. Clonar repositorio
git clone <repo-url>
cd gemini-notes

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
export GOOGLE_SERVICE_ACCOUNT_JSON='{...}'
export API_KEY="your-api-key"
export SNOWFLAKE_USER="your-user"  # Opcional
export SNOWFLAKE_PASSWORD="your-password"  # Opcional

# 4. Ejecutar verificación
python verify_setup.py
```

**Nota:** `verify_setup.py` valida:
- Estructura de archivos
- Credenciales de Google
- Configuración de Snowflake (opcional)
- Conexión a Google Drive
- Módulo de análisis LLM

---

## Troubleshooting

### Error: "Variable 'google_sheet_creds_upload_v2' no encontrada"
- Verifica que la variable esté creada en **Admin** → **Variables**
- Revisa que el nombre sea exactamente igual (case-sensitive)

### Error: "Permission denied" en Google Drive
- Verifica que la carpeta esté compartida con el email de la cuenta de servicio
- Permisos deben ser **Editor**, no solo **Viewer**
- Revisa que el JSON de Service Account sea válido

### DAG no aparece en la UI
- Verifica errores de sintaxis:
  ```bash
  python dags/farmer_mass_meeting_analysis_dag.py
  ```
- Revisa logs de scheduler:
  ```bash
  tail -f $AIRFLOW_HOME/logs/scheduler/latest/*.log
  ```

### Error: "API Key invalid"
- Verifica que `llm_api_key` esté configurada correctamente
- Prueba la API key con curl:
  ```bash
  curl -H "Authorization: Bearer $API_KEY" https://rappi.litellm-prod.ai/v1/models
  ```

### Documentos no se procesan
- Verifica que los documentos tengan "Notas" en el nombre
- Revisa que la transcripción tenga al menos 100 caracteres
- Chequea logs del task `process_documents`

---

## Notas sobre Snowflake

**Estado actual:** La integración con Snowflake está **comentada en el código** pero lista para usar.

### Para activar Snowflake:

1. **Descomentar código en el DAG:**
   - Línea 9: `from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook`
   - Línea 19: `from utils.snowflake_manager import SnowflakeManager`
   - Línea 23: `SNOWFLAKE_CONN_ID = "CONN_SNOWFLAKE"`
   - Líneas 49-58: Setup de Snowflake
   - Líneas 135-137: Conexión a Snowflake
   - Líneas 148-152: Verificación de duplicados
   - Líneas 171-177: Insert en Snowflake
   - Línea 195: Cerrar conexión

2. **Configurar conexión en Airflow:**
   ```bash
   airflow connections add CONN_SNOWFLAKE \
     --conn-type snowflake \
     --conn-host hg51401.snowflakecomputing.com \
     --conn-schema PUBLIC \
     --conn-login your-user \
     --conn-password your-password \
     --conn-extra '{"account":"hg51401","warehouse":"CPGS","database":"FIVETRAN"}'
   ```

3. **Crear tabla en Snowflake:**
   ```bash
   snowsql -a hg51401 -u your-user -d FIVETRAN < snowflake_schema.sql
   ```

### Tabla y Vistas

Cuando Snowflake esté activo:

```sql
-- Tabla principal
FARMER_MASS_MEETING_ANALYSIS
- Datos de reunión (aliado, farmer, hunter, fecha)
- Evaluación de habilidades (claridad, negociación, resolución)
- Scoring (probabilidad de cierre 0-100)
- Metadata (link a documento, timestamps)

-- Vistas analíticas
VW_FARMER_PERFORMANCE        -- KPIs por Farmer
VW_HITOS_CUMPLIMIENTO        -- Cumplimiento de hitos
```

---

## Datos Capturados

El análisis LLM genera un JSON estructurado con:

```json
{
  "cliente_nombre": "Restaurante La Pasta Feliz",
  "hunter_nombre": "Juan Pérez",
  "fecha_reunion": "2026-01-15",
  "duracion_minutos": 45,
  "tipo_reunion": "presencial",
  "claridad_pitch": 8,
  "negociacion_habilidades": 7,
  "resolucion_objecciones": 9,
  "followup_compromisos": ["Enviar propuesta", "Llamar en 2 días"],
  "nivel_interes_cliente": "alto",
  "objeciones_principales": ["Precio", "Horarios"],
  "necesidades_detectadas": ["Agilidad en entregas"],
  "decision_maker_identificado": "sí",
  "nombre_decision_maker": "María González",
  "probabilidad_cierre": 75,
  "next_steps": ["Propuesta formal", "Demo"],
  "riesgos": ["Competencia local"],
  "resumen_breve": "Reunión positiva...",
  "temas_no_mencionados": ["Integración con POS"]
}
```

**Formato:** JSON escrito en Google Drive como sección "Análisis - Farmer"

---

## Contribuciones

Para contribuir al proyecto:

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
3. Commit cambios: `git commit -m "feat: descripción"`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Abre un Pull Request

---

## Licencia

Propiedad de Rappi - Uso interno

---

**Equipo:** Farmer Mass (156 integrantes)  
**Objetivo:** Mejorar calidad de handoffs 30% (Q1 2026)  
**Mantenedor:** Team AI/Data
