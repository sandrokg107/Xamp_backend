#
# Ejemplo para ejecutar migración de despacho con log dedicado en PowerShell:
# $env:LOG_FILE = 'migrado_despacho.log'; python Migrador\migrado_despacho_1_y_5.py
#
# Para ventas:
# $env:LOG_FILE = 'migrador_ventas.log'; python Migrador\migrador_ventas.py
import logging
from logging.handlers import RotatingFileHandler
import os


# Configuración flexible por operación
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
DEFAULT_LOG_FILE = 'migracion.log'
LOG_FILE = os.path.join(LOG_DIR, os.getenv('LOG_FILE', DEFAULT_LOG_FILE))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("migrador")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# Evitar duplicar handlers
if not logger.hasHandlers():
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5*1024*1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

logger.propagate = False