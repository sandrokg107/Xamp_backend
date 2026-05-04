import os
import sys
import asyncio

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Forzar selector event loop en Windows (evita WinError 10106 al importar uvicorn)
if os.name == 'nt':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# Asegurar que el working dir es la raíz del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# Cargar .env si existe
try:
    from dotenv import load_dotenv
    env_path = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
except Exception:
    pass

# Importar la app (main crea 'app')
from main import app

def main():
    import uvicorn
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))
    uvicorn.run(app, host=host, port=port)

if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Si NSSM redirige stderr/stdout, los verá allí. También volcamos un fallback mínimo.
        try:
            with open('logs/service.err.log', 'a', encoding='utf-8') as f:
                import traceback
                traceback.print_exc(file=f)
        except Exception:
            pass