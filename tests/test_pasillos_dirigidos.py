import pytest

from warehouse.dominio.pasillo import Pasillo
from warehouse.warehouse.warehouse import Warehouse


def _warehouse_con_pasillo(sentido: str) -> Warehouse:
    """Grilla 3x5 con la columna x=1 declarada con un sentido."""
    w = Warehouse(3, 5)
    # Transitables: todo excepto x=0 y x=2 (que serían racks en el modelo real)
    # Pero como no estamos cambiando racks todavía, dejamos todo transitable.
    w.construir_grafo({(x, y) for x in range(3) for y in range(5)})
    w.agregar_pasillo("P1", x=1, y=0, ancho=1, alto=5, sentido=sentido)
    return w


def test_pasillo_n_solo_permite_subir():
    w = _warehouse_con_pasillo("N")
    n_bajo = w._nodo_por_xy[(1, 0)]
    n_alto = w._nodo_por_xy[(1, 1)]

    # N: de (1,0) a (1,1) sí
    destinos = [a.destino for a in w.grafo.vecinos(n_bajo)]
    assert n_alto in destinos

    # N: de (1,1) a (1,0) no
    destinos = [a.destino for a in w.grafo.vecinos(n_alto)]
    assert n_bajo not in destinos


def test_pasillo_solo_permite_bajar():
    w = _warehouse_con_pasillo("S")
    n_bajo = w._nodo_por_xy[(1, 0)]
    n_alto = w._nodo_por_xy[(1, 1)]

    assert n_bajo in [a.destino for a in w.grafo.vecinos(n_alto)]
    assert n_alto not in [a.destino for a in w.grafo.vecinos(n_bajo)]


def test_pasillo_n_permite_lateral():
    """En un pasillo N de ancho > 1, el picker puede moverse lateralmente."""
    w = Warehouse(5, 5)
    w.construir_grafo({(x, y) for x in range(5) for y in range(5)})
    w.agregar_pasillo("P1", x=1, y=0, ancho=3, alto=5, sentido="N")

    n_centro = w._nodo_por_xy[(2, 2)]
    # A la derecha (lateral)
    n_der = w._nodo_por_xy[(3, 2)]
    # Hacia abajo (contra el sentido)
    n_abajo = w._nodo_por_xy[(2, 1)]

    destinos = [a.destino for a in w.grafo.vecinos(n_centro)]
    assert n_der in destinos  # lateral permitido
    assert n_abajo not in destinos  # contra sentido, no


def test_sentido_por_defecto_ambos():
    w = Warehouse(3, 3)
    w.construir_grafo({(x, y) for x in range(3) for y in range(3)})
    assert w.sentido_de(0, 0) == "AMBOS"
    assert w.sentido_de(2, 2) == "AMBOS"


def test_pasillo_solapado_con_rack_falla():
    w = Warehouse(5, 5)
    transitables = {(x, y) for x in range(5) for y in range(5) if (x, y) != (1, 1)}
    w.construir_grafo(transitables)
    w.agregar_rack("R1", 1, 1)  # ok, (1,1) no era transitable
    with pytest.raises(ValueError, match="solapa"):
        w.agregar_pasillo("P1", x=1, y=1, ancho=1, alto=1, sentido="N")


def test_pasillos_solapados_falla():
    w = Warehouse(5, 5)
    w.construir_grafo({(x, y) for x in range(5) for y in range(5)})
    w.agregar_pasillo("P1", x=1, y=0, ancho=2, alto=2, sentido="N")
    with pytest.raises(ValueError, match="solapa"):
        w.agregar_pasillo("P2", x=2, y=0, ancho=2, alto=2, sentido="S")
