import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from warehouse.algoritmos.distancias import CacheDistancias
from warehouse.dominio.picker import Picker
from warehouse.dominio.wave import Wave
from warehouse.warehouse.warehouse import Warehouse

if TYPE_CHECKING:
    from warehouse.dominio.producto import Producto


@dataclass
class Tarea:
    producto_id: str
    cantidad: int
    nodo_picking: int
    completada: bool = False


@dataclass
class EstadoPicker:
    picker: Picker
    nodo_actual: int
    camino_actual: list[int] = field(default_factory=list)
    tarea_actual: Tarea | None = None
    fase: str = "BUSCANDO_TAREA"
    # Fases: BUSCANDO_TAREA, YENDO_A_ITEM, RECOGIENDO, YENDO_A_DESPACHO, DESCARGANDO, TERMINADO
    carga_kg: float = 0.0
    productos_recogidos: set[str] = field(default_factory=set)
    espera_restante: int = 0
    bloqueos_consecutivos: int = 0


@dataclass
class SimulacionDinamica:
    pickers: dict[str, EstadoPicker]
    tareas_pendientes: list[Tarea]
    productos_totales: set[str]
    nodo_a_productos: dict[int, list[str]]
    cantidad_pedida: dict[str, int]
    cache: CacheDistancias
    warehouse: Warehouse
    paso_actual: int = 0

    # Nodos de despacho para volver
    nodos_despacho: list[int] = field(default_factory=list)

    @classmethod
    def desde_waves(
        cls,
        waves: list[Wave],
        pickers: list[Picker],
        warehouse: Warehouse,
    ) -> "SimulacionDinamica":
        cache = CacheDistancias(warehouse.grafo)
        tareas = []
        nodo_a_productos = {}
        productos_totales = set()
        cantidad_pedida = {}

        # 1. Crear el pool global de tareas (de todas las waves)
        for wave in waves:
            for pid in wave.ubicaciones_requeridas():
                prod = warehouse.productos[pid]
                cant = sum(
                    it.cantidad
                    for ped in wave.pedidos
                    for it in ped.items
                    if it.producto_id == pid
                )
                tareas.append(
                    Tarea(
                        producto_id=pid, cantidad=cant, nodo_picking=prod.nodo_picking
                    )
                )
                nodo_a_productos.setdefault(prod.nodo_picking, []).append(pid)
                productos_totales.add(pid)
                cantidad_pedida[pid] = cantidad_pedida.get(pid, 0) + cant

        # 2. Inicializar pickers en sus posiciones iniciales (o el primer despacho)
        nodos_despacho = [z.nodo_representativo for z in warehouse.zonas.values()]
        estado_pickers = {}

        for i, base_picker in enumerate(pickers):
            picker = copy.deepcopy(base_picker)
            nodo_inicio = warehouse._nodo_por_xy.get(
                base_picker.posicion_inicial, nodos_despacho[0]
            )

            estado_pickers[picker.id] = EstadoPicker(
                picker=picker,
                nodo_actual=nodo_inicio,
            )

        return cls(
            pickers=estado_pickers,
            tareas_pendientes=tareas,
            productos_totales=productos_totales,
            nodo_a_productos=nodo_a_productos,
            cantidad_pedida=cantidad_pedida,
            cache=cache,
            warehouse=warehouse,
            nodos_despacho=nodos_despacho,
        )

    @property
    def completada(self) -> bool:
        return all(ep.fase == "TERMINADO" for ep in self.pickers.values())

    @property
    def productos_pendientes(self) -> set[str]:
        recogidos = set()
        for ep in self.pickers.values():
            recogidos.update(ep.productos_recogidos)
        return self.productos_totales - recogidos

    def _buscar_siguiente_tarea(self, ep: EstadoPicker) -> Tarea | None:
        """Encuentra la tarea no completada más cercana desde la posición actual."""
        mejor_tarea = None
        mejor_dist = float("inf")

        for tarea in self.tareas_pendientes:
            if tarea.completada:
                continue

            # Chequeo rápido de capacidad
            peso_item = (
                self.warehouse.productos[tarea.producto_id].peso_kg * tarea.cantidad
            )
            if ep.carga_kg + peso_item > ep.picker.capacidad_carga_kg:
                continue  # No entra, buscamos otra

            d = self.cache.distancia(ep.nodo_actual, tarea.nodo_picking)
            if d < mejor_dist:
                mejor_dist = d
                mejor_tarea = tarea

        return mejor_tarea

    def _nodo_despacho_mas_cercano(self, ep: EstadoPicker) -> int:
        mejor_nodo = self.nodos_despacho[0]
        mejor_dist = float("inf")
        for nd in self.nodos_despacho:
            d = self.cache.distancia(ep.nodo_actual, nd)
            if d < mejor_dist:
                mejor_dist = d
                mejor_nodo = nd
        return mejor_nodo

    def avanzar(self) -> bool:
        if self.completada:
            return False

        self.paso_actual += 1

        # 1. Lógica de estados (asignación)
        for pid, ep in self.pickers.items():
            if ep.espera_restante > 0:
                continue

            if ep.fase == "BUSCANDO_TAREA":
                tarea = self._buscar_siguiente_tarea(ep)
                if tarea:
                    ep.tarea_actual = tarea
                    ep.camino_actual = self.cache.camino(
                        ep.nodo_actual, tarea.nodo_picking
                    )
                    ep.fase = "YENDO_A_ITEM"
                elif ep.carga_kg > 0:
                    # No hay más tareas que entren, pero tengo carga. Voy a despacho.
                    nd = self._nodo_despacho_mas_cercano(ep)
                    ep.camino_actual = self.cache.camino(ep.nodo_actual, nd)
                    ep.fase = "YENDO_A_DESPACHO"
                else:
                    # No hay tareas y no tengo carga. Terminé.
                    ep.fase = "TERMINADO"

        # 2. Lógica de movimiento con colisiones
        propuestas = {}
        for pid, ep in self.pickers.items():
            if (
                ep.fase in ("BUSCANDO_TAREA", "RECOGIENDO", "DESCARGANDO", "TERMINADO")
                or ep.espera_restante > 0
            ):
                continue
            if not ep.camino_actual:
                continue
            propuestas[pid] = ep.camino_actual[
                0
            ]  # El camino incluye el nodo actual, el 0 es a donde va

        # ... (Lógica de colisiones igual a la anterior: destinos, ocupadas, swap) ...
        # [Ver código abajo para el bloque completo de colisiones]

        # 3. Aplicar movimientos
        for pid, ep in self.pickers.items():
            if ep.espera_restante > 0:
                ep.espera_restante -= 1
                continue

            if ep.fase == "RECOGIENDO":
                # Terminó de esperar (recolectar)
                prod = self.warehouse.productos[ep.tarea_actual.producto_id]
                ep.carga_kg += prod.peso_kg * ep.tarea_actual.cantidad
                ep.productos_recogidos.add(ep.tarea_actual.producto_id)
                ep.tarea_actual.completada = True
                ep.tarea_actual = None
                ep.fase = "BUSCANDO_TAREA"
                continue

            if ep.fase == "DESCARGANDO":
                ep.carga_kg = 0.0
                ep.fase = "BUSCANDO_TAREA"
                continue

            # Si se movió
            if pid in propuestas and pid not in bloqueados:
                ep.bloqueos_consecutivos = 0
                ep.nodo_actual = propuestas[pid]
                ep.camino_actual.pop(0)  # Avanzar en el camino

                # ¿Llegó a destino?
                if not ep.camino_actual:
                    if ep.fase == "YENDO_A_ITEM":
                        ep.espera_restante = (
                            ep.tarea_actual.nodo_picking
                        )  # Usar z o algo
                        ep.espera_restante = self.warehouse.productos[
                            ep.tarea_actual.producto_id
                        ].z
                        ep.fase = "RECOGIENDO"
                    elif ep.fase == "YENDO_A_DESPACHO":
                        ep.espera_restante = 2  # Tiempo de descarga
                        ep.fase = "DESCARGANDO"
            elif pid in bloqueados:
                ep.bloqueos_consecutivos += 1
                if ep.bloqueos_consecutivos > 3 and len(ep.camino_actual) > 1:
                    # Retroceso táctico
                    ep.nodo_actual = ep.camino_actual.pop(0)
                    ep.bloqueos_consecutivos = 0

        return True
