from warehouse.estructuras.cola import dequeue, enqueue
from warehouse.estructuras.grafo import Grafo
from warehouse.estructuras.linkedlist import LinkedList


def bfs_alcanzables(grafo: Grafo, origen: int) -> set[int]:
    """
    BFS desde un nodo. Devuelve el conjunto de nodos alcanzables (incluye origen).

    Usa Cola (LinkedList) como estructura de exploración.
    Complejidad: O(V + E) tiempo, O(V) espacio.
    """
    if not grafo.contiene(origen):
        raise KeyError(f"Nodo {origen} no existe en el grafo")

    visitados: set[int] = {origen}
    cola: LinkedList[int] = LinkedList()
    enqueue(cola, origen)

    while cola.head is not None:
        actual = dequeue(cola)
        if actual is None:
            break
        for arista in grafo.vecinos(actual):
            if arista.destino not in visitados:
                visitados.add(arista.destino)
                enqueue(cola, arista.destino)

    return visitados
