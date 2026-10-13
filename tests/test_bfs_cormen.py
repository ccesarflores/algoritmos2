from warehouse.estructuras.bfs import bfs, camino_mas_corto
from warehouse.warehouse.warehouse import Warehouse


def _grilla(n: int) -> Warehouse:
    w = Warehouse(n, n)
    w.construir_grafo({(x, y) for x in range(n) for y in range(n)})
    return w


def test_bfs_alcanza_toda_la_grilla():
    w = _grilla(3)
    color, dist, parent = bfs(w.grafo, 0)
    # Todos menos el origen tienen dist finita
    for v in range(len(w.grafo)):
        assert dist[v] != float("inf")


def test_bfs_distancias_correctas():
    w = _grilla(3)
    color, dist, parent = bfs(w.grafo, 0)
    esquina_op = w._nodo_por_xy[(2, 2)]
    assert dist[esquina_op] == 4  # 2 pasos en x + 2 en y


def test_bfs_origen_aislado():
    w = Warehouse(5, 5)
    w.construir_grafo({(0, 0), (4, 4)})  # no adyacentes
    n0 = w._nodo_por_xy[(0, 0)]
    n1 = w._nodo_por_xy[(4, 4)]

    color, dist, parent = bfs(w.grafo, n0)
    assert dist[n0] == 0
    assert dist[n1] == float("inf")
    assert parent[n1] is None


def test_bfs_camino_mas_corto():
    w = _grilla(3)
    color, dist, parent = bfs(w.grafo, 0)
    destino = w._nodo_por_xy[(2, 0)]
    camino = camino_mas_corto(parent, 0, destino)
    assert camino is not None
    assert camino[0] == 0
    assert camino[-1] == destino
    assert len(camino) == 3  # 2 aristas, 3 nodos


def test_bfs_camino_inexistente():
    w = Warehouse(5, 5)
    w.construir_grafo({(0, 0), (4, 4)})
    n0 = w._nodo_por_xy[(0, 0)]
    n1 = w._nodo_por_xy[(4, 4)]

    color, dist, parent = bfs(w.grafo, n0)
    camino = camino_mas_corto(parent, n0, n1)
    assert camino is None
