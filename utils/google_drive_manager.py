"""
Módulo para interactuar con Google Drive.
Permite listar carpetas, leer documentos y moverlos entre carpetas.
"""

import os
import json
from typing import List, Dict, Optional
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


class GoogleDriveManager:
    """Gestor de operaciones con Google Drive."""

    SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/documents.readonly"]

    def __init__(self, credentials_json: Optional[str] = None):
        """
        Inicializa el manager de Google Drive.

        Args:
            credentials_json: JSON string de las credenciales de cuenta de servicio
        """
        if credentials_json:
            creds_info = json.loads(credentials_json)
        else:
            creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
            if not creds_json:
                raise ValueError("No se encontraron credenciales de Google")
            creds_info = json.loads(creds_json)

        self.credentials = Credentials.from_service_account_info(creds_info, scopes=self.SCOPES)
        self.drive_service = build("drive", "v3", credentials=self.credentials)
        self.docs_service = build("docs", "v1", credentials=self.credentials)

    def list_folders(self, parent_folder_id: str) -> List[Dict]:
        """
        Lista las subcarpetas dentro de una carpeta padre.

        Args:
            parent_folder_id: ID de la carpeta padre

        Returns:
            Lista de diccionarios con info de carpetas
        """
        query = (
            f"'{parent_folder_id}' in parents "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )

        results = (
            self.drive_service.files()
            .list(q=query, fields="files(id, name, createdTime, modifiedTime)", orderBy="createdTime desc")
            .execute()
        )

        folders = results.get("files", [])
        print(f"Encontradas {len(folders)} carpetas en {parent_folder_id}")
        return folders

    def find_document_by_name(self, folder_id: str, name_pattern: str) -> Optional[Dict]:
        """
        Busca un documento que contenga cierto patrón en el nombre.

        Args:
            folder_id: ID de la carpeta donde buscar
            name_pattern: Patrón a buscar en el nombre (ej: "Notas")

        Returns:
            Diccionario con info del documento o None
        """
        query = (
            f"'{folder_id}' in parents "
            f"and name contains '{name_pattern}' "
            f"and mimeType='application/vnd.google-apps.document' "
            f"and trashed=false"
        )

        results = self.drive_service.files().list(q=query, fields="files(id, name, createdTime)", pageSize=1).execute()

        files = results.get("files", [])
        if files:
            print(f"Documento encontrado: {files[0]['name']}")
            return files[0]

        print(f"No se encontró documento con patrón '{name_pattern}' en carpeta {folder_id}")
        return None

    def read_document_content(self, document_id: str) -> str:
        """
        Lee el contenido completo de un Google Doc.

        Args:
            document_id: ID del documento

        Returns:
            Texto completo del documento
        """
        try:
            document = self.docs_service.documents().get(documentId=document_id).execute()

            content_parts = []
            for element in document.get("body", {}).get("content", []):
                if "paragraph" in element:
                    para = element["paragraph"]
                    for text_run in para.get("elements", []):
                        if "textRun" in text_run:
                            content_parts.append(text_run["textRun"]["content"])

            full_text = "".join(content_parts)
            print(f"Documento leído: {len(full_text)} caracteres")
            return full_text

        except Exception as e:
            print(f"Error leyendo documento {document_id}: {e}")
            raise

    def read_document_tab(self, document_id: str, tab_name: str) -> Optional[str]:
        """
        Lee el contenido de una pestaña específica del documento.

        Args:
            document_id: ID del documento
            tab_name: Nombre de la pestaña (ej: "Transcripción")

        Returns:
            Contenido de la pestaña o None si no existe
        """
        # Google Docs API no soporta pestañas directamente
        # Asumimos que el contenido está en el documento principal
        return self.read_document_content(document_id)

    def create_document_tab(self, document_id: str, tab_name: str, content: str):
        """
        Crea una nueva pestaña/sección en el documento con el análisis.

        Args:
            document_id: ID del documento
            tab_name: Nombre de la pestaña/sección
            content: Contenido a agregar
        """
        try:
            # Agregamos el contenido al final del documento
            requests = [{"insertText": {"location": {"index": 1}, "text": f"\n\n--- {tab_name} ---\n\n{content}\n"}}]

            self.docs_service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()

            print(f"Sección '{tab_name}' agregada al documento")

        except Exception as e:
            print(f"Error creando sección: {e}")
            raise

    def move_file(self, file_id: str, current_parent_id: str, new_parent_id: str):
        """
        Mueve un archivo de una carpeta a otra.

        Args:
            file_id: ID del archivo a mover
            current_parent_id: ID de la carpeta actual
            new_parent_id: ID de la carpeta destino
        """
        try:
            self.drive_service.files().update(
                fileId=file_id, addParents=new_parent_id, removeParents=current_parent_id, fields="id, parents"
            ).execute()

            print(f"Archivo movido de {current_parent_id} a {new_parent_id}")

        except Exception as e:
            print(f"Error moviendo archivo: {e}")
            raise

    def extract_folder_id(self, drive_url: str) -> Optional[str]:
        """
        Extrae el ID de carpeta de una URL de Google Drive.

        Args:
            drive_url: URL completa de Google Drive

        Returns:
            ID de la carpeta
        """
        import re

        match = re.search(r"/folders/([a-zA-Z0-9_-]+)", drive_url)
        if match:
            return match.group(1)
        return None
