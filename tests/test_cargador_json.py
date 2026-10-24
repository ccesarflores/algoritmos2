from pathlib import Path

import pytest

from warehouse.io.cargador_json import ErrorDeCarga, cargar_escenario

RUTA_CHICO = Path(__file__).parent.parent / "data" / "escenarios" / "chico.json"


@pytest.fixture
def escenario_chico():
    return cargar_escenario(RUTA_CHICO)


def test_carga_dimensiones(escenario_chico):
    w = escenario_chico.warehouse
    assert w.ancho == 18
    assert w.alto == 16


def test_racks_cargados(escenario_chico):
    racks = escenario_chico.warehouse.racks
    assert set(racks.keys()) == {"R1", "R2", "R3"}
    r1 = racks["R1"]
    assert (r1.x, r1.y) == (3, 5)
    assert r1.ancho == 2 and r1.alto == 6


def test_pasillos_cargados(escenario_chico):
    p = escenario_chico.warehouse.pasillos
    assert p["PAS_V0"].sentido == "N"
    assert p["PAS_V1"].sentido == "S"
    assert p["PAS_H_INF"].sentido == "AMBOS"


def test_puertas_cargadas(escenario_chico):
    puertas = escenario_chico.warehouse.puertas
    assert set(puertas.keys()) == {"PUERTA_OUT_1", "PUERTA_IN_1"}
    assert puertas["PUERTA_OUT_1"].tipo == "OUTBOUND"


def test_zonas_cargadas(escenario_chico):
    zonas = escenario_chico.warehouse.zonas
    assert set(zonas.keys()) == {"ZONA_A", "ZONA_B"}
    za = zonas["ZONA_A"]
    assert za.puerta_id == "PUERTA_OUT_1"
    assert za.p1 == (2, 1) and za.p2 == (6, 2)
    assert za.peso_max_kg == 500.0


def test_productos_cargados(escenario_chico):
    prods = escenario_chico.warehouse.productos
    assert len(prods) == 8
    p1 = prods["P001"]
    assert p1.nombre == "Monitor 27"
    assert (p1.x, p1.y, p1.z) == (3, 5, 1)
    assert p1.peso_kg == 6.5
    assert p1.nodo_picking >= 0


def test_picking_p001_es_pasillo_izquierdo(escenario_chico):
    """P001 en (3,5) columna izquierda del rack R1 → picking en (2,5)."""
    w = escenario_chico.warehouse
    p1 = w.productos["P001"]
    nodo = w.grafo.nodo(p1.nodo_picking)
    assert (nodo.posicion.x, nodo.posicion.y) == (2, 5)


def test_picking_p003_es_pasillo_derecho(escenario_chico):
    """P003 en (4,7) columna derecha del rack R1 → picking en (5,7)."""
    w = escenario_chico.warehouse
    p3 = w.productos["P003"]
    nodo = w.grafo.nodo(p3.nodo_picking)
    assert (nodo.posicion.x, nodo.posicion.y) == (5, 7)


def test_pickers_cargados(escenario_chico):
    assert len(escenario_chico.pickers) == 2
    pk1 = escenario_chico.pickers[0]
    assert pk1.id == "PK_01"
    assert pk1.posicion_inicial == (1, 3)
    assert pk1.capacidad_carga_kg == 150.0


def test_pedidos_cargados(escenario_chico):
    assert len(escenario_chico.pedidos) == 3
    p1 = escenario_chico.pedidos[0]
    assert p1.id == "PED_01"
    assert p1.prioridad == 5
    assert p1.productos_ids() == {"P001", "P002"}


def test_wave_config(escenario_chico):
    cfg = escenario_chico.wave_config
    assert cfg.max_pedidos == 3
    assert cfg.max_productos == 15


# --- errores ---


def test_archivo_inexistente():
    with pytest.raises(ErrorDeCarga):
        cargar_escenario("/ruta/que/no/existe.json")


def test_json_invalido(tmp_path):
    f = tmp_path / "mal.json"
    f.write_text("{no es json", encoding="utf-8")
    with pytest.raises(ErrorDeCarga):
        cargar_escenario(f)


def test_falta_warehouse(tmp_path):
    f = tmp_path / "sin_wh.json"
    f.write_text('{"productos":[],"pedidos":[]}', encoding="utf-8")
    with pytest.raises(ErrorDeCarga, match="warehouse"):
        cargar_escenario(f)


def test_rack_fuera_de_limites(tmp_path):
    import json

    data = {
        "warehouse": {
            "dimensiones": {"ancho_x": 5, "largo_y": 5},
            "racks": [
                {"id": "R1", "ubicacion": {"x": 4, "y": 4}, "ancho": 2, "alto": 2}
            ],
            "puertas": [],
            "zonas_despacho": [],
            "pasillos": [],
        },
        "productos": [],
        "pedidos": [],
    }
    f = tmp_path / "esc.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ErrorDeCarga, match="fuera"):
        cargar_escenario(f)


def test_producto_rack_inexistente(tmp_path):
    import json

    data = {
        "warehouse": {
            "dimensiones": {"ancho_x": 5, "largo_y": 5},
            "racks": [
                {"id": "R1", "ubicacion": {"x": 1, "y": 1}, "ancho": 2, "alto": 1}
            ],
            "puertas": [],
            "zonas_despacho": [],
            "pasillos": [],
        },
        "productos": [
            {
                "id": "P1",
                "nombre": "X",
                "rack_id": "NO_EXISTE",
                "ubicacion": {"x": 1, "y": 1, "z": 1},
                "cantidad_disponible": 1,
                "peso_kg": 1.0,
            }
        ],
        "pedidos": [],
    }
    f = tmp_path / "esc.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ErrorDeCarga, match="NO_EXISTE"):
        cargar_escenario(f)
