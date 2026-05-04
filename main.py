import logging
import time
import traceback
import os
import sys
import asyncio
from datetime import date

from fastapi import FastAPI, Body, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pydantic import BaseModel
from dotenv import load_dotenv

# Módulos locales
from Migrador.migrador import Migrador
from Migrador.migrador_traslado import MigradorTraslados
from Migrador.migrador_ventas import MigradorVentas
from Migrador.migrado_despacho_1_y_5 import MigradorDespacho
from Migrador.migrador_recepcion import MigradorRecepcion
from Migrador.migrador_organoleptico import MigradorOrganoleptico

from generador_pdf.endpoints import (
    acta_ventas,
    acta_traslado,
    acta_despacho,
    acta_recepcion,
    acta_organoleptico,
)

# Configuración de entorno
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, '.env')

if os.name == 'nt':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

print("Iniciando servicio")
if os.path.exists(env_path):
    print(f"Cargando variables desde: {env_path}")
    load_dotenv(env_path, override=True)
else:
    print(f"Advertencia: no se encontró el archivo .env en {env_path}")

print(f"SQL_SERVER configurado: {os.getenv('SQL_SERVER', 'NO DETECTADO')}")

# Logging
if not os.path.exists('logs'):
    os.makedirs('logs')

LOG_FILE = "logs/migracion.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# App FastAPI
app = FastAPI(title="API de Migración y Generación de PDFs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Archivos estáticos
static_path = os.path.join("generador_pdf", "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")
else:
    logger.warning(f"La carpeta estática no existe: {static_path}")

# Manejo 422
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        body = await request.body()
        body_str = body.decode('utf-8')
    except:
        body_str = "No se pudo leer el cuerpo"

    logger.error(
        f"Error de Validación 422 en {request.url}. Body recibido: {body_str}. Errores: {exc.errors()}"
    )

    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body_received": body_str},
    )

# Modelos
class MigracionRequest(BaseModel):
    fecha: date
    tabla: str = "*"

class MigracionTrasladoRequest(BaseModel):
    fecha: date
    almacen_id: str = "*"

class MigracionVentasRequest(BaseModel):
    fecha: date
    almacen_id: str = "*"

class MigracionDespachoRequest(BaseModel):
    fecha: date
    almacen_id: str = "*"

class MigracionOrganolepticoRequest(BaseModel):
    fecha: date
    almacen_id: str = "*"

class MigracionRecepcionRequest(BaseModel):
    fecha: date
    almacen_id: str = "*"

# Endpoints
@app.post("/")
def root():
    return {"mensaje": "API Migrador funcionando correctamente"}

@app.post("/api/importar/")
async def importar_data(request: MigracionRequest = Body(...)):
    fecha_str = request.fecha.isoformat()
    logger.info(f"Migración: fecha={fecha_str}, tabla={request.tabla}")

    try:
        migrador = Migrador(fecha_str=fecha_str)

        tablas = ([
            "OITM", "OWHS", "OWTR", "WTR1", "OITL", "ODLN",
            "OINV", "OBTW", "OBTN", "ITL1", "DLN1", "INV1", "IBT1"
        ] if request.tabla == "*" else [request.tabla])

        resultados = {}

        for tabla in tablas:
            logger.info(f"Iniciando migración de {tabla}")
            inicio = time.perf_counter()

            try:
                resultado = migrador.migrar_tabla(tabla)
                duracion = round(time.perf_counter() - inicio, 2)
                resultados[tabla] = {
                    "status": "ok",
                    "mensaje": resultado,
                    "tiempo": duracion
                }

            except Exception as e:
                duracion = round(time.perf_counter() - inicio, 2)
                resultados[tabla] = {
                    "status": "error",
                    "mensaje": str(e),
                    "tiempo": duracion
                }
                logger.error(f"Error migrando {tabla}: {e}")

        return {"status": "success", "fecha": fecha_str, "resultados": resultados}

    except Exception as e:
        logger.critical(f"Error inesperado en importar_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/importar_traslados/")
async def importar_traslados(request: MigracionTrasladoRequest = Body(...)):
    try:
        migrador = MigradorTraslados(request.fecha, request.almacen_id)
        resultados = migrador.migrar_todas()
        return {"status": "success", "fecha": str(request.fecha), "resultados": resultados}
    except Exception as e:
        logger.critical(f"Error inesperado en traslados: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/importar_ventas/")
async def importar_ventas(request: MigracionVentasRequest = Body(...)):
    try:
        migrador = MigradorVentas(request.fecha, request.almacen_id)
        resultados = migrador.migrar_todas()
        return {"status": "success", "fecha": str(request.fecha), "resultados": resultados}
    except Exception as e:
        logger.critical(f"Error inesperado en ventas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/importar_despacho/")
async def importar_despacho(request: MigracionDespachoRequest = Body(...)):
    try:
        migrador = MigradorDespacho(request.fecha, request.almacen_id)
        resultados = migrador.migrar_todas()
        return {"status": "success", "fecha": str(request.fecha), "resultados": resultados}
    except Exception as e:
        logger.critical(f"Error inesperado en despacho: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/importar_organoleptico/")
async def importar_organoleptico(request: MigracionOrganolepticoRequest = Body(...)):
    try:
        migrador = MigradorOrganoleptico(request.fecha, request.almacen_id)
        resultados = migrador.migrar_todas()
        return {"status": "success", "fecha": str(request.fecha), "resultados": resultados}
    except Exception as e:
        logger.critical(f"Error inesperado en organoleptico: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/importar_recepcion/")
async def importar_recepcion(request: MigracionRecepcionRequest = Body(...)):
    try:
        migrador = MigradorRecepcion(request.fecha, request.almacen_id)
        resultados = migrador.migrar_todas()
        return {
            "status": "success",
            "fecha": str(request.fecha),
            "almacen": request.almacen_id,
            "resultados": resultados
        }
    except Exception as e:
        logger.critical(f"Error inesperado en recepción: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Routers PDF
app.include_router(acta_ventas.router, prefix="/api")
app.include_router(acta_traslado.router, prefix="/api")
app.include_router(acta_despacho.router, prefix="/api")
app.include_router(acta_recepcion.router, prefix="/api")
app.include_router(acta_organoleptico.router, prefix="/api")

# Uvicorn
if __name__ == "__main__":
    import uvicorn
    print("Iniciando servidor Uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
