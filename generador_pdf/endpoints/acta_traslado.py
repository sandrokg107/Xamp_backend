import logging
import traceback
import os
import shutil
import time
import zipfile
import uuid  # <--- NECESARIO PARA LOS IDs
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import date, datetime
from Conexion.conexion_sql import ConexionSQL

# Importamos la función generadora específica de Traslados
from generador_pdf.pdf_generator import generar_pdf_acta_traslado

router = APIRouter()

# ==========================================
# CONFIGURACION DE LOGS
# ==========================================
LOG_DIR = "Logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "pdf_traslados.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger(__name__)

# --- MEMORIA RAM PARA EL PROGRESO ---
actividades_progreso = {}

class PDFTrasladosRequest(BaseModel):
    fecha: date
    firma: str
    almacen_id: str

# ==========================================
# 🛠️ TAREA EN SEGUNDO PLANO (WORKER)
# ==========================================
def proceso_generar_pdf_traslados_background(task_id: str, data: PDFTrasladosRequest):
    try:
        # 1. Configuración Inicial (0% - 10%)
        actividades_progreso[task_id] = {"porcentaje": 5, "mensaje": "Preparando entorno...", "listo": False}
        
        timestamp = int(time.time())
        nombre_unico = f"Lote_Traslados_{timestamp}_{task_id}"
        
        base_temp = os.path.join(os.getcwd(), "Temp_Downloads")
        carpeta_trabajo = os.path.join(base_temp, nombre_unico)
        carpeta_pdfs = os.path.join(carpeta_trabajo, "PDFs")
        os.makedirs(carpeta_pdfs, exist_ok=True)

        fecha_str_log = data.fecha.strftime("%Y-%m-%d")
        
        # 2. Consultar Base de Datos (10% - 15%)
        actividades_progreso[task_id].update({"porcentaje": 10, "mensaje": "Consultando SQL..."})
        
        with ConexionSQL() as conn:
            cursor = conn.cursor
            # SP ESPECÍFICO DE TRASLADOS
            sp_listado = "{CALL LISTADO_DOC_DESPACHO_TRASLADOS (?,?)}"
            cursor.execute(sp_listado, (fecha_str_log, data.almacen_id))
            docentries = [row[0] for row in cursor.fetchall()]

        # --- ALERTA AZUL (Si no hay datos) ---
        if not docentries:
            actividades_progreso[task_id] = {
                "porcentaje": 0, 
                "error": "No se encontraron registros de traslado para esta fecha.", 
                "listo": True
            }
            shutil.rmtree(carpeta_trabajo, ignore_errors=True)
            return

        total_docs = len(docentries)
        archivos_para_zip = []

        # 3. Bucle de Generación (15% - 90%)
        for index, docentry in enumerate(docentries):
            
            # --- CÁLCULO DE PROGRESO REAL ---
            progreso_actual = 15 + int((index / total_docs) * 75)
            mensaje = f"Procesando traslado {index + 1} de {total_docs}..."
            actividades_progreso[task_id].update({"porcentaje": progreso_actual, "mensaje": mensaje})

            try:
                with ConexionSQL() as conn:
                    cursor = conn.cursor
                    # SP DETALLE TRASLADOS
                    cursor.execute("EXEC INFO_DOC_DESPACHO_TRASLADOS ?", docentry)
                    if cursor.description is None: continue
                    columnas = [col[0] for col in cursor.description]
                    registros = [dict(zip(columnas, row)) for row in cursor.fetchall()]

                if not registros: continue

                encabezado = registros[0]
                productos = registros[0:]

                # --- Formateo específico de Traslados ---
                productos_formateados = []
                for item in productos:
                    def safe(val):
                        if val is None or str(val).strip().lower() == "none": return ""
                        return str(val)

                    try:
                        anio = item.get("Anio")
                        if anio: anio = str(int(anio) + 2000)
                        fecha_vcto = f"{safe(item.get('Dia')).zfill(2)}/{safe(item.get('Mes')).zfill(2)}/{anio}"
                    except: fecha_vcto = "N/A"

                    # Descripción con NombreComercial (Propio de Traslados)
                    descripcion = " ".join([
                        safe(item.get("NombreComercial")), safe(item.get("Concentracion")),
                        safe(item.get("FormaFarmaceutica")), safe(item.get("FormaPresentacion")),
                    ]).strip()

                    productos_formateados.append({
                        "cantidad": safe(item.get("CantidadLote", 0)), # Campo específico
                        "descripcion": descripcion,
                        "lote": safe(item.get("NroLote")),
                        "vencimiento": fecha_vcto,
                        "rs": safe(item.get("RegistroSanit")),
                        "condicion": safe(item.get("CondicionAlm")),
                    })

                # --- Data PDF ---
                fecha_str_pdf = data.fecha.strftime("%d-%m-%Y")
                data_pdf = {
                    "fecha": fecha_str_pdf,
                    "docdate": str(encabezado.get("DocDate", "")), # Simplificado
                    "guia": encabezado.get("NroGuia"),      
                    "AlmOrigen": encabezado.get("AlmOrigen"),   
                    "AlmDestino": encabezado.get("AlmDestino"), 
                    "productos": productos_formateados,
                    "firma": data.firma,
                }

                # Generar PDF
                ruta_original = generar_pdf_acta_traslado(data_pdf)

                if os.path.exists(ruta_original):
                    nombre_archivo = os.path.basename(ruta_original)
                    ruta_destino_zip = os.path.join(carpeta_pdfs, nombre_archivo)
                    shutil.copy2(ruta_original, ruta_destino_zip)
                    archivos_para_zip.append(ruta_destino_zip)

            except Exception as e:
                logger.error(f"Error en doc {docentry}: {e}")

        # 4. Compresión y Finalización (90% - 100%)
        if not archivos_para_zip:
            actividades_progreso[task_id] = {"error": "No se generaron PDFs válidos", "listo": True}
            return

        actividades_progreso[task_id].update({"porcentaje": 95, "mensaje": "Comprimiendo ZIP..."})
        
        nombre_zip = f"Actas_Traslados_{fecha_str_log}.zip"
        ruta_zip_final = os.path.join(carpeta_trabajo, nombre_zip)

        with zipfile.ZipFile(ruta_zip_final, "w") as zipf:
            for archivo in archivos_para_zip:
                zipf.write(archivo, arcname=os.path.basename(archivo))

        actividades_progreso[task_id].update({
            "porcentaje": 100, 
            "mensaje": "Descarga lista",
            "archivo": ruta_zip_final,
            "carpeta": carpeta_trabajo,
            "listo": True
        })

    except Exception as e:
        logger.critical(f"Error fatal thread: {e}")
        actividades_progreso[task_id] = {"error": str(e), "listo": True}


# ==========================================
# 🚀 ENDPOINTS ASÍNCRONOS (SISTEMA DE COLA)
# ==========================================

@router.post("/iniciar_generacion_pdf_traslados/")
def iniciar_generacion(data: PDFTrasladosRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    background_tasks.add_task(proceso_generar_pdf_traslados_background, task_id, data)
    return {"task_id": task_id}

@router.get("/progreso_traslados/{task_id}")
def consultar_progreso(task_id: str):
    return actividades_progreso.get(task_id, {"error": "Tarea no encontrada"})

@router.get("/descargar_traslados/{task_id}")
def descargar_resultado(task_id: str, background_tasks: BackgroundTasks):
    info = actividades_progreso.get(task_id)
    if not info or not info.get("listo") or not info.get("archivo"):
        raise HTTPException(status_code=400, detail="Archivo no listo")
    
    def limpiar():
        try:
            time.sleep(5)
            shutil.rmtree(info["carpeta"])
            del actividades_progreso[task_id]
        except: pass
    
    background_tasks.add_task(limpiar)
    return FileResponse(path=info["archivo"], media_type="application/zip", filename=os.path.basename(info["archivo"]))


# --- Endpoint de Verificación (Se mantiene igual, solo correcciones menores) ---
@router.get("/verificar_migracion/")
def verificar_migracion(fecha: str, grupo: str, almacen_id: str):
    try:
        if grupo.lower() != "traslados": pass 
        
        with ConexionSQL() as conn:
            cursor = conn.cursor
            # Consulta a tabla OWTR
            query = """
            SELECT COUNT(*) FROM OWTR 
            WHERE CONVERT(varchar(10), U_BPP_FECINITRA, 120) = ? AND ToWhsCode = ? AND Canceled = 'N'
            """
            cursor.execute(query, (fecha, almacen_id))
            migrado = cursor.fetchone()[0] > 0
            
            return {"migrado": migrado, "mensaje": "Verificado"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))