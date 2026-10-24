import pytest

from warehouse.algoritmos.recorridos import recorrer_wave
from warehouse.dominio.pedido import Pedido
from warehouse.dominio.producto import Producto
from warehouse.dominio.wave import Wave
from warehouse.simulacion.estado import EstadoSimulacion
from warehouse.warehouse.warehouse import Warehouse


def _escenario_simple():
    w = Warehouse(10, 3)
    transitables = {(x, y) for x in range(10) for y in range(3)}
    transitables -= {(1, 1), (5, 1)}
    w.construir_grafo(transitables)
    w.agregar_zona_despacho("A", (0, 0), (0, 0))
    w.agregar_rack("R1", 1, 1)
    w.agregar_rack("R2", 5, 1)
    w.agregar_producto(Producto(id="PA", nombre="A", rack_id="R1", z=1, stock=10))
    w.agregar_producto(Producto(id="PB", nombre="B", rack_id="R2", z=1, stock=10))

    wave = Wave(id="W1", max_pedidos=2, max_productos=10)
    p1 = Pedido(id="P1", prioridad=3)
    p1.agregar_item("PA", 1)
    p2 = Pedido(id="P2", prioridad=3)
    p2.agregar_item("PB", 1)
    wave.agregar_pedido(p1)
    wave.agregar_pedido(p2)
    wave.cerrar()
    return w, wave


def test_estado_inicial():
    w, wave = _escenario_simple()
    r = recorrer_wave(wave, w, estrategia="orden_pedidos")
    estado = EstadoSimulacion.desde_wave(wave, r, w)

    assert estado.indice_actual == 0
    assert estado.nodo_actual == r.camino_completo[0]  # despacho
    assert estado.productos_recogidos() == set()
    assert estado.productos_pendientes() == {"PA", "PB"}
    assert not estado.al_final
    assert not estado.completada


def test_avanzar_hasta_el_final():
    w, wave = _escenario_simple()
    r = recorrer_wave(wave, w, estrategia="orden_pedidos")
    estado = EstadoSimulacion.desde_wave(wave, r, w)

    pasos = 0
    while estado.avanzar():
        pasos += 1

    assert estado.al_final
    # Cada movimiento consume 1 paso. Cada parada consume z pasos de espera.
    esperas_totales = sum(estado.espera_por_nodo.values())
    assert pasos == len(r.camino_completo) - 1 + esperas_totales
    assert estado.productos_recogidos() == {"PA", "PB"}
    assert estado.completada


def test_avanzar_en_el_final_devuelve_false():
    w, wave = _escenario_simple()
    r = recorrer_wave(wave, w, estrategia="orden_pedidos")
    estado = EstadoSimulacion.desde_wave(wave, r, w)

    while estado.avanzar():
        pass
    assert estado.avanzar() is False


def test_retroceder():
    w, wave = _escenario_simple()
    r = recorrer_wave(wave, w, estrategia="orden_pedidos")
    estado = EstadoSimulacion.desde_wave(wave, r, w)

    for _ in range(3):
        estado.avanzar()
    i_antes = estado.indice_actual
    assert estado.retroceder() is True
    assert estado.indice_actual == i_antes - 1


def test_retroceder_al_inicio_devuelve_false():
    w, wave = _escenario_simple()
    r = recorrer_wave(wave, w, estrategia="orden_pedidos")
    estado = EstadoSimulacion.desde_wave(wave, r, w)
    assert estado.retroceder() is False
    assert estado.indice_actual == 0


def test_reiniciar():
    w, wave = _escenario_simple()
    r = recorrer_wave(wave, w, estrategia="orden_pedidos")
    estado = EstadoSimulacion.desde_wave(wave, r, w)

    while estado.avanzar():
        pass
    estado.reiniciar()
    assert estado.indice_actual == 0
    assert estado.productos_recogidos() == set()


def test_productos_recogidos_al_pasar_por_nodo_de_picking():
    """Un producto se considera recogido recién cuando el picker terminó
    de esperar en la parada (no al llegar)."""
    w, wave = _escenario_simple()
    r = recorrer_wave(wave, w, estrategia="orden_pedidos")
    estado = EstadoSimulacion.desde_wave(wave, r, w)

    # Avanzar hasta que PA esté recogido. El bucle termina cuando
    # productos_recogidos() incluye PA (i.e. el picker ya esperó z pasos
    # en el nodo de picking).
    max_pasos = len(estado.camino) + sum(estado.espera_por_nodo.values())
    for _ in range(max_pasos):
        if "PA" in estado.productos_recogidos():
            break
        if not estado.avanzar():
            break

    assert "PA" in estado.productos_recogidos()


def test_completada_cuando_todos_los_productos_recogidos():
    w, wave = _escenario_simple()
    r = recorrer_wave(wave, w, estrategia="vecino_mas_cercano")
    estado = EstadoSimulacion.desde_wave(wave, r, w)

    while estado.avanzar():
        pass
    assert estado.completada
    assert estado.productos_pendientes() == set()


def test_no_recoge_producto_antes_de_dar_un_paso():
    """Si el picker arranca justo sobre una parada, el producto NO debe
    aparecer como recogido antes de dar el primer paso."""
    from warehouse.algoritmos.distancias import CacheDistancias
    from warehouse.algoritmos.recorridos import ResultadoRecorrido, _armar_camino

    w = Warehouse(10, 3)
    transitables = {(x, y) for x in range(10) for y in range(3)}
    transitables -= {(1, 1)}
    w.construir_grafo(transitables)
    w.agregar_zona_despacho("A", (0, 0), (0, 0))
    w.agregar_rack("R1", 1, 1)
    w.agregar_producto(Producto(id="PA", nombre="A", rack_id="R1", z=2, stock=10))

    wave = Wave(id="W1", max_pedidos=1, max_productos=10)
    p1 = Pedido(id="P1", prioridad=3)
    p1.agregar_item("PA", 1)
    wave.agregar_pedido(p1)
    wave.cerrar()

    nodo_pa = w.productos["PA"].nodo_picking
    despacho = w.zonas["A"].nodo_representativo

    # Recorrido que arranca SOBRE la parada (equivale a nodo_inicio == nodo_pa
    # en demo_completa.recorrer_wave_random con estrategia orden_pedidos)
    cache = CacheDistancias(w.grafo)
    camino, dist, idxs = _armar_camino([nodo_pa, nodo_pa, despacho], cache)
    resultado = ResultadoRecorrido(
        estrategia="orden_pedidos",
        orden_paradas=[nodo_pa],
        camino_completo=camino,
        distancia_total=dist,
        nodos_visitados=len(camino),
        aristas_recorridas=max(0, len(camino) - 1),
        tiempo_segundos=0.0,
        indices_de_paradas=idxs[:1],
    )

    estado = EstadoSimulacion.desde_wave(wave, resultado, w)

    # Estado inicial: en la parada, pero aún esperando → NO recogido
    assert estado.indice_actual == 0
    assert estado.espera_restante == 2  # z del producto
    assert "PA" not in estado.productos_recogidos()

    # Tras consumir la espera completa, recién ahí está recogido
    estado.avanzar()
    estado.avanzar()
    assert "PA" in estado.productos_recogidos()


def test_reset_reaplica_espera_inicial():
    """Reset también debe restaurar la espera inicial si el picker
    arranca sobre una parada."""
    from warehouse.algoritmos.distancias import CacheDistancias
    from warehouse.algoritmos.recorridos import ResultadoRecorrido, _armar_camino

    w = Warehouse(10, 3)
    transitables = {(x, y) for x in range(10) for y in range(3)}
    transitables -= {(1, 1)}
    w.construir_grafo(transitables)
    w.agregar_zona_despacho("A", (0, 0), (0, 0))
    w.agregar_rack("R1", 1, 1)
    w.agregar_producto(Producto(id="PA", nombre="A", rack_id="R1", z=2, stock=10))

    wave = Wave(id="W1", max_pedidos=1, max_productos=10)
    p1 = Pedido(id="P1", prioridad=3)
    p1.agregar_item("PA", 1)
    wave.agregar_pedido(p1)
    wave.cerrar()

    nodo_pa = w.productos["PA"].nodo_picking
    despacho = w.zonas["A"].nodo_representativo

    cache = CacheDistancias(w.grafo)
    camino, dist, idxs = _armar_camino([nodo_pa, nodo_pa, despacho], cache)
    resultado = ResultadoRecorrido(
        estrategia="orden_pedidos",
        orden_paradas=[nodo_pa],
        camino_completo=camino,
        distancia_total=dist,
        nodos_visitados=len(camino),
        aristas_recorridas=max(0, len(camino) - 1),
        tiempo_segundos=0.0,
        indices_de_paradas=idxs[:1],
    )

    estado = EstadoSimulacion.desde_wave(wave, resultado, w)

    # Estado inicial: sobre la parada, aún esperando → NO recogido
    assert estado.espera_restante == 2  # z del producto
    assert "PA" not in estado.productos_recogidos()

    # Consumir la espera completa (2 pasos)
    estado.avanzar()
    estado.avanzar()
    assert "PA" in estado.productos_recogidos()

    # Reset debe restaurar la espera inicial
    estado.reiniciar()
    assert estado.indice_actual == 0
    assert estado.espera_restante == 2
    assert "PA" not in estado.productos_recogidos()
