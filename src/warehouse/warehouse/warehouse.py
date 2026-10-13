from typing import Optional

from warehouse.dominio.pasillo import Pasillo
from warehouse.dominio.posicion import Posicion
from warehouse.dominio.producto import Producto
from warehouse.dominio.puerta import Puerta
from warehouse.dominio.rack import Rack
from warehouse.dominio.tipo_nodo import TipoNodo
from warehouse.dominio.zona import ZonaDespacho
from warehouse.estructuras.grafo import Grafo
from warehouse.estructuras.linkedlist import to_python_list
from warehouse.estructuras.trie import Trie, autocomplete
from warehouse.estructuras.trie import insert as trie_insert


class Warehouse:
    def __init__(self, ancho: int, alto: int) -> None:
        self.ancho = ancho
        self.alto = alto

        self.grafo = Grafo(es_dirigido=True)
        self.productos: dict[str, Producto] = {}
        self.racks: dict[str, Rack] = {}
        self.zonas: dict[str, ZonaDespacho] = {}
        self.puertas: dict[str, Puerta] = {}

        # Pasillos y sentidos de circulación
        self.pasillos: dict[str, Pasillo] = {}
        self._sentido_por_celda: dict[tuple[int, int], str] = {}

        # Índice de nombres para búsqueda por prefijo
        self.trie_nombres = Trie()
        self.nombre_a_id: dict[str, str] = {}

        self._nodo_por_xy: dict[tuple[int, int], int] = {}
        self._racks_ocupados: set[tuple[int, int]] = set()

    # --- helpers de construcción ---
    def _nodo_en(
        self, x: int, y: int, tipo: TipoNodo, producto_id: Optional[str] = None
    ) -> int:
        key = (x, y)
        if key in self._nodo_por_xy:
            nid = self._nodo_por_xy[key]
            nodo = self.grafo.nodo(nid)
            # Promover PASILLO → tipo más específico (DESPACHO, PUERTA)
            if nodo.tipo == TipoNodo.PASILLO and tipo != TipoNodo.PASILLO:
                nodo.tipo = tipo
                if producto_id is not None:
                    nodo.producto_id = producto_id
            return nid
        nid = self.grafo.agregar_nodo(Posicion(x, y), tipo, producto_id)
        self._nodo_por_xy[key] = nid
        return nid

    def _conectar_vecinos(self) -> None:
        """Conecta cada nodo con sus vecinos según el sentido de cada celda."""
        for (x, y), nid in self._nodo_por_xy.items():
            for dx, dy in ((1, 0), (0, 1)):
                v_xy = (x + dx, y + dy)
                if v_xy not in self._nodo_por_xy:
                    continue
                vid = self._nodo_por_xy[v_xy]
                if self._puede_moverse((x, y), v_xy):
                    self.grafo.agregar_arista(nid, vid, peso=1.0)
                if self._puede_moverse(v_xy, (x, y)):
                    self.grafo.agregar_arista(vid, nid, peso=1.0)

    # --- construcción del grafo ---
    def construir_grafo(self, celdas_transitables: set[tuple[int, int]]) -> None:
        """Crea nodos PASILLO para cada (x, y) y conecta vecinos.
        Las celdas de racks NO deben estar acá."""
        for x, y in sorted(celdas_transitables):
            self._nodo_en(x, y, TipoNodo.PASILLO)
        self._conectar_vecinos()

    def agregar_pasillo(
        self,
        pasillo_id: str,
        x: int,
        y: int,
        ancho: int,
        alto: int,
        sentido: str,
    ) -> None:
        p = Pasillo(pasillo_id, x, y, ancho, alto, sentido)

        for cx, cy in p.celdas():
            if (cx, cy) in self._racks_ocupados:
                raise ValueError(
                    f"El pasillo {p.id} se solapa con un rack en ({cx},{cy})"
                )
            if (cx, cy) in self._sentido_por_celda:
                raise ValueError(
                    f"El pasillo {p.id} se solapa con otro pasillo en ({cx},{cy})"
                )

        self.pasillos[pasillo_id] = p
        for cx, cy in p.celdas():
            self._sentido_por_celda[(cx, cy)] = sentido

        # Reconstruir las aristas del grafo con los nuevos sentidos
        self.reconstruir_conexiones()

    def reconstruir_conexiones(self) -> None:
        """Limpia las aristas y las reconstruye según los sentidos actuales."""
        self.grafo.limpiar_aristas()
        self._conectar_vecinos()

    def sentido_de(self, x: int, y: int) -> str:
        """Sentido de la celda. AMBOS si no pertenece a ningún pasillo declarado."""
        return self._sentido_por_celda.get((x, y), "AMBOS")

    def _puede_moverse(self, u: tuple[int, int], v: tuple[int, int]) -> bool:
        """¿Puede el picker ir de u a v? Solo importa el sentido de u."""
        s = self.sentido_de(*u)
        if s == "AMBOS":
            return True
        dx = v[0] - u[0]
        dy = v[1] - u[1]
        if s == "N":
            return dy >= 0
        if s == "S":
            return dy <= 0
        if s == "E":
            return dx >= 0
        if s == "O":
            return dx <= 0
        return False

    # --- racks ---
    def agregar_rack(self, rack_id: str, x: int, y: int, niveles: int = 4) -> None:
        """Registra un rack como obstáculo físico. NO crea nodo en el grafo.
        La celda del rack no debe ser transitable."""
        if (x, y) in self._nodo_por_xy:
            raise ValueError(
                f"El rack {rack_id} en ({x}, {y}) choca con una celda transitable"
            )
        if (x, y) in self._racks_ocupados:
            raise ValueError(f"Ya hay un rack en ({x}, {y})")
        self.racks[rack_id] = Rack(rack_id, x, y, niveles)
        self._racks_ocupados.add((x, y))

    def _nodo_picking_de_rack(self, rack: Rack) -> Optional[int]:
        """Un rack se alcanza solo desde un pasillo vertical (mismo y, distinto x).
        Solo se consideran vecinos horizontales."""
        for dx in (-1, 1):
            vecino = self._nodo_por_xy.get((rack.x + dx, rack.y))
            if vecino is not None:
                return vecino
        return None

    # --- productos ---
    def agregar_producto(self, producto: Producto) -> None:
        if producto.rack_id not in self.racks:
            raise ValueError(
                f"El producto {producto.id} referencia rack inexistente: {producto.rack_id}"
            )

        # Normalizar el nombre para el índice (el Trie también normaliza)
        nombre_normalizado = producto.nombre.lower()

        # Validar nombre único ANTES de mutar nada
        if nombre_normalizado in self.nombre_a_id:
            raise ValueError(
                f"Ya existe un producto con el nombre '{producto.nombre}' "
                f"(id: {self.nombre_a_id[nombre_normalizado]})"
            )

        rack = self.racks[producto.rack_id]
        nodo = self._nodo_picking_de_rack(rack)
        if nodo is None:
            raise ValueError(
                f"El rack {rack.id} en ({rack.x}, {rack.y}) no tiene pasillo adyacente"
            )

        producto.nodo_picking = nodo
        self.productos[producto.id] = producto

        trie_insert(self.trie_nombres, producto.nombre)
        self.nombre_a_id[nombre_normalizado] = producto.id

    def buscar_por_prefijo(self, prefix: str) -> list[Producto]:
        """
        Devuelve los productos cuyos nombres empiezan con `prefix`.

        Usa el Trie para resolver la búsqueda en O(k + N), donde k es la
        longitud del prefijo y N la cantidad de resultados.

        Args:
            prefix (str): Prefijo a buscar. Es case-insensitive.

        Returns:
            list[Producto]: Productos que coinciden. Lista vacía si no hay.
        """
        if not prefix:
            return []

        nombres = to_python_list(autocomplete(self.trie_nombres, prefix))
        return [self.productos[self.nombre_a_id[n]] for n in nombres]

    # --- zonas y puertas ---
    def agregar_zona_despacho(
        self, zona_id: str, p1: tuple[int, int], p2: tuple[int, int]
    ) -> int:
        cx = (p1[0] + p2[0]) // 2
        cy = (p1[1] + p2[1]) // 2
        nid = self._nodo_en(cx, cy, TipoNodo.DESPACHO)
        self.zonas[zona_id] = ZonaDespacho(zona_id, p1, p2, nid)
        return nid

    def agregar_puerta(self, puerta_id: str, x: int, y: int, tipo: str) -> int:
        nid = self._nodo_en(x, y, TipoNodo.PUERTA)
        self.puertas[puerta_id] = Puerta(puerta_id, Posicion(x, y), tipo, nid)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            vecino = self._nodo_por_xy.get((x + dx, y + dy))
            if vecino is not None:
                self.grafo.agregar_arista(nid, vecino, peso=1.0)
        return nid
