from Procesamiento.Importador import Importador
import logging

logger = logging.getLogger(__name__)

class ImportadorOrganoleptico(Importador):
    def __init__(self):
        # 1. Inicializamos al Padre para usar sus herramientas (limpieza, bloques, etc.)
        super().__init__()

        # 2. CONFIGURACION DE RANGOS (SLICES)
        # Basado en tu codigo original:
        self.INDICES = {
            'OWTR': (0, 11),   # 11 campos
            'WTR1': (11, 17),  # 6 campos
            'OITL': (17, 24),  # 7 campos
            'ITL1': (24, 29),  # 5 campos
            'OBTN': (29, 35),  # 6 campos
            'OBTW': (35, 40),  # 5 campos
            'OITM': (40, 48)   # 8 campos
        }

        # 3. ALMACEN DE QUERIES (Diccionario para el Migrador)
        self.inserts = {
            'OWTR': [], 'WTR1': [], 'OITL': [], 'ITL1': [], 
            'OBTN': [], 'OBTW': [], 'OITM': []
        }
        
        # 4. MEMORIA CACHE (Evitar Duplicados / Primary Key Violations)
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
        """Usa la logica de limpieza del padre para armar el INSERT."""
        # Nota: self._formatear_valor viene de la clase padre Importador
        vals_str = [self._formatear_valor(x) for x in valores]
        return f"INSERT INTO {tabla} VALUES({','.join(vals_str)})"

    def procesar_fila(self, fila):
        """Distribuye la fila flat de HANA en las tablas correspondientes."""
        try:
            # 1. OWTR (Cabecera)
            doc_entry = fila[0]
            if doc_entry not in self.procesados['OWTR']:
                r = self.INDICES['OWTR']
                self.inserts['OWTR'].append(self._generar_sql('OWTR', fila[r[0]:r[1]]))
                self.procesados['OWTR'].add(doc_entry)

            # 2. WTR1 (Detalle)
            pk_wtr1 = (fila[11], fila[12])
            if pk_wtr1 not in self.procesados['WTR1']:
                r = self.INDICES['WTR1']
                self.inserts['WTR1'].append(self._generar_sql('WTR1', fila[r[0]:r[1]]))
                self.procesados['WTR1'].add(pk_wtr1)

            # 3. OITL (Log)
            log_entry = fila[17]
            if log_entry and log_entry not in self.procesados['OITL']:
                r = self.INDICES['OITL']
                self.inserts['OITL'].append(self._generar_sql('OITL', fila[r[0]:r[1]]))
                self.procesados['OITL'].add(log_entry)

            # 4. ITL1 (Detalle Log)
            pk_itl1 = (fila[24], fila[25], fila[27])
            if pk_itl1[0] and pk_itl1 not in self.procesados['ITL1']:
                r = self.INDICES['ITL1']
                self.inserts['ITL1'].append(self._generar_sql('ITL1', fila[r[0]:r[1]]))
                self.procesados['ITL1'].add(pk_itl1)

            # 5. OBTN (Lotes)
            pk_obtn = (fila[29], fila[30])
            if pk_obtn[0] and pk_obtn not in self.procesados['OBTN']:
                r = self.INDICES['OBTN']
                self.inserts['OBTN'].append(self._generar_sql('OBTN', fila[r[0]:r[1]]))
                self.procesados['OBTN'].add(pk_obtn)

            # 6. OBTW (Lotes x Almacen)
            abs_entry_lote = fila[39]
            if abs_entry_lote and abs_entry_lote not in self.procesados['OBTW']:
                r = self.INDICES['OBTW']
                self.inserts['OBTW'].append(self._generar_sql('OBTW', fila[r[0]:r[1]]))
                self.procesados['OBTW'].add(abs_entry_lote)

            # 7. OITM (Articulos)
            item_code = fila[40]
            if item_code and item_code not in self.procesados['OITM']:
                r = self.INDICES['OITM']
                self.inserts['OITM'].append(self._generar_sql('OITM', fila[r[0]:r[1]]))
                self.procesados['OITM'].add(item_code)

        except Exception as e:
            logger.error(f"Error procesando fila Organoleptico: {e}")

    def obtener_bloques(self, tabla):
        """Retorna los inserts acumulados para una tabla especifica."""
        return self.inserts.get(tabla, [])