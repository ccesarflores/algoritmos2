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
    productos_entregados: set[str] = field(default_factory=set)
    distancia_total: float = 0.0
    aristas_recorridas: int = 0
    nodos_visitados: int = 0
    tiempo_ejecucion: float = 0.0

    def copiar_estado(self) -> "SimulacionDinamica":
        """Hace un snapshot rápido del estado actual para poder retroceder."""
        estado_mutable = {
            "pickers": self.pickers,
            "tareas_pendientes": self.tareas_pendientes,
            "peso_en_zona": self.peso_en_zona,
            "cajas_en_zona": self.cajas_en_zona,
            "productos_entregados": self.productos_entregados,
        }
        copia = copy.deepcopy(estado_mutable)

        return SimulacionDinamica(
            pickers=copia["pickers"],
            tareas_pendientes=copia["tareas_pendientes"],
            productos_totales=self.productos_totales,
            nodo_a_productos=self.nodo_a_productos,
            cantidad_pedida=self.cantidad_pedida,
            cache=self.cache,
            warehouse=self.warehouse,
            paso_actual=self.paso_actual,
            zonas_despacho=self.zonas_despacho,
            peso_en_zona=copia["peso_en_zona"],
            cajas_en_zona=copia["cajas_en_zona"],
            productos_entregados=copia["productos_entregados"],
            distancia_total=self.distancia_total,
            aristas_recorridas=self.aristas_recorridas,
            nodos_visitados=self.nodos_visitados,
            tiempo_ejecucion=self.tiempo_ejecucion,
        )

    @classmethod
    def desde_waves(
        cls,
        waves: list[Wave],
        pickers: list[Picker],
        warehouse: Warehouse,
        posiciones_aleatorias: bool = False
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
                    tareas_dict[pid] = Tarea(producto_id=pid, cantidad=0, nodo_picking=prod.nodo_picking)
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

        # NUEVO: Obtener todos los nodos de pasillo disponibles
        nodos_pasillo = [
            nid for nid, nodo in warehouse.grafo._nodos.items()
            if nodo.tipo == TipoNodo.PASILLO
        ]
        if posiciones_aleatorias:
            random.shuffle(nodos_pasillo)

        estado_pickers = {}
        for i, base_picker in enumerate(pickers):
            picker = copy.deepcopy(base_picker)

            # Si pedimos aleatorio, tomamos el i-ésimo pasillo mezclado
            if posiciones_aleatorias and i < len(nodos_pasillo):
                nodo_inicio = nodos_pasillo[i]
            else:
                nodo_inicio = warehouse._nodo_por_xy.get(base_picker.posicion_inicial)
                if nodo_inicio is None:
                    nodo_inicio = next(iter(warehouse._nodo_por_xy.values()))

            estado_pickers[picker.id] = EstadoPicker(picker=picker, nodo_actual=nodo_inicio)

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

    def _camino_rodeando_zonas(self, start_nid: int, end_nid: int) -> list[int]:
        """Calcula una ruta que evita atravesar cualquier celda de zona de despacho."""
        from collections import deque
        queue = deque([(start_nid, [start_nid])])
        visited = {start_nid}

        while queue:
            current, path = queue.popleft()
            if current == end_nid:
                return path

            for a in self.warehouse.grafo.vecinos(current):
                vecino = a.destino
                if vecino in visited:
                    continue
                if self.zonas_despacho.get(vecino) is not None:
                    continue

                visited.add(vecino)
                queue.append((vecino, path + [vecino]))

        return [start_nid, end_nid]

    def _es_celda_segura_para_caja(self, zona, target_nid, nodo_puerta) -> bool:
        from collections import deque
        temp_cajas = self.cajas_en_zona.copy()
        temp_cajas[target_nid] = temp_cajas.get(target_nid, 0) + 1

        empty_cells = set()
        for x in range(zona.p1[0], zona.p2[0] + 1):
            for y in range(zona.p1[1], zona.p2[1] + 1):
                nid = self.warehouse._nodo_por_xy.get((x, y))
                if nid and temp_cajas.get(nid, 0) == 0:
                    empty_cells.add(nid)

        if not empty_cells:
            return True

        queue = deque([nodo_puerta])
        visited = {nodo_puerta}
        reached = 0

        while queue:
            current = queue.popleft()
            if current in empty_cells:
                reached += 1

            for a in self.warehouse.grafo.vecinos(current):
                vecino = a.destino
                if vecino in visited:
                    continue
                if self.zonas_despacho.get(vecino) != zona:
                    continue
                if temp_cajas.get(vecino, 0) > 0:
                    continue
                visited.add(vecino)
                queue.append(vecino)

        return reached == len(empty_cells)

    def _path_a_celda_libre(self, zona, nodo_puerta) -> list[int] | None:
        from collections import deque
        queue = deque([(nodo_puerta, [nodo_puerta])])
        visited = {nodo_puerta}
        pickers_ocupados = {p.nodo_actual for p in self.pickers.values()}

        while queue:
            current, path = queue.popleft()
            dist_to_door = self.cache.distancia(current, nodo_puerta)
            if (current != nodo_puerta and dist_to_door > 1
                and self.cajas_en_zona.get(current, 0) == 0
                and current not in pickers_ocupados):
                if self._es_celda_segura_para_caja(zona, current, nodo_puerta):
                    return path

            for a in self.warehouse.grafo.vecinos(current):
                vecino = a.destino
                if vecino in visited:
                    continue
                if self.zonas_despacho.get(vecino) != zona:
                    continue
                if self.cajas_en_zona.get(vecino, 0) > 0:
                    continue
                visited.add(vecino)
                queue.append((vecino, path + [vecino]))
        return None

    def _path_desde_zona_a_puerta(self, zona, nodo_actual, nodo_puerta) -> list[int]:
        from collections import deque
        queue = deque([(nodo_actual, [nodo_actual])])
        visited = {nodo_actual}

        while queue:
            current, path = queue.popleft()
            if current == nodo_puerta:
                return path

            for a in self.warehouse.grafo.vecinos(current):
                vecino = a.destino
                if vecino in visited:
                    continue
                if self.zonas_despacho.get(vecino) != zona and vecino != nodo_puerta:
                    continue
                if self.cajas_en_zona.get(vecino, 0) > 0:
                    continue

                visited.add(vecino)
                queue.append((vecino, path + [vecino]))

        return [nodo_actual]

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
        zona_llena_cercana = None
        dist_llena = float("inf")

        for zona in self.warehouse.zonas.values():
            puerta = self.warehouse.puertas.get(zona.puerta_id)
            if not puerta:
                continue

            d = self.cache.distancia(ep.nodo_actual, puerta.nodo)

            # Si hay capacidad de peso, es candidata principal
            if self.peso_en_zona[zona.id] + ep.carga_kg <= zona.peso_max_kg:
                if d < mejor_dist:
                    mejor_dist = d
                    mejor_zona = zona
            else:
                # Si está llena, la guardamos como opción de emergencia
                if d < dist_llena:
                    dist_llena = d
                    zona_llena_cercana = zona

        # FORZAR ENTREGA: Si no hay ninguna con capacidad, devolvemos la más cercana (aunque se pase de peso)
        return mejor_zona if mejor_zona else zona_llena_cercana

    def _buscar_nodo_final_exterior(self, ep: EstadoPicker) -> int | None:
        """Busca un pasillo alejado de la puerta y prioriza los cercanos al centro."""
        from collections import deque
        queue = deque([(ep.nodo_actual, 0)])
        visited = {ep.nodo_actual}

        center_x = self.warehouse.ancho // 2
        center_y = self.warehouse.alto // 2

        # NUEVO: Obtener todas las celdas ocupadas para no estacionar sobre otro
        ocupadas = {p.nodo_actual for p in self.pickers.values()}

        mejor_nodo = None
        mejor_dist_centro = float("inf")

        while queue:
            current, dist = queue.popleft()
            n_curr = self.warehouse.grafo.nodo(current)

            # Buscamos pasillos a 3+ celdas, que NO sean zona, y que NO estén ocupados
            if dist >= 3 and n_curr.tipo == TipoNodo.PASILLO and self.zonas_despacho.get(current) is None:
                if current not in ocupadas: # <-- LA CLAVE ESTÁ ACÁ
                    d_centro = abs(n_curr.posicion.x - center_x) + abs(n_curr.posicion.y - center_y)
                    if d_centro < mejor_dist_centro:
                        mejor_dist_centro = d_centro
                        mejor_nodo = current

            if dist < 10:
                for a in self.warehouse.grafo.vecinos(current):
                    v = a.destino
                    if v not in visited and self.zonas_despacho.get(v) is None:
                        visited.add(v)
                        queue.append((v, dist + 1))

        return mejor_nodo if mejor_nodo else ep.nodo_actual

    def avanzar(self) -> bool:
        if self.completada:
            return False

        t_inicio_tick = time.perf_counter()
        self.paso_actual += 1

        for pid, ep in self.pickers.items():
            if ep.espera_restante > 0 or ep.fase in ("TERMINADO", "RECOGIENDO", "DESCARGANDO"):
                continue

            if ep.fase == "BUSCANDO_TAREA":
                tarea = self._buscar_siguiente_tarea(ep)
                if tarea:
                    ep.tarea_actual = tarea
                    ep.camino_actual = self._camino_rodeando_zonas(ep.nodo_actual, tarea.nodo_picking)
                    ep.fase = "YENDO_A_ITEM"
                elif ep.carga_kg > 0:
                    zona = self._zona_mas_cercana(ep)
                    if zona:
                        ep.zona_objetivo = zona
                        puerta = self.warehouse.puertas[zona.puerta_id]
                        nodo_puerta = puerta.nodo
                        ep.camino_actual = self._camino_rodeando_zonas(ep.nodo_actual, nodo_puerta)
                        ep.fase = "YENDO_A_DESPACHO"
                    else:
                        ep.espera_restante = 1
                else:
                    nodo_final = self._buscar_nodo_final_exterior(ep)
                    if nodo_final:
                        ep.camino_actual = self._camino_rodeando_zonas(ep.nodo_actual, nodo_final)
                        ep.fase = "YENDO_A_FINAL"
                    else:
                        ep.fase = "TERMINADO"
                        ep.camino_actual = []

            if ep.fase in ("YENDO_A_ITEM", "YENDO_A_DESPACHO", "ENTRANDO_A_ZONA", "SALIENDO_DE_ZONA", "YENDO_A_FINAL"):
                if len(ep.camino_actual) <= 1:
                    if ep.fase == "YENDO_A_ITEM" and ep.tarea_actual:
                        prod = self.warehouse.productos[ep.tarea_actual.producto_id]
                        ep.espera_restante = prod.z
                        ep.fase = "RECOGIENDO"

                    elif ep.fase == "YENDO_A_DESPACHO":
                        if ep.zona_objetivo:
                            camino_adentro = self._path_a_celda_libre(ep.zona_objetivo, ep.nodo_actual)
                            if camino_adentro:
                                ep.camino_actual = camino_adentro
                                ep.fase = "ENTRANDO_A_ZONA"
                            else:
                                ep.espera_restante = 1
                        else:
                            ep.fase = "BUSCANDO_TAREA"
                            ep.camino_actual = []

                    elif ep.fase == "ENTRANDO_A_ZONA":
                        ep.espera_restante = 2
                        ep.fase = "DESCARGANDO"

                    elif ep.fase == "SALIENDO_DE_ZONA":
                        ep.fase = "BUSCANDO_TAREA"
                        ep.camino_actual = []
                        ep.zona_objetivo = None
                        ep.espera_restante = 1

                    elif ep.fase == "YENDO_A_FINAL":
                        ep.fase = "TERMINADO"
                        ep.camino_actual = []

        propuestas = {}
        for pid, ep in self.pickers.items():
            if ep.fase in ("BUSCANDO_TAREA", "RECOGIENDO", "DESCARGANDO", "TERMINADO") or ep.espera_restante > 0:
                continue
            if len(ep.camino_actual) > 1:
                propuestas[pid] = ep.camino_actual[1]

        ocupadas_ahora = {ep.nodo_actual: pid for pid, ep in self.pickers.items() if ep.fase != "TERMINADO"}
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
                if (pid != other_pid and other_dst == origen and propuestas[other_pid] == origen and self.pickers[other_pid].nodo_actual == dst):
                    fase_a = self.pickers[pid].fase
                    fase_b = self.pickers[other_pid].fase

                    if fase_a == "SALIENDO_DE_ZONA" and fase_b in ("YENDO_A_DESPACHO", "ENTRANDO_A_ZONA"):
                        bloqueados.add(other_pid)
                    elif fase_b == "SALIENDO_DE_ZONA" and fase_a in ("YENDO_A_DESPACHO", "ENTRANDO_A_ZONA"):
                        bloqueados.add(pid)
                    else:
                        bloqueados.add(pid)
                        bloqueados.add(other_pid)

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
                            self.cajas_en_zona[ep.nodo_actual] = self.cajas_en_zona.get(ep.nodo_actual, 0) + 1
                            self.productos_entregados.update(ep.productos_recogidos)
                            puerta_nodo = self.warehouse.puertas[zona.puerta_id].nodo
                            ep.camino_actual = self._path_desde_zona_a_puerta(zona, ep.nodo_actual, puerta_nodo)
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

                    if ep.fase in ("YENDO_A_DESPACHO", "ENTRANDO_A_ZONA", "SALIENDO_DE_ZONA", "YENDO_A_FINAL"):
                        continue

                    vecinos = [a.destino for a in self.warehouse.grafo.vecinos(ep.nodo_actual)]
                    vecinos_libres = [v for v in vecinos if v not in ocupadas_ahora]
                    if vecinos_libres:
                        ep.nodo_actual = random.choice(vecinos_libres)
                        if ep.fase == "YENDO_A_ITEM" and ep.tarea_actual:
                            ep.camino_actual = self._camino_rodeando_zonas(ep.nodo_actual, ep.tarea_actual.nodo_picking)

        self.tiempo_ejecucion += time.perf_counter() - t_inicio_tick
        return True
