"""
Módulo minheap.py
Implementación del TAD Cola con Prioridad usando un Min-Heap binario.

Un Min-Heap es un árbol binario completo almacenado implícitamente en
un arreglo, donde cada nodo cumple: padre <= hijos.

Para el nodo en índice i:
    - hijo izquierdo: 2*i + 1
    - hijo derecho:   2*i + 2
    - padre:          (i - 1) // 2

Complejidad:
    - enqueue: O(log n)
    - dequeue: O(log n)
    - peek:    O(1)
"""

from typing import Any


class MinHeap:
    def __init__(self) -> None:
        # Cada elemento es una tupla (priority, value)
        self.heap: list[tuple[float | int, Any]] = []

    def is_empty(self) -> bool:
        return len(self.heap) == 0

    def size(self) -> int:
        return len(self.heap)

    def peek(self) -> Any | None:
        """Devuelve el elemento de menor prioridad sin extraerlo. O(1)."""
        if self.is_empty():
            return None
        return self.heap[0][1]

    def enqueue(self, value: Any, priority: float | int) -> None:
        """Inserta un elemento con su prioridad. O(log n)."""
        self.heap.append((priority, value))
        self._sift_up(len(self.heap) - 1)

    def dequeue(self) -> Any | None:
        """Extrae y devuelve el elemento de menor prioridad. O(log n)."""
        if self.is_empty():
            return None

        min_value = self.heap[0][1]

        # Movemos el último elemento a la raíz
        last = self.heap.pop()
        if not self.is_empty():
            self.heap[0] = last
            self._sift_down(0)

        return min_value

    # --------------------------------------------------------
    # Operaciones internas
    # --------------------------------------------------------

    def _sift_up(self, index: int) -> None:
        """Sube el elemento hasta que su padre sea menor o igual."""
        while index > 0:
            parent = (index - 1) // 2
            if self.heap[index][0] < self.heap[parent][0]:
                self.heap[index], self.heap[parent] = (
                    self.heap[parent],
                    self.heap[index],
                )
                index = parent
            else:
                break

    def _sift_down(self, index: int) -> None:
        """Baja el elemento hasta que sea menor o igual a sus hijos."""
        n = len(self.heap)
        while True:
            left = 2 * index + 1
            right = 2 * index + 2
            smallest = index

            if left < n and self.heap[left][0] < self.heap[smallest][0]:
                smallest = left
            if right < n and self.heap[right][0] < self.heap[smallest][0]:
                smallest = right

            if smallest != index:
                self.heap[index], self.heap[smallest] = (
                    self.heap[smallest],
                    self.heap[index],
                )
                index = smallest
            else:
                break
