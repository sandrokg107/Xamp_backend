import logging
import sys
import os
from datetime import datetime, timedelta
from pydantic import BaseModel

from Conexion.conexion_hana import ConexionHANA
from Conexion.conexion_sql import ConexionSQL
from Config.conexion_config import CONFIG_HANA
from Procesamiento.Importador import Importador
from Procesamiento.Importador_despacho import ImportadorDespacho

# Configuración de logs
LOG_DIR = "Logs"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(os.path.join(LOG_DIR, 'migrador_despacho.log'), encoding='utf-8')]
)
logger = logging.getLogger(__name__)

class MigracionDespachoRequest(BaseModel):
    fecha: datetime
    almacen_id: str = "*"

class MigradorDespacho:
    def __init__(self, fecha: datetime, almacen_id: str):
        self.fecha = datetime.strptime(fecha, "%Y-%m-%d") if isinstance(fecha, str) else fecha
        self.almacen_id = almacen_id
        self.importador_generico = Importador()
        self.tablas_objetivo = ['DESPACHO', 'OWHS']
        self.queries = self._construir_queries()

    def _esquema(self, tabla):
        return CONFIG_HANA.get("schema", "SBO_SCHEMA")

    def _construir_queries(self):
        # FECHA EXACTA (Como en el C#)
        fecha_fmt = self.fecha.strftime('%Y-%m-%d')

        # --- LOGICA REPLICADA DEL C# ---
        # El C# dice: COALESCE("U_BPP_FECINITRA" , "DocDate") = Fecha
        # Esto significa: Prioridad a Fecha Traslado, si es null, usa DocDate.
        condicion_fecha_hana = f"AND COALESCE(OINV.\"U_BPP_FECINITRA\", OINV.\"DocDate\") = '{fecha_fmt}'"

        # --- QUERY BLINDADA ---
        consulta_despacho = f'''
            SELECT
                OINV."DocEntry", OINV."NumAtCard", 
                COALESCE(OINV."U_SYP_NGUIA", '') AS "U_SYP_NGUIA", 
                OINV."ObjType", OINV."DocNum", 
                OINV."CardCode", OINV."CardName", 
                TO_VARCHAR(OINV."DocDate", 'YYYY-MM-DD') AS "DocDate", 
                TO_VARCHAR(OINV."TaxDate", 'YYYY-MM-DD') AS "TaxDate", 
                OINV."U_SYP_MDTD", OINV."U_SYP_MDSD", OINV."U_SYP_MDCD", 
                OINV."U_COB_LUGAREN", 
                TO_VARCHAR(OINV."U_BPP_FECINITRA", 'YYYY-MM-DD') AS "U_BPP_FECINITRA",
                
                INV1."DocEntry", INV1."ObjType", INV1."WhsCode", INV1."ItemCode", 
                INV1."LineNum", INV1."Dscription", INV1."UomCode", INV1."BaseType", INV1."BaseEntry",
                IBT1."ItemCode", IBT1."BatchNum", IBT1."WhsCode", IBT1."BaseEntry", 
                IBT1."BaseType", IBT1."BaseLinNum", IBT1."Quantity",
                OBTN."ItemCode", OBTN."DistNumber", OBTN."SysNumber", OBTN."AbsEntry", OBTN."MnfSerial", OBTN."ExpDate",
                OBTW."ItemCode", OBTW."MdAbsEntry", OBTW."WhsCode", OBTW."Location", OBTW."AbsEntry",
                OITL."LogEntry", OITL."ItemCode", OITL."DocEntry", OITL."DocLine", OITL."DocType", OITL."StockEff", OITL."LocCode",
                ITL1."LogEntry", ITL1."ItemCode", ITL1."Quantity", ITL1."SysNumber", ITL1."MdAbsEntry",
                OITM."ItemCode", OITM."ItemName", OITM."FrgnName", OITM."U_SYP_CONCENTRACION", OITM."U_SYP_FORPR", 
                OITM."U_SYP_FFDET", OITM."U_SYP_FABRICANTE"
            FROM {self._esquema("OINV")}.OINV OINV
            INNER JOIN {self._esquema("INV1")}.INV1 INV1 ON INV1."DocEntry" = OINV."DocEntry"
            LEFT JOIN {self._esquema("IBT1")}.IBT1 IBT1 ON IBT1."BaseEntry" = INV1."DocEntry" AND IBT1."BaseType" = INV1."ObjType" AND IBT1."BaseLinNum" = INV1."LineNum" AND IBT1."Quantity" < 0
            LEFT JOIN {self._esquema("OBTN")}.OBTN OBTN ON OBTN."ItemCode" = INV1."ItemCode" AND OBTN."DistNumber" = IBT1."BatchNum"
            LEFT JOIN {self._esquema("OITL")}.OITL OITL ON OITL."DocEntry" = INV1."DocEntry" AND OITL."DocType" = INV1."ObjType" AND OITL."DocLine" = INV1."LineNum" AND OITL."StockEff" = 1
            LEFT JOIN {self._esquema("ITL1")}.ITL1 ITL1 ON ITL1."LogEntry" = OITL."LogEntry" AND ITL1."SysNumber" = OBTN."SysNumber"
            LEFT JOIN {self._esquema("OBTW")}.OBTW OBTW ON OBTW."ItemCode" = INV1."ItemCode" AND OBTW."MdAbsEntry" = ITL1."MdAbsEntry"
            INNER JOIN {self._esquema("OITM")}.OITM OITM ON OITM."ItemCode" = INV1."ItemCode"
            WHERE OINV."CANCELED" = 'N'
            {condicion_fecha_hana}
            AND OINV."U_COB_LUGAREN" = '{self.almacen_id}'
        '''
        
        consulta_owhs = f"SELECT \"WhsCode\", \"WhsName\", \"TaxOffice\" FROM {self._esquema('OWHS')}.OWHS"
        
        return {'DESPACHO': consulta_despacho, 'OWHS': consulta_owhs}

    def _limpiar_sql_quirurgico(self, tabla_sql):
        """
        Limpieza exacta usando la misma lógica del C#:
        Borramos registros donde COALESCE(FechaTraslado, DocDate) sea igual a la fecha procesada.
        """
        if not self.almacen_id or self.almacen_id == "*": return True
        
        fecha_fmt = self.fecha.strftime('%Y-%m-%d')
        
        # TRADUCCION DE LOGICA C# A T-SQL (SQL SERVER)
        # ISNULL en T-SQL es equivalente a COALESCE/IFNULL
        condicion_fecha_sql = f"AND ISNULL(T_PADRE.U_BPP_FECINITRA, T_PADRE.DocDate) = '{fecha_fmt}'"
        
        filtro = f"WHERE T_PADRE.U_COB_LUGAREN = '{self.almacen_id}' {condicion_fecha_sql}"

        if tabla_sql == 'DESPACHO':
            script = f"""
            DELETE T1 FROM dbo.ITL1 T1 JOIN dbo.OITL T2 ON T1.LogEntry = T2.LogEntry JOIN dbo.OINV T_PADRE ON T2.DocEntry = T_PADRE.DocEntry AND T2.DocType = T_PADRE.ObjType {filtro};
            DELETE T1 FROM dbo.OITL T1 JOIN dbo.OINV T_PADRE ON T1.DocEntry = T_PADRE.DocEntry AND T1.DocType = T_PADRE.ObjType {filtro};
            DELETE T1 FROM dbo.IBT1 T1 JOIN dbo.OINV T_PADRE ON T1.BaseEntry = T_PADRE.DocEntry AND T1.BaseType = T_PADRE.ObjType {filtro};
            DELETE T1 FROM dbo.INV1 T1 JOIN dbo.OINV T_PADRE ON T1.DocEntry = T_PADRE.DocEntry {filtro};
            DELETE T_PADRE FROM dbo.OINV T_PADRE {filtro};
            """
            try:
                with ConexionSQL() as sql:
                    if sql.db_estado:
                        sql.cursor.execute(script)
                        sql.conexion.commit()
                        logger.info(f"Limpieza exacta (Lógica C#) para Almacen {self.almacen_id} fecha {fecha_fmt} completada.")
            except Exception as e:
                logger.error(f"Error en limpieza segregada: {e}")
        return True

    def migracion_hana_sql(self, query, tabla_sql):
        logger.info(f"--- 🚀 Iniciando migración: {tabla_sql} (Almacen: {self.almacen_id}) ---")
        
        self._limpiar_sql_quirurgico(tabla_sql)
        
        registros = []
        with ConexionHANA(query) as hana:
            if not hana.db_estado: 
                logger.error("❌ No hay conexión con HANA")
                return 0
            registros = hana.obtener_tabla()
            
        if not registros:
            logger.warning(f"⚠️ HANA devolvió 0 registros para {tabla_sql}. Revisa filtros.")
            return 0
        
        # --- DIAGNOSTICO ---
        if tabla_sql == 'DESPACHO':
            r_test = registros[0]
            val_guia = getattr(r_test, 'U_SYP_NGUIA', 'NO_EXISTE')
            val_fecha = getattr(r_test, 'U_BPP_FECINITRA', 'NO_EXISTE')
            logger.info(f"🔍 [MUESTRA] Guía: '{val_guia}' | Fecha: '{val_fecha}'")
        # -------------------

        logger.info(f"✅ HANA trajo {len(registros)} registros. Procesando...")

        exitos = 0
        errores_count = 0
        
        with ConexionSQL() as sql:
            if not sql.db_estado: 
                logger.error("❌ No hay conexión con SQL Server")
                return 0
            
            if tabla_sql == 'DESPACHO':
                imp = ImportadorDespacho()
                try:
                    for f in registros: imp.procesar_fila(f)
                except Exception as e:
                    logger.error(f"❌ Error transformando: {e}")
                    return 0

                tablas_ordenadas = ['OINV', 'INV1', 'IBT1', 'OITL', 'ITL1', 'OBTN', 'OBTW', 'OITM']
                
                for t in tablas_ordenadas:
                    bloques = imp.obtener_bloques(t)
                    if not bloques: continue
                    
                    # Log visual OINV
                    if t == 'OINV':
                        print(f"👀 INSERT OINV: {bloques[0][:150]}...")

                    for bloque in bloques:
                        try:
                            if not bloque.strip(): continue
                            sql.cursor.execute(bloque)
                            exitos += 1
                        except Exception as e:
                            if 'PRIMARY KEY' not in str(e):
                                errores_count += 1
                                logger.error(f"❌ Error {t}: {e}")

            else:
                self.importador_generico.query_sql = []
                for f in registros: self.importador_generico.query_transaccion(f, tabla_sql)
                bloques = self.importador_generico.obtener_query_final()
                for bloque in bloques:
                    try: 
                        sql.cursor.execute(bloque)
                        exitos += 1
                    except Exception as e: 
                        errores_count += 1

            if exitos > 0:
                sql.conexion.commit()
                logger.info("💾 Commit realizado.")
            else:
                logger.warning("⚠️ No hubo inserciones.")

        return {"registros_hana": len(registros), "insertados_sql": exitos, "errores": errores_count}

    def migrar_todas(self) -> list:
        return [{"tabla": t, "registros": self.migracion_hana_sql(self.queries[t], t)} for t in self.tablas_objetivo]