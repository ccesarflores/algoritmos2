from pathlib import Path

from warehouse.generacion.generador import ConfigGeneracion, generar_escenario
from warehouse.io.cargador_json import cargar_escenario
from warehouse.io.exportador import escenario_a_dict, exportar_escenario


def test_exportar_escenario_crea_archivo(tmp_path):
    esc = generar_escenario(ConfigGeneracion(seed=42))
    out = tmp_path / "salida.json"
    exportar_escenario(esc, out)
    assert out.exists()


def test_dict_tiene_campos_esperados():
    esc = generar_escenario(ConfigGeneracion(seed=42))
    d = escenario_a_dict(esc)
    for campo in ("warehouse", "productos", "pedidos", "configuracion"):
        assert campo in d
    for campo in ("dimensiones", "racks", "zonas_despacho", "puertas"):
        assert campo in d["warehouse"]


def test_round_trip_generador_exportador_cargador(tmp_path):
    esc = generar_escenario(ConfigGeneracion(seed=42, n_pedidos=5))
    out = tmp_path / "esc.json"
    exportar_escenario(esc, out)
    esc2 = cargar_escenario(out)

    assert esc2.warehouse.ancho == esc.warehouse.ancho
    assert esc2.warehouse.alto == esc.warehouse.alto
    assert set(esc2.warehouse.racks.keys()) == set(esc.warehouse.racks.keys())
    for pid in esc.warehouse.productos:
        p1 = esc.warehouse.productos[pid]
        p2 = esc2.warehouse.productos[pid]
        assert p1.nombre == p2.nombre
        assert p1.peso_kg == p2.peso_kg
        assert (p1.x, p1.y, p1.z) == (p2.x, p2.y, p2.z)
    assert len(esc2.pedidos) == len(esc.pedidos)


def test_round_trip_mantiene_nodos_de_picking(tmp_path):
    esc = generar_escenario(ConfigGeneracion(seed=42))
    out = tmp_path / "esc.json"
    exportar_escenario(esc, out)
    esc2 = cargar_escenario(out)
    for pid, prod in esc.warehouse.productos.items():
        pos1 = esc.warehouse.grafo.nodo(prod.nodo_picking).posicion
        pos2 = esc2.warehouse.grafo.nodo(
            esc2.warehouse.productos[pid].nodo_picking
        ).posicion
        assert pos1 == pos2


def test_exportar_escenario_chico(tmp_path):
    ruta = Path(__file__).parent.parent / "data" / "escenarios" / "chico.json"
    esc = cargar_escenario(ruta)
    out = tmp_path / "chico_re.json"
    exportar_escenario(esc, out)
    esc2 = cargar_escenario(out)
    assert set(esc2.warehouse.productos.keys()) == set(esc.warehouse.productos.keys())
    assert set(esc2.warehouse.racks.keys()) == set(esc.warehouse.racks.keys())
    assert len(esc2.pickers) == len(esc.pickers)


def test_exportar_incluye_seed(tmp_path):
    esc = generar_escenario(ConfigGeneracion(seed=42))
    out = tmp_path / "esc.json"
    exportar_escenario(esc, out)
    assert cargar_escenario(out).seed == 42


def test_exportar_sin_seed(tmp_path):
    esc = generar_escenario(ConfigGeneracion(seed=None))
    out = tmp_path / "esc.json"
    exportar_escenario(esc, out)
    assert cargar_escenario(out).seed is None


def test_round_trip_con_waves_y_resultados(tmp_path):
    from warehouse.algoritmos.recorridos import recorrer_wave
    from warehouse.waves.generador_waves import EstrategiaWaves, generar_waves

    esc = generar_escenario(ConfigGeneracion(seed=42, n_pedidos=10))
    waves = generar_waves(
        esc.pedidos,
        esc.warehouse,
        max_pedidos=3,
        max_productos=20,
        estrategia=EstrategiaWaves.PRIORIDAD_Y_CERCANIA,
    )
    esc.waves = waves
    esc.resultados = {
        w.id: recorrer_wave(w, esc.warehouse, estrategia="vecino_mas_cercano")
        for w in waves
    }

    out = tmp_path / "esc.json"
    exportar_escenario(esc, out)
    esc2 = cargar_escenario(out)
    assert len(esc2.waves) == len(esc.waves)
    assert set(esc2.resultados.keys()) == set(esc.resultados.keys())
    for wid, r1 in esc.resultados.items():
        r2 = esc2.resultados[wid]
        assert r1.camino_completo == r2.camino_completo


def test_cargar_sin_waves_ni_resultados(tmp_path):
    esc = generar_escenario(ConfigGeneracion(seed=42))
    out = tmp_path / "esc.json"
    exportar_escenario(esc, out)
    esc2 = cargar_escenario(out)
    assert esc2.waves == []
    assert esc2.resultados == {}


def test_exportar_incluye_sesion(tmp_path):
    from warehouse.warehouse.escenario import Sesion

    esc = generar_escenario(ConfigGeneracion(seed=42, n_pedidos=10))
    esc.sesion = Sesion(
        wave_actual=2, indice_actual=15, estrategia_recorrido="orden_pedidos"
    )
    out = tmp_path / "esc.json"
    exportar_escenario(esc, out)
    esc2 = cargar_escenario(out)
    assert esc2.sesion is not None
    assert esc2.sesion.wave_actual == 2
    assert esc2.sesion.indice_actual == 15
    assert esc2.sesion.estrategia_recorrido == "orden_pedidos"


def test_exportar_sin_sesion(tmp_path):
    esc = generar_escenario(ConfigGeneracion(seed=42))
    esc.sesion = None
    out = tmp_path / "esc.json"
    exportar_escenario(esc, out)
    assert cargar_escenario(out).sesion is None
