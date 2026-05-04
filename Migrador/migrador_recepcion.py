import logging
import sys
import os
from datetime import datetime
from pydantic import BaseModel

# Imports de Conexion y Config
from Conexion.conexion_hana import ConexionHANA
from Conexion.conexion_sql import ConexionSQL
from Config.conexion_config import CONFIG_HANA

# Imports de Procesamiento
from Procesamiento.Importador import Importador
from Procesamiento.Importador_recepcion import ImportadorRecepcion

# ==========================================
# CONFIGURACION DE LOGS
# ==========================================
LOG_DIR = "Logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, 'migrador_recepcion.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class MigracionRecepcionRequest(BaseModel):
    fecha: datetime
    almacen_id: str = "*"

class MigradorRecepcion:
    def __init__(self, fecha: datetime, almacen_id: str):
        self.fecha = datetime.strptime(fecha, "%Y-%m-%d") if isinstance(fecha, str) else fecha
        self.almacen_id = almacen_id
        
        self.importador_generico = Importador()
        self.tablas_objetivo = ['RECEPCION', 'OWHS']
        self.queries = self._construir_queries()

    def _esquema(self, tabla):
        return CONFIG_HANA.get("schema", "SBO_SCHEMA")

    def _formato_fecha_hana(self, columna):
        return f"TO_VARCHAR({columna}, 'YYYY-MM-DD')"

    def _construir_queries(self):
        fecha_str = self.fecha.strftime('%Y-%m-%d')
        
        # Filtro de almacen (ToWhsCode)
        condicion_almacen = ""
        if self.almacen_id != "*":
            condicion_almacen = f"AND OWTR.\"ToWhsCode\" = '{self.almacen_id}'"

        # 1. QUERY RECEPCION (OWTR filtrado por ToWhsCode)
        consulta_recepcion = f"""
        SELECT  
          OWTR."DocEntry", OWTR."DocNum", OWTR."DocDate", OWTR."Filler", OWTR."ToWhsCode", OWTR."U_SYP_MDTD", OWTR."U_SYP_MDSD", 
          OWTR."U_SYP_MDCD", OWTR."ObjType", OWTR."CardName", OWTR."U_BPP_FECINITRA",
          WTR1."DocEntry", WTR1."LineNum", WTR1."ItemCode", WTR1."Dscription", WTR1."WhsCode", WTR1."ObjType",
          OITL."LogEntry", OITL."ItemCode", OITL."DocEntry", OITL."DocLine", OITL."DocType", OITL."StockEff", OITL."LocCode",
          ITL1."LogEntry", ITL1."ItemCode", ITL1."Quantity", ITL1."SysNumber", ITL1."MdAbsEntry",
          OBTN."ItemCode", OBTN."DistNumber", OBTN."SysNumber", OBTN."AbsEntry", OBTN."MnfSerial", OBTN."ExpDate",
          OBTW."ItemCode", OBTW."MdAbsEntry", OBTW."WhsCode", OBTW."Location", OBTW."AbsEntry",
          OITM."ItemCode", OITM."ItemName", OITM."FrgnName", OITM."U_SYP_CONCENTRACION", OITM."U_SYP_FORPR", OITM."U_SYP_FFDET", 
          OITM."U_SYP_FABRICANTE"
        FROM {self._esquema("OWTR")}.OWTR OWTR
        INNER JOIN {self._esquema("WTR1")}.WTR1 WTR1 ON WTR1."DocEntry" = OWTR."DocEntry"
        LEFT JOIN {self._esquema("OITL")}.OITL OITL ON OITL."DocEntry" = OWTR."DocEntry" AND OITL."DocType" = OWTR."ObjType" AND OITL."DocLine" = WTR1."LineNum" AND OITL."ItemCode" = WTR1."ItemCode"
        LEFT JOIN {self._esquema("ITL1")}.ITL1 ITL1 ON ITL1."LogEntry" = OITL."LogEntry" AND ITL1."ItemCode" = WTR1."ItemCode"
        LEFT JOIN {self._esquema("OBTN")}.OBTN OBTN ON OBTN."SysNumber" = ITL1."SysNumber" AND OBTN."ItemCode" = WTR1."ItemCode"
        LEFT JOIN {self._esquema("OBTW")}.OBTW OBTW ON OBTW."ItemCode" = WTR1."ItemCode" AND OBTW."MdAbsEntry" = ITL1."MdAbsEntry" AND OBTW."WhsCode" = WTR1."WhsCode"
        LEFT JOIN {self._esquema("OITM")}.OITM OITM ON OITM."ItemCode" = WTR1."ItemCode"
        WHERE {self._formato_fecha_hana('OWTR."U_BPP_FECINITRA"')} = '{fecha_str}'
          AND OWTR."CANCELED" = 'N'
          AND OWTR."U_SYP_STATUS" = 'V'
          AND OWTR."U_SYP_MDSD" IS NOT NULL
          AND OWTR."U_SYP_MDCD" IS NOT NULL
          {condicion_almacen};
        """
        
        consulta_owhs = f"""SELECT T0."WhsCode", T0."WhsName", T0."TaxOffice" FROM {self._esquema("OWHS")}.OWHS T0"""
        
        return {
            'RECEPCION': consulta_recepcion,
            'OWHS': consulta_owhs
        }

    def _limpiar_sql_previo(self, tabla_sql: str) -> bool:
        """Limpieza basada en ToWhsCode (Almacen Destino)."""
        if not self.almacen_id: return True

        # Filtro clave: ToWhsCode
        filtro_almacen = f"WHERE T_PADRE.ToWhsCode = '{self.almacen_id}'"
        script = ""

        if tabla_sql == 'RECEPCION':
            if self.almacen_id == "*": return "TRUNCATE TABLE dbo.OWTR;"

            # Orden de borrado: Hijos -> Padres
            script = f"""
                DELETE T1 FROM dbo.ITL1 T1 INNER JOIN dbo.OITL T2 ON T1.LogEntry = T2.LogEntry INNER JOIN dbo.OWTR T_PADRE ON T2.DocEntry = T_PADRE.DocEntry AND T2.DocType = T_PADRE.ObjType {filtro_almacen};
                DELETE T1 FROM dbo.OITL T1 INNER JOIN dbo.OWTR T_PADRE ON T1.DocEntry = T_PADRE.DocEntry AND T1.DocType = T_PADRE.ObjType {filtro_almacen};
                DELETE T1 FROM dbo.OBTW T1 INNER JOIN dbo.WTR1 T2 ON T1.ItemCode = T2.ItemCode AND T1.WhsCode = T2.WhsCode INNER JOIN dbo.OWTR T_PADRE ON T2.DocEntry = T_PADRE.DocEntry {filtro_almacen};
                DELETE T1 FROM dbo.OBTN T1 INNER JOIN dbo.WTR1 T2 ON T1.ItemCode = T2.ItemCode INNER JOIN dbo.OWTR T_PADRE ON T2.DocEntry = T_PADRE.DocEntry {filtro_almacen};
                DELETE T1 FROM dbo.WTR1 T1 INNER JOIN dbo.OWTR T_PADRE ON T1.DocEntry = T_PADRE.DocEntry {filtro_almacen};
                DELETE T_PADRE FROM dbo.OWTR T_PADRE {filtro_almacen};
            """
        
        elif tabla_sql == 'OWHS' and self.almacen_id == "*":
            script = "TRUNCATE TABLE dbo.OWHS;"

        if not script: return True

        try:
            with ConexionSQL() as sql:
                if sql.db_estado:
                    sql.cursor.execute(script)
                    sql.conexion.commit()
            return True
        except Exception as e:
            logger.critical(f"Error limpieza SQL {tabla_sql}: {e}")
            return False

    def migracion_hana_sql(self, query: str, tabla_sql: str) -> int:
        logger.info(f"--- Procesando RECEPCION: {tabla_sql} (Almacen: {self.almacen_id}) ---")

        # 1. Limpieza
        if not self._limpiar_sql_previo(tabla_sql): return 0

        # 2. Leer HANA
        try:
            with ConexionHANA(query) as hana:
                if not hana.db_estado: return 0
                registros = hana.obtener_tabla()
                total = len(registros)
                logger.info(f"Registros leidos de HANA: {total}")
                if total == 0: return 0
        except Exception as e:
            logger.error(f"Error leyendo HANA: {e}")
            return 0

        # 3. Procesar y Generar SQL
        inserts_generados = []

        if tabla_sql == 'RECEPCION':
            importador = ImportadorRecepcion()
            for fila in registros:
                importador.procesar_fila(fila)
            
            # Orden de insercion (Misma estructura que Traslados, es la misma tabla OWTR)
            orden = ['OWTR', 'WTR1', 'OITL', 'ITL1', 'OBTN', 'OBTW', 'OITM']
            for t in orden:
                inserts_generados.extend(importador.obtener_bloques(t))
        
        else: # Generico (OWHS)
            importador = self.importador_generico
            importador.query_sql = [] 
            importador.bloque_actual = []
            for fila in registros:
                importador.query_transaccion(fila, tabla_sql)
            inserts_generados = importador.obtener_query_final()

        # 4. Insertar en SQL Server
        exitos = 0
        errores = {}
        
        with ConexionSQL() as sql:
            if not sql.db_estado: return 0
            for bloque in inserts_generados:
                if not bloque.strip(): continue
                try:
                    sql.cursor.execute(bloque)
                    exitos += 1
                except Exception as e:
                    msg = str(e)
                    errores[msg] = errores.get(msg, 0) + 1
            sql.conexion.commit()

        logger.info(f"[OK] {tabla_sql}: {exitos} bloques insertados.")
        if errores:
            logger.warning(f"[WARNING] Errores en {tabla_sql}:")
            for msg, count in errores.items():
                logger.warning(f"   -> {count} veces: {msg[:100]}...")

        return total

    def migrar_todas(self) -> list:
        resultados = []
        for tabla in self.tablas_objetivo:
            cantidad = self.migracion_hana_sql(self.queries[tabla], tabla)
            resultados.append({
                "tabla": tabla,
                "fecha": self.fecha.strftime("%Y-%m-%d"),
                "registros": cantidad,
                "exito": True
            })
        return resultados