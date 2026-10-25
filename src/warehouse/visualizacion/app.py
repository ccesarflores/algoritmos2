"""Aplicación Tk de simulación Dinámica."""
import copy
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from warehouse.simulacion.dinamica import SimulacionDinamica
from warehouse.visualizacion.render import (COLOR_CANVAS_FONDO, COLOR_PICKER,
                                            COLOR_PRODUCTO_INVENTARIO,
                                            COLOR_PRODUCTO_PENDIENTE,
                                            COLOR_PRODUCTO_RECOGIDO,
                                            COLOR_RECORRIDO_HECHO,
                                            COLOR_RECORRIDO_PENDIENTE,
                                            centro_celda_px,
                                            crear_panel_leyenda,
                                            dibujar_polilinea, dibujar_punto,
                                            dibujar_warehouse)
from warehouse.visualizacion.sprites import SpriteLoader

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

ANCHO_CANVAS = 850
ALTO_CANVAS = 500


class SimulacionApp:
    def __init__(
        self,
        escenario,
        simulacion: SimulacionDinamica,
        estrategia: str,
        delay_caminar: int = 100,
        delay_esperar: int = 1000,
        picker_scale: float = 2.2,
        rack_scale: float = 0.92,
    ) -> None:
        self.escenario = escenario
        self.simulacion = simulacion
        self.simulacion_inicial = copy.deepcopy(simulacion)
        self.estrategia = estrategia
        self.delay_caminar = delay_caminar
        self.delay_esperar = delay_esperar

        self.sprites = SpriteLoader(picker_scale, rack_scale)

        self.root: ctk.CTk | None = None
        self.celda_px = 30
        self.ancho_canvas = ANCHO_CANVAS
        self.alto_canvas = ALTO_CANVAS
        self.margen = 20

        self.after_id = None
        self.coords: dict = {}
        self.labels_productos: dict[str, ctk.CTkLabel] = {}
        self.rack_resaltado: tuple[int, int] | None = None

    def run(self) -> None:
        self.root = ctk.CTk()
        self.root.withdraw()

        alto_pantalla = self.root.winfo_screenheight()
        ancho_pantalla = self.root.winfo_screenwidth()
        self.ancho_canvas = min(ANCHO_CANVAS, ancho_pantalla - 450)
        self.alto_canvas = min(ALTO_CANVAS, alto_pantalla - 250)
        celda_px_w = (self.ancho_canvas - 2 * self.margen) // self.escenario.warehouse.ancho
        celda_px_h = (self.alto_canvas - 2 * self.margen) // self.escenario.warehouse.alto
        self.celda_px = max(4, min(celda_px_w, celda_px_h))

        self.sprites.set_celda_px(self.celda_px)
        self.sprites.cargar()

        self.root.deiconify()
        self.root.title(f"Demo — Multi-Picker Dinámico — {self.estrategia}")
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_rowconfigure(3, weight=0)
        self.root.grid_columnconfigure(0, weight=1)

        self._construir_ui()
        try:
            self._construir_lista_productos()
            self._redibujar_todo()
        except Exception:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error al iniciar", "Ver consola.")

        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        x = max((self.root.winfo_screenwidth() - w) // 2, 0)
        y = max((self.root.winfo_screenheight() - h) // 2, 0)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.mainloop()

    def _cerrar(self) -> None:
        self.pause()
        if self.root is not None:
            self.root.destroy()

    def _construir_ui(self) -> None:
        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        self.lbl_titulo = ctk.CTkLabel(
            header, text="Simulación Multi-Picker Dinámica", anchor="w",
            font=ctk.CTkFont(family="sans-serif", size=16, weight="bold"),
        )
        self.lbl_titulo.pack(side="left")

        self.progress = ctk.CTkProgressBar(header, width=300)
        self.progress.set(0)
        self.progress.pack(side="right", padx=20)

        frame_busqueda = ctk.CTkFrame(self.root, fg_color="transparent")
        frame_busqueda.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 0))

        ctk.CTkLabel(frame_busqueda, text="🔍 Buscar producto:",
                     font=ctk.CTkFont(size=12)).pack(side="left")
        self.entry_busqueda = ctk.CTkEntry(
            frame_busqueda, width=200,
            font=ctk.CTkFont(family="monospace", size=12),
        )
        self.entry_busqueda.pack(side="left", padx=(6, 12))
        self.entry_busqueda.bind("<KeyRelease>", self._on_buscar)
        self.entry_busqueda.bind("<Escape>", self._limpiar_busqueda)

        self.lbl_resultados_busqueda = ctk.CTkLabel(
            frame_busqueda, text="", anchor="w",
            text_color="#aaaaaa",
            font=ctk.CTkFont(family="monospace", size=11),
        )
        self.lbl_resultados_busqueda.pack(side="left", fill="x", expand=True)

        frame_principal = ctk.CTkFrame(self.root, fg_color=COLOR_CANVAS_FONDO)
        frame_principal.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

        self.canvas = tk.Canvas(
            frame_principal, bg=COLOR_CANVAS_FONDO,
            width=self.ancho_canvas, height=self.alto_canvas,
            highlightthickness=1, highlightbackground="#3a3a3a",
        )
        self.canvas.pack(side="left", anchor="n", padx=(0, 10))

        panel_derecho = ctk.CTkFrame(frame_principal, fg_color="transparent", width=320)
        panel_derecho.pack(side="left", fill="both", expand=True)
        panel_derecho.pack_propagate(False)

        crear_panel_leyenda(panel_derecho).pack(side="top", fill="x")

        panel_info = ctk.CTkFrame(panel_derecho, fg_color="transparent")
        panel_info.pack(side="top", fill="both", expand=True, pady=(10, 0))

        ctk.CTkLabel(panel_info, text="Estado de la Simulación", anchor="w",
                     font=ctk.CTkFont(family="sans-serif", size=13, weight="bold"),
                     text_color="#ffffff").pack(fill="x", pady=(0, 5))

        mono = ctk.CTkFont(family="monospace", size=11)

        # Etiquetas sin duplicados
        self.lbl_info_waves = ctk.CTkLabel(panel_info, text="", anchor="w", font=mono, text_color="#ffffff")
        self.lbl_info_waves.pack(fill="x", pady=(0, 5))

        self.lbl_info_paso = ctk.CTkLabel(panel_info, text="", anchor="w", font=mono, text_color="#ffffff")
        self.lbl_info_paso.pack(fill="x")

        self.lbl_info_prod = ctk.CTkLabel(panel_info, text="", anchor="w", font=mono, text_color="#ffffff")
        self.lbl_info_prod.pack(fill="x")

        self.lbl_info_prio = ctk.CTkLabel(panel_info, text="", anchor="w", font=mono, text_color="#ffffff")
        self.lbl_info_prio.pack(fill="x", pady=(0, 10))

        # SEPARADOR MÉTRICAS
        ctk.CTkLabel(panel_info, text="Métricas de Rendimiento", anchor="w",
                     font=ctk.CTkFont(family="sans-serif", size=12, weight="bold"),
                     text_color="#64b5f6").pack(fill="x", pady=(10, 5))

        mono_small = ctk.CTkFont(family="monospace", size=10)

        self.lbl_met_distancia = ctk.CTkLabel(panel_info, text="", anchor="w", font=mono_small, text_color="#aaaaaa")
        self.lbl_met_distancia.pack(fill="x")

        self.lbl_met_aristas = ctk.CTkLabel(panel_info, text="", anchor="w", font=mono_small, text_color="#aaaaaa")
        self.lbl_met_aristas.pack(fill="x")

        self.lbl_met_nodos = ctk.CTkLabel(panel_info, text="", anchor="w", font=mono_small, text_color="#aaaaaa")
        self.lbl_met_nodos.pack(fill="x")

        self.lbl_met_tiempo = ctk.CTkLabel(panel_info, text="", anchor="w", font=mono_small, text_color="#aaaaaa")
        self.lbl_met_tiempo.pack(fill="x")

        ctk.CTkLabel(panel_info, text="Productos a recoger:", anchor="w",
                     font=ctk.CTkFont(family="sans-serif", size=11, weight="bold"),
                     text_color="#ffffff").pack(fill="x", pady=(10, 5))

        self.frame_productos = ctk.CTkScrollableFrame(panel_info, fg_color="#252525", height=150)
        self.frame_productos.pack(fill="both", expand=True)

        # --- AQUÍ ESTÁ LA MAGIA PARA RECUPERAR LOS BOTONES ---
        panel = ctk.CTkFrame(self.root, fg_color="transparent")
        panel.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10)) # <-- Faltaba esta línea

        self.btn_play_pause = ctk.CTkButton(panel, text="▶ Play", command=self.toggle_play_pause, width=90)
        self.btn_play_pause.pack(side="left", padx=2)
        ctk.CTkButton(panel, text="⏭ Step", command=self.step, width=80).pack(side="left", padx=2)
        ctk.CTkButton(panel, text="⟲ Reset", command=self.reset, width=80).pack(side="left", padx=2)

        ctk.CTkButton(panel, text="✕ Cerrar", command=self._cerrar, width=90).pack(side="right", padx=2)

    def _redibujar_todo(self) -> None:
        self.canvas.delete("all")
        self.coords = dibujar_warehouse(
            self.canvas, self.escenario.warehouse, self.celda_px, self.margen
        )

        # Racks
        rack_img = self.sprites.obtener_rack()
        if rack_img is not None:
            for rack in self.escenario.warehouse.racks.values():
                for rx in range(rack.x, rack.x + rack.ancho):
                    for ry in range(rack.y, rack.y + rack.alto):
                        if (rx, ry) in self.coords:
                            cx, cy = centro_celda_px(self.coords, rx, ry)
                            self.canvas.create_image(cx, cy, image=rack_img, anchor="center")

        if self.simulacion is None:
            return

        # --- Dibujar puertas con imagen ---
        door_img = self.sprites.obtener_door()
        if door_img is not None:
            for puerta in self.escenario.warehouse.puertas.values():
                if (puerta.posicion.x, puerta.posicion.y) in self.coords:
                    cx, cy = centro_celda_px(self.coords, puerta.posicion.x, puerta.posicion.y)
                    self.canvas.create_image(cx, cy, image=door_img, anchor="center")

        if self.simulacion is None:
            return

        # Pasillos (Flechas)
        for pasillo in self.escenario.warehouse.pasillos.values():
            if pasillo.sentido == "N": flecha = "↑"
            elif pasillo.sentido == "S": flecha = "↓"
            elif pasillo.sentido == "E": flecha = "→"
            elif pasillo.sentido == "O": flecha = "←"
            else:
                flecha = "↔" if pasillo.ancho > pasillo.alto else "↕"

            # Calculamos un tamaño de fuente más armónico (40% de la celda)
            font_size = max(6, int(self.celda_px * 0.4))
            fuente_flecha = ("sans-serif", font_size, "bold")

            if pasillo.ancho > pasillo.alto:
                # Pasillo horizontal: dibujar una cada 4 celdas
                for x_off in range(0, pasillo.ancho, 4):
                    cx_p, cy_p = centro_celda_px(self.coords, pasillo.x + x_off, pasillo.y + pasillo.alto // 2)
                    self.canvas.create_text(cx_p, cy_p, text=flecha, fill="#555555", font=fuente_flecha)
            else:
                # Pasillo vertical: dibujar una cada 4 celdas
                for y_off in range(0, pasillo.alto, 4):
                    cx_p, cy_p = centro_celda_px(self.coords, pasillo.x + pasillo.ancho // 2, pasillo.y + y_off)
                    self.canvas.create_text(cx_p, cy_p, text=flecha, fill="#555555", font=fuente_flecha)

        def centro(nid: int) -> tuple[float, float]:
            nodo = self.escenario.warehouse.grafo.nodo(nid)
            return centro_celda_px(self.coords, nodo.posicion.x, nodo.posicion.y)

        # Recorridos dinámicos
        for ep in self.simulacion.pickers.values():
            if ep.fase == "TERMINADO":
                continue

            puntos = [centro(ep.nodo_actual)] + [centro(nid) for nid in ep.camino_actual]
            if len(puntos) > 1:
                dibujar_polilinea(self.canvas, puntos, color=COLOR_RECORRIDO_PENDIENTE, grosor=1, dash=(3, 3))

        # Productos
        recogidos = self.simulacion.productos_totales - self.simulacion.productos_pendientes
        productos_de_la_wave = self.simulacion.productos_totales

        for pid, prod in self.escenario.warehouse.productos.items():
            cx_cell, cy_cell = centro_celda_px(self.coords, prod.x, prod.y)
            rack = self.escenario.warehouse.racks[prod.rack_id]
            niveles = rack.niveles
            separacion = self.celda_px * 0.25

            if niveles == 1: y_pos = cy_cell
            else:
                z_relativo = (prod.z - 1) / (niveles - 1)
                offset = separacion * (niveles - 1) / 2
                y_pos = cy_cell + offset - (z_relativo * 2 * offset)

            if pid in recogidos: color = COLOR_PRODUCTO_RECOGIDO
            elif pid in productos_de_la_wave: color = COLOR_PRODUCTO_PENDIENTE
            else: color = COLOR_PRODUCTO_INVENTARIO

            icono_prod = self.sprites.obtener_producto(pid)
            if icono_prod is not None:
                self.canvas.create_image(cx_cell, y_pos - (self.celda_px*0.05), image=icono_prod, anchor="center")
                radio = self.celda_px * 0.06
                self.canvas.create_oval(cx_cell - radio, y_pos + self.celda_px*0.1 - radio, cx_cell + radio, y_pos + self.celda_px*0.1 + radio, fill=color, outline="white", width=1)
            else:
                dibujar_punto(self.canvas, cx_cell, y_pos, radio=self.celda_px * 0.09, color=color)

        # Dibujar las cajas depositadas en la zona de despacho
        caja_img = self.sprites.obtener_caja()
        for nid, cantidad in self.simulacion.cajas_en_zona.items():
            if cantidad > 0:
                cx_box, cy_box = centro(nid)
                if caja_img is not None:
                    self.canvas.create_image(cx_box, cy_box, image=caja_img, anchor="center")
                else:
                    # Fallback si no hay box.png
                    dibujar_punto(self.canvas, cx_box, cy_box, self.celda_px * 0.3, "#a0522d")

        # Pickers
        for picker_id, ep in self.simulacion.pickers.items():
            cx, cy = centro(ep.nodo_actual)

            if ep.espera_restante > 0:
                self.canvas.create_text(cx, cy - self.celda_px * 1.8, text=f"⏳ {ep.espera_restante}", fill="#ffb74d", font=("sans-serif", 10, "bold"), anchor="s")

            self.canvas.create_text(cx, cy - self.celda_px * 0.8, text=f"{ep.carga_kg:.1f} kg", fill="white", font=("sans-serif", 7))

            direccion = self._calcular_direccion(ep)
            picker_foto = self.sprites.obtener_picker(direccion)
            if picker_foto is not None:
                self.canvas.create_image(cx, cy, image=picker_foto, anchor="center")
            else:
                self._dibujar_picker_stick(cx, cy)

            self.canvas.create_text(cx, cy + self.celda_px * 0.8, text=picker_id, fill="white", font=("sans-serif", 8, "bold"))

        self._actualizar_label()
        self._actualizar_panel_info()

    def _dibujar_picker_stick(self, cx: float, cy: float) -> None:
        c = self.celda_px
        color = COLOR_PICKER
        w = max(2, int(c * 0.08))
        head_r = c * 0.15
        head_cy = cy - c * 0.5
        self.canvas.create_oval(cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r, fill=color, outline="white", width=1)
        self.canvas.create_line(cx, head_cy + head_r, cx, cy + c * 0.1, fill=color, width=w)
        arm_y = cy - c * 0.2
        arm_dx = c * 0.25
        self.canvas.create_line(cx - arm_dx, arm_y, cx + arm_dx, arm_y, fill=color, width=w)
        leg_y = cy + c * 0.1
        leg_dx = c * 0.18
        self.canvas.create_line(cx, leg_y, cx - leg_dx, cy + c * 0.5, fill=color, width=w)
        self.canvas.create_line(cx, leg_y, cx + leg_dx, cy + c * 0.5, fill=color, width=w)

    def _calcular_direccion(self, ep) -> str:
        if ep.espera_restante > 0:
            if ep.fase == "RECOGIENDO" and ep.tarea_actual:
                prod = self.escenario.warehouse.productos[ep.tarea_actual.producto_id]
                nodo = self.escenario.warehouse.grafo.nodo(ep.nodo_actual)
                if prod.x > nodo.posicion.x: return "right"
                if prod.x < nodo.posicion.x: return "left"
                if prod.y > nodo.posicion.y: return "down"
                if prod.y < nodo.posicion.y: return "up"
            return "right"

        # Si está terminado o no tiene camino, que mire hacia abajo
        if ep.fase == "TERMINADO" or not ep.camino_actual or len(ep.camino_actual) < 2:
            return "down"

        nodo_actual = self.escenario.warehouse.grafo.nodo(ep.nodo_actual)
        nodo_siguiente = self.escenario.warehouse.grafo.nodo(ep.camino_actual[1])

        dx = nodo_siguiente.posicion.x - nodo_actual.posicion.x
        dy = nodo_siguiente.posicion.y - nodo_actual.posicion.y

        if dx > 0: return "right"
        if dx < 0: return "left"
        if dy < 0: return "up"
        if dy > 0: return "down"
        return "right"

    def _actualizar_label(self) -> None:
        if not self.simulacion: return

        txt = f"Paso global: {self.simulacion.paso_actual} | "
        completados = sum(1 for ep in self.simulacion.pickers.values() if ep.fase == "TERMINADO")
        txt += f"Pickers completados: {completados}/{len(self.simulacion.pickers)}"

        if self.simulacion.completada:
            txt += " ✔"

        total = len(self.simulacion.productos_totales)
        pendientes = len(self.simulacion.productos_pendientes)
        self.progress.set((total - pendientes) / total if total > 0 else 1.0)

    def _construir_lista_productos(self) -> None:
        for lbl in self.labels_productos.values():
            try: lbl.destroy()
            except Exception: pass
        self.labels_productos.clear()

        if not self.simulacion: return

        for pid in sorted(self.simulacion.productos_totales):
            prod = self.escenario.warehouse.productos[pid]
            cant = self.simulacion.cantidad_pedida.get(pid, 0)

            lbl = ctk.CTkLabel(
                self.frame_productos,
                text=f"● {pid} ({prod.x},{prod.y},{prod.z}) | Disp:{prod.cantidad_disponible} Req:{cant}",
                anchor="w", text_color=COLOR_PRODUCTO_PENDIENTE,
                font=ctk.CTkFont(family="monospace", size=11),
            )
            lbl.pack(fill="x", pady=1)
            self.labels_productos[pid] = lbl

    def _actualizar_panel_info(self) -> None:
        if not self.simulacion: return

        recogidos = self.simulacion.productos_totales - self.simulacion.productos_pendientes
        total = len(self.simulacion.productos_totales)

        self.lbl_info_waves.configure(text=f"Waves: {len(self.escenario.waves)} | Pedidos Totales: {len(self.escenario.pedidos)}")
        self.lbl_info_paso.configure(text=f"Paso global: {self.simulacion.paso_actual}")
        self.lbl_info_prod.configure(text=f"Productos: {len(recogidos)} / {total}")

        pendientes = len([t for t in self.simulacion.tareas_pendientes if not t.completada])
        self.lbl_info_prio.configure(text=f"Tareas pendientes: {pendientes}")

        # --- Actualizar Métricas ---
        self.lbl_met_distancia.configure(text=f"Distancia total: {self.simulacion.distancia_total:.1f}")
        self.lbl_met_aristas.configure(text=f"Aristas recorridas: {self.simulacion.aristas_recorridas}")
        self.lbl_met_nodos.configure(text=f"Nodos visitados: {self.simulacion.nodos_visitados}")

        # Formato de tiempo ultra-claro
        t = self.simulacion.tiempo_ejecucion
        self.lbl_met_tiempo.configure(text=f"Tiempo de CPU: {t:.2f} s ({t*1000:.0f} ms)")

        for pid, lbl in self.labels_productos.items():
            nuevo_color = COLOR_PRODUCTO_RECOGIDO if pid in recogidos else COLOR_PRODUCTO_PENDIENTE
            try:
                current = lbl.cget("text_color")
            except Exception:
                current = None
            if current != nuevo_color:
                lbl.configure(text_color=nuevo_color)

    def toggle_play_pause(self) -> None:
        self.pause() if self.after_id is not None else self.play()

    def _actualizar_boton_play_pause(self) -> None:
        if self.after_id is not None:
            self.btn_play_pause.configure(text="⏸ Pause")
        else:
            self.btn_play_pause.configure(text="▶ Play")

    def play(self) -> None:
        if self.after_id is not None or self.simulacion is None or self.simulacion.completada:
            return
        self._tick()
        self._actualizar_boton_play_pause()

    def _tick(self) -> None:
        if self.simulacion is None or not self.simulacion.avanzar():
            self.after_id = None
            self._actualizar_boton_play_pause()
            return
        self._redibujar_todo()
        if self.simulacion.completada:
            self.after_id = None
            self._actualizar_boton_play_pause()
        else:
            self.after_id = self.root.after(self.delay_caminar, self._tick)

    def pause(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self._actualizar_boton_play_pause()

    def step(self) -> None:
        self.pause()
        if self.simulacion is not None:
            self.simulacion.avanzar()
            self._redibujar_todo()

    def reset(self) -> None:
        self.pause()
        if hasattr(self, 'simulacion_inicial'):
            self.simulacion = copy.deepcopy(self.simulacion_inicial)
            self._construir_lista_productos()
            self._redibujar_todo()

    # --- búsqueda Trie ---
    def _on_buscar(self, event) -> None:
        prefix = self.entry_busqueda.get().strip()
        if not prefix:
            self.lbl_resultados_busqueda.configure(text="")
            self.rack_resaltado = None
            self._redibujar_todo()
            return
        resultados = self.escenario.warehouse.buscar_por_prefijo(prefix)
        if not resultados:
            self.lbl_resultados_busqueda.configure(text="Sin resultados")
            self.rack_resaltado = None
            self._redibujar_todo()
            return
        primeros = resultados[:3]
        texto = "  ·  ".join(f"{p.id} ({p.nombre})" for p in primeros)
        if len(resultados) > 3:
            texto += f"  ... (+{len(resultados) - 3})"
        self.lbl_resultados_busqueda.configure(text=texto)
        rack = self.escenario.warehouse.racks[resultados[0].rack_id]
        self.rack_resaltado = (rack.x, rack.y)
        self._redibujar_todo()

    def _limpiar_busqueda(self, event) -> None:
        self.entry_busqueda.delete(0, tk.END)
        self.lbl_resultados_busqueda.configure(text="")
        self.rack_resaltado = None
        self._redibujar_todo()

