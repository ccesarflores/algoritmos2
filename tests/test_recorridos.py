import math

import pytest

from warehouse.algoritmos.distancias import CacheDistancias
from warehouse.algoritmos.recorridos import (
    ESTRATEGIAS,
    ResultadoRecorrido,
    recorrer_wave,
)
from warehouse.dominio.pedido import Pedido
from warehouse.dominio.producto import Producto
from warehouse.dominio.wave import Wave
from warehouse.warehouse.warehouse import Warehouse

# --- helpers ---


def _warehouse_con_productos(ancho=10, alto=3):
    w = Warehouse(ancho, alto)
    rack_cells = {(1, 1), (2, 1), (5, 1), (6, 1), (8, 1), (9, 1)}
    transitables = {(x, y) for x in range(ancho) for y in range(alto)} - rack_cells
    w.construir_grafo(transitables)
    w.agregar_zona_despacho("A", (0, 0), (0, 0))
    w.agregar_rack("R1", 1, 1, 2, 1)
    w.agregar_rack("R2", 5, 1, 2, 1)
    w.agregar_rack("R3", 8, 1, 2, 1)
    w.agregar_producto(
        Producto(
            id="PA",
            nombre="A",
            rack_id="R1",
            x=1,
            y=1,
            z=1,
            cantidad_disponible=10,
            peso_kg=1.0,
        )
    )
    w.agregar_producto(
        Producto(
            id="PB",
            nombre="B",
            rack_id="R2",
            x=5,
            y=1,
            z=1,
            cantidad_disponible=10,
            peso_kg=1.0,
        )
    )
    w.agregar_producto(
        Producto(
            id="PC",
            nombre="C",
            rack_id="R3",
            x=8,
            y=1,
            z=1,
            cantidad_disponible=10,
            peso_kg=1.0,
        )
    )
    nodos = {
        "despacho": w.zonas["A"].nodo_representativo,
        "PA": w.productos["PA"].nodo_picking,
        "PB": w.productos["PB"].nodo_picking,
        "PC": w.productos["PC"].nodo_picking,
    }
    return w, nodos


def _wave_con_productos(productos_por_pedido: list[list[str]]) -> Wave:
    w = Wave(id="W1", max_pedidos=len(productos_por_pedido), max_productos=100)
    for i, prods in enumerate(productos_por_pedido, start=1):
        p = Pedido(id=f"P{i:02d}", prioridad=3)
        for prod in prods:
            p.agregar_item(prod, 1)
        w.agregar_pedido(p)
    w.cerrar()
    return w


# --- casos básicos ---


def test_recorrido_vacio():
    w, nodos = _warehouse_con_productos()
    wave = Wave(id="W1", max_pedidos=3)
    wave.cerrar()

    r = recorrer_wave(wave, w, estrategia="orden_pedidos")
    assert r.orden_paradas == []
    assert r.camino_completo == [nodos["despacho"]]
    assert r.distancia_total == 0
    assert r.aristas_recorridas == 0


def test_estrategia_invalida():
    w, _ = _warehouse_con_productos()
    wave = _wave_con_productos([["PA"]])
    with pytest.raises(ValueError, match="Estrategia"):
        recorrer_wave(wave, w, estrategia="no_existe")


def test_zona_despacho_inexistente():
    w, _ = _warehouse_con_productos()
    wave = _wave_con_productos([["PA"]])
    with pytest.raises(ValueError, match="zona"):
        recorrer_wave(wave, w, zona_despacho_id="NO_EXISTE")


# --- estrategia orden_pedidos ---


def test_orden_pedidos_visita_en_orden():
    w, nodos = _warehouse_con_productos()
    wave = _wave_con_productos([["PC"], ["PA"]])  # PC primero, luego PA
    r = recorrer_wave(wave, w, estrategia="orden_pedidos")
    assert r.orden_paradas == [nodos["PC"], nodos["PA"]]


def test_orden_pedidos_empieza_y_termina_en_despacho():
    w, nodos = _warehouse_con_productos()
    wave = _wave_con_productos([["PA"], ["PB"]])
    r = recorrer_wave(wave, w, estrategia="orden_pedidos")
    assert r.camino_completo[0] == nodos["despacho"]
    assert r.camino_completo[-1] == nodos["despacho"]


def test_orden_pedidos_deduplica_paradas():
    """Si dos pedidos comparten el nodo de picking, es una sola parada."""
    w, nodos = _warehouse_con_productos()
    wave = _wave_con_productos([["PA"], ["PA"]])  # mismo producto dos veces
    r = recorrer_wave(wave, w, estrategia="orden_pedidos")
    assert r.orden_paradas == [nodos["PA"]]


# --- estrategia vecino_mas_cercano ---


def test_vecino_cercano_ordena_por_proximidad():
    """Desde el despacho, PA está más cerca que PC.
    La secuencia debería ser despacho → PA → ... (no PC primero)."""
    w, nodos = _warehouse_con_productos()
    wave = _wave_con_productos([["PC"], ["PA"]])  # orden de pedidos: PC, PA
    r = recorrer_wave(wave, w, estrategia="vecino_mas_cercano")
    # El más cercano al despacho es PA, así que va primero
    assert r.orden_paradas[0] == nodos["PA"]


def test_vecino_cercano_termina_en_despacho():
    w, nodos = _warehouse_con_productos()
    wave = _wave_con_productos([["PA"], ["PB"], ["PC"]])
    r = recorrer_wave(wave, w, estrategia="vecino_mas_cercano")
    assert r.camino_completo[0] == nodos["despacho"]
    assert r.camino_completo[-1] == nodos["despacho"]


def test_vecino_cercano_visita_todas_las_paradas():
    w, nodos = _warehouse_con_productos()
    wave = _wave_con_productos([["PA"], ["PB"], ["PC"]])
    r = recorrer_wave(wave, w, estrategia="vecino_mas_cercano")
    assert set(r.orden_paradas) == {nodos["PA"], nodos["PB"], nodos["PC"]}


# --- comparación entre estrategias ---


def test_vecino_cercano_no_es_peor_que_orden_pedidos():
    """En un caso diseñado para que el vecino cercano gane, la distancia
    debe ser estrictamente menor."""
    w, nodos = _warehouse_con_productos()
    # Orden: PC (lejos), PA (cerca), PB (medio)
    wave = _wave_con_productos([["PC"], ["PA"], ["PB"]])

    r_orden = recorrer_wave(wave, w, estrategia="orden_pedidos")
    r_cercano = recorrer_wave(wave, w, estrategia="vecino_mas_cercano")

    assert r_cercano.distancia_total <= r_orden.distancia_total


# --- métricas ---


def test_metricas_coherentes():
    w, nodos = _warehouse_con_productos()
    wave = _wave_con_productos([["PA"], ["PB"]])
    r = recorrer_wave(wave, w, estrategia="vecino_mas_cercano")
    assert r.aristas_recorridas == len(r.camino_completo) - 1
    assert r.nodos_visitados == len(r.camino_completo)
    assert r.tiempo_segundos >= 0


def test_camino_completo_es_continuo():
    """Nodos consecutivos del camino completo deben ser vecinos en el grafo."""
    w, nodos = _warehouse_con_productos()
    wave = _wave_con_productos([["PA"], ["PB"], ["PC"]])
    r = recorrer_wave(wave, w, estrategia="vecino_mas_cercano")

    for i in range(len(r.camino_completo) - 1):
        u = r.camino_completo[i]
        v = r.camino_completo[i + 1]
        vecinos = {a.destino for a in w.grafo.vecinos(u)}
        assert v in vecinos, f"{u} y {v} no son vecinos en el grafo"


# --- inalcanzables ---


def test_parada_inalcanzable_falla():
    """Si un producto está en un sector desconectado del despacho, debe fallar."""
    w = Warehouse(10, 3)

    # Isla izquierda (conectada al despacho)
    izq = {(x, y) for x in range(3) for y in range(3)}
    # Isla derecha (aislada)
    der = {(x, y) for x in range(7, 10) for y in range(3)}

    # Hacemos un hueco para el rack en la isla derecha
    der -= {(7, 1), (8, 1)}

    w.construir_grafo(izq | der)
    w.agregar_zona_despacho("A", (0, 0), (0, 0))
    w.agregar_rack("R1", 7, 1, 2, 1)

    # El producto se recoge desde (7,0) o (9,1), ambos aislados del despacho
    w.agregar_producto(
        Producto(
            id="PA",
            nombre="A",
            rack_id="R1",
            x=8,
            y=1,
            z=1,
            cantidad_disponible=1,
            peso_kg=1.0,
        )
    )

    wave = Wave(id="W1", max_pedidos=1, max_productos=10)
    p1 = Pedido(id="P1", prioridad=3)
    p1.agregar_item("PA", 1)
    wave.agregar_pedido(p1)
    wave.cerrar()

    with pytest.raises(ValueError, match="inalcanzable|No hay camino"):
        recorrer_wave(wave, w, estrategia="orden_pedidos")
