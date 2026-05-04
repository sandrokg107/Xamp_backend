# � Backend de Migración y Generación de PDFs

Este backend automatiza la migración de datos desde SAP (HANA/SQL Server) y la generación de actas de despacho en PDF, integrándose con un frontend moderno en Vue.js.

---

## � Funcionalidades principales

- **Migración de datos**: Extrae y migra información de SAP HANA/SQL Server a la nueva base de datos, con control de fechas, deduplicación y logs detallados.
- **Generación de PDFs**: Crea actas de despacho en PDF usando HTML+CSS y WeasyPrint, con plantillas personalizadas y nombres de archivo únicos.
- **API REST**: Endpoints para disparar migraciones, verificar estados y generar PDFs bajo demanda.
- **Logging avanzado**: Registro de errores, operaciones y métricas de migración/PDF para trazabilidad y auditoría.

---

## �️ Tecnologías utilizadas

| Componente         | Tecnología                                 |
|--------------------|--------------------------------------------|
| Backend            | Python 3.x                                 |
| Framework API      | FastAPI                                    |
| PDF                | WeasyPrint                                 |
| Plantillas         | Jinja2                                     |
| DB Conexión        | pyodbc (SQL Server), pyhdb (SAP HANA)      |
| Logging            | logging (RotatingFileHandler)              |

---

## Instalacion rapida

1. **Clona el repositorio y entra al backend:**
	```bash
	git clone <repo-url>
	cd backend
	```

2. **Crea y activa un entorno virtual:**
	```bash
	python -m venv env
	env\\Scripts\\activate   # En Windows
	# source env/bin/activate  # En Linux/Mac
	```

3. **Instala las dependencias:**
	```bash
	pip install -r requirements.txt
	```

4. **Instala dependencias del sistema para WeasyPrint:**
	- **Windows:** [GTK for Windows Runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer?tab=readme-ov-file)
	- **Linux:**  
	  ```bash
	  sudo apt install libpangocairo-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf2.0-0
	  ```

---

## 🏃‍♂️ Ejecución

```bash
uvicorn main:app --reload
```

---

## 📚 Estructura principal

- `main.py` — Punto de entrada FastAPI.
- `Migrador/` — Lógica de migración de datos.
- `generador_pdf/` — Lógica y endpoints para generación de PDFs.
- `Config/`, `Conexion/`, `Utils/` — Configuración, conexiones y utilidades.
- `logs/` — Archivos de log de migración y generación de PDFs.

---

## � Notas

- Asegúrate de configurar correctamente las cadenas de conexión a SAP y SQL Server en los archivos de configuración.
- Los PDFs se guardan en carpetas por fecha, con nombres únicos para evitar sobrescritura.
- El sistema registra cada operación relevante para facilitar auditoría y depuración.

---



