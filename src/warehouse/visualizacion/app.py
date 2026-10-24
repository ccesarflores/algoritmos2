"""Aplicación Tk de simulación. No sabe de CLI ni de argparse."""
import random
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from warehouse.simulacion.estado import EstadoSimulacion
from warehouse.visualizacion.render import (COLOR_CANVAS_FONDO, COLOR_PICKER,
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
        resultados: list,
        estrategia: str,
        indice_inicial: int = 0,
        paso_inicial: int = 0,
        delay_caminar: int = 100,
        delay_esperar: int = 1000,
        picker_scale: float = 2.2,
        rack_scale: float = 0.92,
    ) -> None:
        self.escenario = escenario
        self.resultados = resultados
        self.estrategia = estrategia
        self.delay_caminar = delay_caminar
        self.delay_esperar = delay_esperar

        self._indice_inicial = indice_inicial
        self._paso_inicial = paso_inicial

        self.sprites = SpriteLoader(picker_scale, rack_scale)

        self.root: ctk.CTk | None = None
        self.celda_px = 30
        self.ancho_canvas = ANCHO_CANVAS
        self.alto_canvas = ALTO_CANVAS
        self.margen = 20

        self.indice_actual = 0
        self.after_id = None
        self.estado: EstadoSimulacion | None = None
        self.coords: dict = {}
        self.labels_productos: dict[str, ctk.CTkLabel] = {}
        self.rack_resaltado: tuple[int, int] | None = None

    # --- ciclo de vida ---

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
        self.root.title(f"Demo — {len(self.resultados)} waves — {self.estrategia}")
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_rowconfigure(3, weight=0)
        self.root.grid_columnconfigure(0, weight=1)

        self._construir_ui()
        try:
            self._cargar_wave(self._indice_inicial, paso_inicial=self._paso_inicial)
        except Exception:
            import traceback
            traceback.print_exc()
            messagebox.showerror(
                "Error al iniciar",
                "Falló la carga inicial. Ver consola para el traceback.",
            )

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

    # --- construcción de la UI (idéntica a la actual) ---

    def _construir_ui(self) -> None:
        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        self.lbl_titulo = ctk.CTkLabel(
            header, text="", anchor="w",
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

        ctk.CTkLabel(panel_info, text="Estado de la Wave", anchor="w",
                     font=ctk.CTkFont(family="sans-serif", size=13, weight="bold"),
                     text_color="#ffffff").pack(fill="x", pady=(0, 5))

        mono = ctk.CTkFont(family="monospace", size=11)
        self.lbl_info_paso = ctk.CTkLabel(panel_info, text="", anchor="w",
                                          font=mono, text_color="#ffffff")
        self.lbl_info_paso.pack(fill="x")
        self.lbl_info_prod = ctk.CTkLabel(panel_info, text="", anchor="w",
                                          font=mono, text_color="#ffffff")
        self.lbl_info_prod.pack(fill="x")
        self.lbl_info_prio = ctk.CTkLabel(panel_info, text="", anchor="w",
                                          font=mono, text_color="#ffffff")
        self.lbl_info_prio.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(panel_info, text="Productos a recoger:", anchor="w",
                     font=ctk.CTkFont(family="sans-serif", size=11, weight="bold"),
                     text_color="#ffffff").pack(fill="x", pady=(0, 5))

        self.frame_productos = ctk.CTkScrollableFrame(panel_info, fg_color="#252525", height=200)
        self.frame_productos.pack(fill="both", expand=True)

        panel = ctk.CTkFrame(self.root, fg_color="transparent")
        panel.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.btn_play_pause = ctk.CTkButton(panel, text="▶ Play",
                                            command=self.toggle_play_pause, width=90)
        self.btn_play_pause.pack(side="left", padx=2)
        ctk.CTkButton(panel, text="⏮ Step atrás", command=self.step_atras, width=110).pack(side="left", padx=2)
        ctk.CTkButton(panel, text="⏭ Step", command=self.step, width=80).pack(side="left", padx=2)
        ctk.CTkButton(panel, text="⟲ Reset", command=self.reset, width=80).pack(side="left", padx=2)
        ctk.CTkLabel(panel, text="  |  ").pack(side="left")

        self.btn_prev = ctk.CTkButton(panel, text="◀ Wave ant.",
                                      command=self.wave_anterior, width=110)
        self.btn_prev.pack(side="left", padx=2)
        self.btn_next = ctk.CTkButton(panel, text="Wave sig. ▶",
                                      command=self.wave_siguiente, width=110)
        self.btn_next.pack(side="left", padx=2)

        self.lbl_estado = ctk.CTkLabel(panel, text="", anchor="w",
                                       font=ctk.CTkFont(family="monospace", size=11))
        self.lbl_estado.pack(side="left", padx=20)

        ctk.CTkButton(panel, text="✕ Cerrar", command=self._cerrar, width=90).pack(side="right", padx=2)
        ctk.CTkButton(panel, text="📂 Cargar", command=self.cargar_sesion, width=100).pack(side="right", padx=2)
        ctk.CTkButton(panel, text="💾 Guardar", command=self.guardar_sesion, width=100).pack(side="right", padx=2)

    # --- carga de wave ---

    def _cargar_wave(self, indice: int, paso_inicial: int = 0) -> None:
        if not (0 <= indice < len(self.resultados)):
            return

        self.entry_busqueda.delete(0, tk.END)
        self.lbl_resultados_busqueda.configure(text="")
        self.rack_resaltado = None

        self.pause()
        self.indice_actual = indice
        wave, resultado = self.resultados[indice]
        self.estado = EstadoSimulacion.desde_wave(wave, resultado, self.escenario.warehouse)
        if paso_inicial > 0:
            paso_inicial = min(paso_inicial, len(self.estado.camino) - 1)
            self.estado.indice_actual = paso_inicial
            self.estado.espera_restante = 0

        self._construir_lista_productos()
        self._redibujar_todo()

    # --- dibujo ---

    def _redibujar_todo(self) -> None:
        self.canvas.delete("all")
        self.coords = dibujar_warehouse(
            self.canvas, self.escenario.warehouse, self.celda_px, self.margen
        )

        rack_img = self.sprites.obtener_rack()
        if rack_img is not None:
            for rack in self.escenario.warehouse.racks.values():
                if (rack.x, rack.y) in self.coords:
                    cx, cy = centro_celda_px(self.coords, rack.x, rack.y)
                    self.canvas.create_image(cx, cy, image=rack_img, anchor="center")

        if self.estado is None:
            return

        def centro(nid: int):
            nodo = self.escenario.warehouse.grafo.nodo(nid)
            return centro_celda_px(self.coords, nodo.posicion.x, nodo.posicion.y)

        puntos = [centro(nid) for nid in self.estado.camino]
        dibujar_polilinea(self.canvas, puntos, color=COLOR_RECORRIDO_PENDIENTE,
                          grosor=1, dash=(3, 3))

        idx = self.estado.indice_actual
        if idx >= 1:
            puntos_hechos = [centro(nid) for nid in self.estado.camino[: idx + 1]]
            dibujar_polilinea(self.canvas, puntos_hechos, color=COLOR_RECORRIDO_HECHO, grosor=3)

        recogidos = self.estado.productos_recogidos()
        productos_de_la_wave = self.estado.productos_totales

        productos_por_rack: dict[str, dict[int, str]] = {}
        for pid, prod in self.escenario.warehouse.productos.items():
            productos_por_rack.setdefault(prod.rack_id, {})[prod.z] = pid

        for rack_id, rack in self.escenario.warehouse.racks.items():
            cx_rack, cy_rack = centro_celda_px(self.coords, rack.x, rack.y)
            niveles = rack.niveles
            separacion = self.celda_px * 0.25
            prods_en_rack = productos_por_rack.get(rack_id, {})
            for z in range(1, niveles + 1):
                if niveles == 1:
                    y = cy_rack
                else:
                    z_rel = (z - 1) / (niveles - 1)
                    y = cy_rack + separacion * (niveles - 1) / 2 * (1 - 2 * z_rel)
                pid = prods_en_rack.get(z)
                if pid is None:
                    continue
                icono = self.sprites.obtener_producto(pid)
                if pid in recogidos:
                    color = COLOR_PRODUCTO_RECOGIDO
                elif pid in productos_de_la_wave:
                    color = COLOR_PRODUCTO_PENDIENTE
                else:
                    color = "#757575"
                if icono is not None:
                    self.canvas.create_image(
                        cx_rack, y - self.celda_px * 0.05, image=icono, anchor="center")
                    radio = self.celda_px * 0.06
                    self.canvas.create_oval(
                        cx_rack - radio, y + self.celda_px * 0.1 - radio,
                        cx_rack + radio, y + self.celda_px * 0.1 + radio,
                        fill=color, outline="white", width=1)
                else:
                    dibujar_punto(self.canvas, cx_rack, y,
                                  radio=self.celda_px * 0.09, color=color)

        cx, cy = centro(self.estado.nodo_actual)
        if self.estado.espera_restante > 0:
            self.canvas.create_text(
                cx, cy - self.celda_px * 1.8,
                text=f"⏳ {self.estado.espera_restante}",
                fill="#ffb74d", font=("sans-serif", 10, "bold"), anchor="s")

        direccion = self._calcular_direccion()
        picker_foto = self.sprites.obtener_picker(direccion)
        if picker_foto is not None:
            self.canvas.create_image(cx, cy, image=picker_foto, anchor="center")
        else:
            self._dibujar_picker_stick(cx, cy)

        # próxima parada
        for i, idx_parada in enumerate(self.estado.indices_de_paradas):
            if self.estado.indice_actual < idx_parada:
                proxima = self.estado.nodos_paradas[i]
                pids = self.estado.nodo_a_productos.get(proxima, [])
                if pids:
                    prod = self.escenario.warehouse.productos[pids[0]]
                    rack = self.escenario.warehouse.racks[prod.rack_id]
                    x0, y0, x1, y1 = self.coords[(rack.x, rack.y)]
                    if rack.x % 3 == 1:
                        text_x, anchor = x0 - 4, "e"
                    else:
                        text_x, anchor = x1 + 4, "w"
                    self.canvas.create_text(
                        text_x, (y0 + y1) / 2, text=f"→ {rack.x},{rack.y}",
                        font=("monospace", 7, "bold"), fill="#64b5f6", anchor=anchor)
                break

        if self.rack_resaltado is not None:
            rx, ry = self.rack_resaltado
            if (rx, ry) in self.coords:
                x0, y0, x1, y1 = self.coords[(rx, ry)]
                self.canvas.create_rectangle(
                    x0 - 3, y0 - 3, x1 + 3, y1 + 3, outline="#e91e63", width=3)

        self._actualizar_label()
        self._actualizar_panel_info()

    def _dibujar_picker_stick(self, cx: float, cy: float) -> None:
        c = self.celda_px
        color = COLOR_PICKER
        w = max(2, int(c * 0.08))
        head_r = c * 0.15
        head_cy = cy - c * 0.5
        self.canvas.create_oval(cx - head_r, head_cy - head_r,
                                cx + head_r, head_cy + head_r,
                                fill=color, outline="white", width=1)
        self.canvas.create_line(cx, head_cy + head_r, cx, cy + c * 0.1,
                                fill=color, width=w)
        arm_y = cy - c * 0.2
        arm_dx = c * 0.25
        self.canvas.create_line(cx - arm_dx, arm_y, cx + arm_dx, arm_y,
                                fill=color, width=w)
        leg_y = cy + c * 0.1
        leg_dx = c * 0.18
        self.canvas.create_line(cx, leg_y, cx - leg_dx, cy + c * 0.5,
                                fill=color, width=w)
        self.canvas.create_line(cx, leg_y, cx + leg_dx, cy + c * 0.5,
                                fill=color, width=w)

    def _calcular_direccion(self) -> str:
        if self.estado is None:
            return "right"
        if self.estado.espera_restante > 0:
            pids = self.estado.nodo_a_productos.get(self.estado.nodo_actual, [])
            if pids:
                prod = self.escenario.warehouse.productos[pids[0]]
                rack = self.escenario.warehouse.racks[prod.rack_id]
                nodo = self.escenario.warehouse.grafo.nodo(self.estado.nodo_actual)
                if rack.x > nodo.posicion.x: return "right"
                if rack.x < nodo.posicion.x: return "left"
                if rack.y > nodo.posicion.y: return "down"
                if rack.y < nodo.posicion.y: return "up"
        if self.estado.indice_actual == 0:
            return "right"
        idx = self.estado.indice_actual
        nodo_actual = self.escenario.warehouse.grafo.nodo(self.estado.camino[idx])
        nodo_prev = self.escenario.warehouse.grafo.nodo(self.estado.camino[idx - 1])
        dx = nodo_actual.posicion.x - nodo_prev.posicion.x
        dy = nodo_actual.posicion.y - nodo_prev.posicion.y
        if dx > 0: return "right"
        if dx < 0: return "left"
        if dy < 0: return "up"
        if dy > 0: return "down"
        return "right"

    def _actualizar_label(self) -> None:
        if self.estado is None:
            return
        wave = self.resultados[self.indice_actual][0]
        self.lbl_titulo.configure(
            text=f"Wave {wave.id}  ·  {self.estrategia}  ·  "
                 f"{wave.cantidad_pedidos()} pedidos"
        )
        idx = self.estado.indice_actual
        total = len(self.estado.camino) - 1
        rec = len(self.estado.productos_recogidos())
        tot = len(self.estado.productos_totales)
        txt = (f"Wave {self.indice_actual + 1}/{len(self.resultados)}  |  "
               f"paso {idx:>3}/{total:<3}  |  "
               f"productos {rec:>2}/{tot:<2}")
        if self.estado.espera_restante > 0:
            txt += f"  ⏳ (esperando {self.estado.espera_restante})"
        elif self.estado.completada:
            txt += "  ✔"
        self.lbl_estado.configure(text=txt)
        self.btn_prev.configure(state="normal" if self.indice_actual > 0 else "disabled")
        self.btn_next.configure(
            state="normal" if self.indice_actual < len(self.resultados) - 1 else "disabled")

    def _construir_lista_productos(self) -> None:
        for lbl in self.labels_productos.values():
            try:
                lbl.destroy()
            except Exception:
                pass
        self.labels_productos.clear()
        if self.estado is None:
            return
        wave = self.resultados[self.indice_actual][0]
        for pid in sorted(self.estado.productos_totales):
            prod = self.escenario.warehouse.productos[pid]
            rack = self.escenario.warehouse.racks[prod.rack_id]
            cant = sum(
                item.cantidad for ped in wave.pedidos for item in ped.items
                if item.producto_id == pid
            )
            lbl = ctk.CTkLabel(
                self.frame_productos,
                text=f"● {pid} ({rack.x},{rack.y},{prod.z}) | Stk:{prod.stock} Req:{cant}",
                anchor="w", text_color=COLOR_PRODUCTO_PENDIENTE,
                font=ctk.CTkFont(family="monospace", size=11),
            )
            lbl.pack(fill="x", pady=1)
            self.labels_productos[pid] = lbl

    def _actualizar_panel_info(self) -> None:
        if self.estado is None:
            return
        wave = self.resultados[self.indice_actual][0]
        idx = self.estado.indice_actual
        total = len(self.estado.camino) - 1
        rec = len(self.estado.productos_recogidos())
        tot = len(self.estado.productos_totales)
        if self.estado.espera_restante > 0:
            self.lbl_info_paso.configure(
                text=f"Paso: {idx} / {total} (Esperando {self.estado.espera_restante})")
        else:
            self.lbl_info_paso.configure(text=f"Paso: {idx} / {total}")
        self.lbl_info_prod.configure(text=f"Productos: {rec} / {tot}")
        self.lbl_info_prio.configure(text=f"Prioridad máx: {wave.prioridad_maxima()}")
        self.progress.set(idx / total if total > 0 else 0)
        recogidos = self.estado.productos_recogidos()
        for pid, lbl in self.labels_productos.items():
            nuevo_color = COLOR_PRODUCTO_RECOGIDO if pid in recogidos else COLOR_PRODUCTO_PENDIENTE
            try:
                current = lbl.cget("text_color")
            except Exception:
                current = None
            if current != nuevo_color:
                lbl.configure(text_color=nuevo_color)

    # --- controles ---

    def toggle_play_pause(self) -> None:
        self.pause() if self.after_id is not None else self.play()

    def _actualizar_boton_play_pause(self) -> None:
        if self.after_id is not None:
            self.btn_play_pause.configure(text="⏸ Pause")
        else:
            self.btn_play_pause.configure(text="▶ Play")

    def play(self) -> None:
        if self.after_id is not None or self.estado is None or self.estado.completada:
            return
        self._tick()
        self._actualizar_boton_play_pause()

    def _tick(self) -> None:
        if self.estado is None or not self.estado.avanzar():
            self.after_id = None
            self._actualizar_boton_play_pause()
            return
        self._redibujar_todo()
        if self.estado.completada:
            self.after_id = None
            self._actualizar_boton_play_pause()
        else:
            delay = self.delay_esperar if self.estado.espera_restante > 0 else self.delay_caminar
            self.after_id = self.root.after(delay, self._tick)

    def pause(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self._actualizar_boton_play_pause()

    def step(self) -> None:
        self.pause()
        if self.estado is not None:
            self.estado.avanzar()
            self._redibujar_todo()

    def step_atras(self) -> None:
        self.pause()
        if self.estado is not None and self.estado.retroceder():
            self._redibujar_todo()

    def reset(self) -> None:
        self.pause()
        if self.estado is not None:
            self.estado.reiniciar()
            self._redibujar_todo()

    def wave_anterior(self) -> None:
        if self.indice_actual > 0:
            self._cargar_wave(self.indice_actual - 1)

    def wave_siguiente(self) -> None:
        if self.indice_actual < len(self.resultados) - 1:
            self._cargar_wave(self.indice_actual + 1)

    # --- guardar / cargar sesión ---

    def guardar_sesion(self) -> None:
        from warehouse.io.exportador import exportar_escenario
        from warehouse.warehouse.escenario import Sesion

        directorio = Path(__file__).parent.parent.parent.parent / "data" / "sesiones"
        directorio.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(
            initialdir=directorio,
            initialfile=f"{self.escenario.nombre}.json",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            title="Guardar sesión como...",
        )
        if not path:
            return
        self.escenario.sesion = Sesion(
            wave_actual=self.indice_actual,
            indice_actual=self.estado.indice_actual if self.estado else 0,
            estrategia_recorrido=self.estrategia,
        )
        try:
            exportar_escenario(self.escenario, path)
            messagebox.showinfo("Guardado", f"Sesión guardada en:\n{path}")
        except Exception as e:
            self.lbl_estado.configure(text=f"Error al guardar: {e}")

    def cargar_sesion(self) -> None:
        from warehouse.io.cargador_json import cargar_escenario

        self.pause()
        directorio = Path(__file__).parent.parent.parent.parent / "data" / "sesiones"
        directorio.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            initialdir=directorio, defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            title="Cargar sesión",
        )
        if not path:
            return
        try:
            cargar_escenario(path)
        except Exception as e:
            messagebox.showerror("Error al cargar", f"No se pudo cargar:\n{e}")
            return
        if not messagebox.askokcancel("Confirmar carga", "Se reiniciará la app. ¿Continuar?"):
            return

        ruta_script = Path(__file__).parent.parent.parent.parent / "scripts" / "demo_completa.py"
        log_path = directorio / "ultimo_lanzamiento.log"
        with open(log_path, "w") as log:
            subprocess.Popen(
                [sys.executable, str(ruta_script), "--cargar", path],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
            )
        self._cerrar()

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
