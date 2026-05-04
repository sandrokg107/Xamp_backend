from Procesamiento.Importador import Importador
import logging

logger = logging.getLogger(__name__)

class ImportadorDespacho(Importador):
    def __init__(self):
        # 1. Inicializamos al Padre para reutilizar herramientas de limpieza y bloques
        super().__init__()

        # 2. CONFIGURACION DE RANGOS (SLICES)
        # Extraído de la lógica de tu código original para mantener compatibilidad
        self.INDICES = {
            'OINV': (0, 14),   # 14 campos
            'INV1': (14, 23),  # 9 campos
            'IBT1': (23, 30),  # 7 campos
            'OBTN': (30, 36),  # 6 campos
            'OBTW': (36, 41),  # 5 campos
            'OITL': (41, 48),  # 7 campos
            'ITL1': (48, 53),  # 5 campos
            'OITM': (53, 60)   # 7 campos
        }

        # 3. ALMACEN DE QUERIES
        self.inserts = {
            'OINV': [], 'INV1': [], 'IBT1': [], 'OBTN': [],
            'OBTW': [], 'OITL': [], 'ITL1': [], 'OITM': []
        }
        
        # 4. MEMORIA CACHE (Control de duplicados de Llave Primaria)
        self.procesados = {
            'OINV': set(), # PK: DocEntry
            'INV1': set(), # PK: DocEntry + LineNum
            'OBTN': set(), # PK: ItemCode + DistNumber
            'OBTW': set(), # PK: AbsEntry
            'OITL': set(), # PK: LogEntry
            'ITL1': set(), # PK: LogEntry + ItemCode + SysNumber
            'OITM': set()  # PK: ItemCode
        }

    def _generar_sql(self, tabla, valores):
        """Genera el comando INSERT utilizando el formateador del padre."""
        vals_str = [self._formatear_valor(x) for x in valores]
        return f"INSERT INTO {tabla} VALUES({','.join(vals_str)})"

    def procesar_fila(self, fila):
        """Descompone la fila flat de HANA en las tablas de despacho en SQL Server."""
        try:
            # 1. OINV (Cabecera Factura)
            doc_entry = fila[0]
            if doc_entry not in self.procesados['OINV']:
                r = self.INDICES['OINV']
                self.inserts['OINV'].append(self._generar_sql('OINV', fila[r[0]:r[1]]))
                self.procesados['OINV'].add(doc_entry)

            # 2. INV1 (Detalle Factura)
            # PK: DocEntry(14) + LineNum(18)
            pk_inv1 = (fila[14], fila[18])
            if pk_inv1 not in self.procesados['INV1']:
                r = self.INDICES['INV1']
                self.inserts['INV1'].append(self._generar_sql('INV1', fila[r[0]:r[1]]))
                self.procesados['INV1'].add(pk_inv1)

            # 3. IBT1 (Transaccion Lotes)
            # Se insertan todos los registros que vinculan lotes
            r = self.INDICES['IBT1']
            self.inserts['IBT1'].append(self._generar_sql('IBT1', fila[r[0]:r[1]]))

            # 4. OBTN (Maestro Lotes)
            pk_obtn = (fila[30], fila[31]) # ItemCode + DistNumber
            if pk_obtn[0] and pk_obtn not in self.procesados['OBTN']:
                r = self.INDICES['OBTN']
                self.inserts['OBTN'].append(self._generar_sql('OBTN', fila[r[0]:r[1]]))
                self.procesados['OBTN'].add(pk_obtn)

            # 5. OBTW (Lotes por Almacen)
            abs_entry_lote = fila[40]
            if abs_entry_lote and abs_entry_lote not in self.procesados['OBTW']:
                r = self.INDICES['OBTW']
                self.inserts['OBTW'].append(self._generar_sql('OBTW', fila[r[0]:r[1]]))
                self.procesados['OBTW'].add(abs_entry_lote)

            # 6. OITL (Log Transaccion)
            log_entry = fila[41]
            if log_entry and log_entry not in self.procesados['OITL']:
                r = self.INDICES['OITL']
                self.inserts['OITL'].append(self._generar_sql('OITL', fila[r[0]:r[1]]))
                self.procesados['OITL'].add(log_entry)

            # 7. ITL1 (Detalle Log)
            # PK: LogEntry(48) + ItemCode(49) + SysNumber(51)
            pk_itl1 = (fila[48], fila[49], fila[51])
            if pk_itl1[0] and pk_itl1 not in self.procesados['ITL1']:
                r = self.INDICES['ITL1']
                self.inserts['ITL1'].append(self._generar_sql('ITL1', fila[r[0]:r[1]]))
                self.procesados['ITL1'].add(pk_itl1)

            # 8. OITM (Maestro Articulos)
            item_code = fila[53]
            if item_code and item_code not in self.procesados['OITM']:
                r = self.INDICES['OITM']
                self.inserts['OITM'].append(self._generar_sql('OITM', fila[r[0]:r[1]]))
                self.procesados['OITM'].add(item_code)

        except Exception as e:
            logger.error(f"Error procesando fila en ImportadorDespacho: {e}")

    def obtener_bloques(self, tabla):
        """Retorna la lista de sentencias SQL generadas para la tabla solicitada."""
        return self.inserts.get(tabla, [])