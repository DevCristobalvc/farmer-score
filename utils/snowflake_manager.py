"""
Módulo para interactuar con Snowflake.
Permite escribir resultados de análisis de reuniones.
"""

import os
import json
from datetime import datetime
from typing import Dict, Optional
import snowflake.connector


class SnowflakeManager:
    """Gestor de operaciones con Snowflake."""

    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
    ):
        """
        Inicializa la conexión a Snowflake.

        Args:
            account: Cuenta de Snowflake
            user: Usuario
            password: Contraseña
            warehouse: Warehouse a usar
            database: Base de datos
            schema: Schema
        """
        self.account = account or os.getenv("SNOWFLAKE_ACCOUNT", "hg51401")
        self.user = user or os.getenv("SNOWFLAKE_USER")
        self.password = password or os.getenv("SNOWFLAKE_PASSWORD")
        self.warehouse = warehouse or os.getenv("SNOWFLAKE_WAREHOUSE", "CPGS")
        self.database = database or os.getenv("SNOWFLAKE_DATABASE", "FIVETRAN")
        self.schema = schema or os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")

        self.conn = None

    def connect(self):
        """Establece conexión con Snowflake."""
        try:
            self.conn = snowflake.connector.connect(
                user=self.user,
                password=self.password,
                account=self.account,
                warehouse=self.warehouse,
                database=self.database,
                schema=self.schema,
            )
            print(f"Conectado a Snowflake: {self.database}.{self.schema}")
        except Exception as e:
            print(f"Error conectando a Snowflake: {e}")
            raise

    def close(self):
        """Cierra la conexión."""
        if self.conn:
            self.conn.close()
            print("Conexión a Snowflake cerrada")

    def create_table_if_not_exists(self):
        """Crea la tabla de análisis de reuniones si no existe."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS FARMER_MASS_MEETING_ANALYSIS (
            ID VARCHAR(100) PRIMARY KEY,
            ALIADO_NAME VARCHAR(500),
            FARMER_NAME VARCHAR(500),
            HUNTER_NAME VARCHAR(500),
            FECHA_REUNION VARCHAR(100),
            DURACION_MINUTOS NUMBER,
            TIPO_REUNION VARCHAR(100),
            
            -- Habilidades
            CLARIDAD_PITCH NUMBER,
            NEGOCIACION_HABILIDADES NUMBER,
            RESOLUCION_OBJECCIONES NUMBER,
            FOLLOWUP_COMPROMISOS VARIANT,
            
            -- Evaluación del cliente
            NIVEL_INTERES_CLIENTE VARCHAR(100),
            OBJECIONES_PRINCIPALES VARIANT,
            NECESIDADES_DETECTADAS VARIANT,
            DECISION_MAKER_IDENTIFICADO VARCHAR(50),
            NOMBRE_DECISION_MAKER VARCHAR(500),
            
            -- Scoring y próximos pasos
            PROBABILIDAD_CIERRE NUMBER,
            NEXT_STEPS VARIANT,
            RIESGOS VARIANT,
            
            -- Metadata
            RESUMEN_BREVE VARCHAR(5000),
            TEMAS_NO_MENCIONADOS VARIANT,
            LINK_DOCUMENTO VARCHAR(1000),
            FOLDER_ID VARCHAR(200),
            DOCUMENT_ID VARCHAR(200),
            FECHA_PROCESAMIENTO TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            
            -- Análisis completo
            ANALISIS_COMPLETO_JSON VARIANT
        )
        """

        try:
            cursor = self.conn.cursor()
            cursor.execute(create_table_sql)
            print("Tabla FARMER_MASS_MEETING_ANALYSIS verificada/creada")
            cursor.close()
        except Exception as e:
            print(f"Error creando tabla: {e}")
            raise

    def insert_analysis(self, analysis_data: Dict, document_id: str, folder_id: str, link_documento: str) -> bool:
        """
        Inserta un análisis de reunión en Snowflake.

        Args:
            analysis_data: Diccionario con el análisis completo
            document_id: ID del documento de Google Drive
            folder_id: ID de la carpeta padre
            link_documento: URL del documento original

        Returns:
            True si fue exitoso
        """
        try:
            # Generar ID único
            analysis_id = f"{folder_id}_{document_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            insert_sql = """
            INSERT INTO FARMER_MASS_MEETING_ANALYSIS (
                ID,
                ALIADO_NAME,
                FARMER_NAME,
                HUNTER_NAME,
                FECHA_REUNION,
                DURACION_MINUTOS,
                TIPO_REUNION,
                CLARIDAD_PITCH,
                NEGOCIACION_HABILIDADES,
                RESOLUCION_OBJECCIONES,
                FOLLOWUP_COMPROMISOS,
                NIVEL_INTERES_CLIENTE,
                OBJECIONES_PRINCIPALES,
                NECESIDADES_DETECTADAS,
                DECISION_MAKER_IDENTIFICADO,
                NOMBRE_DECISION_MAKER,
                PROBABILIDAD_CIERRE,
                NEXT_STEPS,
                RIESGOS,
                RESUMEN_BREVE,
                TEMAS_NO_MENCIONADOS,
                LINK_DOCUMENTO,
                FOLDER_ID,
                DOCUMENT_ID,
                ANALISIS_COMPLETO_JSON
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                PARSE_JSON(%s), %s, PARSE_JSON(%s), PARSE_JSON(%s), %s, %s,
                %s, PARSE_JSON(%s), PARSE_JSON(%s), %s, PARSE_JSON(%s),
                %s, %s, %s, PARSE_JSON(%s)
            )
            """

            # Preparar valores
            values = (
                analysis_id,
                analysis_data.get("cliente_nombre", "No mencionado"),
                analysis_data.get("farmer_nombre", "No mencionado"),
                analysis_data.get("hunter_nombre", "No mencionado"),
                analysis_data.get("fecha_reunion", "No mencionado"),
                analysis_data.get("duracion_minutos", 0),
                analysis_data.get("tipo_reunion", "No mencionado"),
                analysis_data.get("claridad_pitch", 0),
                analysis_data.get("negociacion_habilidades", 0),
                analysis_data.get("resolucion_objecciones", 0),
                json.dumps(analysis_data.get("followup_compromisos", [])),
                analysis_data.get("nivel_interes_cliente", "No mencionado"),
                json.dumps(analysis_data.get("objeciones_principales", [])),
                json.dumps(analysis_data.get("necesidades_detectadas", [])),
                analysis_data.get("decision_maker_identificado", "No mencionado"),
                analysis_data.get("nombre_decision_maker", "No mencionado"),
                analysis_data.get("probabilidad_cierre", 0),
                json.dumps(analysis_data.get("next_steps", [])),
                json.dumps(analysis_data.get("riesgos", [])),
                analysis_data.get("resumen_breve", "No mencionado"),
                json.dumps(analysis_data.get("temas_no_mencionados", [])),
                link_documento,
                folder_id,
                document_id,
                json.dumps(analysis_data),
            )

            cursor = self.conn.cursor()
            cursor.execute(insert_sql, values)
            self.conn.commit()
            cursor.close()

            print(f"Análisis insertado en Snowflake: {analysis_id}")
            return True

        except Exception as e:
            print(f"Error insertando en Snowflake: {e}")
            if self.conn:
                self.conn.rollback()
            raise

    def check_already_processed(self, document_id: str) -> bool:
        """
        Verifica si un documento ya fue procesado.

        Args:
            document_id: ID del documento

        Returns:
            True si ya existe en la base de datos
        """
        try:
            cursor = self.conn.cursor()
            query = "SELECT COUNT(*) FROM FARMER_MASS_MEETING_ANALYSIS WHERE DOCUMENT_ID = %s"
            cursor.execute(query, (document_id,))
            count = cursor.fetchone()[0]
            cursor.close()

            return count > 0

        except Exception as e:
            print(f"Error verificando documento: {e}")
            return False
