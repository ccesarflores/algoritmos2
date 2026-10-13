"""
Módulo bfs.py
Algoritmo BFS (Breadth-First Search) sobre el Grafo del proyecto.

Traducción directa del pseudocódigo de Cormen (Introduction to
Algorithms, 3ra ed., p. 595), con las siguientes particularidades:
    - Los vértices son enteros 0..n-1, así que se usan TRES arrays
      paralelos (color, dist, parent) en lugar de un único objeto Vertex.
    - La cola auxiliar es el TAD Cola (LinkedList) del proyecto.

Complejidad:
    - Tiempo:  O(V + E)
    - Espacio: O(V)
"""

from warehouse.estructuras.cola import dequeue, enqueue
from warehouse.estructuras.grafo import Grafo
from warehouse.estructuras.linkedlist import LinkedList

WHITE = 0  # no descubierto
GRAY = 1  # descubierto, en la cola
BLACK = 2  # procesado


def bfs(grafo: Grafo, origen: int) -> tuple[list[int], list[float], list[int | None]]:
    """
    Recorre el grafo en anchura desde `origen`.

    Args:
        grafo (Grafo): Grafo con vértices 0..n-1.
        origen (int): Vértice desde donde arranca el BFS.

    Returns:
        tuple: (color, dist, parent), tres listas de tamaño n.
            - color[v]: WHITE / GRAY / BLACK al finalizar.
            - dist[v]:  distancia en aristas desde `origen`, o inf si no
                        es alcanzable.
            - parent[v]: predecesor en el árbol BFS, o None si es raíz
                         o inalcanzable.
    """
    n = len(grafo)

    color: list[int] = [WHITE] * n
    dist: list[float] = [float("inf")] * n
    parent: list[int | None] = [None] * n

    color[origen] = GRAY
    dist[origen] = 0
    parent[origen] = None

    cola: LinkedList[int] = LinkedList()
    enqueue(cola, origen)

    while cola.head is not None:
        u = dequeue(cola)
        if u is None:
            break

        for arista in grafo.vecinos(u):
            v = arista.destino
            if color[v] == WHITE:
                color[v] = GRAY
                dist[v] = dist[u] + 1
                parent[v] = u
                enqueue(cola, v)

        color[u] = BLACK

    return color, dist, parent


def camino_mas_corto(
    parent: list[int | None], origen: int, destino: int
) -> list[int] | None:
    """
    Reconstruye el camino más corto desde `origen` hasta `destino` usando
    el árbol BFS devuelto por `bfs()`.

    Returns:
        list[int] | None: Lista [origen, ..., destino], o None si no hay
                          camino.
    """
    if parent[destino] is None and destino != origen:
        return None

    camino: list[int] = []
    actual: int | None = destino
    while actual is not None:
        camino.append(actual)
        actual = parent[actual]

    camino.reverse()
    return camino
