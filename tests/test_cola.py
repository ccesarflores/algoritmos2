from warehouse.estructuras.cola import dequeue, enqueue
from warehouse.estructuras.linkedlist import LinkedList


def test_cola_fifo():
    q = LinkedList()
    enqueue(q, 1)
    enqueue(q, 2)
    enqueue(q, 3)
    assert dequeue(q) == 1
    assert dequeue(q) == 2
    assert dequeue(q) == 3
    assert dequeue(q) is None
