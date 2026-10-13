"""
Módulo grafo.py
Implementación del TAD Grafo no ponderado, con lista de adyacencia.

Representación (según la definición del práctico):
    G = Array(n, LinkedList())
    donde n = |V| y cada G[u] es una LinkedList con los vecinos de u.

Los vértices están indexados de 0 a n-1.

Complejidad:
    - Acceso a vecinos de u:    O(1)
    - Iterar vecinos de u:      O(grado(u))
    - Suma de grados (dir.):    O(m)
    - Suma de grados (no dir.): O(2m) = O(m)
    - Espacio total:            O(n + m)
"""

from typing import Iterator

from warehouse.estructuras.linkedlist import LinkedList, add, append, length


class ListaAdyacencia:
    def __init__(self, n: int, es_dirigido: bool = False) -> None:
        """
        Crea un grafo con n vértices (indexados 0..n-1) sin aristas.

        Args:
            n (int): Número de vértices.
            es_dirigido (bool): True para dirigido, False para no dirigido.
        """
        self.n = n
        self.es_dirigido = es_dirigido
        # Array de n slots, cada uno con una LinkedList vacía
        self.adj: list[LinkedList[int]] = [LinkedList() for _ in range(n)]

    def agregar_vertice(self) -> int:
        """Agrega un vértice nuevo y devuelve su id."""
        self.adj.append(LinkedList())
        self.n += 1
        return self.n - 1

    def agregar_arista(self, u: int, v: int) -> None:
        """
        Agrega la arista (u, v). Si el grafo es no dirigido, agrega (v, u).

        Complejidad: O(1).

        Args:
            u (int): Vértice origen (0 <= u < n).
            v (int): Vértice destino (0 <= v < n).

        Returns:
            None

        Raises:
            ValueError: Si u o v están fuera de rango.
        """
        if not (0 <= u < self.n) or not (0 <= v < self.n):
            raise ValueError(f"Vértice fuera de rango: u={u}, v={v}")

        append(self.adj[u], v)
        if not self.es_dirigido:
            append(self.adj[v], u)

    def vecinos(self, u: int) -> LinkedList[int]:
        """
        Devuelve la LinkedList de vecinos de u. O(1).

        Args:
            u (int): Vértice (0 <= u < n).

        Returns:
            LinkedList[int]: Lista enlazada con los vecinos.
        """
        return self.adj[u]

    def iterar_vecinos(self, u: int) -> Iterator[int]:
        """
        Generador que recorre los vecinos de u uno por uno. O(grado(u)).

        Args:
            u (int): Vértice.

        Yields:
            int: Cada vecino de u, en el orden en que está en la LinkedList.
        """
        current = self.adj[u].head
        while current is not None:
            yield current.value
            current = current.nextNode

    def grado(self, u: int) -> int:
        """
        Devuelve el grado de u. O(1) gracias al atributo size de LinkedList.

        Args:
            u (int): Vértice.

        Returns:
            int: Número de vecinos de u.
        """
        return self.adj[u].size

    def mostrar(self) -> None:
        """
        Imprime las listas de adyacencia.

        Returns:
            None
        """
        tipo = "Dirigido" if self.es_dirigido else "No Dirigido"
        print(f"\n--- Lista de Adyacencia (Array + LinkedList, {tipo}) ---")
        for u in range(self.n):
            vecinos = list(self.iterar_vecinos(u))
            cadena = " -> ".join(map(str, vecinos)) if vecinos else "/"
            print(f"{u:>3} -> {cadena}")
