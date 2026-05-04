import logging
import traceback
import os
import shutil
import time
import zipfile
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import date, datetime
from Conexion.conexion_sql import ConexionSQL

# Importar la función generadora específica
from generador_pdf.pdf_generator import generar_pdf_acta_organoleptico

router = APIRouter()

# ==========================================
# CONFIGURACION DE LOGS
# ==========================================
LOG_DIR = "Logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "pdf_organoleptico.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger(__name__)


class PDFOrganolepticoRequest(BaseModel):
    fecha: date
    firma: str
    almacen_id: str


# --- FUNCION UTILITARIA PARA NOMBRE FIRMA ---
def limpiar_nombre_firma(firma: str) -> str:
    """
    Convierte 'FirmaAlfredoRoldanEsparraga.png' en 'Alfredo Roldan Esparraga'
    """
    if not firma:
        return ""
    nombre = firma.replace("Firma", "").replace(".png", "")
    # Insertar espacios antes de mayúsculas (excepto la primera letra)
    nombre = "".join([" " + c if c.isupper() and i != 0 else c for i, c in enumerate(nombre)])
    return nombre.strip()


# --- FUNCION DE LIMPIEZA DE TEMPORALES ---
def borrar_archivos_temporales(ruta_carpeta):
    try:
        time.sleep(2)
        if os.path.exists(ruta_carpeta):
            shutil.rmtree(ruta_carpeta)
            logger.info(f"Carpeta temporal eliminada: {ruta_carpeta}")
    except Exception as e:
        logger.warning(f"No se pudo eliminar la carpeta {ruta_carpeta}: {e}")


# --- ENDPOINT PRINCIPAL (ORGANOLEPTICO) ---
@router.post("/generar_pdf_organoleptico/")
def generar_pdf_organoleptico(data: PDFOrganolepticoRequest, background_tasks: BackgroundTasks):

    # 1. Preparar Carpetas Temporales
    timestamp = int(time.time())
    nombre_unico = f"Lote_Organo_{timestamp}"
    
    base_temp = os.path.join(os.getcwd(), "Temp_Downloads")
    carpeta_trabajo = os.path.join(base_temp, nombre_unico)
    carpeta_pdfs = os.path.join(carpeta_trabajo, "PDFs")

    os.makedirs(carpeta_pdfs, exist_ok=True)

    fecha_str_log = data.fecha.strftime("%Y-%m-%d")
    logger.info(f"Iniciando proceso masivo ZIP (Organoleptico) para fecha: {fecha_str_log}")

    try:
        # 2. LOGICA SQL
        with ConexionSQL() as conn:
            cursor = conn.cursor
            sp_listado = "{CALL LISTADO_DOC_ORGA_TS (?, ?)}"
            logger.info(f"Ejecutando SP: {sp_listado} con {fecha_str_log} y {data.almacen_id}")

            cursor.execute(sp_listado, (fecha_str_log, data.almacen_id))
            rows = cursor.fetchall()
            docentries = [row[0] for row in rows]
            logger.info(f"DocEntries encontrados: {docentries}")

        if not docentries:
            raise HTTPException(
                status_code=404, detail="No se encontraron registros organolepticos para esta fecha."
            )

        archivos_para_zip = []

        # 3. BUCLE DE GENERACION
        for docentry in docentries:
            with ConexionSQL() as conn:
                cursor = conn.cursor
                logger.info(f"Obteniendo datos para DocEntry {docentry}")
                cursor.execute("EXEC INFO_DOC_ORGANO_LEP_TS ?", docentry)

                if cursor.description is None:
                    continue

                columnas = [col[0] for col in cursor.description]
                registros = [dict(zip(columnas, row)) for row in cursor.fetchall()]

            if not registros:
                logger.warning(f"DocEntry {docentry} no tiene registros. Saltando.")
                continue

            encabezado = registros[0]
            productos = registros[0:]

            logger.info(f"Generando PDF DocEntry {docentry} | Guia: {encabezado.get('NroDeGuia')}")

            # --- Formateo de productos ---
            productos_formateados = []
            for item in productos:
                def safe(val):
                    if val is None or str(val).strip().lower() == 'none':
                        return ""
                    return str(val)

                try:
                    dia = safe(item.get('Dia'))
                    mes = safe(item.get('Mes'))
                    anio = item.get('Anio')
                    if anio is not None and anio != "":
                        anio = str(int(anio) + 2000)
                    else:
                        anio = ""
                    fecha_vcto = f"{dia.zfill(2)}/{mes.zfill(2)}/{anio}"
                except Exception:
                    fecha_vcto = "N/A"

                # Descripcion concatenada
                descripcion = " ".join([
                    safe(item.get('Nombre')).strip(),
                    safe(item.get('Concentracion')).strip(),
                    safe(item.get('FormaPresentacion')).strip(),
                    safe(item.get('FormaFarmaceutica')).strip()
                ]).strip()

                # Nombre producto especifico (A veces difiere de descripcion en logica de negocio)
                nombre_producto = " ".join([
                    safe(item.get('Nombre')).strip(),
                    safe(item.get('Concentracion')).strip(),
                    safe(item.get('FormaPresentacion')).strip()
                ]).strip()

                productos_formateados.append({
                    "cantidad": safe(item.get("Quantity", 0)),
                    "descripcion": descripcion,
                    "lote": safe(item.get("Lote")),
                    "vencimiento": fecha_vcto,
                    "rs": safe(item.get("RegistroSan")),
                    "condicion": safe(item.get("CondAlmac")),
                    "nombre_producto": nombre_producto,
                    "fabricante": safe(item.get("Fabricante")),
                    "presentacion": safe(item.get("FormaFarmaceutica", "")),
                })

            # --- Formateo de fechas ---
            fecha_str_pdf = data.fecha.strftime("%d-%m-%Y")
            docdate_val = encabezado.get("DocDate")
            if docdate_val:
                try:
                    if hasattr(docdate_val, 'strftime'):
                        docdate_str = docdate_val.strftime("%d-%m-%Y")
                    else:
                        docdate_str = datetime.strptime(str(docdate_val)[:10], "%Y-%m-%d").strftime("%d-%m-%Y")
                except Exception:
                    docdate_str = str(docdate_val)
            else:
                docdate_str = ""

            # --- Logica especifica Organoleptico (Primer producto) ---
            # El formato organoleptico suele ser de un solo producto/lote principal
            primer_producto = productos_formateados[0] if productos_formateados else {}

            # Limpiar nombre de firma para mostrar en texto
            firma_limpia = limpiar_nombre_firma(data.firma)

            data_pdf = {
                "fecha": fecha_str_pdf,
                "docdate": docdate_str,
                "guia": encabezado.get("NroDeGuia", ""),
                "almacen": encabezado.get("Almacen", ""),
                "descripcion": encabezado.get("NombreProd", ""), # A veces viene del header
                "nombre_producto": primer_producto.get("nombre_producto", ""),
                "cantidad": primer_producto.get("cantidad", ""),
                "lote": primer_producto.get("Lote", ""),
                "rs": primer_producto.get("rs", ""),
                "fabricante": primer_producto.get("fabricante", ""),
                "condicion": primer_producto.get("condicion", ""),
                "fecha_vencimiento": primer_producto.get("vencimiento", ""),
                "presentacion": primer_producto.get("presentacion", ""),
                "firma": data.firma,           # Nombre archivo imagen
                "nombre_firma": firma_limpia,  # Nombre texto legible
                "productos": productos_formateados,
            }

            try:
                # 4. Generar PDF
                ruta_original = generar_pdf_acta_organoleptico(data_pdf)

                # Copiar a carpeta temporal para el ZIP
                if os.path.exists(ruta_original):
                    nombre_archivo = os.path.basename(ruta_original)
                    ruta_destino_zip = os.path.join(carpeta_pdfs, nombre_archivo)
                    shutil.copy2(ruta_original, ruta_destino_zip)
                    archivos_para_zip.append(ruta_destino_zip)
                    logger.info(f"PDF agregado al lote: {nombre_archivo}")
                else:
                    logger.error(f"El archivo generado no existe: {ruta_original}")

            except Exception as pdf_error:
                logger.error(f"Error generando PDF DocEntry {docentry}: {pdf_error}")
                logger.debug(traceback.format_exc())

        # 5. CREAR ZIP FINAL
        if not archivos_para_zip:
            raise HTTPException(
                status_code=500, detail="No se genero ningun PDF valido."
            )

        nombre_zip = f"Actas_Organoleptico_{fecha_str_log}.zip"
        ruta_zip_final = os.path.join(carpeta_trabajo, nombre_zip)

        logger.info(f"Comprimiendo {len(archivos_para_zip)} archivos...")
        with zipfile.ZipFile(ruta_zip_final, "w") as zipf:
            for archivo in archivos_para_zip:
                zipf.write(archivo, arcname=os.path.basename(archivo))

        # 6. ENVIAR Y LIMPIAR
        background_tasks.add_task(borrar_archivos_temporales, carpeta_trabajo)

        logger.info("Enviando ZIP al cliente...")
        return FileResponse(
            path=ruta_zip_final, filename=nombre_zip, media_type="application/zip"
        )

    except Exception as e:
        borrar_archivos_temporales(carpeta_trabajo)
        logger.critical(f"Error critico en Organoleptico: {e}")
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# --- VERIFICACION MIGRACION ---
@router.get("/verificar_migracion/")
def verificar_migracion(fecha: str, grupo: str):
    logger.info(f"Verificando migracion Organoleptico: {fecha}, grupo: {grupo}")
    try:
        # Validacion grupo
        if grupo.lower() != "organoleptico":
             pass 

        with ConexionSQL() as conn:
            cursor = conn.cursor
            # ATENCION: Verifica la tabla correcta. Si es calidad, quizas no sea OWTR.
            # Se mantiene OWTR por consistencia con tu codigo anterior, pero revisalo.
            query = """
            SELECT COUNT(*) 
            FROM OWTR 
            WHERE CONVERT(varchar(10), U_BPP_FECINITRA, 120) = ?
            """
            cursor.execute(query, fecha)
            count = cursor.fetchone()[0]
            migrado = count > 0
            
            mensaje = f"Datos {'ya migrados' if migrado else 'no migrados'} para {fecha}"
            logger.info(f"Resultado: {mensaje}")
            return {"migrado": migrado, "mensaje": mensaje}
            
    except Exception as e:
        logger.error(f"Error verificando: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")