from Procesamiento.Importador import Importador
import logging

logger = logging.getLogger(__name__)

class ImportadorVentas(Importador):
    def __init__(self):
        # 1. Inicializamos al Padre (para tener acceso a herramientas comunes si las hubiera)
        super().__init__()

        # 2. DEFINICIÓN DE INDICES (Mapa del tesoro)
        # Esto evita que tengas números como [13:20] regados por todo el código.
        # Si cambia el Query de HANA, solo cambias estos números aquí.
        self.INDICES = {
            'ODLN': (0, 13),   # Cabecera
            'DLN1': (13, 20),  # Detalle Líneas
            'IBT1': (20, 27),  # Detalle Lotes
            'OBTN': (27, 33),  # Maestro Lotes
            'OBTW': (33, 38),  # Lotes por Almacén
            'OITL': (38, 45),  # Log Transacción
            'ITL1': (45, 50),  # Detalle Log
            'OITM': (50, 57)   # Maestro Artículos
        }

        # 3. ALMACÉN DE QUERIES (Diccionario)
        # Mantenemos esto porque tu Migrador pide los bloques por nombre de tabla.
        self.inserts = {
            'ODLN': [], 'DLN1': [], 'IBT1': [], 'OBTN': [],
            'OBTW': [], 'OITL': [], 'ITL1': [], 'OITM': []
        }
        
        # 4. MEMORIA CACHÉ (Evitar Duplicados)
        self.procesados = {
            'ODLN': set(), 'DLN1': set(), 'OITM': set(),
            'OBTN': set(), 'OBTW': set(), 'OITL': set(), 'ITL1': set()
        }

    # Sobreescribimos o usamos un helper local para asegurar la limpieza específica
    def _limpiar_y_formatear(self, val):
        """Versión robusta de _str para este importador específico."""
        if val is None:
            return "NULL"
        # Convertimos a string y escapamos comillas simples
        val_limpio = str(val).replace("'", "''")
        return f"'{val_limpio}'"

    def _generar_sql(self, tabla, valores):
        """Helper para crear la sentencia INSERT limpia."""
        vals_str = [self._limpiar_y_formatear(x) for x in valores]
        return f"INSERT INTO {tabla} VALUES({','.join(vals_str)})"

    # ==========================================
    # LÓGICA PRINCIPAL (Procesamiento)
    # ==========================================

    def procesar_fila(self, fila):
        try:
            # --- 1. CABECERA (ODLN) ---
            # PK: DocEntry (Índice 0 relativo al slice ODLN)
            doc_entry = fila[0] 
            if doc_entry not in self.procesados['ODLN']:
                rango = self.INDICES['ODLN']
                stmt = self._generar_sql('ODLN', fila[rango[0]:rango[1]])
                self.inserts['ODLN'].append(stmt)
                self.procesados['ODLN'].add(doc_entry)

            # --- 2. DETALLE LÍNEA (DLN1) ---
            # PK: DocEntry + LineNum. (Indices absolutos: 13 y 17)
            # Usamos el diccionario para obtener los índices exactos
            idx_dln1 = self.INDICES['DLN1']
            # Nota: LineNum es el 5to elemento dentro del bloque DLN1 (13+4 = 17)
            line_num = fila[17] 
            
            pk_dln1 = (doc_entry, line_num)
            
            if pk_dln1 not in self.procesados['DLN1']:
                stmt = self._generar_sql('DLN1', fila[idx_dln1[0]:idx_dln1[1]])
                self.inserts['DLN1'].append(stmt)
                self.procesados['DLN1'].add(pk_dln1)

            # --- 3. TRANSACCIÓN LOTES (IBT1) ---
            # RELACIÓN N:N (No se filtra, siempre se inserta)
            rango_ibt1 = self.INDICES['IBT1']
            stmt = self._generar_sql('IBT1', fila[rango_ibt1[0]:rango_ibt1[1]])
            self.inserts['IBT1'].append(stmt)

            # --- 4. MAESTRO LOTES (OBTN) ---
            # PK: ItemCode (27) + DistNumber (28)
            item_code_lote = fila[27]
            dist_number = fila[28]
            pk_obtn = (item_code_lote, dist_number)

            if pk_obtn not in self.procesados['OBTN']:
                rango = self.INDICES['OBTN']
                stmt = self._generar_sql('OBTN', fila[rango[0]:rango[1]])
                self.inserts['OBTN'].append(stmt)
                self.procesados['OBTN'].add(pk_obtn)

            # --- 5. LOTES POR ALMACÉN (OBTW) ---
            # PK: AbsEntry (37)
            abs_entry = fila[37]
            if abs_entry not in self.procesados['OBTW']:
                rango = self.INDICES['OBTW']
                stmt = self._generar_sql('OBTW', fila[rango[0]:rango[1]])
                self.inserts['OBTW'].append(stmt)
                self.procesados['OBTW'].add(abs_entry)

            # --- 6. LOG TRANSACCIÓN (OITL) ---
            # PK: LogEntry (38)
            log_entry = fila[38]
            if log_entry not in self.procesados['OITL']:
                rango = self.INDICES['OITL']
                stmt = self._generar_sql('OITL', fila[rango[0]:rango[1]])
                self.inserts['OITL'].append(stmt)
                self.procesados['OITL'].add(log_entry)

            # --- 7. DETALLE LOG (ITL1) ---
            # PK: LogEntry(45) + ItemCode(46) + SysNumber(48)
            pk_itl1 = (fila[45], fila[46], fila[48])
            if pk_itl1 not in self.procesados['ITL1']:
                rango = self.INDICES['ITL1']
                stmt = self._generar_sql('ITL1', fila[rango[0]:rango[1]])
                self.inserts['ITL1'].append(stmt)
                self.procesados['ITL1'].add(pk_itl1)

            # --- 8. MAESTRO ARTÍCULOS (OITM) ---
            # PK: ItemCode (50)
            item_code_master = fila[50]
            if item_code_master not in self.procesados['OITM']:
                rango = self.INDICES['OITM']
                stmt = self._generar_sql('OITM', fila[rango[0]:rango[1]])
                self.inserts['OITM'].append(stmt)
                self.procesados['OITM'].add(item_code_master)

        except Exception as e:
            # Logueamos el error pero no detenemos todo el proceso masivo,
            # aunque idealmente deberías manejar esto según tu política de errores.
            logger.error(f"Error procesando fila en ImportadorVentas: {e}")

    # ==========================================
    # INTERFAZ PÚBLICA (Lo que llama el Migrador)
    # ==========================================
    
    def obtener_bloques(self, tabla):
        """
        Retorna la lista de inserts para una tabla específica.
        El Migrador llama a esto: importador.obtener_bloques('ODLN')
        """
        return self.inserts.get(tabla, [])

    # Métodos placeholder para compatibilidad con la estructura del Migrador
    # si es que llama a métodos específicos para otras tablas
    def procesar_fila_oinv(self, fila):
        # Implementar lógica OINV similar si es necesario, 
        # o usar una clase ImportadorFacturas separada.
        pass

    def procesar_fila_inv1(self, fila):
        pass