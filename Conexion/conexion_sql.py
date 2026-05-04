import pyodbc
from Config.conexion_config import CONFIG_SQL
import logging

logger = logging.getLogger("migrador")

class ConexionSQL:
    def __init__(self):
        self.conexion = None
        self.cursor = None
        self.db_estado = False

    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cerrar_conexion()

    def conectar(self):
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={CONFIG_SQL['server']};"
                f"DATABASE={CONFIG_SQL['database']};"
                f"UID={CONFIG_SQL['user']};"
                f"PWD={CONFIG_SQL['password']};"
                f"TrustServerCertificate=yes;"
            )
            self.conexion = pyodbc.connect(conn_str, autocommit=False)
            self.cursor = self.conexion.cursor()
            self.db_estado = True
            logger.info("Conexión SQL Server establecida (autocommit=False)")
        except Exception as e:
            logger.error(f"Error al conectar a SQL Server: {e}")
            self.db_estado = False

    def valida_conexion(self):
        return self.db_estado

    def ejecutar(self, query: str):
        if not self.valida_conexion():
            logger.warning("Intento de ejecutar query sin conexion valida")
            return None
        try:
            self.cursor.execute(query)
            self.conexion.commit()
            logger.info(f"Query ejecutada en SQL Server: {query[:50]}...")
            return self.cursor
        except Exception as e:
            logger.error(f"Error ejecutando query SQL: {e}")
            return None

    def obtener_todos(self):
        try:
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"Error al obtener resultados: {e}")
            return []

    def cerrar_conexion(self):
        try:
            # CRITICAL: Commit final antes de cerrar para evitar rollback implícito
            if self.conexion:
                try:
                    self.conexion.commit()
                    logger.info("Commit final ejecutado antes de cerrar conexión")
                except:
                    pass
            if self.cursor:
                self.cursor.close()
            if self.conexion:
                self.conexion.close()
            logger.info("Conexión SQL Server cerrada")
        except Exception as e:
            logger.warning(f"Error al cerrar conexión SQL Server: {e}")
