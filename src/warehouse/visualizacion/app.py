"""Aplicación Tk de simulación Dinámica con Layout de 3 Columnas."""
import copy
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from warehouse.simulacion.dinamica import SimulacionDinamica
from warehouse.visualizacion.render import (COLOR_CANVAS_FONDO, COLOR_PICKER,
                                            COLOR_PRODUCTO_ENTREGADO,
                                            COLOR_PRODUCTO_INVENTARIO,
                                            COLOR_PRODUCTO_PENDIENTE,
                                            COLOR_PRODUCTO_RECOGIDO,
                                            centro_celda_px,
                                            crear_panel_leyenda,
                                            dibujar_polilinea, dibujar_punto,
                                            dibujar_warehouse)
from warehouse.visualizacion.sprites import SpriteLoader

COLORES_PICKERS = {
    "PK_01": "#ff5252", "PK_02": "#42a5f5", "PK_03": "#66bb6a", "PK_04": "#ffca28",
    "PK_05": "#ab47bc", "PK_06": "#26c6da", "PK_07": "#ff7043", "PK_08": "#8d6e63",
}

def obtener_color_picker(picker_id: str) -> str:
    if picker_id in COLORES_PICKERS:
        return COLORES_PICKERS[picker_id]
    base_id = "_".join(picker_id.split("_")[:2])
    return COLORES_PICKERS.get(base_id, "#ffffff")

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

ANCHO_CANVAS = 1400
ALTO_CANVAS = 900


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
        self.margen = 10

        self.after_id = None
        self.coords: dict = {}
        self.labels_productos: dict[str, ctk.CTkLabel] = {}
        self.historial: list[SimulacionDinamica] = []

        # Variable para el filtro de productos
        self.mostrar_solo_activos = None

    def run(self) -> None:
        self.root = ctk.CTk()
        self.root.withdraw()

        alto_pantalla = self.root.winfo_screenheight()
        ancho_pantalla = self.root.winfo_screenwidth()

        # Ajustamos el canvas para que quepa entre los paneles laterales (220 izq + 280 der = 500px)
        self.ancho_canvas = min(ANCHO_CANVAS, ancho_pantalla - 480)
        self.alto_canvas = min(ALTO_CANVAS, alto_pantalla - 100)


        # Reducimos el margen interno del canvas para que el dibujo crezca
        self.margen = 5

        celda_px_w = (self.ancho_canvas - 2 * self.margen) // self.escenario.warehouse.ancho
        celda_px_h = (self.alto_canvas - 2 * self.margen) // self.escenario.warehouse.alto
        self.celda_px = max(4, min(celda_px_w, celda_px_h))

        self.sprites.set_celda_px(self.celda_px)
        self.sprites.cargar()

        self.root.deiconify()
        self.root.title(f"Demo — Multi-Picker Dinámico — {self.estrategia}")
        self.root.grid_rowconfigure(0, weight=1)
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
        # Frame principal de 3 columnas
        main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=2, pady=2)

        main_frame.grid_columnconfigure(0, weight=0) # Panel Izquierdo
        main_frame.grid_columnconfigure(1, weight=1) # Canvas
        main_frame.grid_columnconfigure(2, weight=0) # Panel Derecho
        main_frame.grid_rowconfigure(0, weight=1)

        # ==================== PANEL IZQUIERDO (Controles y Métricas) ====================
        panel_izq = ctk.CTkFrame(main_frame, fg_color="transparent", width=190)
        panel_izq.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        panel_izq.grid_propagate(False)

        ctk.CTkLabel(panel_izq, text="Controles", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(0, 10))

        self.btn_play_pause = ctk.CTkButton(panel_izq, text="▶ Play", command=self.toggle_play_pause, width=180)
        self.btn_play_pause.pack(pady=5)
        ctk.CTkButton(panel_izq, text="⏮ Step atrás", command=self.step_atras, width=180).pack(pady=5)
        ctk.CTkButton(panel_izq, text="⏭ Step", command=self.step, width=180).pack(pady=5)
        ctk.CTkButton(panel_izq, text="⟲ Reset", command=self.reset, width=180).pack(pady=5)

        self.progress = ctk.CTkProgressBar(panel_izq, width=180)
        self.progress.set(0)
        self.progress.pack(pady=20)

        ctk.CTkLabel(panel_izq, text="Estado", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 5))
        mono = ctk.CTkFont(family="monospace", size=11)

        self.lbl_info_waves = ctk.CTkLabel(panel_izq, text="", anchor="w", font=mono)
        self.lbl_info_waves.pack(fill="x")
        self.lbl_info_paso = ctk.CTkLabel(panel_izq, text="", anchor="w", font=mono)
        self.lbl_info_paso.pack(fill="x")
        self.lbl_info_prod = ctk.CTkLabel(panel_izq, text="", anchor="w", font=mono)
        self.lbl_info_prod.pack(fill="x")
        self.lbl_info_prio = ctk.CTkLabel(panel_izq, text="", anchor="w", font=mono)
        self.lbl_info_prio.pack(fill="x")

        ctk.CTkLabel(panel_izq, text="Métricas", font=ctk.CTkFont(size=14, weight="bold"), text_color="#64b5f6").pack(pady=(20, 5))
        mono_s = ctk.CTkFont(family="monospace", size=10)
        self.lbl_met_distancia = ctk.CTkLabel(panel_izq, text="", anchor="w", font=mono_s, text_color="#aaaaaa")
        self.lbl_met_distancia.pack(fill="x")
        self.lbl_met_aristas = ctk.CTkLabel(panel_izq, text="", anchor="w", font=mono_s, text_color="#aaaaaa")
        self.lbl_met_aristas.pack(fill="x")
        self.lbl_met_nodos = ctk.CTkLabel(panel_izq, text="", anchor="w", font=mono_s, text_color="#aaaaaa")
        self.lbl_met_nodos.pack(fill="x")
        self.lbl_met_tiempo = ctk.CTkLabel(panel_izq, text="", anchor="w", font=mono_s, text_color="#aaaaaa")
        self.lbl_met_tiempo.pack(fill="x")

        ctk.CTkButton(panel_izq, text="✕ Cerrar", command=self._cerrar, fg_color="#a83232", hover_color="#7a2020").pack(side="bottom", pady=10)

        # ==================== PANEL CENTRAL (Canvas) ====================
        self.canvas = tk.Canvas(
            main_frame, bg=COLOR_CANVAS_FONDO,
            width=self.ancho_canvas, height=self.alto_canvas,
            highlightthickness=1, highlightbackground="#3a3a3a",
        )
        self.canvas.grid(row=0, column=1, sticky="nsew")

        # ==================== PANEL DERECHO (Leyenda y Productos) ====================
        panel_der = ctk.CTkFrame(main_frame, fg_color="transparent", width=250)
        panel_der.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        panel_der.grid_propagate(False)

        crear_panel_leyenda(panel_der).pack(side="top", fill="x")

        # Búsqueda Trie
        frame_busqueda = ctk.CTkFrame(panel_der, fg_color="transparent")
        frame_busqueda.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(frame_busqueda, text="🔍 Buscar producto:", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_busqueda = ctk.CTkEntry(frame_busqueda, width=200, font=ctk.CTkFont(family="monospace", size=12))
        self.entry_busqueda.pack(fill="x", pady=2)
        self.entry_busqueda.bind("<KeyRelease>", self._on_buscar)

        # Lista de productos
        frame_prod_header = ctk.CTkFrame(panel_der, fg_color="transparent")
        frame_prod_header.pack(fill="x", pady=(15, 5))
        ctk.CTkLabel(frame_prod_header, text="Productos", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        self.mostrar_solo_activos = ctk.BooleanVar(master=self.root, value=False)

        self.switch_filtro = ctk.CTkSwitch(
            frame_prod_header, text="Ocultar Entregados",
            variable=self.mostrar_solo_activos,
            command=self._construir_lista_productos,
            font=ctk.CTkFont(size=11)
        )
        self.switch_filtro.pack(side="right")

        self.frame_productos = ctk.CTkScrollableFrame(panel_der, fg_color="#252525")
        self.frame_productos.pack(fill="both", expand=True)

    def _redibujar_todo(self) -> None:
        self.canvas.delete("all")
        self.coords = dibujar_warehouse(
            self.canvas, self.escenario.warehouse, self.celda_px, self.margen
        )

        # 1. Dibujar Racks
        rack_img = self.sprites.obtener_rack()
        if rack_img is not None:
            for rack in self.escenario.warehouse.racks.values():
                for rx in range(rack.x, rack.x + rack.ancho):
                    for ry in range(rack.y, rack.y + rack.alto):
                        if (rx, ry) in self.coords:
                            cx, cy = centro_celda_px(self.coords, rx, ry)
                            self.canvas.create_image(cx, cy, image=rack_img, anchor="center")

        # 2. Dibujar Puertas
        door_img = self.sprites.obtener_door()
        if door_img is not None:
            for puerta in self.escenario.warehouse.puertas.values():
                if (puerta.posicion.x, puerta.posicion.y) in self.coords:
                    cx, cy = centro_celda_px(self.coords, puerta.posicion.x, puerta.posicion.y)
                    self.canvas.create_image(cx, cy, image=door_img, anchor="center")

        # 3. Flechas de Pasillos
        for pasillo in self.escenario.warehouse.pasillos.values():
            if pasillo.sentido == "N": flecha = "↑"
            elif pasillo.sentido == "S": flecha = "↓"
            elif pasillo.sentido == "E": flecha = "→"
            elif pasillo.sentido == "O": flecha = "←"
            else: flecha = "↔" if pasillo.ancho > pasillo.alto else "↕"

            font_size = max(6, int(self.celda_px * 0.4))
            fuente_flecha = ("sans-serif", font_size, "bold")

            if pasillo.ancho > pasillo.alto:
                for x_off in range(0, pasillo.ancho, 4):
                    cx_p, cy_p = centro_celda_px(self.coords, pasillo.x + x_off, pasillo.y + pasillo.alto // 2)
                    self.canvas.create_text(cx_p, cy_p, text=flecha, fill="#555555", font=fuente_flecha)
            else:
                for y_off in range(0, pasillo.alto, 4):
                    cx_p, cy_p = centro_celda_px(self.coords, pasillo.x + pasillo.ancho // 2, pasillo.y + y_off)
                    self.canvas.create_text(cx_p, cy_p, text=flecha, fill="#555555", font=fuente_flecha)

        def centro(nid: int) -> tuple[float, float]:
            nodo = self.escenario.warehouse.grafo.nodo(nid)
            return centro_celda_px(self.coords, nodo.posicion.x, nodo.posicion.y)

        # 4. Mostrar peso de las zonas
        for zona in self.escenario.warehouse.zonas.values():
            cx_z = (zona.p1[0] + zona.p2[0]) // 2
            cy_z = (zona.p1[1] + zona.p2[1]) // 2
            if (cx_z, cy_z) in self.coords:
                cx_px, cy_px = centro_celda_px(self.coords, cx_z, cy_z)
                peso_actual = self.simulacion.peso_en_zona.get(zona.id, 0.0)
                texto_peso = f"{peso_actual:.0f} / {zona.peso_max_kg:.0f} kg"
                color_txt = "#ff5252" if peso_actual >= zona.peso_max_kg else "#ffffff"

                self.canvas.create_text(
                    cx_px, cy_px, text=texto_peso, fill=color_txt,
                    font=("sans-serif", max(8, int(self.celda_px * 0.4)), "bold")
                )

        # 5. Productos
        recogidos = self.simulacion.productos_totales - self.simulacion.productos_pendientes
        entregados = self.simulacion.productos_entregados

        for pid, prod in self.escenario.warehouse.productos.items():
            cx_cell, cy_cell = centro_celda_px(self.coords, prod.x, prod.y)
            rack = self.escenario.warehouse.racks[prod.rack_id]
            niveles = rack.niveles
            separacion = self.celda_px * 0.25

            if niveles == 1: y_pos = cy_cell
            else:
                z_rel = (prod.z - 1) / (niveles - 1)
                offset = separacion * (niveles - 1) / 2
                y_pos = cy_cell + offset - (z_rel * 2 * offset)

            if pid in entregados: color = COLOR_PRODUCTO_ENTREGADO
            elif pid in recogidos: color = COLOR_PRODUCTO_RECOGIDO
            elif pid in self.simulacion.productos_totales: color = COLOR_PRODUCTO_PENDIENTE
            else: color = COLOR_PRODUCTO_INVENTARIO

            icono = self.sprites.obtener_producto(pid)
            if icono is not None:
                self.canvas.create_image(cx_cell, y_pos - (self.celda_px*0.05), image=icono, anchor="center")
                radio = self.celda_px * 0.06
                self.canvas.create_oval(cx_cell - radio, y_pos + self.celda_px*0.1 - radio, cx_cell + radio, y_pos + self.celda_px*0.1 + radio, fill=color, outline="white", width=1)
            else:
                dibujar_punto(self.canvas, cx_cell, y_pos, radio=self.celda_px * 0.09, color=color)

        # 6. Cajas en zona
        caja_img = self.sprites.obtener_caja()
        for nid, cantidad in self.simulacion.cajas_en_zona.items():
            if cantidad > 0:
                cx_box, cy_box = centro(nid)
                if caja_img is not None:
                    self.canvas.create_image(cx_box, cy_box, image=caja_img, anchor="center")
                if cantidad > 1:
                    self.canvas.create_text(cx_box + self.celda_px * 0.3, cy_box - self.celda_px * 0.3, text=f"x{cantidad}", fill="#ffffff", font=("sans-serif", max(6, int(self.celda_px * 0.3)), "bold"))

        # 7. Pickers y Rutas
        for picker_id, ep in self.simulacion.pickers.items():
            color_p = obtener_color_picker(picker_id)

            puntos = [centro(ep.nodo_actual)] + [centro(nid) for nid in ep.camino_actual]
            if len(puntos) > 1:
                dibujar_polilinea(self.canvas, puntos, color=color_p, grosor=2, dash=(4, 2))

            cx, cy = centro(ep.nodo_actual)

            # Desplazamiento visual
            offset_x = (hash(picker_id) % 10 - 5) * (self.celda_px * 0.1)
            offset_y = (hash(picker_id) % 7 - 3) * (self.celda_px * 0.1)
            cx_vis, cy_vis = cx + offset_x, cy + offset_y

            # Texto sin fondo negro feo
            texto_peso = f"{ep.carga_kg:.1f} / {ep.picker.capacidad_carga_kg:.0f} kg"
            self.canvas.create_text(cx_vis, cy_vis - self.celda_px * 0.85, text=texto_peso, fill=color_p, font=("sans-serif", 8, "bold"))

            if ep.fase == "TERMINADO":
                self.canvas.create_text(cx_vis, cy_vis - self.celda_px * 1.8, text="✔", fill="#00e676", font=("sans-serif", 14, "bold"))
            elif ep.espera_restante > 0:
                self.canvas.create_text(cx_vis, cy_vis - self.celda_px * 1.8, text=f"⏳ {ep.espera_restante}", fill="#ffb74d", font=("sans-serif", 10, "bold"))

            direccion = self._calcular_direccion(ep)
            picker_foto = self.sprites.obtener_picker(direccion)
            if picker_foto is not None:
                self.canvas.create_image(cx_vis, cy_vis, image=picker_foto, anchor="center")
            else:
                self._dibujar_picker_stick(cx_vis, cy_vis)

            self.canvas.create_text(cx_vis, cy_vis + self.celda_px * 0.8, text=picker_id, fill=color_p, font=("sans-serif", 9, "bold"))

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
        completados = sum(1 for ep in self.simulacion.pickers.values() if ep.fase == "TERMINADO")
        total_p = len(self.simulacion.productos_totales)
        pendientes_p = len(self.simulacion.productos_pendientes)
        self.progress.set((total_p - pendientes_p) / total_p if total_p > 0 else 1.0)

    def _construir_lista_productos(self) -> None:
        for lbl in self.labels_productos.values():
            try: lbl.destroy()
            except Exception: pass
        self.labels_productos.clear()

        if not self.simulacion: return

        recogidos = self.simulacion.productos_totales - self.simulacion.productos_pendientes
        solo_activos = self.mostrar_solo_activos.get()

        for pid in sorted(self.simulacion.productos_totales):
            # FILTRO
            if solo_activos and pid in self.simulacion.productos_entregados:
                continue

            prod = self.escenario.warehouse.productos[pid]
            cant = self.simulacion.cantidad_pedida.get(pid, 0)

            quien_lo_tiene = ""
            for pk_id, pk_estado in self.simulacion.pickers.items():
                if pid in pk_estado.productos_recogidos and pid not in self.simulacion.productos_entregados:
                    quien_lo_tiene = f" [{pk_id}]"
                    break

            if pid in self.simulacion.productos_entregados: estado = "Entregado"
            elif pid in recogidos: estado = "En carrito" + quien_lo_tiene
            else: estado = "Pendiente"

            lbl = ctk.CTkLabel(
                self.frame_productos,
                text=f"● {pid} ({prod.x},{prod.y},{prod.z})\n   {estado} | Req:{cant}",
                anchor="w", text_color=COLOR_PRODUCTO_PENDIENTE,
                font=ctk.CTkFont(family="monospace", size=11),
                justify="left"
            )
            lbl.pack(fill="x", pady=2)
            self.labels_productos[pid] = lbl

    def _actualizar_panel_info(self) -> None:
        if not self.simulacion: return
        recogidos = self.simulacion.productos_totales - self.simulacion.productos_pendientes
        total = len(self.simulacion.productos_totales)

        self.lbl_info_waves.configure(text=f"Waves: {len(self.escenario.waves)}")
        self.lbl_info_paso.configure(text=f"Paso: {self.simulacion.paso_actual}")
        self.lbl_info_prod.configure(text=f"Prods: {len(recogidos)} / {total}")

        pendientes = len([t for t in self.simulacion.tareas_pendientes if not t.completada])
        self.lbl_info_prio.configure(text=f"Tareas: {pendientes}")

        self.lbl_met_distancia.configure(text=f"Dist: {self.simulacion.distancia_total:.1f}")
        self.lbl_met_aristas.configure(text=f"Aristas: {self.simulacion.aristas_recorridas}")
        self.lbl_met_nodos.configure(text=f"Nodos: {self.simulacion.nodos_visitados}")

        t = self.simulacion.tiempo_ejecucion
        self.lbl_met_tiempo.configure(text=f"CPU: {t:.2f} s")

        for pid, lbl in self.labels_productos.items():
            if pid in self.simulacion.productos_entregados: nuevo_color = COLOR_PRODUCTO_ENTREGADO
            elif pid in recogidos: nuevo_color = COLOR_PRODUCTO_RECOGIDO
            else: nuevo_color = COLOR_PRODUCTO_PENDIENTE

            try:
                current = lbl.cget("text_color")
                if current != nuevo_color:
                    lbl.configure(text_color=nuevo_color)
            except Exception:
                pass

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
        if self.simulacion is None: return
        self.historial.append(self.simulacion.copiar_estado())
        if not self.simulacion.avanzar():
            self.after_id = None
            self._actualizar_boton_play_pause()
            return
        self._redibujar_todo()
        if self.simulacion.completada:
            self.after_id = None
            self._actualizar_boton_play_pause()
        else:
            self.after_id = self.root.after(self.delay_caminar, self._tick)

    def step_atras(self) -> None:
        self.pause()
        if self.historial:
            self.simulacion = self.historial.pop()
            self._construir_lista_productos()
            self._redibujar_todo()

    def step(self) -> None:
        self.pause()
        if self.simulacion is not None:
            self.historial.append(self.simulacion.copiar_estado())
            self.simulacion.avanzar()
            self._redibujar_todo()

    def pause(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self._actualizar_boton_play_pause()

    def reset(self) -> None:
        self.pause()
        if hasattr(self, 'simulacion_inicial'):
            self.simulacion = copy.deepcopy(self.simulacion_inicial)
            self.historial.clear()
            self._construir_lista_productos()
            self._redibujar_todo()

    def _on_buscar(self, event) -> None:
        prefix = self.entry_busqueda.get().strip()
        if not prefix:
            self._construir_lista_productos() # Volver a mostrar todo
            return
        resultados = self.escenario.warehouse.buscar_por_prefijo(prefix)
        if not resultados:
            return
        # Opcional: Resaltar el primer resultado en el mapa
        rack = self.escenario.warehouse.racks[resultados[0].rack_id]
        self.rack_resaltado = (rack.x, rack.y)
        self._redibujar_todo()

    def _limpiar_busqueda(self, event) -> None:
        self.entry_busqueda.delete(0, tk.END)
        self.rack_resaltado = None
        self._redibujar_todo()

