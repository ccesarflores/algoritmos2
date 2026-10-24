from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from warehouse.algoritmos.recorridos import ResultadoRecorrido
from warehouse.dominio.picker import Picker
from warehouse.dominio.wave import Wave
from warehouse.warehouse.warehouse import Warehouse

if TYPE_CHECKING:
    from warehouse.dominio.producto import Producto


@dataclass
class EstadoPicker:
    picker: Picker
    camino: list[int]
    indice_actual: int = 0
    espera_restante: int = 0
    carga_kg: float = 0.0
    productos_recogidos: set[str] = field(default_factory=set)
    completado: bool = False


@dataclass
class SimulacionMultiPicker:
    pickers: dict[str, EstadoPicker]
    nodo_a_productos: dict[int, list[str]]
    productos_totales: set[str]
    espera_por_nodo: dict[int, int]
    productos_db: dict[str, "Producto"]
    cantidad_pedida: dict[str, int]
    paso_actual: int = 0

    @classmethod
    def desde_waves(
        cls,
        waves_y_resultados: list[tuple[Wave, ResultadoRecorrido, Picker]],
        warehouse: Warehouse,
    ) -> "SimulacionMultiPicker":
        pickers = {}
        nodo_a_productos = {}
        productos_totales = set()
        espera_por_nodo = {}
        cantidad_pedida = {}

        for wave, resultado, picker in waves_y_resultados:
            # Mapeo de productos por nodo y esperas
            for pid in wave.ubicaciones_requeridas():
                prod = warehouse.productos[pid]
                nodo_a_productos.setdefault(prod.nodo_picking, []).append(pid)
                productos_totales.add(pid)

                if prod.nodo_picking not in espera_por_nodo:
                    espera_por_nodo[prod.nodo_picking] = 0
                espera_por_nodo[prod.nodo_picking] += prod.z

                # Cantidad total pedida para este producto en esta wave
                cant = sum(
                    it.cantidad
                    for ped in wave.pedidos
                    for it in ped.items
                    if it.producto_id == pid
                )
                cantidad_pedida[pid] = cantidad_pedida.get(pid, 0) + cant

            ep = EstadoPicker(picker=picker, camino=list(resultado.camino_completo))

            # Si arranca justo en una parada
            if ep.indice_actual in resultado.indices_de_paradas:
                nodo = ep.camino[ep.indice_actual]
                if nodo in espera_por_nodo:
                    ep.espera_restante = espera_por_nodo[nodo]
                    if ep.espera_restante == 0:
                        # Recoger inmediato
                        for prod_id in nodo_a_productos.get(nodo, []):
                            if prod_id not in ep.productos_recogidos:
                                peso_item = (
                                    warehouse.productos[prod_id].peso_kg
                                    * cantidad_pedida[prod_id]
                                )
                                if ep.carga_kg + peso_item <= picker.capacidad_carga_kg:
                                    ep.carga_kg += peso_item
                                    ep.productos_recogidos.add(prod_id)

            pickers[picker.id] = ep

        return cls(
            pickers=pickers,
            nodo_a_productos=nodo_a_productos,
            productos_totales=productos_totales,
            espera_por_nodo=espera_por_nodo,
            productos_db=warehouse.productos,
            cantidad_pedida=cantidad_pedida,
        )

    @property
    def completada(self) -> bool:
        return all(ep.completado for ep in self.pickers.values())

    @property
    def productos_pendientes(self) -> set[str]:
        recogidos = set()
        for ep in self.pickers.values():
            recogidos.update(ep.productos_recogidos)
        return self.productos_totales - recogidos

    def _recoger_productos(self, ep: EstadoPicker) -> None:
        """Lógica interna para recoger productos al estar en una parada."""
        nodo_actual = ep.camino[ep.indice_actual]
        if nodo_actual in self.nodo_a_productos:
            for prod_id in self.nodo_a_productos[nodo_actual]:
                if prod_id not in ep.productos_recogidos:
                    peso_item = (
                        self.productos_db[prod_id].peso_kg
                        * self.cantidad_pedida[prod_id]
                    )
                    if ep.carga_kg + peso_item <= ep.picker.capacidad_carga_kg:
                        ep.carga_kg += peso_item
                        ep.productos_recogidos.add(prod_id)

    def avanzar(self) -> bool:
        if self.completada:
            return False

        self.paso_actual += 1

        # 1. Identificar propuestas de movimiento
        propuestas = {}
        for pid, ep in self.pickers.items():
            if ep.completado or ep.espera_restante > 0:
                continue
            if ep.indice_actual + 1 >= len(ep.camino):
                continue
            propuestas[pid] = ep.camino[ep.indice_actual + 1]

        # 2. Resolver colisiones
        ocupadas_ahora = {
            ep.camino[ep.indice_actual]: pid
            for pid, ep in self.pickers.items()
            if not ep.completado
        }

        bloqueados = set()

        # Colisión de destino
        destinos = {}
        for pid, dst in propuestas.items():
            destinos.setdefault(dst, []).append(pid)
        for dst, pids in destinos.items():
            if len(pids) > 1:
                pids.sort()
                bloqueados.update(pids[1:])

        # Colisión con el que ya está ahí
        for pid, dst in propuestas.items():
            if dst in ocupadas_ahora and ocupadas_ahora[dst] not in propuestas:
                bloqueados.add(pid)

        # Colisión de swap
        for pid, dst in propuestas.items():
            origen = self.pickers[pid].camino[self.pickers[pid].indice_actual]
            for other_pid, other_dst in propuestas.items():
                if (
                    pid != other_pid
                    and other_dst == origen
                    and propuestas[other_pid] == origen
                    and self.pickers[other_pid].camino[
                        self.pickers[other_pid].indice_actual
                    ]
                    == dst
                ):
                    bloqueados.add(pid)
                    bloqueados.add(other_pid)

        # 3. Aplicar movimientos
        for pid, ep in self.pickers.items():
            if ep.completado:
                continue

            if ep.espera_restante > 0:
                ep.espera_restante -= 1
                if ep.espera_restante == 0:
                    self._recoger_productos(ep)
                continue

            if pid in propuestas and pid not in bloqueados:
                ep.indice_actual += 1

                nodo_actual = ep.camino[ep.indice_actual]
                if nodo_actual in self.espera_por_nodo:
                    ep.espera_restante = self.espera_por_nodo[nodo_actual]

                if ep.espera_restante == 0:
                    self._recoger_productos(ep)

            if ep.indice_actual >= len(ep.camino) - 1 and ep.espera_restante == 0:
                ep.completado = True

        return True
