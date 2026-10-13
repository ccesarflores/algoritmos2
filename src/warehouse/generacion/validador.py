from warehouse.algoritmos.bfs import bfs
from warehouse.warehouse.escenario import Escenario


def validar_escenario(escenario: Escenario) -> None:
    """Lanza ValueError si el escenario no cumple los invariantes.
    Asume Modelo B: racks son obstáculos, el picker camina solo por pasillos."""

    w = escenario.warehouse

    # 1. debe haber al menos una zona de despacho
    if not w.zonas:
        raise ValueError("El escenario no tiene zonas de despacho")

    # 2. cada rack debe tener al menos un pasillo horizontal adyacente
    for rack in w.racks.values():
        tiene_pasillo = any((rack.x + dx, rack.y) in w._nodo_por_xy for dx in (-1, 1))
        if not tiene_pasillo:
            raise ValueError(
                f"El rack {rack.id} en ({rack.x}, {rack.y}) "
                f"no tiene pasillo horizontal adyacente"
            )

    # 3. BFS desde la primera zona de despacho alcanza todos los nodos de picking
    zona = next(iter(w.zonas.values()))

    _, dist, _ = bfs(w.grafo, zona.nodo_representativo)

    for prod in w.productos.values():
        if dist[prod.nodo_picking] == float("inf"):
            raise ValueError(...)

    # 4. cada pedido referencia productos existentes
    for pedido in escenario.pedidos:
        for item in pedido.items:
            if item.producto_id not in w.productos:
                raise ValueError(
                    f"El pedido {pedido.id} referencia "
                    f"producto inexistente: {item.producto_id}"
                )
