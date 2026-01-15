"""
DAG de Airflow para analizar reuniones de Farmer Mass.
Procesa documentos de Google Drive, analiza con LLM y guarda en Snowflake.
"""

from __future__ import annotations
from datetime import datetime, timedelta
import os
import sys
import json

from airflow.decorators import dag, task
from airflow.models.variable import Variable

# from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook  # Temporalmente deshabilitado

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.google_drive_manager import GoogleDriveManager  # noqa: E402

# from utils.snowflake_manager import SnowflakeManager  # Temporalmente deshabilitado
import analyzer  # noqa: E402


# --- CONFIGURACIÓN ---
# SNOWFLAKE_CONN_ID = "CONN_SNOWFLAKE"  # Temporalmente deshabilitado
GOOGLE_CREDS_VAR_KEY = "google_sheet_creds_upload_v2"
DRIVE_FOLDER_URL_VAR_KEY = "farmer_mass_drive_folder_url"


@dag(
    dag_id="farmer_mass_meeting_analysis",
    start_date=datetime(2025, 1, 15),
    schedule="0 */4 * * *",  # Cada 4 horas
    catchup=False,
    tags=["farmer-mass", "llm", "analysis", "snowflake", "google-drive"],
    default_args={"owner": "rappi-ai", "retries": 2, "retry_delay": timedelta(minutes=5)},
    description="Analiza reuniones de Farmer Mass desde Google Drive",
)
def farmer_mass_analysis_pipeline():

    @task
    def setup_environment():
        """Configura variables de entorno desde Airflow Variables."""
        print("Configurando entorno...")

        # TODO: Snowflake config temporalmente deshabilitado
        # sf_hook = SnowflakeHook(snowflake_conn_id=SNOWFLAKE_CONN_ID)
        # sf_conn = sf_hook.get_connection(SNOWFLAKE_CONN_ID)
        #
        # os.environ['SNOWFLAKE_USER'] = sf_conn.login
        # os.environ['SNOWFLAKE_PASSWORD'] = sf_conn.password
        # os.environ['SNOWFLAKE_ACCOUNT'] = sf_hook.account or "hg51401"
        # os.environ['SNOWFLAKE_WAREHOUSE'] = 'CPGS'
        # os.environ['SNOWFLAKE_DATABASE'] = 'FIVETRAN'
        # os.environ['SNOWFLAKE_SCHEMA'] = sf_conn.schema or 'PUBLIC'

        # Google credentials
        creds_json = Variable.get(GOOGLE_CREDS_VAR_KEY, default_var=None)
        if not creds_json:
            raise ValueError(f"Variable '{GOOGLE_CREDS_VAR_KEY}' no encontrada")

        # Validar JSON
        try:
            json.loads(creds_json)
        except ValueError as e:
            raise ValueError(f"JSON inválido en '{GOOGLE_CREDS_VAR_KEY}': {e}")

        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = creds_json

        # API LLM configuration - Core LLM Proxy de Rappi
        # El proxy inyecta automáticamente las credenciales de OpenAI
        os.environ["API_KEY"] = Variable.get("llm_api_key", default_var="dummykey")
        os.environ["BASE_URL"] = Variable.get(
            "llm_base_url",
            default_var="https://core-llm-proxy-external.security.rappi.com/api/core-llm-proxy/openai/v1"
        )
        os.environ["MODEL"] = Variable.get("llm_model", default_var="gpt-4o-mini")

        print("Entorno configurado correctamente")
        return {"status": "success"}

    @task
    def scan_drive_folders(setup_result: dict):
        """Escanea carpetas de Google Drive buscando documentos pendientes."""
        print("Escaneando carpetas de Drive...")

        # Obtener URL de carpeta desde Airflow Variables
        drive_folder_url = Variable.get(
            DRIVE_FOLDER_URL_VAR_KEY,
            default_var="https://drive.google.com/drive/u/0/folders/1iLJ8xFfYlRSbwaAtmthFQD8PT7AQsJzC",
        )

        drive_manager = GoogleDriveManager()
        folder_id = drive_manager.extract_folder_id(drive_folder_url)

        if not folder_id:
            raise ValueError(f"No se pudo extraer folder_id de: {drive_folder_url}")

        # Listar subcarpetas (cada reunión)
        meeting_folders = drive_manager.list_folders(folder_id)

        documents_to_process = []

        for meeting_folder in meeting_folders:
            meeting_id = meeting_folder["id"]
            meeting_name = meeting_folder["name"]

            print(f"Procesando carpeta: {meeting_name}")

            # Buscar documento "Notas - ..."
            doc = drive_manager.find_document_by_name(meeting_id, "Notas")

            if doc:
                documents_to_process.append(
                    {
                        "folder_id": meeting_id,
                        "folder_name": meeting_name,
                        "document_id": doc["id"],
                        "document_name": doc["name"],
                        "document_url": f"https://docs.google.com/document/d/{doc['id']}",
                    }
                )

        print(f"Encontrados {len(documents_to_process)} documentos para procesar")
        return documents_to_process

    @task
    def process_documents(documents: list):
        """Procesa cada documento: lee, analiza y guarda resultados."""
        print(f"Procesando {len(documents)} documentos...")

        drive_manager = GoogleDriveManager()

        # TODO: Snowflake temporalmente deshabilitado
        # sf_manager = SnowflakeManager()
        # sf_manager.connect()
        # sf_manager.create_table_if_not_exists()

        processed_count = 0
        skipped_count = 0
        error_count = 0

        for doc_info in documents:
            try:
                document_id = doc_info["document_id"]

                # TODO: Verificación de duplicados deshabilitada (Snowflake)
                # if sf_manager.check_already_processed(document_id):
                #     print(f"Documento ya procesado: {doc_info['document_name']}")
                #     skipped_count += 1
                #     continue

                print(f"\nProcesando: {doc_info['document_name']}")

                # Leer contenido
                transcription = drive_manager.read_document_content(document_id)

                if not transcription or len(transcription) < 100:
                    print("Transcripción muy corta o vacía, omitiendo...")
                    skipped_count += 1
                    continue

                # Analizar con LLM
                print("Analizando con LLM...")
                analysis_result = analyzer.analyze_transcription(transcription, verbose=False)

                # TODO: Guardar en Snowflake deshabilitado
                # sf_manager.insert_analysis(
                #     analysis_data=analysis_result,
                #     document_id=document_id,
                #     folder_id=doc_info['folder_id'],
                #     link_documento=doc_info['document_url']
                # )

                # Agregar sección de análisis al documento
                analysis_text = json.dumps(analysis_result, indent=2, ensure_ascii=False)
                drive_manager.create_document_tab(document_id, "Análisis - Farmer", analysis_text)

                processed_count += 1
                print("Documento procesado exitosamente\n")

            except Exception as e:
                print(f"Error procesando {doc_info.get('document_name', 'unknown')}: {e}")
                error_count += 1
                continue

        # TODO: Cerrar conexión Snowflake deshabilitado
        # sf_manager.close()

        summary = {
            "total": len(documents),
            "processed": processed_count,
            "skipped": skipped_count,
            "errors": error_count,
        }

        print("\n" + "=" * 50)
        print("RESUMEN DE PROCESAMIENTO")
        print("=" * 50)
        print(f"Total documentos: {summary['total']}")
        print(f"Procesados: {summary['processed']}")
        print(f"Omitidos: {summary['skipped']}")
        print(f"Errores: {summary['errors']}")
        print("=" * 50)

        return summary

    # Flujo del DAG
    env_setup = setup_environment()
    documents = scan_drive_folders(env_setup)
    results = process_documents(documents)

    return results


# Instanciar el DAG
farmer_mass_analysis_pipeline()
