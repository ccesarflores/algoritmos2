from warehouse.dominio.posicion import Posicion
from warehouse.dominio.tipo_nodo import TipoNodo
from warehouse.estructuras.grafo import Grafo


def test_agregar_nodo_devuelve_ids_consecutivos():
    g = Grafo()
    a = g.agregar_nodo(Posicion(0, 0), TipoNodo.PASILLO)
    b = g.agregar_nodo(Posicion(1, 0), TipoNodo.PASILLO)
    assert a == 0
    assert b == 1
    assert len(g) == 2


def test_agregar_arista_es_no_dirigida():
    g = Grafo()
    a = g.agregar_nodo(Posicion(0, 0), TipoNodo.PASILLO)
    b = g.agregar_nodo(Posicion(1, 0), TipoNodo.PASILLO)
    g.agregar_arista(a, b, peso=2.5)

    vecinos_a = {ar.destino: ar.peso for ar in g.vecinos(a)}
    vecinos_b = {ar.destino: ar.peso for ar in g.vecinos(b)}

    assert vecinos_a == {b: 2.5}
    assert vecinos_b == {a: 2.5}


def test_peso_devuelve_el_valor_correcto():
    g = Grafo()
    a = g.agregar_nodo(Posicion(0, 0), TipoNodo.PASILLO)
    b = g.agregar_nodo(Posicion(1, 0), TipoNodo.PASILLO)
    g.agregar_arista(a, b, peso=3.0)
    assert g.peso(a, b) == 3.0
    assert g.peso(b, a) == 3.0


def test_grafo_dirigido_no_agrega_arista_inversa():
    from warehouse.dominio.posicion import Posicion
    from warehouse.dominio.tipo_nodo import TipoNodo
    from warehouse.estructuras.grafo import Grafo

    g = Grafo(es_dirigido=True)
    a = g.agregar_nodo(Posicion(0, 0), TipoNodo.PASILLO)
    b = g.agregar_nodo(Posicion(1, 0), TipoNodo.PASILLO)
    g.agregar_arista(a, b)

    assert b in [ar.destino for ar in g.vecinos(a)]
    assert a not in [ar.destino for ar in g.vecinos(b)]  # ← dirigido


def test_grafo_no_dirigido_agrega_ambos_sentidos():
    from warehouse.dominio.posicion import Posicion
    from warehouse.dominio.tipo_nodo import TipoNodo
    from warehouse.estructuras.grafo import Grafo

    g = Grafo(es_dirigido=False)
    a = g.agregar_nodo(Posicion(0, 0), TipoNodo.PASILLO)
    b = g.agregar_nodo(Posicion(1, 0), TipoNodo.PASILLO)
    g.agregar_arista(a, b)

    assert b in [ar.destino for ar in g.vecinos(a)]
    assert a in [ar.destino for ar in g.vecinos(b)]
