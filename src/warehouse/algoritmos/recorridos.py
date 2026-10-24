from dataclasses import dataclass
from time import perf_counter

from warehouse.algoritmos.distancias import CacheDistancias
from warehouse.dominio.wave import Wave
from warehouse.warehouse.warehouse import Warehouse


@dataclass
class ResultadoRecorrido:
    estrategia: str
    orden_paradas: list[int]
    camino_completo: list[int]
    distancia_total: float
    nodos_visitados: int
    aristas_recorridas: int
    tiempo_segundos: float
    indices_de_paradas: list[int]


# --- helpers ---


def _nodo_despacho(warehouse: Warehouse, zona_despacho_id: str | None) -> int:
    if zona_despacho_id is None:
        if not warehouse.zonas:
            raise ValueError("El warehouse no tiene zonas de despacho")
        zona = next(iter(warehouse.zonas.values()))
    else:
        if zona_despacho_id not in warehouse.zonas:
            raise ValueError(f"No existe la zona de despacho: {zona_despacho_id}")
        zona = warehouse.zonas[zona_despacho_id]
    return zona.nodo_representativo


def _paradas_de_wave(wave: Wave, warehouse: Warehouse) -> list[int]:
    paradas: list[int] = []
    vistos: set[int] = set()
    for pedido in wave.pedidos:
        for item in pedido.items:
            pid = item.producto_id
            if pid not in warehouse.productos:
                raise ValueError(
                    f"El pedido {pedido.id} referencia producto inexistente: {pid}"
                )
            nodo = warehouse.productos[pid].nodo_picking
            if nodo not in vistos:
                vistos.add(nodo)
                paradas.append(nodo)
    return paradas


def _armar_camino(secuencia: list[int], cache: CacheDistancias):
    if len(secuencia) < 2:
        return list(secuencia), 0.0, []
    camino_total: list[int] = []
    distancia_total = 0.0
    indices_destino: list[int] = []
    for i in range(len(secuencia) - 1):
        origen, destino = secuencia[i], secuencia[i + 1]
        sub = cache.camino(origen, destino)
        if not sub:
            raise ValueError(f"No hay camino entre los nodos {origen} y {destino}")
        if camino_total:
            camino_total.extend(sub[1:])
        else:
            camino_total.extend(sub)
        distancia_total += cache.distancia(origen, destino)
        indices_destino.append(len(camino_total) - 1)
    return camino_total, distancia_total, indices_destino


# --- estrategias (ambas aceptan inicio y fin arbitrarios) ---


def _estrategia_orden_pedidos(
    wave, warehouse, nodo_inicio: int, nodo_fin: int, cache
) -> ResultadoRecorrido:
    t0 = perf_counter()
    paradas = _paradas_de_wave(wave, warehouse)
    secuencia = [nodo_inicio] + paradas + [nodo_fin]
    camino, distancia, indices = _armar_camino(secuencia, cache)
    t1 = perf_counter()
    return ResultadoRecorrido(
        estrategia="orden_pedidos",
        orden_paradas=paradas,
        camino_completo=camino,
        distancia_total=distancia,
        nodos_visitados=len(camino),
        aristas_recorridas=max(0, len(camino) - 1),
        tiempo_segundos=t1 - t0,
        indices_de_paradas=indices[: len(paradas)],
    )


def _estrategia_vecino_mas_cercano(
    wave, warehouse, nodo_inicio: int, nodo_fin: int, cache
) -> ResultadoRecorrido:
    t0 = perf_counter()
    paradas = _paradas_de_wave(wave, warehouse)

    if not paradas:
        camino, distancia, _ = _armar_camino([nodo_inicio, nodo_fin], cache)
        t1 = perf_counter()
        return ResultadoRecorrido(
            estrategia="vecino_mas_cercano",
            orden_paradas=[],
            camino_completo=camino,
            distancia_total=distancia,
            nodos_visitados=len(camino),
            aristas_recorridas=max(0, len(camino) - 1),
            tiempo_segundos=t1 - t0,
            indices_de_paradas=[],
        )

    pendientes = set(paradas)
    secuencia = [nodo_inicio]
    actual = nodo_inicio
    while pendientes:
        mejor = None
        mejor_dist = float("inf")
        for candidato in pendientes:
            d = cache.distancia(actual, candidato)
            if d < mejor_dist:
                mejor_dist = d
                mejor = candidato
        if mejor is None or mejor_dist == float("inf"):
            raise ValueError(f"Hay paradas inalcanzables desde el nodo {actual}")
        secuencia.append(mejor)
        pendientes.remove(mejor)
        actual = mejor
    secuencia.append(nodo_fin)

    camino, distancia, indices = _armar_camino(secuencia, cache)
    t1 = perf_counter()
    return ResultadoRecorrido(
        estrategia="vecino_mas_cercano",
        orden_paradas=secuencia[1:-1],
        camino_completo=camino,
        distancia_total=distancia,
        nodos_visitados=len(camino),
        aristas_recorridas=max(0, len(camino) - 1),
        tiempo_segundos=t1 - t0,
        indices_de_paradas=indices[: len(secuencia) - 2],
    )


# --- API pública ---

ESTRATEGIAS = {
    "orden_pedidos": _estrategia_orden_pedidos,
    "vecino_mas_cercano": _estrategia_vecino_mas_cercano,
}


def recorrer_wave(
    wave: Wave,
    warehouse: Warehouse,
    zona_despacho_id: str | None = None,
    estrategia: str = "orden_pedidos",
    nodo_inicio: int | None = None,
    nodo_fin: int | None = None,
) -> ResultadoRecorrido:
    """Calcula el recorrido para preparar una wave.

    Si `nodo_inicio` / `nodo_fin` son None, usan la zona de despacho.
    Si se pasan, el recorrido empieza/termina en esos nodos.
    """
    if estrategia not in ESTRATEGIAS:
        raise ValueError(
            f"Estrategia desconocida: {estrategia}. "
            f"Disponibles: {list(ESTRATEGIAS.keys())}"
        )
    nodo_despacho = _nodo_despacho(warehouse, zona_despacho_id)
    inicio = nodo_inicio if nodo_inicio is not None else nodo_despacho
    fin = nodo_fin if nodo_fin is not None else nodo_despacho
    cache = CacheDistancias(warehouse.grafo)
    return ESTRATEGIAS[estrategia](wave, warehouse, inicio, fin, cache)
