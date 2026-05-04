import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)

class Importador:
    def __init__(self):
        self.query_sql = []  # Lista de bloques de queries
        self.bloque_actual = [] # Buffer temporal para el bloque actual
        self.tamano_bloque = 50 # Límite de inserts por bloque
        
        # DEFINICIÓN DE MAPEOS (Tabla -> Índices de HANA)
        # Esto reemplaza el if/elif gigante. Es más limpio y fácil de editar.
        self.mapeos = {
            "OITM": lambda r: [r[0], r[1], r[2], r[3], r[4], r[5], r[6]],
            "OWHS": lambda r: [r[0], r[1], r[2]],
            "OWTR": lambda r: [r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10]],
            "WTR1": lambda r: [r[0], r[1], r[2], r[3], r[4], r[5]],
            "OITL": lambda r: [r[0], r[1], r[2], r[3], r[4], r[5], r[6]],
            "ODLN": lambda r: [r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12]],
            "OBTW": lambda r: [r[0], r[1], r[2], r[3], r[4]],
            "ITL1": lambda r: [r[0], r[1], r[2], r[3], r[4]],
            "IBT1": lambda r: [r[0], r[1], r[2], r[3], r[4], r[5], r[6]],
            "DLN1": lambda r: [r[0], r[1], r[2], r[3], r[4], r[5], r[6]],
            "INV1": lambda r: [r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]],
            # OBTN tiene lógica especial para la fecha, lo manejamos en una función aparte abajo si es necesario,
            # pero aquí asumimos el mapeo directo y _formatear_valor hará el trabajo sucio.
            "OBTN": lambda r: [r[0], r[1], r[2], r[3], r[4], r[5]], 
            
            # OINV: Mapeo específico según tu código anterior
            # Indices: 0=DocEntry, 1=NumAtCard, 2=NGUIA, 3=ObjType, 4=DocNum, 5=CardCode, 
            # 6=CardName, 7=DocDate, 8=TaxDate, 9=MDTD, 10=MDSD, 11=MDCD, 12=Lugar, 13=FecIniTra
            "OINV": lambda r: [r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13]]
        }

    def _formatear_valor(self, val):
        """Limpia y formatea el valor para SQL Server."""
        if val is None or val == '' or str(val).lower() == 'none':
            return 'NULL'
        
        # Manejo automático de fechas (datetime o date)
        if isinstance(val, (datetime, date)):
            return f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'"
        
        # Convertir a string y escapar comillas simples
        val_str = str(val).strip()
        val_limpio = val_str.replace("'", "''") # Escapar comillas para SQL
        return f"'{val_limpio}'"

    def _agregar_insert(self, tabla, valores):
        """Construye el string del INSERT y maneja los bloques."""
        # Unimos los valores formateados con comas
        valores_sql = ",".join([self._formatear_valor(v) for v in valores])
        stmt = f"INSERT INTO dbo.{tabla} VALUES ({valores_sql});\n"
        
        self.bloque_actual.append(stmt)

        # Si alcanzamos el límite, guardamos el bloque y limpiamos
        if len(self.bloque_actual) >= self.tamano_bloque:
            self.query_sql.append("".join(self.bloque_actual))
            self.bloque_actual = []

    def query_transaccion(self, reg_hana, tabla):
        """Método principal llamado desde el bucle de migración."""
        try:
            if tabla not in self.mapeos:
                logger.error(f"❌ Tabla {tabla} no definida en los mapeos del Importador.")
                return

            # Extraer valores usando la lambda definida en __init__
            valores_crudos = self.mapeos[tabla](reg_hana)
            
            # Caso especial OBTN (Validación extra de fecha expiración si viene corrupta)
            if tabla == "OBTN":
                # El índice 5 es ExpDate
                fecha_exp = valores_crudos[5]
                if isinstance(fecha_exp, str):
                    try:
                        # Intentar parsear si viene como string extraño
                        valores_crudos[5] = datetime.strptime(fecha_exp, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        valores_crudos[5] = None # Si falla, NULL

            self._agregar_insert(tabla, valores_crudos)

        except IndexError as e:
            logger.error(f"❌ Error de índice en {tabla}. Registro tiene {len(reg_hana)} campos, se esperaban más. Detalle: {e}")
        except Exception as e:
            logger.error(f"❌ Error procesando registro de {tabla}: {e}")

    def obtener_query_final(self):
        """Devuelve todos los bloques restantes."""
        if self.bloque_actual:
            self.query_sql.append("".join(self.bloque_actual))
            self.bloque_actual = []
        return self.query_sql

    # Compatibilidad con tu código existente que llama a .query_sql directamente
    @property
    def sql_generated(self):
        # Asegura que lo que quede en el buffer se pase a la lista final
        if self.bloque_actual:
            self.query_sql.append("".join(self.bloque_actual))
            self.bloque_actual = []
        return self.query_sql