from dataclasses import dataclass, field

from warehouse.algoritmos.recorridos import ResultadoRecorrido
from warehouse.dominio.wave import Wave
from warehouse.warehouse.warehouse import Warehouse


@dataclass
class EstadoSimulacion:
    wave_id: str
    camino: list[int]  # secuencia completa de nodos
    nodo_a_productos: dict[int, list[str]]  # nodo_picking -> [producto_ids]
    productos_totales: set[str]
    indices_de_paradas: list[int]
    nodos_paradas: list[int]
    espera_por_nodo: dict[int, int] = field(default_factory=dict)
    indice_actual: int = 0
    espera_restante: int = 0

    # --- construcción ---

    @classmethod
    def desde_wave(
        cls,
        wave: Wave,
        resultado: ResultadoRecorrido,
        warehouse: Warehouse,
    ) -> "EstadoSimulacion":
        mapa: dict[int, list[str]] = {}
        espera_por_nodo: dict[int, int] = {}

        for pid in wave.ubicaciones_requeridas():
            producto = warehouse.productos.get(pid)
            if producto is None:
                raise ValueError(
                    f"La wave {wave.id} referencia producto inexistente: {pid}"
                )
            mapa.setdefault(producto.nodo_picking, []).append(pid)

            # El tiempo de espera en un nodo es la suma de las alturas (z)
            # de los productos que se recogen allí.
            if producto.nodo_picking not in espera_por_nodo:
                espera_por_nodo[producto.nodo_picking] = 0
            espera_por_nodo[producto.nodo_picking] += producto.z

        estado = cls(
            wave_id=wave.id,
            camino=list(resultado.camino_completo),
            nodo_a_productos=mapa,
            productos_totales=set(wave.ubicaciones_requeridas()),
            indices_de_paradas=list(resultado.indices_de_paradas),
            nodos_paradas=list(resultado.orden_paradas),
            espera_por_nodo=espera_por_nodo,
        )
        estado._inicializar_espera_si_en_parada()
        return estado

    def _inicializar_espera_si_en_parada(self) -> None:
        """Si el picker está sobre una parada, arrancar la espera para
        no marcar el producto como recogido antes de tiempo.
        Esto cubre el caso de 'inicio de wave' con picker sobre un
        nodo de picking y también el de Reset."""
        if self.indice_actual in self.indices_de_paradas:
            nodo_actual = self.camino[self.indice_actual]
            if nodo_actual in self.espera_por_nodo:
                self.espera_restante = self.espera_por_nodo[nodo_actual]

    # --- consultas ---

    @property
    def nodo_actual(self) -> int:
        return self.camino[self.indice_actual]

    @property
    def al_final(self) -> bool:
        return self.indice_actual >= len(self.camino) - 1

    @property
    def completada(self) -> bool:
        # Ahora también requiere que no haya esperas pendientes
        return (
            self.al_final
            and self.espera_restante == 0
            and self.productos_recogidos() == self.productos_totales
        )

    def productos_recogidos(self) -> set[str]:
        """Productos recogidos hasta el paso actual. Un producto solo se
        considera recogido si el picker ya terminó de esperar en esa parada."""
        recogidos: set[str] = set()
        for i, nodo_parada in enumerate(self.nodos_paradas):
            if i >= len(self.indices_de_paradas):
                break
            idx_parada = self.indices_de_paradas[i]

            if self.indice_actual > idx_parada:
                recogidos.update(self.nodo_a_productos.get(nodo_parada, ()))
            elif self.indice_actual == idx_parada:
                # Si estamos en la parada, lo recoge SOLO si ya no debe esperar
                if self.espera_restante == 0:
                    recogidos.update(self.nodo_a_productos.get(nodo_parada, ()))

        return recogidos

    def productos_pendientes(self) -> set[str]:
        return self.productos_totales - self.productos_recogidos()

    # --- mutación ---

    def avanzar(self) -> bool:
        """Avanza un paso en el tiempo. Devuelve False si ya terminó."""
        # 1. Si estamos esperando, consumimos un paso de espera y no nos movemos
        if self.espera_restante > 0:
            self.espera_restante -= 1
            return True

        # 2. Si ya estamos en el final del camino, no podemos avanzar
        if self.al_final:
            return False

        # 3. Nos movemos al siguiente nodo
        self.indice_actual += 1

        # 4. Si acabamos de llegar a un nodo de parada, inicializamos la espera
        if self.indice_actual in self.indices_de_paradas:
            nodo_actual = self.camino[self.indice_actual]
            if nodo_actual in self.espera_por_nodo:
                self.espera_restante = self.espera_por_nodo[nodo_actual]

        return True

    def retroceder(self) -> bool:
        """Retrocede un paso en el tiempo."""
        # Si estábamos esperando, cancelamos un paso de espera
        if self.espera_restante > 0:
            self.espera_restante -= 1
            return True

        if self.indice_actual <= 0:
            return False

        self.indice_actual -= 1
        self.espera_restante = 0
        return True

    def reiniciar(self) -> None:
        self.indice_actual = 0
        self.espera_restante = 0
        self._inicializar_espera_si_en_parada()  # ← Fix para el botón Reset
