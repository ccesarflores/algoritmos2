from warehouse.estructuras.lista_adyacencia import ListaAdyacencia


def test_agregar_vertices_y_aristas_dirigidas():
    g = ListaAdyacencia(n=0, es_dirigido=True)
    a = g.agregar_vertice()
    b = g.agregar_vertice()
    g.agregar_arista(a, b)
    assert list(g.iterar_vecinos(a)) == [b]
    assert list(g.iterar_vecinos(b)) == []  # dirigido: b no tiene a como vecino


def test_no_dirigido_agrega_ambos_sentidos():
    g = ListaAdyacencia(n=0, es_dirigido=False)
    a = g.agregar_vertice()
    b = g.agregar_vertice()
    g.agregar_arista(a, b)
    assert b in list(g.iterar_vecinos(a))
    assert a in list(g.iterar_vecinos(b))


def test_crecimiento_dinamico():
    g = ListaAdyacencia(n=0)
    for _ in range(5):
        g.agregar_vertice()
    assert g.n == 5
