import logging
import sys
import os
from datetime import datetime, timedelta
from pydantic import BaseModel

# --- IMPORTS DE TUS CLASES (Respetando nombres) ---
from Conexion.conexion_hana import ConexionHANA
from Conexion.conexion_sql import ConexionSQL
from Config.conexion_config import CONFIG_HANA

# Importamos la clase PADRE (Genérica) y la HIJA (Especializada)
from Procesamiento.Importador import Importador
from Procesamiento.importador_ventas import ImportadorVentas

# ==========================================
# CONFIGURACION DE LOGS CENTRALIZADA
# ==========================================
LOG_DIR = "Logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, 'migrador_ventas.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class MigracionVentasRequest(BaseModel):
    fecha: datetime
    almacen_id: str = "*"

class MigradorVentas:
    def __init__(self, fecha: datetime, almacen_id: str):
        # Normalización de fecha
        self.fecha = datetime.strptime(fecha, "%Y-%m-%d") if isinstance(fecha, str) else fecha
        self.almacen_id = almacen_id
        
        # Instancia genérica para tablas simples (OWHS)
        self.importador_generico = Importador()
        
        # Definimos qué tablas procesar
        self.tablas_objetivo = ['VENTAS', 'OINV', 'INV1', 'OWHS']
        self.queries = self._construir_queries()

    def _esquema(self, tabla):
        return CONFIG_HANA.get("schema", "SBO_SCHEMA")

    def _formato_fecha_hana(self, columna):
        return f"TO_VARCHAR({columna}, 'YYYY-MM-DD')"

    def _construir_queries(self):
        fecha_str = self.fecha.strftime('%Y-%m-%d')
        # Rango para facturas
        fecha_inicio = (self.fecha - timedelta(days=7)).strftime('%Y-%m-%d')
        fecha_fin = (self.fecha + timedelta(days=7)).strftime('%Y-%m-%d')

        condicion_almacen = ""
        if self.almacen_id != "*":
            condicion_almacen = f"AND ODLN.\"U_COB_LUGAREN\" = '{self.almacen_id}'"

        # 1. QUERY VENTAS (ODLN) - Compleja con Joins
        consulta_ventas = f"""
            SELECT
                ODLN."DocEntry",ODLN."ObjType",ODLN."DocNum",ODLN."CardCode",ODLN."CardName",ODLN."NumAtCard",ODLN."DocDate",
                ODLN."TaxDate",ODLN."U_SYP_MDTD",ODLN."U_SYP_MDSD",ODLN."U_SYP_MDCD",ODLN."U_COB_LUGAREN",ODLN."U_BPP_FECINITRA",
                DLN1."DocEntry",DLN1."ObjType",DLN1."WhsCode",DLN1."ItemCode",DLN1."LineNum",DLN1."Dscription",DLN1."UomCode",
                IBT1."ItemCode",IBT1."BatchNum",IBT1."WhsCode",IBT1."BaseEntry",IBT1."BaseType",IBT1."BaseLinNum",IBT1."Quantity",
                OBTN."ItemCode", OBTN."DistNumber",OBTN."SysNumber",OBTN."AbsEntry",OBTN."MnfSerial",OBTN."ExpDate",
                OBTW."ItemCode",OBTW."MdAbsEntry",OBTW."WhsCode",OBTW."Location",OBTW."AbsEntry",      
                OITL."LogEntry",OITL."ItemCode",OITL."DocEntry",OITL."DocLine",OITL."DocType",OITL."StockEff",OITL."LocCode",
                ITL1."LogEntry",ITL1."ItemCode",ITL1."Quantity",ITL1."SysNumber",ITL1."MdAbsEntry",
                OITM."ItemCode",OITM."ItemName",OITM."FrgnName",OITM."U_SYP_CONCENTRACION",OITM."U_SYP_FORPR",
                OITM."U_SYP_FFDET",OITM."U_SYP_FABRICANTE"
            FROM {self._esquema("ODLN")}.ODLN ODLN
            INNER JOIN {self._esquema("DLN1")}.DLN1 DLN1 ON DLN1."DocEntry" = ODLN."DocEntry"
            INNER JOIN {self._esquema("IBT1")}.IBT1 IBT1 
                ON IBT1."BaseEntry" = DLN1."DocEntry" AND IBT1."BaseType" = DLN1."ObjType" 
                AND IBT1."WhsCode" = DLN1."WhsCode" AND IBT1."ItemCode" = DLN1."ItemCode" AND IBT1."BaseLinNum" = DLN1."LineNum"
            INNER JOIN {self._esquema("OBTN")}.OBTN OBTN 
                ON OBTN."ItemCode" = DLN1."ItemCode" AND OBTN."DistNumber" = IBT1."BatchNum"
            INNER JOIN {self._esquema("OITL")}.OITL OITL 
                ON OITL."DocEntry" = DLN1."DocEntry" AND OITL."ItemCode" = IBT1."ItemCode" AND OITL."DocType" = DLN1."ObjType" 
                AND OITL."DocLine" = DLN1."LineNum" AND OITL."StockEff" = 1
            INNER JOIN {self._esquema("ITL1")}.ITL1 ITL1 
                ON ITL1."LogEntry" = OITL."LogEntry" AND ITL1."SysNumber" = OBTN."SysNumber"
            INNER JOIN {self._esquema("OBTW")}.OBTW OBTW 
                ON OBTW."ItemCode" = DLN1."ItemCode" AND OBTW."MdAbsEntry" = ITL1."MdAbsEntry" AND OBTW."WhsCode" = DLN1."WhsCode"
            INNER JOIN {self._esquema("OITM")}.OITM OITM ON OITM."ItemCode" = DLN1."ItemCode"
            WHERE {self._formato_fecha_hana('ODLN."U_BPP_FECINITRA"')} = '{fecha_str}'
                AND ODLN."CANCELED" = 'N' 
                AND ODLN."U_SYP_STATUS" = 'V'
                AND ODLN."U_SYP_MDSD" IS NOT NULL 
                AND ODLN."U_SYP_MDCD" IS NOT NULL
                {condicion_almacen}
        """

        # 2. QUERY OINV
        consulta_oinv = f"""
            SELECT T0."DocEntry", T0."NumAtCard", T0."U_SYP_NGUIA", T0."ObjType", T0."DocNum", T0."CardCode", T0."CardName", 
                   T0."DocDate", T0."TaxDate", T0."U_SYP_MDTD", T0."U_SYP_MDSD", T0."U_SYP_MDCD", T0."U_COB_LUGAREN", T0."U_BPP_FECINITRA"
            FROM {self._esquema("OINV")}.OINV T0
            WHERE T0."CANCELED" = 'N'
            AND T0."U_BPP_FECINITRA" BETWEEN '{fecha_inicio}' AND '{fecha_fin}'
            AND T0."U_COB_LUGAREN" = '{self.almacen_id}'
        """

        # 3. QUERY INV1
        consulta_inv1 = f"""
            SELECT T0."DocEntry", T0."ObjType", T0."WhsCode", T0."ItemCode", T0."LineNum", T0."Dscription",
                   T0."UomCode", T0."BaseType", T0."BaseEntry"
            FROM {self._esquema("INV1")}.INV1 T0
            INNER JOIN {self._esquema("OINV")}.OINV T1 ON T0."DocEntry" = T1."DocEntry"
            WHERE T1."CANCELED" = 'N'
            AND T1."U_BPP_FECINITRA" BETWEEN '{fecha_inicio}' AND '{fecha_fin}'
            AND T1."U_COB_LUGAREN" = '{self.almacen_id}'
        """

        # 4. QUERY OWHS
        consulta_owhs = f"""SELECT T0."WhsCode", T0."WhsName", T0."TaxOffice" FROM {self._esquema("OWHS")}.OWHS T0"""

        return {
            'VENTAS': consulta_ventas,
            'OINV': consulta_oinv,
            'INV1': consulta_inv1,
            'OWHS': consulta_owhs,
        }

    def _limpiar_sql_previo(self, tabla_sql: str) -> bool:
        """Limpia los datos en SQL Server antes de insertar."""
        if not self.almacen_id: return True

        script = ""
        filtro_almacen = f"WHERE T_PADRE.U_COB_LUGAREN = '{self.almacen_id}'"

        # 1. CASO VENTAS (ODLN) - Borra todo el árbol de una vez
        if tabla_sql == 'VENTAS':
            if self.almacen_id == "*": return "TRUNCATE TABLE dbo.ODLN;" 
            
            script = f"""
                BEGIN TRAN;

                -- =========================
                -- 1. ITL1 (detalle log)
                -- =========================
                DELETE FROM dbo.ITL1
                WHERE LogEntry IN (
                    SELECT OITL.LogEntry
                    FROM dbo.OITL
                    WHERE OITL.DocEntry IN (
                        SELECT DocEntry
                        FROM dbo.ODLN
                        WHERE U_COB_LUGAREN = '{self.almacen_id}'
                    )
                );

                -- =========================
                -- 2. OITL (log inventario)
                -- =========================
                DELETE FROM dbo.OITL
                WHERE DocEntry IN (
                    SELECT DocEntry
                    FROM dbo.ODLN
                    WHERE U_COB_LUGAREN = '{self.almacen_id}'
                );

                -- =========================
                -- 3. IBT1 (lotes por doc)
                -- =========================
                DELETE FROM dbo.IBT1
                WHERE BaseEntry IN (
                    SELECT DocEntry
                    FROM dbo.ODLN
                    WHERE U_COB_LUGAREN = '{self.almacen_id}'
                );

                -- =========================
                -- 4. DLN1 (detalle)
                -- =========================
                DELETE FROM dbo.DLN1
                WHERE DocEntry IN (
                    SELECT DocEntry
                    FROM dbo.ODLN
                    WHERE U_COB_LUGAREN = '{self.almacen_id}'
                );

                -- =========================
                -- 5. ODLN (cabecera)
                -- =========================
                DELETE FROM dbo.ODLN
                WHERE U_COB_LUGAREN = '{self.almacen_id}';

                COMMIT TRAN;
                """

        # 2. CASO OINV (Cabecera) - Aquí SÍ borramos todo para empezar limpio
        elif tabla_sql == 'OINV':
            fecha_inicio = (self.fecha - timedelta(days=7)).strftime('%Y-%m-%d')
            fecha_fin = (self.fecha + timedelta(days=7)).strftime('%Y-%m-%d')
            script = f"""
                -- Borramos primero hijos (INV1) para evitar error de FK
                DELETE T1 FROM dbo.INV1 T1 INNER JOIN dbo.OINV T_PADRE ON T1.DocEntry=T_PADRE.DocEntry 
                WHERE T_PADRE.U_COB_LUGAREN='{self.almacen_id}' AND T_PADRE.U_BPP_FECINITRA BETWEEN '{fecha_inicio}' AND '{fecha_fin}';
                
                -- Borramos Padres (OINV)
                DELETE T_PADRE FROM dbo.OINV T_PADRE 
                WHERE T_PADRE.U_COB_LUGAREN='{self.almacen_id}' AND T_PADRE.U_BPP_FECINITRA BETWEEN '{fecha_inicio}' AND '{fecha_fin}';
            """

        # 3. CASO INV1 (Detalle) - ¡CORRECCIÓN CRÍTICA!
        elif tabla_sql == 'INV1':
            # NO BORRAMOS NADA.
            # ¿Por qué? Porque el paso anterior ('OINV') ya borró todo (padres e hijos).
            # Si borramos aquí de nuevo, corremos riesgo de borrar las OINV que acabamos de insertar.
            # Además, OINV e INV1 se migran juntas en bloque por fecha.
            return True 

        # 4. CASO OWHS (Almacenes)
        elif tabla_sql == 'OWHS':
            if self.almacen_id == "*":
                script = "TRUNCATE TABLE dbo.OWHS;"
            else:
                # Si filtramos por almacén, NO borramos OWHS porque contiene otros almacenes
                # Solo dejamos pasar para que intente insertar (y falle si ya existe, que es lo esperado)
                return True

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
        """
        Orquestador principal.
        Conecta HANA -> Obtiene Datos -> Instancia ImportadorVentas -> Obtiene SQL -> Inserta SQL
        """
        logger.info(f"--- Procesando: {tabla_sql} (Almacén: {self.almacen_id}) ---")

        # 1. Limpieza
        if not self._limpiar_sql_previo(tabla_sql): return 0

        # 2. Leer HANA
        try:
            with ConexionHANA(query) as hana:
                if not hana.db_estado: return 0
                registros = hana.obtener_tabla()
                logger.info(f"Registros leídos de HANA: {len(registros)}")
                if not registros: return 0
        except Exception as e:
            logger.error(f"Error leyendo HANA: {e}")
            return 0

        # 3. Procesar Datos y Generar SQL
        inserts_generados = []
        
        # CASO A: TABLAS COMPLEJAS (VENTAS) - Usan la clase hija ImportadorVentas
        if tabla_sql == 'VENTAS':
            importador = ImportadorVentas() # Usamos la clase especializada
            for fila in registros:
                importador.procesar_fila(fila)
            
            # Extraemos los bloques en orden de integridad referencial
            # Primero cabeceras, luego detalles
            orden_tablas = ['ODLN', 'DLN1', 'IBT1', 'OBTN', 'OBTW', 'OITL', 'ITL1', 'OITM']
            for t in orden_tablas:
                inserts_generados.extend(importador.obtener_bloques(t))

        # CASO B: FACTURAS (OINV/INV1) - Usamos ImportadorVentas (si tiene los métodos) o el Genérico
        # Nota: Aquí asumo que usaremos el Genérico para OINV/INV1 si no implementaste procesar_fila_oinv en la clase anterior
        # Si prefieres usar la lógica genérica simple para esto:
        elif tabla_sql in ['OINV', 'INV1', 'OWHS']:
            importador = self.importador_generico # Usamos la clase padre
            importador.query_sql = [] # Limpiamos buffer anterior
            importador.bloque_actual = []
            
            for fila in registros:
                importador.query_transaccion(fila, tabla_sql)
            
            inserts_generados = importador.obtener_query_final()

        # 4. Insertar en SQL Server
        exitos = 0
        errores = {}
        
        with ConexionSQL() as sql:
            if not sql.db_estado: return 0
            
            # Ejecutamos bloque por bloque
            for bloque in inserts_generados:
                if not bloque.strip(): continue
                try:
                    sql.cursor.execute(bloque)
                    exitos += 1
                except Exception as e:
                    msg = str(e)
                    errores[msg] = errores.get(msg, 0) + 1

            sql.conexion.commit() # Un solo commit al final es suficiente y más rápido

        # Resumen limpio
        logger.info(f"✅ {tabla_sql}: {exitos} bloques insertados correctamente.")
        if errores:
            logger.warning(f"⚠️ Errores en {tabla_sql}:")
            for msg, count in errores.items():
                logger.warning(f"   -> {count} veces: {msg[:100]}...")

        return exitos

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