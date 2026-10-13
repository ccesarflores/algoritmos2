from dataclasses import dataclass
from typing import Optional

from warehouse.dominio.posicion import Posicion
from warehouse.dominio.tipo_nodo import TipoNodo
from warehouse.estructuras.lista_adyacencia import ListaAdyacencia


@dataclass
class Nodo:
    id: int
    posicion: Posicion
    tipo: TipoNodo
    producto_id: Optional[str] = None


@dataclass
class Arista:
    origen: int
    destino: int
    peso: float = 1.0


class Grafo:
    """
    Grafo con lista de adyacencia.

    Los nodos guardan metadatos del dominio (posición, tipo, producto).
    La adyacencia se delega a `ListaAdyacencia`, que soporta grafos
    dirigidos y no dirigidos.
    """

    def __init__(self, es_dirigido: bool = False) -> None:
        self.es_dirigido = es_dirigido
        self._nodos: dict[int, Nodo] = {}
        self._lista = ListaAdyacencia(n=0, es_dirigido=es_dirigido)
        self._pesos: dict[tuple[int, int], float] = {}

    # --- construcción ---
    def agregar_nodo(
        self,
        posicion: Posicion,
        tipo: TipoNodo,
        producto_id: Optional[str] = None,
    ) -> int:
        nid = len(self._nodos)
        self._nodos[nid] = Nodo(nid, posicion, tipo, producto_id)
        self._lista.agregar_vertice()
        return nid

    def agregar_arista(self, u: int, v: int, peso: float = 1.0) -> None:
        self._lista.agregar_arista(u, v)
        self._pesos[(u, v)] = peso
        if not self.es_dirigido:
            self._pesos[(v, u)] = peso

    # --- consulta ---
    def nodo(self, nid: int) -> Nodo:
        return self._nodos[nid]

    def vecinos(self, nid: int) -> list[Arista]:
        return [
            Arista(nid, v, self._pesos.get((nid, v), 1.0))
            for v in self._lista.iterar_vecinos(nid)
        ]

    def peso(self, u: int, v: int) -> float:
        if (u, v) not in self._pesos:
            raise KeyError(f"No existe arista {u}->{v}")
        return self._pesos[(u, v)]

    def nodos(self):
        return self._nodos.values()

    def contiene(self, nid: int) -> bool:
        return nid in self._nodos

    def __len__(self) -> int:
        return len(self._nodos)
