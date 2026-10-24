import pytest

from warehouse.dominio.producto import Producto
from warehouse.warehouse.warehouse import Warehouse


def _warehouse_minimo() -> Warehouse:
    w = Warehouse(5, 5)
    transitables = {
        (x, y) for x in range(5) for y in range(5) if (x, y) not in {(2, 2), (3, 2)}
    }
    w.construir_grafo(transitables)
    w.agregar_zona_despacho("A", (0, 0), (0, 0))
    w.agregar_rack("R001", 2, 2, 2, 1)
    return w


def _producto(pid: str, nombre: str) -> Producto:
    return Producto(
        id=pid,
        nombre=nombre,
        rack_id="R001",
        x=2,
        y=2,
        z=1,
        cantidad_disponible=10,
        peso_kg=1.0,
    )


# --- indexación ---


def test_agregar_producto_lo_indexa_en_el_trie():
    w = _warehouse_minimo()
    w.agregar_producto(_producto("P001", "Caja chica"))
    # El índice normaliza a minúsculas
    assert w.nombre_a_id["caja chica"] == "P001"
    assert w.trie_nombres.size == 1


def test_multiples_productos_se_indexan():
    w = _warehouse_minimo()
    w.agregar_producto(_producto("P001", "Caja chica"))
    w.agregar_producto(_producto("P002", "Caja grande"))
    w.agregar_producto(_producto("P003", "Bolsa"))
    assert w.trie_nombres.size == 3
    assert len(w.nombre_a_id) == 3


# --- unicidad ---


def test_nombre_duplicado_permite_multiples_ids():
    w = _warehouse_minimo()
    w.agregar_producto(_producto("P001", "Caja"))
    w.agregar_producto(_producto("P002", "Caja"))  # No debe lanzar excepción
    assert len(w.productos) == 2
    assert len(w.buscar_por_prefijo("Caja")) == 2


def test_id_duplicado_falla():
    w = _warehouse_minimo()
    w.agregar_producto(_producto("P001", "Caja"))
    with pytest.raises(ValueError, match="Ya existe un producto con ID"):
        w.agregar_producto(_producto("P001", "Otra Cosa"))


# --- búsqueda por prefijo ---


def test_buscar_por_prefijo_devuelve_todos_los_que_empiezan():
    w = _warehouse_minimo()
    w.agregar_producto(_producto("P001", "Caja chica"))
    w.agregar_producto(_producto("P002", "Caja grande"))
    w.agregar_producto(_producto("P003", "Bolsa"))

    resultados = w.buscar_por_prefijo("Caja")
    ids = sorted(p.id for p in resultados)
    assert ids == ["P001", "P002"]


def test_buscar_por_prefijo_case_insensitive():
    w = _warehouse_minimo()
    w.agregar_producto(_producto("P001", "Caja chica"))

    # El Trie normaliza a minúscula
    assert len(w.buscar_por_prefijo("caja")) == 1
    assert len(w.buscar_por_prefijo("CAJA")) == 1
    assert len(w.buscar_por_prefijo("CaJa")) == 1


def test_buscar_por_prefijo_sin_resultados():
    w = _warehouse_minimo()
    w.agregar_producto(_producto("P001", "Caja"))
    assert w.buscar_por_prefijo("xyz") == []


def test_buscar_por_prefijo_vacio():
    w = _warehouse_minimo()
    w.agregar_producto(_producto("P001", "Caja"))
    assert w.buscar_por_prefijo("") == []


def test_buscar_por_prefijo_con_prefijo_mas_largo():
    w = _warehouse_minimo()
    w.agregar_producto(_producto("P001", "Caja chica"))
    w.agregar_producto(_producto("P002", "Caja grande"))

    resultados = w.buscar_por_prefijo("Caja ch")
    assert len(resultados) == 1
    assert resultados[0].id == "P001"
