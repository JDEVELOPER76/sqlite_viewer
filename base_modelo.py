import sqlite3
from pathlib import Path


class BaseModelo:
	def __init__(self):
		self.conn = None
		self.db_path = None

	@staticmethod
	def _q(identifier: str) -> str:
		return '"' + identifier.replace('"', '""') + '"'

	def conectar(self, db_path: str):
		ruta = Path(db_path).expanduser().resolve()
		if not ruta.exists():
			raise FileNotFoundError(f"No existe la base de datos: {ruta}")

		if self.conn:
			self.conn.close()

		self.conn = sqlite3.connect(str(ruta))
		self.conn.row_factory = sqlite3.Row
		self.db_path = str(ruta)

	def cerrar(self):
		if self.conn:
			self.conn.close()
			self.conn = None

	def _check_conn(self):
		if not self.conn:
			raise RuntimeError("Primero debes conectar una base de datos.")

	def obtener_tablas(self):
		self._check_conn()
		cursor = self.conn.execute(
			"""
			SELECT name
			FROM sqlite_master
			WHERE type='table' AND name NOT LIKE 'sqlite_%'
			ORDER BY name
			"""
		)
		return [fila["name"] for fila in cursor.fetchall()]

	def obtener_columnas(self, tabla: str):
		self._check_conn()
		cursor = self.conn.execute(f"PRAGMA table_info({self._q(tabla)})")
		columnas = []
		for fila in cursor.fetchall():
			columnas.append(
				{
					"cid": fila["cid"],
					"name": fila["name"],
					"type": fila["type"],
					"notnull": fila["notnull"],
					"default": fila["dflt_value"],
					"pk": fila["pk"],
				}
			)
		return columnas

	def _columnas_pk(self, tabla: str):
		columnas = self.obtener_columnas(tabla)
		pks = sorted((c for c in columnas if c["pk"]), key=lambda c: c["pk"])
		return [c["name"] for c in pks]

	def leer_tabla(self, tabla: str, limite: int = 500):
		self._check_conn()
		tabla_q = self._q(tabla)

		try:
			query = f"SELECT rowid AS __rowid__, * FROM {tabla_q} LIMIT ?"
			cursor = self.conn.execute(query, (limite,))
		except sqlite3.OperationalError:
			query = f"SELECT * FROM {tabla_q} LIMIT ?"
			cursor = self.conn.execute(query, (limite,))

		filas = [dict(fila) for fila in cursor.fetchall()]
		return filas

	def _build_where(self, tabla: str, fila_original: dict):
		pk_cols = self._columnas_pk(tabla)
		if pk_cols:
			where_cols = pk_cols
		elif "__rowid__" in fila_original:
			where_cols = ["__rowid__"]
		else:
			where_cols = [k for k in fila_original.keys() if k != "__rowid__"]

		if not where_cols:
			raise RuntimeError("No se pudo identificar una clave para editar/eliminar.")

		condiciones = []
		valores = []
		for col in where_cols:
			if col == "__rowid__":
				condiciones.append("rowid = ?")
			else:
				condiciones.append(f"{self._q(col)} = ?")
			valores.append(fila_original.get(col))

		return " AND ".join(condiciones), valores, where_cols

	def actualizar_fila(self, tabla: str, fila_original: dict, fila_nueva: dict):
		self._check_conn()

		where_sql, where_vals, where_cols = self._build_where(tabla, fila_original)
		cols_a_editar = [c for c in fila_nueva.keys() if c != "__rowid__" and c not in where_cols]

		if not cols_a_editar:
			cols_a_editar = [c for c in fila_nueva.keys() if c != "__rowid__"]

		if not cols_a_editar:
			raise RuntimeError("No hay columnas para actualizar.")

		set_sql = ", ".join([f"{self._q(col)} = ?" for col in cols_a_editar])
		valores = [fila_nueva.get(col) for col in cols_a_editar] + where_vals

		query = f"UPDATE {self._q(tabla)} SET {set_sql} WHERE {where_sql}"
		cur = self.conn.execute(query, valores)
		self.conn.commit()
		return cur.rowcount

	def eliminar_fila(self, tabla: str, fila_original: dict):
		self._check_conn()

		where_sql, where_vals, _ = self._build_where(tabla, fila_original)
		query = f"DELETE FROM {self._q(tabla)} WHERE {where_sql}"
		cur = self.conn.execute(query, where_vals)
		self.conn.commit()
		return cur.rowcount

	def insertar_fila(self, tabla: str, datos: dict):
		"""
		Inserta una nueva fila en la tabla especificada.
		:param tabla: Nombre de la tabla.
		:param datos: Diccionario con los datos a insertar (columna: valor).
		:return: rowid de la fila insertada.
		"""
		self._check_conn()
		columnas = list(datos.keys())
		valores = [datos[col] for col in columnas]
		cols_q = ', '.join([self._q(col) for col in columnas])
		placeholders = ', '.join(['?' for _ in columnas])
		query = f"INSERT INTO {self._q(tabla)} ({cols_q}) VALUES ({placeholders})"
		cur = self.conn.execute(query, valores)
		self.conn.commit()
		return cur.lastrowid
