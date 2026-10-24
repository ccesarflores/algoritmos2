from enum import Enum
from typing import TYPE_CHECKING

from warehouse.algoritmos.distancias import CacheDistancias
from warehouse.dominio.pedido import Pedido
from warehouse.dominio.wave import Wave
from warehouse.warehouse.warehouse import Warehouse

if TYPE_CHECKING:
    from warehouse.dominio.producto import Producto


class EstrategiaWaves(Enum):
    PRIORIDAD = "prioridad"
    PRIORIDAD_Y_CERCANIA = "prioridad_y_cercania"


# --- helpers ---


def _puede_agregar_con_peso(
    wave: Wave, pedido: Pedido, productos: dict[str, "Producto"], max_peso_kg: float
) -> bool:
    """Valida capacidad estándar + peso."""
    if not wave.puede_agregar(pedido):
        return False

    peso_actual = wave.peso_total(productos)
    peso_nuevo = sum(
        productos[item.producto_id].peso_kg * item.cantidad for item in pedido.items
    )
    return (peso_actual + peso_nuevo) <= max_peso_kg


def _productos_de_wave(wave: Wave) -> set[str]:
    ids: set[str] = set()
    for p in wave.pedidos:
        ids |= p.productos_ids()
    return ids


def _distancia_minima_pedido_wave(
    pedido: Pedido,
    wave: Wave,
    warehouse: Warehouse,
    cache: CacheDistancias,
) -> float:
    productos_wave = _productos_de_wave(wave)
    if not productos_wave:
        return float("inf")

    mejor = float("inf")
    for pid_ped in pedido.productos_ids():
        nodo_ped = warehouse.productos[pid_ped].nodo_picking
        for pid_wave in productos_wave:
            nodo_wave = warehouse.productos[pid_wave].nodo_picking
            d = cache.distancia(nodo_ped, nodo_wave)
            if d < mejor:
                mejor = d
    return mejor


# --- estrategias ---


def _generar_waves_prioridad(
    pedidos: list[Pedido],
    warehouse: Warehouse,
    max_pedidos: int,
    max_productos: int,
    max_peso_kg: float,
) -> list[Wave]:
    pendientes = sorted(pedidos, key=lambda p: (-p.prioridad, p.id))
    waves: list[Wave] = []
    contador = 1

    while pendientes:
        wave = Wave(
            id=f"W{contador:03d}",
            max_pedidos=max_pedidos,
            max_productos=max_productos,
            max_peso_kg=max_peso_kg,
        )

        primero = pendientes.pop(0)

        # Validamos si el pedido semilla entra en una wave vacía (incluyendo peso)
        peso_primero = sum(
            warehouse.productos[it.producto_id].peso_kg * it.cantidad
            for it in primero.items
        )
        if (
            primero.cantidad_total_productos() > max_productos
            or peso_primero > max_peso_kg
        ):
            raise ValueError(f"El pedido {primero.id} no cabe ni en una wave vacía.")

        wave.agregar_pedido(primero)

        i = 0
        while i < len(pendientes):
            if _puede_agregar_con_peso(
                wave, pendientes[i], warehouse.productos, max_peso_kg
            ):
                wave.agregar_pedido(pendientes.pop(i))
            else:
                i += 1

        wave.cerrar()
        waves.append(wave)
        contador += 1

    return waves


def _generar_waves_prioridad_cercania(
    pedidos: list[Pedido],
    warehouse: Warehouse,
    max_pedidos: int,
    max_productos: int,
    max_peso_kg: float,
) -> list[Wave]:
    pendientes = sorted(pedidos, key=lambda p: (-p.prioridad, p.id))
    cache = CacheDistancias(warehouse.grafo)
    waves: list[Wave] = []
    contador = 1

    while pendientes:
        wave = Wave(
            id=f"W{contador:03d}",
            max_pedidos=max_pedidos,
            max_productos=max_productos,
            max_peso_kg=max_peso_kg,
        )

        semilla = pendientes.pop(0)

        # Validamos si la semilla entra (incluyendo peso)
        peso_semilla = sum(
            warehouse.productos[it.producto_id].peso_kg * it.cantidad
            for it in semilla.items
        )
        if (
            semilla.cantidad_total_productos() > max_productos
            or peso_semilla > max_peso_kg
        ):
            raise ValueError(f"El pedido {semilla.id} no cabe ni en una wave vacía.")

        wave.agregar_pedido(semilla)

        while True:
            mejor_idx: int | None = None
            mejor_dist = float("inf")
            mejor_prioridad = -1

            for i, candidato in enumerate(pendientes):
                if not _puede_agregar_con_peso(
                    wave, candidato, warehouse.productos, max_peso_kg
                ):
                    continue
                d = _distancia_minima_pedido_wave(candidato, wave, warehouse, cache)
                if d < mejor_dist or (
                    d == mejor_dist and candidato.prioridad > mejor_prioridad
                ):
                    mejor_idx = i
                    mejor_dist = d
                    mejor_prioridad = candidato.prioridad

            if mejor_idx is None:
                break
            wave.agregar_pedido(pendientes.pop(mejor_idx))

        wave.cerrar()
        waves.append(wave)
        contador += 1

    return waves


# --- API pública ---


def generar_waves(
    pedidos: list[Pedido],
    warehouse: Warehouse,
    max_pedidos: int,
    max_productos: int,
    max_peso_kg: float = 500.0,
    estrategia: EstrategiaWaves = EstrategiaWaves.PRIORIDAD_Y_CERCANIA,
) -> list[Wave]:
    if estrategia == EstrategiaWaves.PRIORIDAD:
        return _generar_waves_prioridad(
            pedidos, warehouse, max_pedidos, max_productos, max_peso_kg
        )
    if estrategia == EstrategiaWaves.PRIORIDAD_Y_CERCANIA:
        return _generar_waves_prioridad_cercania(
            pedidos, warehouse, max_pedidos, max_productos, max_peso_kg
        )
    raise ValueError(f"Estrategia desconocida: {estrategia}")
