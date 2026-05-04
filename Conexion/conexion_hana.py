import pyodbc
from Config.conexion_config import CONFIG_HANA
import logging

logger = logging.getLogger("migrador")

class ConexionHANA:
    def __init__(self, query=None):
        self.conexion = None
        self.cursor = None
        self.db_estado = False
        self.query = query

    def __enter__(self):
        self.conectar()
        if self.query:
            self.ejecutar(self.query)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cerrar_conexion()

    def conectar(self):
        try:
            conn_str = (
                f"DSN={CONFIG_HANA['dsn']};"
                f"UID={CONFIG_HANA['user']};"
                f"PWD={CONFIG_HANA['password']};"
            )
            self.conexion = pyodbc.connect(conn_str)
            self.cursor = self.conexion.cursor()
            self.db_estado = True
            logger.info("Conexión SAP HANA establecida")
        except Exception as e:
            logger.error(f"❌ Error al conectar a SAP HANA: {e}")
            self.db_estado = False

    def ejecutar(self, query: str):
        if not self.db_estado or not self.cursor:
            logger.warning("Intento de ejecutar query sin conexión activa")
            return None
        try:
            self.cursor.execute(query)
            logger.info(f"Query ejecutada en HANA: {query[:50]}...")  # Solo primeros 50 caracteres
            return self.cursor
        except Exception as e:
            logger.error(f"❌ Error al ejecutar query HANA: {e}")
            return None

    def obtener_registro(self):
        if self.db_estado and self.cursor:
            return self.cursor.fetchone()
        return None

    def obtener_tabla(self):
        if self.db_estado and self.cursor:
            return self.cursor.fetchall()
        return []

    def cerrar_conexion(self):
        try:
            if self.cursor:
                self.cursor.close()
            if self.conexion:
                self.conexion.close()
            logger.info("Conexión SAP HANA cerrada")
        except Exception as e:
            logger.warning(f"Error al cerrar conexión SAP HANA: {e}")
