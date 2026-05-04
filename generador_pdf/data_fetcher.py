import logging
import traceback
from Conexion.conexion_sql import ConexionSQL

logger = logging.getLogger(__name__)


# --------------------------------------------------------
# DESPACHO (ACTA DESPACHO VENTA)
# --------------------------------------------------------
def obtener_docentries_acta_despacho_venta(fecha: str):
    try:
        with ConexionSQL() as conn:
            if not conn.valida_conexion():
                logger.error("❌ Conexión SQL no válida en obtener_docentries_acta_despacho_venta()")
                return []
            logger.info(f"📦 Ejecutando: EXEC LISTADO_DOC_ACTA_DESP_VENTA '{fecha}'")
            conn.cursor.execute("EXEC LISTADO_DOC_ACTA_DESP_VENTA ?", fecha)
            resultados = [row[0] for row in conn.cursor.fetchall()]
            logger.info(f"✅ {len(resultados)} DocEntries encontrados para acta despacho venta")
            return resultados
    except Exception as e:
        logger.error(f"❌ Error en obtener_docentries_acta_despacho_venta({fecha}): {e}")
        logger.debug(traceback.format_exc())
        return []

def obtener_info_acta_despacho_venta(docentry: int):
    try:
        with ConexionSQL() as conn:
            if not conn.valida_conexion():
                logger.error("❌ Conexión SQL no válida en obtener_info_acta_despacho_venta()")
                return []
            logger.info(f"📦 Ejecutando: EXEC INFO_DOC_ACTA_DESP_VENTA {docentry}")
            conn.cursor.execute("EXEC INFO_DOC_ACTA_DESP_VENTA ?", docentry)
            columnas = [col[0] for col in conn.cursor.description]
            registros = [dict(zip(columnas, row)) for row in conn.cursor.fetchall()]
            logger.info(f"✅ {len(registros)} registros obtenidos para acta despacho venta {docentry}")
            return registros
    except Exception as e:
        logger.error(f"❌ Error en obtener_info_acta_despacho_venta({docentry}): {e}")
        logger.debug(traceback.format_exc())
        return []

# --------------------------------------------------------
# RECEPCION (ACTA RECEPCION TS)
# --------------------------------------------------------
def obtener_docentries_acta_recepcion_ts(fecha: str):
    try:
        with ConexionSQL() as conn:
            if not conn.valida_conexion():
                logger.error("❌ Conexión SQL no válida en obtener_docentries_acta_recepcion_ts()")
                return []
            logger.info(f"📦 Ejecutando: EXEC LISTADO_DOC_ACTA_RECEP_TS '{fecha}'")
            conn.cursor.execute("EXEC LISTADO_DOC_ACTA_RECEP_TS ?", fecha)
            resultados = [row[0] for row in conn.cursor.fetchall()]
            logger.info(f"✅ {len(resultados)} DocEntries encontrados para acta recepción TS")
            return resultados
    except Exception as e:
        logger.error(f"❌ Error en obtener_docentries_acta_recepcion_ts({fecha}): {e}")
        logger.debug(traceback.format_exc())
        return []

def obtener_info_acta_recepcion_ts(docentry: int):
    try:
        with ConexionSQL() as conn:
            if not conn.valida_conexion():
                logger.error("❌ Conexión SQL no válida en obtener_info_acta_recepcion_ts()")
                return []
            logger.info(f"📦 Ejecutando: EXEC INFO_DOC_ACTA_RECEP_TS {docentry}")
            conn.cursor.execute("EXEC INFO_DOC_ACTA_RECEP_TS ?", docentry)
            columnas = [col[0] for col in conn.cursor.description]
            registros = [dict(zip(columnas, row)) for row in conn.cursor.fetchall()]
            logger.info(f"✅ {len(registros)} registros obtenidos para acta recepción TS {docentry}")
            return registros
    except Exception as e:
        logger.error(f"❌ Error en obtener_info_acta_recepcion_ts({docentry}): {e}")
        logger.debug(traceback.format_exc())
        return []

# --------------------------------------------------------
# ORGANOLEPTICO (ACTA ORGANOLEPTICO TS)
# --------------------------------------------------------
def obtener_docentries_organo_lep_ts(fecha: str):
    try:
        with ConexionSQL() as conn:
            if not conn.valida_conexion():
                logger.error("❌ Conexión SQL no válida en obtener_docentries_organo_lep_ts()")
                return []
            logger.info(f"📦 Ejecutando: EXEC LISTADO_DOC_ORGA_TS '{fecha}'")
            conn.cursor.execute("EXEC LISTADO_DOC_ORGA_TS ?", fecha)
            resultados = [row[0] for row in conn.cursor.fetchall()]
            logger.info(f"✅ {len(resultados)} DocEntries encontrados para acta organoleptico TS")
            return resultados
    except Exception as e:
        logger.error(f"❌ Error en obtener_docentries_organo_lep_ts({fecha}): {e}")
        logger.debug(traceback.format_exc())
        return []

def obtener_info_organo_lep_ts(docentry: int):
    try:
        with ConexionSQL() as conn:
            if not conn.valida_conexion():
                logger.error("❌ Conexión SQL no válida en obtener_info_organo_lep_ts()")
                return []
            logger.info(f"📦 Ejecutando: EXEC INFO_DOC_ORGANO_LEP_TS {docentry}")
            conn.cursor.execute("EXEC INFO_DOC_ORGANO_LEP_TS ?", docentry)
            columnas = [col[0] for col in conn.cursor.description]
            registros = [dict(zip(columnas, row)) for row in conn.cursor.fetchall()]
            logger.info(f"✅ {len(registros)} registros obtenidos para acta organoleptico TS {docentry}")
            return registros
    except Exception as e:
        logger.error(f"❌ Error en obtener_info_organo_lep_ts({docentry}): {e}")
        logger.debug(traceback.format_exc())
        return []

# --------------------------------------------------------
# ENTREGA VENTA
# --------------------------------------------------------
def obtener_docentries_entrega(fecha: str):
    try:
        with ConexionSQL() as conn:
            if not conn.valida_conexion():
                logger.error("❌ Conexión SQL no válida en obtener_docentries_entrega()")
                return []
            logger.info(f"📦 Ejecutando: EXEC LISTADO_DOC_ENTREGA_VENTA '{fecha}'")
            conn.cursor.execute("EXEC LISTADO_DOC_ENTREGA_VENTA ?", fecha)
            resultados = [row[0] for row in conn.cursor.fetchall()]
            logger.info(f"✅ {len(resultados)} DocEntries encontrados para entrega")
            return resultados
    except Exception as e:
        logger.error(f"❌ Error en obtener_docentries_entrega({fecha}): {e}")
        logger.debug(traceback.format_exc())
        return []

def obtener_info_entrega(docentry: int):
    try:
        with ConexionSQL() as conn:
            if not conn.valida_conexion():
                logger.error("❌ Conexión SQL no válida en obtener_info_entrega()")
                return []
            logger.info(f"📦 Ejecutando: EXEC INFO_DOC_ENTREGA_VENTA {docentry}")
            conn.cursor.execute("EXEC INFO_DOC_ENTREGA_VENTA ?", docentry)
            columnas = [col[0] for col in conn.cursor.description]
            registros = [dict(zip(columnas, row)) for row in conn.cursor.fetchall()]
            logger.info(f"✅ {len(registros)} registros obtenidos para entrega {docentry}")
            return registros
    except Exception as e:
        logger.error(f"❌ Error en obtener_info_entrega({docentry}): {e}")
        logger.debug(traceback.format_exc())
        return []

# --------------------------------------------------------
# TRASLADO
# --------------------------------------------------------
def obtener_docentries_traslado(fecha: str):
    try:
        with ConexionSQL() as conn:
            if not conn.valida_conexion():
                logger.error("❌ Conexión SQL no válida en obtener_docentries_traslado()")
                return []
            logger.info(f"📦 Ejecutando: EXEC LISTADO_DOC_TRASLADO '{fecha}'")
            conn.cursor.execute("EXEC LISTADO_DOC_TRASLADO ?", fecha)
            resultados = [row[0] for row in conn.cursor.fetchall()]
            logger.info(f"✅ {len(resultados)} DocEntries encontrados para traslado")
            return resultados
    except Exception as e:
        logger.error(f"❌ Error en obtener_docentries_traslado({fecha}): {e}")
        logger.debug(traceback.format_exc())
        return []

def obtener_info_traslado(docentry: int):
    try:
        with ConexionSQL() as conn:
            if not conn.valida_conexion():
                logger.error("❌ Conexión SQL no válida en obtener_info_traslado()")
                return []
            logger.info(f"📦 Ejecutando: EXEC INFO_DOC_TRASLADO {docentry}")
            conn.cursor.execute("EXEC INFO_DOC_TRASLADO ?", docentry)
            columnas = [col[0] for col in conn.cursor.description]
            registros = [dict(zip(columnas, row)) for row in conn.cursor.fetchall()]
            logger.info(f"✅ {len(registros)} registros obtenidos para traslado {docentry}")
            return registros
    except Exception as e:
        logger.error(f"❌ Error en obtener_info_traslado({docentry}): {e}")
        logger.debug(traceback.format_exc())
        return []
