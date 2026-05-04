import logging
import traceback
import os
import shutil
import time
import zipfile
import uuid  # <--- IMPORTANTE: Necesario para generar IDs de tarea
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import date, datetime
from Conexion.conexion_sql import ConexionSQL
from generador_pdf.pdf_generator import generar_pdf_acta_ventas

router = APIRouter()

# ==========================================
# CONFIGURACIÓN DE LOGS
# ==========================================
LOG_DIR = "Logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "pdf_ventas.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger(__name__)

# --- VARIABLE EN MEMORIA PARA EL PROGRESO ---
actividades_progreso = {}

class PDFVentasRequest(BaseModel):
    fecha: date
    firma: str       # Firma del empleado (seleccionada en Front)
    almacen_id: str  # ID del almacén

# ==========================================
# 🛠️ TAREA EN SEGUNDO PLANO (WORKER)
# ==========================================
def proceso_generar_pdf_background(task_id: str, data: PDFVentasRequest):
    try:
        # 1. Inicio
        actividades_progreso[task_id] = {"porcentaje": 5, "mensaje": "Iniciando configuración...", "listo": False}
        
        timestamp = int(time.time())
        nombre_unico = f"Lote_Ventas_{timestamp}_{task_id}"
        
        base_temp = os.path.join(os.getcwd(), "Temp_Downloads")
        carpeta_trabajo = os.path.join(base_temp, nombre_unico)
        carpeta_pdfs = os.path.join(carpeta_trabajo, "PDFs")
        os.makedirs(carpeta_pdfs, exist_ok=True)

        fecha_str_log = data.fecha.strftime("%Y-%m-%d")
        
        # 2. Lógica SQL
        actividades_progreso[task_id].update({"porcentaje": 10, "mensaje": "Consultando base de datos..."})
        
        with ConexionSQL() as conn:
            cursor = conn.cursor
            sp_name = "{CALL LISTADO_DOC_ENTREGA_VENTA (?, ?)}"
            cursor.execute(sp_name, (fecha_str_log, data.almacen_id))
            docentries = [row[0] for row in cursor.fetchall()]

        # --- AQUÍ LA MAGIA PARA LA ALERTA AZUL ---
        if not docentries:
            # Enviamos este mensaje exacto para que el Front sepa que es una alerta informativa
            actividades_progreso[task_id] = {
                "porcentaje": 0, 
                "error": "No hay datos para esta fecha", 
                "listo": True
            }
            # Limpiamos carpeta vacía
            shutil.rmtree(carpeta_trabajo, ignore_errors=True)
            return

        total_docs = len(docentries)
        archivos_para_zip = []

        # 3. Bucle de Generación
        for index, docentry in enumerate(docentries):
            # Calculamos porcentaje real (del 15% al 90%)
            progreso_actual = 15 + int((index / total_docs) * 75)
            mensaje = f"Procesando doc {index + 1} de {total_docs}..."
            
            actividades_progreso[task_id].update({"porcentaje": progreso_actual, "mensaje": mensaje})

            try:
                with ConexionSQL() as conn:
                    cursor = conn.cursor
                    cursor.execute("EXEC INFO_DOC_ENTREGA_VENTA ?", docentry)
                    if cursor.description is None: continue
                    columnas = [col[0] for col in cursor.description]
                    registros = [dict(zip(columnas, row)) for row in cursor.fetchall()]

                if not registros: continue

                # ---------------------------------------------------------
                # ✅ CORRECCIÓN DE LÓGICA DE FIRMAS
                # ---------------------------------------------------------
                # A. El ENCARGADO es quien seleccionaste en el Front
                firma_jefe = data.firma 

                # B. El CLIENTE (Receptor) firma en físico -> Vacío
                firma_receptor = "" 

                encabezado = registros[0]
                productos = registros[0:]
                
                # --- Formateo de Productos (Tu lógica original) ---
                productos_formateados = []
                for item in productos:
                    def safe(val):
                        if val is None or str(val).strip().lower() == "none": return ""
                        return str(val)
                    
                    # (Tu lógica de fechas de vencimiento simplificada aquí)
                    try:
                        anio = item.get("Anio")
                        if anio: anio = str(int(anio) + 2000)
                        fecha_vcto = f"{safe(item.get('Dia')).zfill(2)}/{safe(item.get('Mes')).zfill(2)}/{anio}"
                    except: fecha_vcto = ""

                    descripcion = " ".join([
                        safe(item.get("FrgnName")), safe(item.get("Concentracion")),
                        safe(item.get("FormaFarmaceutica")), safe(item.get("FormaPresentacion"))
                    ]).strip()

                    productos_formateados.append({
                        "cantidad": safe(item.get("Quantity", 0)),
                        "descripcion": descripcion,
                        "lote": safe(item.get("DistNumber")),
                        "vencimiento": fecha_vcto,
                        "rs": safe(item.get("MnfSerial")),
                        "condicion": safe(item.get("CondicionAlm")),
                    })

                # --- Data PDF ---
                data_pdf = {
                    "fecha": data.fecha.strftime("%d-%m-%Y"),
                    "docdate": str(encabezado.get("U_BPP_FECINITRA", "")),
                    "factura": encabezado.get("NRO FACTURA", ""),
                    "cliente": encabezado.get("CardName", ""),
                    "productos": productos_formateados,
                    
                    "firma_encargado": firma_jefe,    # <--- USA LA DEL FRONT
                    "firma": firma_receptor,          # <--- VACÍA (CLIENTE)
                    
                    "numCard": encabezado.get("NumAtCard"),
                }

                ruta_original = generar_pdf_acta_ventas(data_pdf)

                if os.path.exists(ruta_original):
                    nombre_archivo = os.path.basename(ruta_original)
                    ruta_destino = os.path.join(carpeta_pdfs, nombre_archivo)
                    shutil.copy2(ruta_original, ruta_destino)
                    archivos_para_zip.append(ruta_destino)

            except Exception as inner_e:
                logger.error(f"Error en doc {docentry}: {inner_e}")

        # 4. Compresión
        if not archivos_para_zip:
             actividades_progreso[task_id] = {"error": "No se generaron PDFs válidos", "listo": True}
             return

        actividades_progreso[task_id].update({"porcentaje": 95, "mensaje": "Comprimiendo ZIP..."})
        
        nombre_zip = f"Actas_Ventas_{fecha_str_log}.zip"
        ruta_zip_final = os.path.join(carpeta_trabajo, nombre_zip)

        with zipfile.ZipFile(ruta_zip_final, "w") as zipf:
            for archivo in archivos_para_zip:
                zipf.write(archivo, arcname=os.path.basename(archivo))

        # 5. Finalizar
        actividades_progreso[task_id].update({
            "porcentaje": 100, 
            "mensaje": "Descarga lista", 
            "archivo": ruta_zip_final,
            "carpeta": carpeta_trabajo,
            "listo": True
        })

    except Exception as e:
        logger.critical(f"Error fatal: {e}")
        actividades_progreso[task_id] = {"error": str(e), "listo": True}


# ==========================================
# 🚀 NUEVOS ENDPOINTS (Sistema de Cola)
# ==========================================

@router.post("/iniciar_generacion_pdf/")
def iniciar_generacion(data: PDFVentasRequest, background_tasks: BackgroundTasks):
    # Generamos un ID único para esta petición
    task_id = str(uuid.uuid4())
    # Lanzamos el proceso en segundo plano (Background)
    background_tasks.add_task(proceso_generar_pdf_background, task_id, data)
    return {"task_id": task_id}

@router.get("/progreso_pdf/{task_id}")
def consultar_progreso(task_id: str):
    # El Frontend consulta esto cada segundo
    return actividades_progreso.get(task_id, {"error": "Tarea no encontrada"})

@router.get("/descargar_resultado/{task_id}")
def descargar_resultado(task_id: str, background_tasks: BackgroundTasks):
    info = actividades_progreso.get(task_id)
    if not info or not info.get("listo") or not info.get("archivo"):
        raise HTTPException(status_code=400, detail="Archivo no listo")
    
    # Función de limpieza post-descarga
    def limpiar():
        try:
            time.sleep(5) # Esperar a que termine la descarga
            shutil.rmtree(info["carpeta"])
            del actividades_progreso[task_id] # Borrar de memoria RAM
        except: pass
    
    background_tasks.add_task(limpiar)
    
    return FileResponse(
        path=info["archivo"], 
        media_type="application/zip", 
        filename=os.path.basename(info["archivo"])
    )


# --- Endpoint existente (sin cambios) ---
@router.get("/verificar_migracion/")
def verificar_migracion(fecha: str, grupo: str, almacen_id: str):
    # ... (Tu código de verificación original se mantiene igual) ...
    # Simplemente pégalo aquí abajo tal cual lo tenías.
    try:
        if grupo.lower() != "ventas": pass 
        with ConexionSQL() as conn:
            cursor = conn.cursor
            query = "SELECT COUNT(*) FROM ODLN WHERE CONVERT(date, U_BPP_FECINITRA) = ? AND U_COB_LUGAREN = ?"
            cursor.execute(query, (fecha, almacen_id))
            migrado = cursor.fetchone()[0] > 0
            mensaje = f"Datos {'ya migrados' if migrado else 'no migrados'} para {fecha}"
            return {"migrado": migrado, "mensaje": mensaje}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))