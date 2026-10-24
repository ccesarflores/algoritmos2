import pytest

from warehouse.generacion.generador import (
    ConfigGeneracion,
    _calcular_ancho,
    _patron_columnas,
    generar_escenario,
)
from warehouse.generacion.validador import validar_escenario


def test_ancho_calculado():
    cfg = ConfigGeneracion(n_bloques_racks=4, ancho_pasillo=1, ancho_bloque_racks=2)
    assert _calcular_ancho(cfg) == 13


def test_patron_columnas():
    cfg = ConfigGeneracion(n_bloques_racks=2, ancho_pasillo=1, ancho_bloque_racks=2)
    assert _patron_columnas(cfg) == ["P", "R", "R", "P", "R", "R", "P"]


def test_generacion_default_es_valida():
    cfg = ConfigGeneracion(seed=42)
    esc = generar_escenario(cfg)
    validar_escenario(esc)  # no debe lanzar


def test_geometria_default():
    cfg = ConfigGeneracion(seed=42)
    esc = generar_escenario(cfg)
    w = esc.warehouse
    # No hardcodear el ancho: derivarlo de la config.
    assert w.ancho == _calcular_ancho(cfg)
    assert w.alto == cfg.alto
    assert len(w.racks) > 0


def test_productos_generados():
    cfg = ConfigGeneracion(seed=42, productos_por_rack=2)
    esc = generar_escenario(cfg)
    n_racks = len(esc.warehouse.racks)
    assert n_racks > 0
    # 1 rack = exactamente 2 productos ocupando 2 niveles distintos
    assert len(esc.warehouse.productos) == n_racks * 2


def test_pedidos_generados():
    cfg = ConfigGeneracion(seed=42, n_pedidos=7, max_productos_por_pedido=3)
    esc = generar_escenario(cfg)
    assert len(esc.pedidos) == 7
    for ped in esc.pedidos:
        assert 1 <= len(ped.items) <= 3


def test_reproducibilidad_con_mismo_seed():
    cfg1 = ConfigGeneracion(seed=123)
    cfg2 = ConfigGeneracion(seed=123)
    e1 = generar_escenario(cfg1)
    e2 = generar_escenario(cfg2)

    assert e1.warehouse.ancho == e2.warehouse.ancho
    assert set(e1.warehouse.racks.keys()) == set(e2.warehouse.racks.keys())
    assert set(e1.warehouse.productos.keys()) == set(e2.warehouse.productos.keys())

    for pid in e1.warehouse.productos:
        p1 = e1.warehouse.productos[pid]
        p2 = e2.warehouse.productos[pid]
        assert p1.stock == p2.stock
        assert p1.rack_id == p2.rack_id
        assert p1.z == p2.z

    for ped1, ped2 in zip(e1.pedidos, e2.pedidos):
        assert ped1.prioridad == ped2.prioridad
        assert ped1.productos_ids() == ped2.productos_ids()


def test_seeds_distintos_dan_escenarios_distintos():
    e1 = generar_escenario(ConfigGeneracion(seed=1))
    e2 = generar_escenario(ConfigGeneracion(seed=2))
    # Al menos las prioridades deberían diferir en algún pedido
    prioridades_1 = [p.prioridad for p in e1.pedidos]
    prioridades_2 = [p.prioridad for p in e2.pedidos]
    assert prioridades_1 != prioridades_2


def test_todos_los_racks_tienen_pasillo_horizontal():
    cfg = ConfigGeneracion(seed=42)
    esc = generar_escenario(cfg)
    w = esc.warehouse
    for rack in w.racks.values():
        assert (rack.x - 1, rack.y) in w._nodo_por_xy or (
            rack.x + 1,
            rack.y,
        ) in w._nodo_por_xy


def test_config_invalida_falla():
    with pytest.raises(ValueError):
        ConfigGeneracion(n_bloques_racks=0)
    with pytest.raises(ValueError):
        ConfigGeneracion(alto=2)
    with pytest.raises(ValueError):
        ConfigGeneracion(stock_min=100, stock_max=10)


def test_pasillos_horizontales_intermedios():
    """Con cada_cuantas_filas_pasillo_horizontal=3, las filas 0, 3, 6, 9 son pasillos."""
    cfg = ConfigGeneracion(
        n_bloques_racks=2, alto=10, cada_cuantas_filas_pasillo_horizontal=3, seed=1
    )
    esc = generar_escenario(cfg)
    w = esc.warehouse

    ancho = w.ancho
    for y in (0, 3, 6, 9):
        for x in range(ancho):
            assert (x, y) in w._nodo_por_xy, f"Falta nodo en ({x}, {y})"


def test_sin_pasillos_horizontales_solo_arriba_y_abajo():
    cfg = ConfigGeneracion(
        n_bloques_racks=3, alto=8, cada_cuantas_filas_pasillo_horizontal=0, seed=1
    )
    esc = generar_escenario(cfg)
    w = esc.warehouse

    # Las filas 0 y 7 son horizontales, las demás solo columnas P
    for y in (0, 7):
        for x in range(w.ancho):
            assert (x, y) in w._nodo_por_xy

    # En la fila 4 (no horizontal), las columnas R no deben ser transitables
    patron = _patron_columnas(cfg)
    for x, tipo in enumerate(patron):
        if tipo == "R":
            assert (x, 4) not in w._nodo_por_xy


def test_mas_pasillos_horizontales_mas_nodos():
    """Agregar pasillos horizontales intermedios debe aumentar la cantidad de nodos."""
    cfg_sin = ConfigGeneracion(
        n_bloques_racks=3, alto=12, cada_cuantas_filas_pasillo_horizontal=0, seed=1
    )
    cfg_con = ConfigGeneracion(
        n_bloques_racks=3, alto=12, cada_cuantas_filas_pasillo_horizontal=3, seed=1
    )
    esc_sin = generar_escenario(cfg_sin)
    esc_con = generar_escenario(cfg_con)

    assert len(esc_con.warehouse.grafo) > len(esc_sin.warehouse.grafo)


def test_generacion_con_pasillos_h_validada():
    cfg = ConfigGeneracion(
        n_bloques_racks=4, alto=10, cada_cuantas_filas_pasillo_horizontal=2, seed=7
    )
    esc = generar_escenario(cfg)
    validar_escenario(esc)  # no debe lanzar


def test_config_pasillos_h_negativo_falla():
    with pytest.raises(ValueError):
        ConfigGeneracion(cada_cuantas_filas_pasillo_horizontal=-1)


def test_niveles_por_rack_mayor_que_productos():
    """Si niveles > productos, algunos estantes quedan vacíos."""
    cfg = ConfigGeneracion(
        n_bloques_racks=2,
        alto=5,
        niveles_por_rack=5,
        productos_por_rack=2,
        seed=42,
    )
    esc = generar_escenario(cfg)
    w = esc.warehouse

    # Cada rack tiene exactamente 2 productos
    for rack in w.racks.values():
        productos_del_rack = [p for p in w.productos.values() if p.rack_id == rack.id]
        assert len(productos_del_rack) == 2
        # Los z de esos productos están entre 1 y 5
        for p in productos_del_rack:
            assert 1 <= p.z <= 5
            assert rack.contiene(p.x, p.y)  # el producto está dentro del rack


def test_config_productos_mayor_que_niveles_falla():
    with pytest.raises(ValueError, match="no puede ser mayor"):
        ConfigGeneracion(niveles_por_rack=2, productos_por_rack=5)


def test_config_niveles_cero_falla():
    with pytest.raises(ValueError):
        ConfigGeneracion(niveles_por_rack=0)


def test_defaults_de_configuracion():
    """Contrato de los defaults. Si cambian, este test lo detecta."""
    cfg = ConfigGeneracion()
    assert cfg.n_bloques_racks == 3
    assert cfg.ancho_pasillo == 3
    assert cfg.ancho_bloque_racks == 2
    assert _calcular_ancho(cfg) == 18
