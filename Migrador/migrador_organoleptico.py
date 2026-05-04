import logging
import sys
import os
from datetime import datetime
from pydantic import BaseModel

# Imports de conexion y procesamiento
from Conexion.conexion_hana import ConexionHANA
from Conexion.conexion_sql import ConexionSQL
from Config.conexion_config import CONFIG_HANA
from Procesamiento.Importador import Importador
from Procesamiento.Importador_organoleptico import ImportadorOrganoleptico

# Configuracion de logs
LOG_DIR = "Logs"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, 'migrador_organoleptico.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class MigracionOrganolepticoRequest(BaseModel):
    fecha: datetime
    almacen_id: str = "*"

class MigradorOrganoleptico:
    def __init__(self, fecha: datetime, almacen_id: str):
        self.fecha = datetime.strptime(fecha, "%Y-%m-%d") if isinstance(fecha, str) else fecha
        self.almacen_id = almacen_id
        self.importador_generico = Importador()
        self.tablas_objetivo = ['ORGANOLEPTICO', 'OWHS']
        self.queries = self._construir_queries()

    def _esquema(self, tabla):
        return CONFIG_HANA.get("schema", "SBO_SCHEMA")

    def _construir_queries(self):
        fecha_str = self.fecha.strftime('%Y-%m-%d')
        # Filtro de Identidad: Identifica que la fila es de Organoleptico y no un traslado comun
        filtro_modulo = "AND OWTR.\"U_SYP_MDSD\" IS NOT NULL AND OWTR.\"U_SYP_MDCD\" IS NOT NULL"
        condicion_almacen = f"AND OWTR.\"ToWhsCode\" = '{self.almacen_id}'" if self.almacen_id != "*" else ""
        
        consulta = f"""
        SELECT OWTR."DocEntry", OWTR."DocNum", OWTR."DocDate", OWTR."Filler", OWTR."ToWhsCode", OWTR."U_SYP_MDTD", OWTR."U_SYP_MDSD", 
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
        LEFT JOIN {self._esquema("OITL")}.OITL OITL ON OITL."DocEntry" = OWTR."DocEntry" AND OITL."DocType" = OWTR."ObjType" AND OITL."DocLine" = WTR1."LineNum"
        LEFT JOIN {self._esquema("ITL1")}.ITL1 ITL1 ON ITL1."LogEntry" = OITL."LogEntry"
        LEFT JOIN {self._esquema("OBTN")}.OBTN OBTN ON OBTN."SysNumber" = ITL1."SysNumber" AND OBTN."ItemCode" = WTR1."ItemCode"
        LEFT JOIN {self._esquema("OBTW")}.OBTW OBTW ON OBTW."ItemCode" = WTR1."ItemCode" AND OBTW."MdAbsEntry" = ITL1."MdAbsEntry"
        LEFT JOIN {self._esquema("OITM")}.OITM OITM ON OITM."ItemCode" = WTR1."ItemCode"
        WHERE TO_VARCHAR(OWTR."U_BPP_FECINITRA", 'YYYY-MM-DD') = '{fecha_str}'
          AND OWTR."CANCELED" = 'N' AND OWTR."U_SYP_STATUS" = 'V'
          {filtro_modulo} {condicion_almacen}
        """
        return {
            'ORGANOLEPTICO': consulta, 
            'OWHS': f"SELECT \"WhsCode\", \"WhsName\", \"TaxOffice\" FROM {self._esquema('OWHS')}.OWHS"
        }

    def _limpiar_sql_quirurgico(self, tabla_sql):
        """Borra solo los datos del almacen actual y del modulo especifico para evitar cruces."""
        if not self.almacen_id or self.almacen_id == "*": return True

        # Este filtro garantiza que NO borraremos datos de otros almacenes o de otros modulos (como Traslados simples)
        filtro_identidad = "AND T_PADRE.U_SYP_MDSD IS NOT NULL AND T_PADRE.U_SYP_MDCD IS NOT NULL AND T_PADRE.CANCELED = 'N'"
        filtro_almacen = f"WHERE T_PADRE.ToWhsCode = '{self.almacen_id}'"

        if tabla_sql == 'ORGANOLEPTICO':
            script = f"""
            DELETE T1 FROM dbo.ITL1 T1 
            JOIN dbo.OITL T2 ON T1.LogEntry = T2.LogEntry 
            JOIN dbo.OWTR T_PADRE ON T2.DocEntry = T_PADRE.DocEntry AND T2.DocType = T_PADRE.ObjType
            {filtro_almacen} {filtro_identidad};

            DELETE T1 FROM dbo.OITL T1 
            JOIN dbo.OWTR T_PADRE ON T1.DocEntry = T_PADRE.DocEntry AND T1.DocType = T_PADRE.ObjType
            {filtro_almacen} {filtro_identidad};

            DELETE T1 FROM dbo.WTR1 T1 
            JOIN dbo.OWTR T_PADRE ON T1.DocEntry = T_PADRE.DocEntry
            {filtro_almacen} {filtro_identidad};

            DELETE T_PADRE FROM dbo.OWTR T_PADRE 
            {filtro_almacen} {filtro_identidad};
            """
            try:
                with ConexionSQL() as sql:
                    if sql.db_estado:
                        sql.cursor.execute(script)
                        sql.conexion.commit()
                        logger.info(f"Limpieza quirúrgica para Almacen {self.almacen_id} completada.")
            except Exception as e:
                logger.error(f"Error en limpieza blindada: {e}")
        return True

    def migracion_hana_sql(self, query, tabla_sql):
        logger.info(f"--- Procesando: {tabla_sql} (Almacen: {self.almacen_id}) ---")
        
        # 1. Limpieza segura antes de procesar
        self._limpiar_sql_quirurgico(tabla_sql)

        # 2. Obtencion de datos desde HANA
        with ConexionHANA(query) as hana:
            if not hana.db_estado: return 0
            registros = hana.obtener_tabla()
            if not registros: return 0
        
        # 3. Procesamiento e Insercion en SQL Server
        exitos, errores = 0, {}
        with ConexionSQL() as sql:
            if not sql.db_estado: return 0
            
            if tabla_sql == 'ORGANOLEPTICO':
                imp = ImportadorOrganoleptico()
                for f in registros: imp.procesar_fila(f)
                # Ejecutamos en orden de jerarquia (Cabecera primero, detalles despues)
                orden_tablas = ['OWTR', 'WTR1', 'OITL', 'ITL1', 'OBTN', 'OBTW', 'OITM']
                for t in orden_tablas:
                    for bloque in imp.obtener_bloques(t):
                        try:
                            sql.cursor.execute(bloque); exitos += 1
                        except Exception as e:
                            msg = str(e)
                            # Ignoramos errores de duplicados en maestros (Articulos compartidos entre almacenes)
                            if not ('PRIMARY KEY' in msg or '2627' in msg):
                                errores[msg] = errores.get(msg, 0) + 1
            else:
                # Logica para tablas maestras globales como OWHS
                self.importador_generico.query_sql, self.importador_generico.bloque_actual = [], []
                for f in registros: self.importador_generico.query_transaccion(f, tabla_sql)
                for bloque in self.importador_generico.obtener_query_final():
                    try: sql.cursor.execute(bloque); exitos += 1
                    except Exception as e: errores[str(e)] = errores.get(str(e), 0) + 1
            
            sql.conexion.commit()

        logger.info(f"[OK] {tabla_sql}: {exitos} bloques procesados correctamente.")
        return len(registros)

    def migrar_todas(self) -> list:
        return [{"tabla": t, "registros": self.migracion_hana_sql(self.queries[t], t)} for t in self.tablas_objetivo]