from warehouse.estructuras.grafo import Grafo
from warehouse.estructuras.minheap import MinHeap


def dijkstra(
    grafo: Grafo, origen: int
) -> tuple[dict[int, float], dict[int, int | None]]:
    """
    Dijkstra desde un nodo origen.

    Devuelve:
      - distancias: dict[nodo_id, distancia mínima desde origen]
      - predecesores: dict[nodo_id, nodo_anterior en el camino óptimo o None]

    Usa MinHeap (TAD propio) como cola de prioridad.
    Complejidad: O((V + E) log V). Espacio: O(V).
    """
    if not grafo.contiene(origen):
        raise KeyError(f"Nodo {origen} no existe en el grafo")

    distancias: dict[int, float] = {origen: 0.0}
    predecesores: dict[int, int | None] = {origen: None}
    visitados: set[int] = set()

    heap = MinHeap()
    heap.enqueue(origen, 0.0)

    while not heap.is_empty():
        actual = heap.dequeue()
        if actual is None or actual in visitados:
            continue
        visitados.add(actual)

        for arista in grafo.vecinos(actual):
            if arista.destino in visitados:
                continue
            nueva_dist = distancias[actual] + arista.peso
            if nueva_dist < distancias.get(arista.destino, float("inf")):
                distancias[arista.destino] = nueva_dist
                predecesores[arista.destino] = actual
                heap.enqueue(arista.destino, nueva_dist)

    return distancias, predecesores


def camino_mas_corto(
    grafo: Grafo, origen: int, destino: int
) -> tuple[list[int], float]:
    """
    Devuelve (lista_de_nodos, distancia_total) del camino más corto
    desde origen hasta destino. Si no hay camino, devuelve ([], inf).
    """
    distancias, predecesores = dijkstra(grafo, origen)
    if destino not in distancias:
        return [], float("inf")

    camino: list[int] = []
    actual: int | None = destino
    while actual is not None:
        camino.append(actual)
        actual = predecesores[actual]
    camino.reverse()

    return camino, distancias[destino]


def distancia(grafo: Grafo, origen: int, destino: int) -> float:
    """Distancia mínima entre dos nodos. inf si no hay camino."""
    distancias, _ = dijkstra(grafo, origen)
    return distancias.get(destino, float("inf"))
