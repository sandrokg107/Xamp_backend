from Procesamiento.Importador import Importador
import logging

logger = logging.getLogger(__name__)

class ImportadorRecepcion(Importador):
    def __init__(self):
        super().__init__()

        # --- MAPA DE INDICES (Basado en tu Query de Recepcion) ---
        self.INDICES = {
            'OWTR': (0, 11),   # Cabecera (DocEntry, DocNum...)
            'WTR1': (11, 17),  # Detalle (ItemCode, Quantity...)
            'OITL': (17, 24),  # Log Transaccion
            'ITL1': (24, 29),  # Detalle Log
            'OBTN': (29, 35),  # Maestro Lotes
            'OBTW': (35, 40),  # Lotes por Almacen
            'OITM': (40, 47)   # Maestro Articulos
        }

        # --- ALMACEN DE QUERIES ---
        self.inserts = {
            'OWTR': [], 'WTR1': [], 'OITL': [], 'ITL1': [], 
            'OBTN': [], 'OBTW': [], 'OITM': []
        }
        
        # --- MEMORIA CACHE (Evitar Duplicados) ---
        self.procesados = {
            'OWTR': set(), # PK: DocEntry
            'WTR1': set(), # PK: DocEntry + LineNum
            'OITL': set(), # PK: LogEntry
            'ITL1': set(), # PK: LogEntry + ItemCode + SysNumber
            'OBTN': set(), # PK: ItemCode + DistNumber
            'OBTW': set(), # PK: AbsEntry
            'OITM': set()  # PK: ItemCode
        }

    def _generar_sql(self, tabla, valores):
        vals_str = []
        for v in valores:
            if v is None:
                vals_str.append("NULL")
            else:
                val_limpio = str(v).replace("'", "''")
                vals_str.append(f"'{val_limpio}'")
        return f"INSERT INTO {tabla} VALUES({','.join(vals_str)})"

    def procesar_fila(self, fila):
        try:
            # 1. CABECERA (OWTR) - PK: DocEntry
            doc_entry = fila[0]
            if doc_entry not in self.procesados['OWTR']:
                rango = self.INDICES['OWTR']
                stmt = self._generar_sql('OWTR', fila[rango[0]:rango[1]])
                self.inserts['OWTR'].append(stmt)
                self.procesados['OWTR'].add(doc_entry)

            # 2. DETALLE (WTR1) - PK: DocEntry + LineNum
            pk_wtr1 = (fila[11], fila[12])
            if pk_wtr1 not in self.procesados['WTR1']:
                rango = self.INDICES['WTR1']
                stmt = self._generar_sql('WTR1', fila[rango[0]:rango[1]])
                self.inserts['WTR1'].append(stmt)
                self.procesados['WTR1'].add(pk_wtr1)

            # 3. LOG (OITL) - PK: LogEntry
            log_entry = fila[17]
            if log_entry not in self.procesados['OITL']:
                rango = self.INDICES['OITL']
                stmt = self._generar_sql('OITL', fila[rango[0]:rango[1]])
                self.inserts['OITL'].append(stmt)
                self.procesados['OITL'].add(log_entry)

            # 4. DETALLE LOG (ITL1) - PK: LogEntry + ItemCode + SysNumber
            pk_itl1 = (fila[24], fila[25], fila[27])
            if pk_itl1 not in self.procesados['ITL1']:
                rango = self.INDICES['ITL1']
                stmt = self._generar_sql('ITL1', fila[rango[0]:rango[1]])
                self.inserts['ITL1'].append(stmt)
                self.procesados['ITL1'].add(pk_itl1)

            # 5. MAESTRO LOTES (OBTN) - PK: ItemCode + DistNumber
            pk_obtn = (fila[29], fila[30])
            if pk_obtn not in self.procesados['OBTN']:
                rango = self.INDICES['OBTN']
                stmt = self._generar_sql('OBTN', fila[rango[0]:rango[1]])
                self.inserts['OBTN'].append(stmt)
                self.procesados['OBTN'].add(pk_obtn)

            # 6. LOTES ALMACEN (OBTW) - PK: AbsEntry
            # Nota: El indice relativo 4 es el AbsEntry (el ultimo del slice)
            abs_entry = fila[39]
            if abs_entry not in self.procesados['OBTW']:
                rango = self.INDICES['OBTW']
                stmt = self._generar_sql('OBTW', fila[rango[0]:rango[1]])
                self.inserts['OBTW'].append(stmt)
                self.procesados['OBTW'].add(abs_entry)

            # 7. ARTICULOS (OITM) - PK: ItemCode
            item_code = fila[40]
            if item_code not in self.procesados['OITM']:
                rango = self.INDICES['OITM']
                stmt = self._generar_sql('OITM', fila[rango[0]:rango[1]])
                self.inserts['OITM'].append(stmt)
                self.procesados['OITM'].add(item_code)

        except Exception as e:
            logger.error(f"Error procesando fila Recepcion: {e}")

    def obtener_bloques(self, tabla):
        return self.inserts.get(tabla, [])