# tests/test_generador_waves.py
import pytest

from warehouse.dominio.estado_pedido import EstadoPedido
from warehouse.dominio.estado_wave import EstadoWave
from warehouse.dominio.pedido import Pedido
from warehouse.dominio.producto import Producto
from warehouse.generacion.generador import ConfigGeneracion, generar_escenario
from warehouse.warehouse.warehouse import Warehouse
from warehouse.waves.generador_waves import EstrategiaWaves, generar_waves


def _pedido(pid: str, prioridad: int, items: dict) -> Pedido:
    p = Pedido(id=pid, prioridad=prioridad)
    for prod, cant in items.items():
        p.agregar_item(prod, cant)
    return p


# --- estrategia PRIORIDAD ---


def test_prioridad_agrupa_por_capacidad():
    esc = generar_escenario(ConfigGeneracion(seed=1, n_pedidos=5))
    waves = generar_waves(
        esc.pedidos,
        esc.warehouse,
        max_pedidos=2,
        max_productos=100,
        max_peso_kg=500.0,
        estrategia=EstrategiaWaves.PRIORIDAD,
    )
    assert len(waves) == 3
    assert [w.cantidad_pedidos() for w in waves] == [2, 2, 1]


def test_prioridad_empieza_con_el_mas_prioritario():
    esc = generar_escenario(ConfigGeneracion(seed=1, n_pedidos=5))
    waves = generar_waves(
        esc.pedidos,
        esc.warehouse,
        max_pedidos=3,
        max_productos=100,
        max_peso_kg=500.0,
        estrategia=EstrategiaWaves.PRIORIDAD,
    )
    mas_prioritario = max(esc.pedidos, key=lambda p: (p.prioridad, -int(p.id[3:])))
    assert waves[0].pedidos[0].id == mas_prioritario.id


def test_todos_los_pedidos_quedan_en_alguna_wave():
    esc = generar_escenario(
        ConfigGeneracion(seed=1, n_pedidos=10, max_productos_por_pedido=2)
    )
    waves = generar_waves(
        esc.pedidos,
        esc.warehouse,
        max_pedidos=3,
        max_productos=50,
        max_peso_kg=500.0,
        estrategia=EstrategiaWaves.PRIORIDAD,
    )
    ids = {p.id for w in waves for p in w.pedidos}
    assert ids == {p.id for p in esc.pedidos}


def test_waves_cerradas_y_pedidos_en_wave():
    esc = generar_escenario(ConfigGeneracion(seed=1, n_pedidos=5))
    waves = generar_waves(
        esc.pedidos,
        esc.warehouse,
        max_pedidos=2,
        max_productos=50,
        max_peso_kg=500.0,
        estrategia=EstrategiaWaves.PRIORIDAD,
    )
    for w in waves:
        assert w.estado == EstadoWave.CERRADA
        for p in w.pedidos:
            assert p.estado == EstadoPedido.EN_WAVE


# --- estrategia PRIORIDAD_Y_CERCANIA ---


def test_cercania_prefiere_pedidos_vecinos():
    """P1 (semilla) y P3 comparten producto cercano; P2 está lejos.
    La cercanía debe meter P3 junto a P1 antes que P2."""
    w = Warehouse(10, 3)
    transitables = {(x, y) for x in range(10) for y in range(3)}
    transitables -= {(1, 1), (2, 1), (8, 1), (9, 1)}
    w.construir_grafo(transitables)
    w.agregar_zona_despacho("A", (0, 0), (0, 0))

    w.agregar_rack("R1", 1, 1, 2, 1)
    w.agregar_rack("R2", 8, 1, 2, 1)

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
            x=8,
            y=1,
            z=1,
            cantidad_disponible=10,
            peso_kg=1.0,
        )
    )

    p1 = _pedido("P1", 5, {"PA": 1})  # semilla
    p2 = _pedido("P2", 3, {"PB": 1})  # lejos
    p3 = _pedido("P3", 3, {"PA": 1})  # cerca

    waves = generar_waves(
        [p1, p2, p3],
        w,
        max_pedidos=2,
        max_productos=10,
        max_peso_kg=500.0,
        estrategia=EstrategiaWaves.PRIORIDAD_Y_CERCANIA,
    )

    assert len(waves) == 2
    assert {p.id for p in waves[0].pedidos} == {"P1", "P3"}
    assert {p.id for p in waves[1].pedidos} == {"P2"}


def test_cercania_misma_cantidad_de_pedidos_que_prioridad():
    esc1 = generar_escenario(ConfigGeneracion(seed=42, n_pedidos=10))
    esc2 = generar_escenario(ConfigGeneracion(seed=42, n_pedidos=10))

    waves_p = generar_waves(
        esc1.pedidos, esc1.warehouse, 3, 50, 500.0, EstrategiaWaves.PRIORIDAD
    )
    waves_c = generar_waves(
        esc2.pedidos, esc2.warehouse, 3, 50, 500.0, EstrategiaWaves.PRIORIDAD_Y_CERCANIA
    )

    assert sum(w.cantidad_pedidos() for w in waves_p) == 10
    assert sum(w.cantidad_pedidos() for w in waves_c) == 10


# --- errores ---


def test_estrategia_invalida():
    esc = generar_escenario(ConfigGeneracion(seed=1, n_pedidos=2))
    with pytest.raises(ValueError, match="Estrategia"):
        generar_waves(esc.pedidos, esc.warehouse, 3, 50, 500.0, "no_existe")


def test_pedido_demasiado_grande_falla():
    """Si un pedido no cabe ni en una wave vacía, ValueError."""
    w = Warehouse(3, 3)
    transitables = {(x, y) for x in range(3) for y in range(3)}
    transitables -= {(1, 1), (2, 1)}
    w.construir_grafo(transitables)
    w.agregar_zona_despacho("A", (0, 0), (0, 0))
    w.agregar_rack("R1", 1, 1, 2, 1)

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

    p = _pedido("P1", 3, {"PA": 100})

    with pytest.raises(ValueError, match="no cabe"):
        generar_waves([p], w, max_pedidos=5, max_productos=10, max_peso_kg=500.0)
