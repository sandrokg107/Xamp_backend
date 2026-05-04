import logging
import sys
import os
from datetime import datetime, timedelta
from Conexion.conexion_hana import ConexionHANA
from Conexion.conexion_sql import ConexionSQL
from Procesamiento.Importador import Importador
from Config.conexion_config import CONFIG_HANA

# ==========================================
# CONFIGURACION DE LOGS
# ==========================================
LOG_DIR = "Logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, 'migrador_general.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class Migrador:
    def __init__(self, fecha_str):
        # Manejo flexible de fecha (string o datetime)
        if isinstance(fecha_str, str):
            self.fecha = datetime.strptime(fecha_str, "%Y-%m-%d")
        else:
            self.fecha = fecha_str

        # Definir rango del día completo
        self.fecha_inicio = self.fecha.replace(hour=0, minute=0, second=0)
        self.fecha_fin = self.fecha_inicio + timedelta(days=1) - timedelta(seconds=1)
        
        self.importador = Importador()
        
        # Lista de tablas a migrar en orden
        self.tablas_objetivo = [
            'OITM', 'OBTW', 'OBTN', 'OWHS', 
            'OINV', 'INV1', 
            'ODLN', 'DLN1', 
            'OWTR', 'WTR1', 
            'OITL', 'ITL1', 
            'IBT1'
        ]
        self.queries = self._construir_queries()

    def _esquema(self, tabla):
        return CONFIG_HANA["schema"]

    def _formato_fecha_hana(self, columna):
        # Usamos TO_VARCHAR estándar de HANA
        return f"TO_VARCHAR({columna}, 'YYYY-MM-DD')"

    def _construir_queries(self):
        fecha_fmt = self.fecha.strftime("%Y-%m-%d")
        inicio_fmt = self.fecha_inicio.strftime("%Y-%m-%d")
        fin_fmt = self.fecha_fin.strftime("%Y-%m-%d")

        return {
            'OBTW': f'''
                SELECT T0."ItemCode", T0."MdAbsEntry", T0."WhsCode", T0."Location", T0."AbsEntry" 
                FROM {self._esquema("OBTW")}.OBTW T0
            ''',
            
            'OBTN': f'''
                SELECT T0."ItemCode", T0."DistNumber", T0."SysNumber", T0."AbsEntry", T0."MnfSerial",
                       {self._formato_fecha_hana('T0."ExpDate"')} AS "ExpDate"
                FROM {self._esquema("OBTN")}.OBTN T0
                WHERE "ExpDate" > '{fecha_fmt}' 
            ''',
           
           'IBT1': f'''
                SELECT T0."ItemCode", T0."BatchNum", T0."WhsCode", T0."BaseEntry", T0."BaseType", T0."BaseLinNum", T0."Quantity"
                FROM {self._esquema("IBT1")}.IBT1 T0
                WHERE "DocDate" = '{fecha_fmt}'
            ''',
   
            'OITM': f'''
                SELECT T0."ItemCode", T0."ItemName", T0."FrgnName", T0."U_SYP_CONCENTRACION", 
                       T0."U_SYP_FORPR", T0."U_SYP_FFDET", T0."U_SYP_FABRICANTE" 
                FROM {self._esquema("OITM")}.OITM T0
            ''',
        
            'OWHS': f'''
                SELECT T0."WhsCode", T0."WhsName", T0."TaxOffice"
                FROM {self._esquema("OWHS")}.OWHS T0
            ''',
        
            'OINV': f'''
                 SELECT T0."DocEntry", T0."NumAtCard", T0."U_SYP_NGUIA", T0."ObjType", T0."DocNum", T0."CardCode", T0."CardName", T0."DocDate",
                T0."TaxDate", T0."U_SYP_MDTD", T0."U_SYP_MDSD", T0."U_SYP_MDCD", T0."U_COB_LUGAREN", T0."U_BPP_FECINITRA"
            FROM {self._esquema("OINV")}.OINV T0
            WHERE T0."CANCELED" = 'N'
                AND T0."DocDate" BETWEEN '{inicio_fmt}' AND '{fin_fmt}' 
            ''',
            
            'INV1': f'''
                SELECT T0."DocEntry", T0."ObjType", T0."WhsCode", T0."ItemCode", T0."LineNum", T0."Dscription",
                    T0."UomCode", T0."BaseType", T0."BaseEntry"
                FROM {self._esquema("OINV")}.OINV T1
                INNER JOIN {self._esquema("INV1")}.INV1 T0 ON T0."DocEntry" = T1."DocEntry"
                WHERE T1."CANCELED" = 'N'
                AND T1."DocDate" = '{fecha_fmt}'
            ''',

            'OITL': f'''
                SELECT T0."LogEntry", T0."ItemCode", T0."DocEntry", T0."DocLine", T0."DocType", T0."StockEff", T0."LocCode"
                FROM {self._esquema("OITL")}.OITL T0
                WHERE T0."DocDate" = '{fecha_fmt}'
            ''',

           'ITL1': f'''
                SELECT T0."LogEntry", T0."ItemCode", T0."Quantity", T0."SysNumber", T0."MdAbsEntry"
                FROM {self._esquema("OITL")}.OITL T1
                INNER JOIN {self._esquema("ITL1")}.ITL1 T0 ON T0."LogEntry" = T1."LogEntry"
                WHERE T1."DocDate" = '{fecha_fmt}'   
            ''',

            'ODLN': f'''
                SELECT T0."DocEntry", T0."ObjType", T0."DocNum", T0."CardCode",
                    CASE
                        WHEN T0."CardCode" = 'C20608815466' THEN 'DROGUERIA JOSUE S S.A.C.'
                        WHEN T0."CardCode" = 'C20612232360' THEN 'INVERSIONES KAELI S SOCIEDAD COMERCIAL DE RESPONSABILIDAD LIMITADA'
                        WHEN T0."CardCode" = 'C20611448971' THEN 'ALISSON'
                        ELSE T0."CardName"
                    END AS "CardName",
                    T0."NumAtCard",
                    {self._formato_fecha_hana('T0."DocDate"')},
                    {self._formato_fecha_hana('T0."TaxDate"')},
                    T0."U_SYP_MDTD", T0."U_SYP_MDSD", T0."U_SYP_MDCD", T0."U_COB_LUGAREN",
                    {self._formato_fecha_hana('T0."U_BPP_FECINITRA"')}
                FROM {self._esquema("ODLN")}.ODLN T0
                WHERE T0."CANCELED" = 'N'
                AND T0."U_COB_LUGAREN" in ('16', '15')
                AND T0."DocDate" = '{fecha_fmt}'
                AND T0."CardCode" NOT IN ('C20611448971')
                ORDER BY T0."DocEntry" ASC
            ''',

            'DLN1': f'''
                SELECT T0."DocEntry", T0."ObjType", T0."WhsCode", T0."ItemCode", T0."LineNum",
                    T0."Dscription", T0."UomCode"
                FROM {self._esquema("ODLN")}.ODLN T1
                INNER JOIN {self._esquema("DLN1")}.DLN1 T0 ON T0."DocEntry" = T1."DocEntry"
                WHERE T1."CANCELED" = 'N'
                AND T1."U_SYP_STATUS" = 'V'
                AND T1."U_COB_LUGAREN" IN ('16', '15')
                AND T1."DocDate" = '{fecha_fmt}'
            ''',
                
            'OWTR': f'''
                SELECT T0."DocEntry", T0."DocNum", {self._formato_fecha_hana('T0."DocDate"')},
                    T0."Filler", T0."ToWhsCode", T0."U_SYP_MDTD", T0."U_SYP_MDSD", T0."U_SYP_MDCD",
                    T0."ObjType", T0."CardName", {self._formato_fecha_hana('T0."U_BPP_FECINITRA"')}
                FROM {self._esquema("OWTR")}.OWTR T0
                WHERE T0."CANCELED" = 'N'
                AND T0."U_SYP_STATUS" = 'V'
                AND T0."U_SYP_MDSD" IS NOT NULL
                AND T0."U_SYP_MDCD" IS NOT NULL
                AND T0."Filler" IN ('15', '16')
                AND T0."ToWhsCode" IN ('01', '09', 'ALM07')
                AND T0."DocDate" = '{fecha_fmt}'
            ''',

           'WTR1': f'''
                SELECT T0."DocEntry", T0."LineNum", T0."ItemCode", T0."Dscription",
                    T0."WhsCode", T0."ObjType"
                FROM {self._esquema("OWTR")}.OWTR T1
                INNER JOIN {self._esquema("WTR1")}.WTR1 T0 ON T0."DocEntry" = T1."DocEntry"
                WHERE T1."CANCELED" = 'N'
                AND T1."U_SYP_STATUS" = 'V'
                AND T1."U_SYP_MDSD" IS NOT NULL
                AND T1."U_SYP_MDCD" IS NOT NULL
                AND T1."Filler" IN ('15', '16')
                AND T1."ToWhsCode" IN ('01', '09', 'ALM07')
                AND T1."DocDate" = '{fecha_fmt}'
            '''
        }

    def migracion_hana_sql(self, query: str, tabla_sql: str) -> int:
        logger.info(f"Procesando tabla: {tabla_sql}...")
        try:
            # 1. Obtener datos de HANA
            with ConexionHANA(query) as hana:
                if not hana.db_estado:
                    logger.error("Conexión a SAP HANA fallida")
                    return 0
                registros = hana.obtener_tabla()
                total = len(registros)
                logger.info(f"Registros extraídos de HANA para {tabla_sql}: {total}")

                if not registros:
                    logger.warning(f"No hay registros en HANA para {tabla_sql}")
                    return 0

                # 2. Generar inserts (Bloques)
                # Reiniciamos el importador para limpiar queries anteriores
                self.importador = Importador()
                
                for i, fila in enumerate(registros, 1):
                    self.importador.query_transaccion(fila, tabla_sql)
                    if i % 1000 == 0:
                        logger.info(f"Generando SQL... {i}/{total}")

                # 3. Insertar en SQL Server
                with ConexionSQL() as sql:
                    if not sql.db_estado:
                        logger.error("Conexión a SQL Server fallida")
                        return 0
                    cursor = sql.cursor

                    # A. Truncar
                    try:
                        cursor.execute(f"TRUNCATE TABLE dbo.{tabla_sql}")
                        logger.info(f"Tabla dbo.{tabla_sql} truncada.")
                    except Exception as e:
                        logger.warning(f"No se pudo truncar dbo.{tabla_sql}: {e}")

                    # B. Insertar bloques
                    bloques = self.importador.query_sql
                    errores_bloques = 0
                    
                    for j, bloque in enumerate(bloques, 1):
                        if not bloque.strip(): continue
                        try:
                            cursor.execute(bloque)
                        except Exception as e:
                            errores_bloques += 1
                            logger.error(f"Error en bloque {j} de {tabla_sql}: {e}")
                            # logger.debug(f"Bloque: {bloque[:100]}...")

                    # C. Commit
                    sql.conexion.commit()
                    
                    if errores_bloques > 0:
                        logger.warning(f"Migración {tabla_sql} completada con {errores_bloques} bloques fallidos.")
                    else:
                        logger.info(f"Migración {tabla_sql} completada exitosamente.")
                    
                    return total

        except Exception as e:
            logger.critical(f"Error general migrando {tabla_sql}: {e}", exc_info=True)
            return 0

    def migrar_todas(self) -> list:
        """
        Ejecuta la migración de todas las tablas en orden.
        """
        resultados = []
        for tabla in self.tablas_objetivo:
            if tabla in self.queries:
                cantidad = self.migracion_hana_sql(self.queries[tabla], tabla)
                resultados.append({
                    "tabla": tabla,
                    "registros": cantidad,
                    "exito": cantidad > 0 or cantidad == 0 # Éxito técnico
                })
            else:
                logger.error(f"Query no definida para la tabla {tabla}")
        
        return resultados