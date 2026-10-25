from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from warehouse.algoritmos.distancias import CacheDistancias
from warehouse.dominio.picker import Picker
from warehouse.dominio.tipo_nodo import TipoNodo
from warehouse.dominio.wave import Wave
from warehouse.warehouse.warehouse import Warehouse

if TYPE_CHECKING:
    from warehouse.dominio.producto import Producto
    from warehouse.dominio.zona import ZonaDespacho


@dataclass
class Tarea:
    producto_id: str
    cantidad: int
    nodo_picking: int
    completada: bool = False
    asignada_a: str | None = None


@dataclass
class EstadoPicker:
    picker: Picker
    nodo_actual: int
    camino_actual: list[int] = field(default_factory=list)
    tarea_actual: Tarea | None = None
    zona_objetivo: "ZonaDespacho" | None = None
    # Fases: BUSCANDO_TAREA, YENDO_A_ITEM, RECOGIENDO, YENDO_A_DESPACHO, ENTRANDO_A_ZONA, DESCARGANDO, SALIENDO_DE_ZONA, YENDO_A_FINAL, TERMINADO
    fase: str = "BUSCANDO_TAREA"
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
    zonas_despacho: dict[int, "ZonaDespacho"] = field(default_factory=dict)
    peso_en_zona: dict[str, float] = field(default_factory=dict)
    cajas_en_zona: dict[int, int] = field(default_factory=dict)
    distancia_total: float = 0.0
    aristas_recorridas: int = 0
    nodos_visitados: int = 0
    tiempo_ejecucion: float = 0.0

    @classmethod
    def desde_waves(
        cls, waves: list[Wave], pickers: list[Picker], warehouse: Warehouse
    ) -> "SimulacionDinamica":
        cache = CacheDistancias(warehouse.grafo)
        nodo_a_productos = {}
        productos_totales = set()
        cantidad_pedida = {}

        tareas_dict = {}
        for wave in waves:
            for pid in wave.ubicaciones_requeridas():
                prod = warehouse.productos[pid]
                cant = sum(
                    it.cantidad
                    for ped in wave.pedidos
                    for it in ped.items
                    if it.producto_id == pid
                )
                if pid not in tareas_dict:
                    tareas_dict[pid] = Tarea(
                        producto_id=pid, cantidad=0, nodo_picking=prod.nodo_picking
                    )
                tareas_dict[pid].cantidad += cant

                nodo_a_productos.setdefault(prod.nodo_picking, []).append(pid)
                productos_totales.add(pid)
                cantidad_pedida[pid] = cantidad_pedida.get(pid, 0) + cant

        tareas = list(tareas_dict.values())

        zonas_dict = {}
        peso_en_zona = {}

        for z in warehouse.zonas.values():
            peso_en_zona[z.id] = 0.0
            for x in range(z.p1[0], z.p2[0] + 1):
                for y in range(z.p1[1], z.p2[1] + 1):
                    nid = warehouse._nodo_por_xy.get((x, y))
                    if nid is not None:
                        zonas_dict[nid] = z

        estado_pickers = {}
        for base_picker in pickers:
            picker = copy.deepcopy(base_picker)
            nodo_inicio = warehouse._nodo_por_xy.get(base_picker.posicion_inicial)
            if nodo_inicio is None:
                nodo_inicio = next(iter(warehouse._nodo_por_xy.values()))

            estado_pickers[picker.id] = EstadoPicker(
                picker=picker, nodo_actual=nodo_inicio
            )

        return cls(
            pickers=estado_pickers,
            tareas_pendientes=tareas,
            productos_totales=productos_totales,
            nodo_a_productos=nodo_a_productos,
            cantidad_pedida=cantidad_pedida,
            cache=cache,
            warehouse=warehouse,
            zonas_despacho=zonas_dict,
            peso_en_zona=peso_en_zona,
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
        mejor_tarea = None
        mejor_dist = float("inf")
        for tarea in self.tareas_pendientes:
            if tarea.completada or tarea.asignada_a is not None:
                continue
            peso_unitario = self.warehouse.productos[tarea.producto_id].peso_kg
            if ep.carga_kg + peso_unitario > ep.picker.capacidad_carga_kg:
                continue
            d = self.cache.distancia(ep.nodo_actual, tarea.nodo_picking)
            if d < mejor_dist:
                mejor_dist = d
                mejor_tarea = tarea
        if mejor_tarea:
            mejor_tarea.asignada_a = ep.picker.id
        return mejor_tarea

    def _zona_mas_cercana(self, ep: EstadoPicker) -> "ZonaDespacho" | None:
        mejor_zona = None
        mejor_dist = float("inf")
        for zona in self.warehouse.zonas.values():
            if self.peso_en_zona[zona.id] + ep.carga_kg > zona.peso_max_kg:
                continue
            puerta = self.warehouse.puertas.get(zona.puerta_id)
            if not puerta:
                continue
            d = self.cache.distancia(ep.nodo_actual, puerta.nodo)
            if d < mejor_dist:
                mejor_dist = d
                mejor_zona = zona
        return mejor_zona

    def _buscar_celda_libre_zona(self, zona, nodo_puerta) -> int | None:
        ocupadas = {p.nodo_actual for p in self.pickers.values()}
        mejor = None
        mejor_dist = float("inf")
        for x in range(zona.p1[0], zona.p2[0] + 1):
            for y in range(zona.p1[1], zona.p2[1] + 1):
                nid = self.warehouse._nodo_por_xy.get((x, y))
                if nid and nid not in ocupadas and nid != nodo_puerta:
                    d = abs(x - zona.p1[0]) + abs(
                        y - zona.p1[1]
                    )  # Distancia simple dentro de la zona
                    if d < mejor_dist:
                        mejor_dist = d
                        mejor = nid
        return mejor

    def _manhattan_path_in_zone(self, start_nid: int, end_nid: int) -> list[int]:
        """Genera un camino en línea recta (Manhattan) entre dos nodos de la misma zona."""
        n_start = self.warehouse.grafo.nodo(start_nid)
        n_end = self.warehouse.grafo.nodo(end_nid)
        path = [start_nid]
        curr_x, curr_y = n_start.posicion.x, n_start.posicion.y
        target_x, target_y = n_end.posicion.x, n_end.posicion.y

        while curr_x != target_x:
            curr_x += 1 if target_x > curr_x else -1
            nid = self.warehouse._nodo_por_xy.get((curr_x, curr_y))
            if nid:
                path.append(nid)
        while curr_y != target_y:
            curr_y += 1 if target_y > curr_y else -1
            nid = self.warehouse._nodo_por_xy.get((curr_x, curr_y))
            if nid:
                path.append(nid)
        return path

    def _buscar_nodo_final_exterior(self, ep: EstadoPicker) -> int | None:
        """Busca un pasillo adyacente para que el picker descanse al terminar."""
        nodo_actual = self.warehouse.grafo.nodo(ep.nodo_actual)
        if nodo_actual.tipo == TipoNodo.PASILLO:
            return ep.nodo_actual  # Ya está en el pasillo
        for a in self.warehouse.grafo.vecinos(ep.nodo_actual):
            nodo = self.warehouse.grafo.nodo(a.destino)
            if nodo.tipo == TipoNodo.PASILLO:
                return a.destino  # Encontró el pasillo de al lado de la puerta
        return None

    def avanzar(self) -> bool:
        if self.completada:
            return False

        t_inicio_tick = time.perf_counter()
        self.paso_actual += 1

        for pid, ep in self.pickers.items():
            if ep.espera_restante > 0 or ep.fase in (
                "TERMINADO",
                "RECOGIENDO",
                "DESCARGANDO",
            ):
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
                    zona = self._zona_mas_cercana(ep)
                    if zona:
                        ep.zona_objetivo = zona
                        puerta = self.warehouse.puertas[zona.puerta_id]
                        nodo_puerta = puerta.nodo
                        nodo_dentro = self._buscar_celda_libre_zona(zona, nodo_puerta)

                        if nodo_dentro:
                            # Ruta exterior a la puerta + ruta interior (Manhattan)
                            path_ext = self.cache.camino(ep.nodo_actual, nodo_puerta)
                            path_int = self._manhattan_path_in_zone(
                                nodo_puerta, nodo_dentro
                            )
                            ep.camino_actual = path_ext + path_int[1:]
                            ep.fase = "YENDO_A_DESPACHO"
                        else:
                            ep.espera_restante = 1  # Zona llena
                else:
                    # Terminó tareas. Buscar pasillo exterior.
                    nodo_final = self._buscar_nodo_final_exterior(ep)
                    if nodo_final:
                        ep.camino_actual = self.cache.camino(ep.nodo_actual, nodo_final)
                        ep.fase = "YENDO_A_FINAL"
                    else:
                        ep.fase = "TERMINADO"
                        ep.camino_actual = []

            if ep.fase in (
                "YENDO_A_ITEM",
                "YENDO_A_DESPACHO",
                "SALIENDO_DE_ZONA",
                "YENDO_A_FINAL",
            ):
                if len(ep.camino_actual) <= 1:
                    if ep.fase == "YENDO_A_ITEM" and ep.tarea_actual:
                        prod = self.warehouse.productos[ep.tarea_actual.producto_id]
                        ep.espera_restante = prod.z
                        ep.fase = "RECOGIENDO"

                    elif ep.fase == "YENDO_A_DESPACHO":
                        ep.espera_restante = 2
                        ep.fase = "DESCARGANDO"

                    elif ep.fase == "SALIENDO_DE_ZONA":
                        ep.fase = "BUSCANDO_TAREA"
                        ep.camino_actual = []
                        ep.zona_objetivo = None

                    elif ep.fase == "YENDO_A_FINAL":
                        ep.fase = "TERMINADO"
                        ep.camino_actual = []

        # Detección de colisiones
        propuestas = {}
        for pid, ep in self.pickers.items():
            if (
                ep.fase in ("BUSCANDO_TAREA", "RECOGIENDO", "DESCARGANDO", "TERMINADO")
                or ep.espera_restante > 0
            ):
                continue
            if len(ep.camino_actual) > 1:
                propuestas[pid] = ep.camino_actual[1]

        ocupadas_ahora = {
            ep.nodo_actual: pid
            for pid, ep in self.pickers.items()
            if ep.fase != "TERMINADO"
        }
        bloqueados = set()

        destinos = {}
        for pid, dst in propuestas.items():
            destinos.setdefault(dst, []).append(pid)
        for dst, pids in destinos.items():
            if len(pids) > 1:
                pids.sort()
                bloqueados.update(pids[1:])

        for pid, dst in propuestas.items():
            if dst in ocupadas_ahora and ocupadas_ahora[dst] not in propuestas:
                bloqueados.add(pid)

        for pid, dst in propuestas.items():
            origen = self.pickers[pid].nodo_actual
            for other_pid, other_dst in propuestas.items():
                if (
                    pid != other_pid
                    and other_dst == origen
                    and propuestas[other_pid] == origen
                    and self.pickers[other_pid].nodo_actual == dst
                ):
                    bloqueados.add(pid)
                    bloqueados.add(other_pid)

        # Movimiento
        for pid, ep in self.pickers.items():
            if ep.espera_restante > 0:
                ep.espera_restante -= 1
                if ep.espera_restante == 0:
                    if ep.fase == "RECOGIENDO" and ep.tarea_actual:
                        prod = self.warehouse.productos[ep.tarea_actual.producto_id]
                        peso_disponible = ep.picker.capacidad_carga_kg - ep.carga_kg
                        max_unidades = int(peso_disponible // prod.peso_kg)
                        cant_real = min(ep.tarea_actual.cantidad, max_unidades)
                        if cant_real > 0:
                            ep.carga_kg += prod.peso_kg * cant_real
                            ep.productos_recogidos.add(ep.tarea_actual.producto_id)
                            ep.tarea_actual.cantidad -= cant_real
                            if ep.tarea_actual.cantidad > 0:
                                ep.tarea_actual.asignada_a = None
                            else:
                                ep.tarea_actual.completada = True
                        ep.tarea_actual = None
                        ep.fase = "BUSCANDO_TAREA"

                    elif ep.fase == "DESCARGANDO":
                        zona = self.zonas_despacho.get(ep.nodo_actual)
                        if zona:
                            self.peso_en_zona[zona.id] += ep.carga_kg
                            self.cajas_en_zona[ep.nodo_actual] = (
                                self.cajas_en_zona.get(ep.nodo_actual, 0) + 1
                            )

                            # Ruta interna de salida a la puerta
                            puerta_nodo = self.warehouse.puertas[zona.puerta_id].nodo
                            ep.camino_actual = self._manhattan_path_in_zone(
                                ep.nodo_actual, puerta_nodo
                            )
                            ep.fase = "SALIENDO_DE_ZONA"
                        else:
                            ep.fase = "BUSCANDO_TAREA"
                        ep.carga_kg = 0.0
                continue

            if pid in propuestas and pid not in bloqueados:
                ep.bloqueos_consecutivos = 0
                ep.nodo_actual = propuestas[pid]
                ep.camino_actual.pop(0)

                self.aristas_recorridas += 1
                self.distancia_total += 1.0
                self.nodos_visitados += 1

            elif pid in bloqueados:
                ep.bloqueos_consecutivos += 1
                if ep.bloqueos_consecutivos >= 2:
                    ep.bloqueos_consecutivos = 0
                    if ep.fase in (
                        "YENDO_A_DESPACHO",
                        "SALIENDO_DE_ZONA",
                        "YENDO_A_FINAL",
                    ):
                        continue

                    vecinos = [
                        a.destino for a in self.warehouse.grafo.vecinos(ep.nodo_actual)
                    ]
                    vecinos_libres = [v for v in vecinos if v not in ocupadas_ahora]
                    if vecinos_libres:
                        ep.nodo_actual = random.choice(vecinos_libres)
                        if ep.fase == "YENDO_A_ITEM" and ep.tarea_actual:
                            ep.camino_actual = self.cache.camino(
                                ep.nodo_actual, ep.tarea_actual.nodo_picking
                            )

        self.tiempo_ejecucion += time.perf_counter() - t_inicio_tick
        return True
