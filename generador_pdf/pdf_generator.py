
import os
from datetime import datetime
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# Ruta base absoluta al directorio actual (donde está este archivo)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def generar_pdf_acta_traslado(data: dict) -> str:
    try:
        # 1. Crear ruta base de salida
        base_folder = os.path.join(BASE_DIR, "..", "ActaDespacho_traslado")
        os.makedirs(base_folder, exist_ok=True)

        # 2. Subcarpeta por fecha (formato dd-mm-yyyy)
        fecha = data["fecha"].replace("/", "-")  # Asegura formato dd-mm-yyyy
        subcarpeta = os.path.join(base_folder, fecha)
        os.makedirs(subcarpeta, exist_ok=True)

        # 3. Cargar plantilla
        template_dir = os.path.join(BASE_DIR, "templates")
        template_file = "acta_despacho_traslado.html"

        env = Environment(loader=FileSystemLoader(template_dir))
        try:
            template = env.get_template(template_file)
            print("✅ Plantilla de traslado cargada correctamente")
        except TemplateNotFound:
            raise FileNotFoundError(f"❌ Plantilla '{template_file}' no encontrada en '{template_dir}'")

        # 4. Renderizar HTML
        html_content = template.render(**data)

        # 5. Nombre de archivo: usar el nombre pasado si existe, si no generar uno por defecto
        nombre_pdf = data.get('nombre_pdf')
        if not nombre_pdf:
            nombre_pdf = f"{data['guia']}.pdf"
        ruta_pdf = os.path.join(subcarpeta, nombre_pdf)

        # 6. Generar PDF
        # Usar base_url como la carpeta de estáticos para que WeasyPrint encuentre la firma
        static_dir = os.path.abspath(os.path.join(BASE_DIR, "static"))
        HTML(string=html_content, base_url=static_dir).write_pdf(ruta_pdf)

        return os.path.abspath(ruta_pdf)

    except Exception as e:
        print(f"❌ Error generando PDF de traslado: {e}")
        raise

def generar_pdf_acta_ventas(data: dict) -> str:
    try:
        # 1. Ruta base de salida
        base_folder = os.path.join(BASE_DIR, "..", "ActaDespacho_ventas")
        os.makedirs(base_folder, exist_ok=True)

        # 2. Subcarpeta por fecha
        fecha_str = data["fecha"]
        subcarpeta = os.path.join(base_folder, fecha_str)
        os.makedirs(subcarpeta, exist_ok=True)

        # 3. Cargar plantilla
        template_dir = os.path.join(BASE_DIR, "templates")
        template_file = "acta_despacho_ventas.html"

        env = Environment(loader=FileSystemLoader(template_dir))
        try:
            template = env.get_template(template_file)
            print("✅ Plantilla de ventas cargada correctamente")
        except TemplateNotFound:
            raise FileNotFoundError(f"❌ Plantilla '{template_file}' no encontrada en '{template_dir}'")


        # 4. Renderizar HTML (igual que traslado)
        html_content = template.render(**data)

        # 5. Nombre del archivo
        nombre_pdf = f"{data.get('guia', data.get('numCard', ''))}.pdf"
        ruta_pdf = os.path.join(subcarpeta, nombre_pdf)

        # 6. Generar PDF (igual que traslado)
        static_dir = os.path.abspath(os.path.join(BASE_DIR, "static"))
        HTML(string=html_content, base_url=static_dir).write_pdf(ruta_pdf)

        return os.path.abspath(ruta_pdf)

    except Exception as e:
        print(f"❌ Error generando PDF de ventas: {e}")
        raise


# --------------------------------------------------------
# GENERAR PDF ACTA RECEPCION
# --------------------------------------------------------
def generar_pdf_acta_recepcion(data: dict) -> str:
    try:
        base_folder = os.path.join(BASE_DIR, "..", "ActaRecepcion")
        os.makedirs(base_folder, exist_ok=True)
        fecha_str = data["fecha"]
        subcarpeta = os.path.join(base_folder, fecha_str)
        os.makedirs(subcarpeta, exist_ok=True)
        template_dir = os.path.join(BASE_DIR, "templates")
        template_file = "acta_recepcion.html"
        env = Environment(loader=FileSystemLoader(template_dir))
        try:
            template = env.get_template(template_file)
            print("✅ Plantilla de recepción cargada correctamente")
        except TemplateNotFound:
            raise FileNotFoundError(f"❌ Plantilla '{template_file}' no encontrada en '{template_dir}'")
        html_content = template.render(**data)
        nombre_pdf = f"Acta_Recepcion_{data.get('guia', '')}.pdf"
        ruta_pdf = os.path.join(subcarpeta, nombre_pdf)
        static_dir = os.path.abspath(os.path.join(BASE_DIR, "static"))
        HTML(string=html_content, base_url=static_dir).write_pdf(ruta_pdf)
        return os.path.abspath(ruta_pdf)
    except Exception as e:
        print(f"❌ Error generando PDF de recepción: {e}")
        raise

# --------------------------------------------------------
# GENERAR PDF ACTA DESPACHO (alias de traslado para compatibilidad)
# --------------------------------------------------------
def generar_pdf_acta_despacho(data: dict) -> str:
    try:
        # 1. Ruta base de salida
        base_folder = os.path.join(BASE_DIR, "..", "ActaDespacho")
        os.makedirs(base_folder, exist_ok=True)

        # 2. Subcarpeta por fecha
        fecha_str = data["fecha"]
        subcarpeta = os.path.join(base_folder, fecha_str)
        os.makedirs(subcarpeta, exist_ok=True)

        # 3. Cargar plantilla
        template_dir = os.path.join(BASE_DIR, "templates")
        template_file = "acta_despacho.html"

        env = Environment(loader=FileSystemLoader(template_dir))
        try:
            template = env.get_template(template_file)
            print("✅ Plantilla de ventas cargada correctamente")
        except TemplateNotFound:
            raise FileNotFoundError(f"❌ Plantilla '{template_file}' no encontrada en '{template_dir}'")


        # 4. Renderizar HTML (igual que traslado)
        html_content = template.render(**data)

        # 5. Nombre del archivo
        nombre_pdf = f"Acta_Despachp_{data.get('factura', '')}.pdf"
        ruta_pdf = os.path.join(subcarpeta, nombre_pdf)

        # 6. Generar PDF (igual que traslado)
        static_dir = os.path.abspath(os.path.join(BASE_DIR, "static"))
        HTML(string=html_content, base_url=static_dir).write_pdf(ruta_pdf)

        return os.path.abspath(ruta_pdf)

    except Exception as e:
        print(f"❌ Error generando PDF de ventas: {e}")
        raise

# --------------------------------------------------------
# GENERAR PDF ACTA ORGANOLEPTICO
# --------------------------------------------------------
def generar_pdf_acta_organoleptico(data: dict) -> str:
    try:
        base_folder = os.path.join(BASE_DIR, "..", "ActaOrganoleptico")
        os.makedirs(base_folder, exist_ok=True)
        fecha_str = data["fecha"]
        subcarpeta = os.path.join(base_folder, fecha_str)
        os.makedirs(subcarpeta, exist_ok=True)
        template_dir = os.path.join(BASE_DIR, "templates")
        template_file = "organoleptico.html"
        env = Environment(loader=FileSystemLoader(template_dir))
        try:
            template = env.get_template(template_file)
            print("✅ Plantilla organoléptica cargada correctamente")
        except TemplateNotFound:
            raise FileNotFoundError(f"❌ Plantilla '{template_file}' no encontrada en '{template_dir}'")
        html_content = template.render(**data)
        nombre_pdf = f"Acta_Organoleptico_{data.get('guia', '')}.pdf"
        ruta_pdf = os.path.join(subcarpeta, nombre_pdf)
        static_dir = os.path.abspath(os.path.join(BASE_DIR, "static"))
        HTML(string=html_content, base_url=static_dir).write_pdf(ruta_pdf)
        return os.path.abspath(ruta_pdf)
    except Exception as e:
        print(f"❌ Error generando PDF organoléptico: {e}")
        raise
