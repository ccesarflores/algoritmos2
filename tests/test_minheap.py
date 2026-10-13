from warehouse.estructuras.minheap import MinHeap


def test_minheap_ordena_por_prioridad():
    h = MinHeap()
    h.enqueue("a", 5)
    h.enqueue("b", 1)
    h.enqueue("c", 3)
    assert h.dequeue() == "b"
    assert h.dequeue() == "c"
    assert h.dequeue() == "a"
    assert h.dequeue() is None


def test_minheap_peek():
    h = MinHeap()
    h.enqueue("a", 5)
    h.enqueue("b", 1)
    assert h.peek() == "b"
    assert h.size() == 2


def test_minheap_vacio():
    h = MinHeap()
    assert h.is_empty()
    assert h.dequeue() is None
    assert h.peek() is None
