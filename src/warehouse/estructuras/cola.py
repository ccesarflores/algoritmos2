from typing import TypeVar

from warehouse.estructuras.linkedlist import LinkedList, append

T = TypeVar("T")


def enqueue(Q: LinkedList[T], element: T) -> None:
    """Agrega un elemento al final de la cola. O(1)."""
    append(Q, element)


def dequeue(Q: LinkedList[T]) -> T | None:
    """Extrae el primer elemento de la cola. O(1)."""
    if Q.head is None:
        return None
    element = Q.head.value
    Q.head = Q.head.nextNode
    if Q.head is None:
        Q.tail = None  # cola quedó vacía
    Q.size -= 1
    return element
