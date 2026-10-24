"""
Demo completa: genera un escenario grande, produce todas las waves y las
simula en secuencia en la misma ventana.

Uso:
    python scripts/demo_completa.py --niveles-por-rack 3
    python scripts/demo_completa.py --bloques 10 --alto 14 --pedidos 100
    python scripts/demo_completa.py --estrategia orden_pedidos
    python scripts/demo_completa.py --delay-caminar 50 --delay-esperar 1500
    python scripts/demo_completa.py --picker-scale 3.0 --rack-scale 1.0
"""

import argparse
import random
import tkinter as tk  # solo para Canvas y tk.END
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from warehouse.algoritmos.distancias import CacheDistancias
from warehouse.algoritmos.recorridos import (ESTRATEGIAS, ResultadoRecorrido,
                                             _armar_camino, _paradas_de_wave)
from warehouse.generacion.generador import ConfigGeneracion, generar_escenario
from warehouse.generacion.validador import validar_escenario
from warehouse.simulacion.estado import EstadoSimulacion
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
from warehouse.waves.generador_waves import EstrategiaWaves, generar_waves

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

ANCHO_CANVAS = 850
ALTO_CANVAS = 500

ASSETS_DIR = Path(__file__).parent.parent / "assets"
RUTA_ICONO_PICKER = ASSETS_DIR / "picker.png"
RUTA_ICONO_RACK = ASSETS_DIR / "rack.png"
RUTA_ICONO_LAMP = ASSETS_DIR / "lamp.png"
RUTA_ICONO_LAPTOP = ASSETS_DIR / "laptop.png"
RUTA_ICONO_BOX = ASSETS_DIR / "box.png"


def recorrer_wave_random(wave, warehouse, estrategia: str, nodo_inicio: int) -> ResultadoRecorrido:
    """Calcula el recorrido de una wave empezando desde un nodo aleatorio y terminando en el despacho."""
    cache = CacheDistancias(warehouse.grafo)
    nodo_despacho = next(iter(warehouse.zonas.values())).nodo_representativo
    paradas = _paradas_de_wave(wave, warehouse)

    if estrategia == "orden_pedidos":
        secuencia = [nodo_inicio] + paradas + [nodo_despacho]
        camino, distancia, indices = _armar_camino(secuencia, cache)
        return ResultadoRecorrido(
            estrategia="orden_pedidos",
            orden_paradas=paradas,
            camino_completo=camino,
            distancia_total=distancia,
            nodos_visitados=len(camino),
            aristas_recorridas=max(0, len(camino) - 1),
            tiempo_segundos=0.0,
            indices_de_paradas=indices[: len(paradas)],
        )

    elif estrategia == "vecino_mas_cercano":
        pendientes = set(paradas)
        secuencia = [nodo_inicio]
        actual = nodo_inicio

        if not pendientes:
            camino, distancia, indices = _armar_camino([nodo_inicio, nodo_despacho], cache)
            return ResultadoRecorrido(
                estrategia="vecino_mas_cercano",
                orden_paradas=[],
                camino_completo=camino,
                distancia_total=distancia,
                nodos_visitados=len(camino),
                aristas_recorridas=max(0, len(camino) - 1),
                tiempo_segundos=0.0,
                indices_de_paradas=[],
            )

        while pendientes:
            mejor = None
            mejor_dist = float("inf")
            for candidato in pendientes:
                d = cache.distancia(actual, candidato)
                if d < mejor_dist:
                    mejor_dist = d
                    mejor = candidato
            if mejor is None or mejor_dist == float("inf"):
                raise ValueError("Parada inalcanzable")
            secuencia.append(mejor)
            pendientes.remove(mejor)
            actual = mejor

        secuencia.append(nodo_despacho)
        camino, distancia, indices = _armar_camino(secuencia, cache)
        return ResultadoRecorrido(
            estrategia="vecino_mas_cercano",
            orden_paradas=secuencia[1:-1],
            camino_completo=camino,
            distancia_total=distancia,
            nodos_visitados=len(camino),
            aristas_recorridas=max(0, len(camino) - 1),
            tiempo_segundos=0.0,
            indices_de_paradas=indices[: len(secuencia) - 2],
        )

    raise ValueError("Estrategia desconocida")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bloques", type=int, default=3)
    parser.add_argument("--alto", type=int, default=4)
    parser.add_argument("--pasillos-h", type=int, default=0)
    parser.add_argument("--pedidos", type=int, default=40)
    parser.add_argument("--max-pedidos-wave", type=int, default=3)
    parser.add_argument("--max-productos-wave", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--productos-por-rack", type=int, default=2)
    parser.add_argument("--niveles-por-rack", type=int, default=3) # CAMBIADO A 3 POR DEFECTO
    parser.add_argument(
        "--estrategia", choices=list(ESTRATEGIAS.keys()), default="vecino_mas_cercano"
    )
    parser.add_argument(
        "--estrategia-waves",
        choices=[e.value for e in EstrategiaWaves],
        default=EstrategiaWaves.PRIORIDAD_Y_CERCANIA.value,
    )
    parser.add_argument("--wave", type=int, default=0)
    parser.add_argument("--cargar", type=str, default=None)

    # VELOCIDAD
    parser.add_argument("--delay-caminar", type=int, default=100, help="Milisegundos por paso al caminar (default: 100)")
    parser.add_argument("--delay-esperar", type=int, default=1000, help="Milisegundos por paso de espera (default: 1000)")

    # TAMAÑO DE SPRITES
    parser.add_argument(
        "--picker-scale", type=float, default=2.2,
        help="Multiplicador del tamaño del picker respecto a la celda (default: 2.2).",
    )
    parser.add_argument(
        "--rack-scale", type=float, default=0.92,
        help="Fracción del tamaño de celda que ocupa la imagen del rack (default: 0.92).",
    )
    args = parser.parse_args()

    if args.cargar:
        from warehouse.io.cargador_json import cargar_escenario
        print(f"Cargando escenario desde {args.cargar}...")
        escenario = cargar_escenario(args.cargar)
        print(f"  Warehouse: {escenario.warehouse.ancho} x {escenario.warehouse.alto}")
        if not escenario.waves:
            raise SystemExit(
                "El archivo cargado no contiene waves. "
                "Generá el escenario de cero en lugar de cargarlo."
            )
        resultados = [(w, escenario.resultados[w.id]) for w in escenario.waves]
        estrategia = (
            escenario.sesion.estrategia_recorrido
            if escenario.sesion is not None else args.estrategia
        )
        indice_inicial = (
            escenario.sesion.wave_actual if escenario.sesion is not None else 0
        )
        paso_inicial = (
            escenario.sesion.indice_actual if escenario.sesion is not None else 0
        )
    else:
        cfg = ConfigGeneracion(
            n_bloques_racks=args.bloques,
            alto=args.alto,
            n_pedidos=args.pedidos,
            niveles_por_rack=args.niveles_por_rack,
            productos_por_rack=args.productos_por_rack,
            cada_cuantas_filas_pasillo_horizontal=args.pasillos_h,
            seed=args.seed,
        )
        escenario = generar_escenario(cfg)
        validar_escenario(escenario)
        waves = generar_waves(
            escenario.pedidos, escenario.warehouse,
            max_pedidos=args.max_pedidos_wave,
            max_productos=args.max_productos_wave,
            estrategia=EstrategiaWaves(args.estrategia_waves),
        )

        resultados = []
        nodos_transitables = list(escenario.warehouse.grafo._nodos.keys())

        for w in waves:
            nodo_inicio = random.choice(nodos_transitables)
            r = recorrer_wave_random(w, escenario.warehouse, args.estrategia, nodo_inicio)
            resultados.append((w, r))

        escenario.waves = waves
        escenario.resultados = {w.id: r for w, r in resultados}
        estrategia = args.estrategia
        indice_inicial = args.wave
        paso_inicial = 0

    root = ctk.CTk()
    root.withdraw()
    alto_pantalla = root.winfo_screenheight()
    ancho_pantalla = root.winfo_screenwidth()
    root.deiconify()

    ancho_canvas = min(ANCHO_CANVAS, ancho_pantalla - 450)
    alto_canvas = min(ALTO_CANVAS, alto_pantalla - 250)
    margen = 20
    celda_px_w = (ancho_canvas - 2 * margen) // escenario.warehouse.ancho
    celda_px_h = (alto_canvas - 2 * margen) // escenario.warehouse.alto
    celda_px = max(4, min(celda_px_w, celda_px_h))

    SimulacionSecuencial(
        root, escenario, resultados,
        estrategia=args.estrategia,
        celda_px=celda_px,
        ancho_canvas=ancho_canvas,
        alto_canvas=alto_canvas,
        indice_inicial=indice_inicial,
        paso_inicial=paso_inicial,
        delay_caminar=args.delay_caminar,
        delay_esperar=args.delay_esperar,
        picker_scale=args.picker_scale,
        rack_scale=args.rack_scale,
    )

    root.update_idletasks()
    w = root.winfo_reqwidth()
    h = root.winfo_reqheight()
    x = max((root.winfo_screenwidth() - w) // 2, 0)
    y = max((root.winfo_screenheight() - h) // 2, 0)
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.mainloop()


class SimulacionSecuencial:
    """Encadena la simulación de todas las waves en la misma ventana."""

    def __init__(
        self,
        root: ctk.CTk,
        escenario,
        resultados: list,
        estrategia: str,
        celda_px: int = 30,
        ancho_canvas: int = ANCHO_CANVAS,
        alto_canvas: int = ALTO_CANVAS,
        indice_inicial: int = 0,
        paso_inicial: int = 0,
        delay_caminar: int = 100,
        delay_esperar: int = 1000,
        picker_scale: float = 2.2,
        rack_scale: float = 0.92,
    ) -> None:
        self.root = root
        self.escenario = escenario
        self.resultados = resultados
        self.estrategia = estrategia
        self.celda_px = celda_px
        self.ancho_canvas = ancho_canvas
        self.alto_canvas = alto_canvas
        self.margen = 20
        self.indice_actual = 0
        self.after_id = None
        self.estado: EstadoSimulacion | None = None
        self.coords: dict = {}
        self.labels_productos: dict[str, ctk.CTkLabel] = {}
        self.base_picker_img: Image.Image | None = None
        self.picker_cache: dict[str, ImageTk.PhotoImage] = {}
        self.base_rack_img: Image.Image | None = None
        self.rack_cache: dict[str, ImageTk.PhotoImage] = {}
        self.product_imgs: dict[str, Image.Image] = {}
        self.product_cache: dict[str, ImageTk.PhotoImage] = {}
        self.rack_resaltado: tuple[int, int] | None = None

        # Velocidades
        self.delay_caminar = delay_caminar
        self.delay_esperar = delay_esperar

        # Tamaño de sprites
        self.picker_scale = picker_scale
        self.rack_scale = rack_scale

        self.root.title(f"Demo — {len(resultados)} waves — {estrategia}")

        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_rowconfigure(3, weight=0)
        self.root.grid_columnconfigure(0, weight=1)

        self._cargar_icono_picker()
        self._cargar_icono_rack()
        self._cargar_iconos_productos()
        self._construir_ui()

        try:
            self._cargar_wave(indice_inicial, paso_inicial=paso_inicial)
        except Exception:
            import traceback
            traceback.print_exc()
            messagebox.showerror(
                "Error al iniciar",
                "Falló la carga inicial. Ver consola para el traceback.",
            )

    def _construir_ui(self) -> None:
        # Header
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

        # Búsqueda
        frame_busqueda = ctk.CTkFrame(self.root, fg_color="transparent")
        frame_busqueda.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 0))

        ctk.CTkLabel(
            frame_busqueda, text="🔍 Buscar producto:",
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

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

        # Canvas + panel derecho
        frame_principal = ctk.CTkFrame(self.root, fg_color=COLOR_CANVAS_FONDO)
        frame_principal.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

        self.canvas = tk.Canvas(
            frame_principal,
            bg=COLOR_CANVAS_FONDO,
            width=self.ancho_canvas,
            height=self.alto_canvas,
            highlightthickness=1,
            highlightbackground="#3a3a3a",
        )
        self.canvas.pack(side="left", anchor="n", padx=(0, 10))

        panel_derecho = ctk.CTkFrame(frame_principal, fg_color="transparent", width=320)
        panel_derecho.pack(side="left", fill="both", expand=True)
        panel_derecho.pack_propagate(False)

        panel_leyenda = crear_panel_leyenda(panel_derecho)
        panel_leyenda.pack(side="top", fill="x")

        panel_info = ctk.CTkFrame(panel_derecho, fg_color="transparent")
        panel_info.pack(side="top", fill="both", expand=True, pady=(10, 0))

        ctk.CTkLabel(
            panel_info, text="Estado de la Wave", anchor="w",
            font=ctk.CTkFont(family="sans-serif", size=13, weight="bold"),
            text_color="#ffffff",
        ).pack(fill="x", pady=(0, 5))

        self.lbl_info_paso = ctk.CTkLabel(
            panel_info, text="", anchor="w",
            font=ctk.CTkFont(family="monospace", size=11),
            text_color="#ffffff",
        )
        self.lbl_info_paso.pack(fill="x")
        self.lbl_info_prod = ctk.CTkLabel(
            panel_info, text="", anchor="w",
            font=ctk.CTkFont(family="monospace", size=11),
            text_color="#ffffff",
        )
        self.lbl_info_prod.pack(fill="x")
        self.lbl_info_prio = ctk.CTkLabel(
            panel_info, text="", anchor="w",
            font=ctk.CTkFont(family="monospace", size=11),
            text_color="#ffffff",
        )
        self.lbl_info_prio.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            panel_info, text="Productos a recoger:", anchor="w",
            font=ctk.CTkFont(family="sans-serif", size=11, weight="bold"),
            text_color="#ffffff",
        ).pack(fill="x", pady=(0, 5))

        self.frame_productos = ctk.CTkScrollableFrame(
            panel_info,
            fg_color="#252525",
            height=200,
        )
        self.frame_productos.pack(fill="both", expand=True)

        # Controles
        panel = ctk.CTkFrame(self.root, fg_color="transparent")
        panel.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.btn_play_pause = ctk.CTkButton(
            panel, text="▶ Play", command=self.toggle_play_pause, width=90,
        )
        self.btn_play_pause.pack(side="left", padx=2)

        ctk.CTkButton(panel, text="⏮ Step atrás", command=self.step_atras, width=110).pack(
            side="left", padx=2
        )
        ctk.CTkButton(panel, text="⏭ Step", command=self.step, width=80).pack(
            side="left", padx=2
        )
        ctk.CTkButton(panel, text="⟲ Reset", command=self.reset, width=80).pack(
            side="left", padx=2
        )

        ctk.CTkLabel(panel, text="  |  ").pack(side="left")

        self.btn_prev = ctk.CTkButton(
            panel, text="◀ Wave ant.", command=self.wave_anterior, width=110,
        )
        self.btn_prev.pack(side="left", padx=2)
        self.btn_next = ctk.CTkButton(
            panel, text="Wave sig. ▶", command=self.wave_siguiente, width=110,
        )
        self.btn_next.pack(side="left", padx=2)

        self.lbl_estado = ctk.CTkLabel(
            panel, text="", anchor="w",
            font=ctk.CTkFont(family="monospace", size=11),
        )
        self.lbl_estado.pack(side="left", padx=20)

        ctk.CTkButton(
            panel, text="✕ Cerrar", command=self.root.destroy, width=90,
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            panel, text="📂 Cargar", command=self.cargar_sesion, width=100,
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            panel, text="💾 Guardar", command=self.guardar_sesion, width=100,
        ).pack(side="right", padx=2)

    # --- sprites: picker ---

    def _cargar_icono_picker(self) -> None:
        if not RUTA_ICONO_PICKER.exists() or RUTA_ICONO_PICKER.stat().st_size == 0:
            self.base_picker_img = None
            self.picker_cache = {}
            return
        try:
            img = Image.open(RUTA_ICONO_PICKER).convert("RGBA")
            pixels = img.load()
            width, height = img.size
            for y in range(height):
                for x in range(width):
                    r, g, b, a = pixels[x, y]
                    if abs(r - g) < 4 and abs(g - b) < 4 and 50 < r < 140:
                        pixels[x, y] = (0, 0, 0, 0)
            self.base_picker_img = img
            self.picker_cache = {}
        except Exception as e:
            print(f"  [picker] Error cargando icono ({e}). Uso stick figure.")
            self.base_picker_img = None
            self.picker_cache = {}

    def _obtener_icono_orientado(self, direction: str, alpha: int = 255) -> ImageTk.PhotoImage | None:
        if self.base_picker_img is None:
            return None

        cache_key = f"{direction}_{alpha}"
        if cache_key in self.picker_cache:
            return self.picker_cache[cache_key]

        img = self.base_picker_img.copy()
        max_size = max(1, int(self.celda_px * self.picker_scale))
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        if direction == "left":
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif direction == "up":
            img = img.transpose(Image.Transpose.ROTATE_270)
        elif direction == "down":
            img = img.transpose(Image.Transpose.ROTATE_90)

        if alpha < 255:
            r, g, b, a = img.split()
            a = a.point(lambda p: int(p * (alpha / 255)))
            img = Image.merge("RGBA", (r, g, b, a))

        photo_img = ImageTk.PhotoImage(img)
        self.picker_cache[cache_key] = photo_img
        return photo_img

    # --- sprites: rack y productos ---

    def _cargar_icono_rack(self) -> None:
        if not RUTA_ICONO_RACK.exists() or RUTA_ICONO_RACK.stat().st_size == 0:
            self.base_rack_img = None
            self.rack_cache = {}
            return
        try:
            img = Image.open(RUTA_ICONO_RACK).convert("RGBA")

            # 1. REFLEJAR HORIZONTALMENTE el rack para que coincida con la perspectiva de los productos
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

            # 2. QUITAR EL FONDO OSCURO del PNG
            pixels = img.load()
            width, height = img.size
            for y in range(height):
                for x in range(width):
                    r, g, b, a = pixels[x, y]
                    # Si el píxel es un gris muy oscuro o negro, lo volvemos transparente
                    if r < 45 and g < 45 and b < 45:
                        pixels[x, y] = (0, 0, 0, 0)

            self.base_rack_img = img
            self.rack_cache = {}
        except Exception as e:
            print(f"  [rack] Error cargando icono ({e}). Uso rectángulos.")
            self.base_rack_img = None
            self.rack_cache = {}

    def _obtener_icono_rack(self) -> ImageTk.PhotoImage | None:
        if self.base_rack_img is None:
            return None
        cache_key = str(self.celda_px)
        if cache_key in self.rack_cache:
            return self.rack_cache[cache_key]

        img = self.base_rack_img.copy()
        size = max(1, int(self.celda_px * self.rack_scale))
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        photo_img = ImageTk.PhotoImage(img)
        self.rack_cache[cache_key] = photo_img
        return photo_img

    def _cargar_iconos_productos(self) -> None:
        self.product_imgs = {}
        rutas = {
            "lamp": RUTA_ICONO_LAMP,
            "laptop": RUTA_ICONO_LAPTOP,
            "box": RUTA_ICONO_BOX,
        }
        for tipo, ruta in rutas.items():
            if ruta.exists() and ruta.stat().st_size > 0:
                try:
                    self.product_imgs[tipo] = Image.open(ruta).convert("RGBA")
                except Exception as e:
                    print(f"  [producto] Error cargando {tipo}.png ({e})")
        self.product_cache = {}

    def _obtener_icono_producto(self, pid: str) -> ImageTk.PhotoImage | None:
        if not self.product_imgs:
            return None

        tipos = list(self.product_imgs.keys())
        tipo = tipos[hash(pid) % len(tipos)]

        cache_key = f"{tipo}_{self.celda_px}"
        if cache_key in self.product_cache:
            return self.product_cache[cache_key]

        img = self.product_imgs[tipo].copy()
        size = max(4, int(self.celda_px * 0.6))
        img.thumbnail((size, size), Image.Resampling.LANCZOS)

        photo_img = ImageTk.PhotoImage(img)
        self.product_cache[cache_key] = photo_img
        return photo_img

    def _dibujar_picker_stick(self, cx: float, cy: float) -> None:
        c = self.celda_px
        color = COLOR_PICKER
        w = max(2, int(c * 0.08))
        head_r = c * 0.15

        head_cy = cy - c * 0.5
        self.canvas.create_oval(
            cx - head_r, head_cy - head_r,
            cx + head_r, head_cy + head_r,
            fill=color, outline="white", width=1,
        )
        self.canvas.create_line(
            cx, head_cy + head_r,
            cx, cy + c * 0.1,
            fill=color, width=w,
        )
        arm_y = cy - c * 0.2
        arm_dx = c * 0.25
        self.canvas.create_line(
            cx - arm_dx, arm_y, cx + arm_dx, arm_y,
            fill=color, width=w,
        )
        leg_y = cy + c * 0.1
        leg_dx = c * 0.18
        self.canvas.create_line(
            cx, leg_y, cx - leg_dx, cy + c * 0.5,
            fill=color, width=w,
        )
        self.canvas.create_line(
            cx, leg_y, cx + leg_dx, cy + c * 0.5,
            fill=color, width=w,
        )

    def _calcular_direccion(self) -> str:
        if self.estado is None:
            return "right"

        if self.estado.espera_restante > 0:
            pids = self.estado.nodo_a_productos.get(self.estado.nodo_actual, [])
            if pids:
                prod = self.escenario.warehouse.productos[pids[0]]
                rack = self.escenario.warehouse.racks[prod.rack_id]
                nodo_actual = self.escenario.warehouse.grafo.nodo(self.estado.nodo_actual)

                if rack.x > nodo_actual.posicion.x:
                    return "right"
                elif rack.x < nodo_actual.posicion.x:
                    return "left"
                elif rack.y > nodo_actual.posicion.y:
                    return "down"
                elif rack.y < nodo_actual.posicion.y:
                    return "up"

        if self.estado.indice_actual == 0:
            return "right"

        idx = self.estado.indice_actual
        nodo_actual = self.escenario.warehouse.grafo.nodo(self.estado.camino[idx])
        nodo_prev = self.escenario.warehouse.grafo.nodo(self.estado.camino[idx - 1])

        dx = nodo_actual.posicion.x - nodo_prev.posicion.x
        dy = nodo_actual.posicion.y - nodo_prev.posicion.y

        if dx > 0: return "right"
        elif dx < 0: return "left"
        elif dy < 0: return "up"
        elif dy > 0: return "down"
        return "right"

    # --- carga de wave ---

    def _cargar_wave(self, indice: int, paso_inicial: int = 0) -> None:
        if not (0 <= indice < len(self.resultados)):
            return

        if hasattr(self, "entry_busqueda"):
            self.entry_busqueda.delete(0, tk.END)
        if hasattr(self, "lbl_resultados_busqueda"):
            self.lbl_resultados_busqueda.configure(text="")
        self.rack_resaltado = None

        self.pause()
        self.indice_actual = indice
        wave, resultado = self.resultados[indice]
        self.estado = EstadoSimulacion.desde_wave(
            wave, resultado, self.escenario.warehouse
        )
        if paso_inicial > 0:
            paso_inicial = min(paso_inicial, len(self.estado.camino) - 1)
            self.estado.indice_actual = paso_inicial
            # Sesión cargada: no sabemos si estaba esperando, asumimos que terminó.
            self.estado.espera_restante = 0
        # Si paso_inicial == 0, se preserva la espera inicializada en desde_wave

        try:
            self._construir_lista_productos()
            self._redibujar_todo()
        except Exception:
            import traceback
            traceback.print_exc()

    # --- dibujo ---

    def _redibujar_todo(self) -> None:
        self.canvas.delete("all")
        self.coords = dibujar_warehouse(
            self.canvas, self.escenario.warehouse, self.celda_px, self.margen
        )

        # Racks con PNG (ahora transparente y reflejado)
        rack_img = self._obtener_icono_rack()
        if rack_img is not None:
            for rack in self.escenario.warehouse.racks.values():
                if (rack.x, rack.y) in self.coords:
                    cx_rack, cy_rack = centro_celda_px(self.coords, rack.x, rack.y)
                    self.canvas.create_image(
                        cx_rack, cy_rack, image=rack_img, anchor="center"
                    )

        if self.estado is None:
            return

        def centro(nid: int) -> tuple[float, float]:
            nodo = self.escenario.warehouse.grafo.nodo(nid)
            return centro_celda_px(self.coords, nodo.posicion.x, nodo.posicion.y)

        # Recorridos
        puntos = [centro(nid) for nid in self.estado.camino]
        dibujar_polilinea(self.canvas, puntos, color=COLOR_RECORRIDO_PENDIENTE, grosor=1, dash=(3, 3))

        idx = self.estado.indice_actual
        if idx >= 1:
            puntos_hechos = [centro(nid) for nid in self.estado.camino[: idx + 1]]
            dibujar_polilinea(self.canvas, puntos_hechos, color=COLOR_RECORRIDO_HECHO, grosor=3)

        # Productos
        recogidos = self.estado.productos_recogidos()
        productos_de_la_wave = self.estado.productos_totales

        productos_por_rack: dict[str, dict[int, str]] = {}
        for pid, prod in self.escenario.warehouse.productos.items():
            productos_por_rack.setdefault(prod.rack_id, {})[prod.z] = pid

        for rack_id, rack in self.escenario.warehouse.racks.items():
            cx_rack, cy_rack = centro_celda_px(self.coords, rack.x, rack.y)
            niveles = rack.niveles
            separacion = self.celda_px * 0.25 # Ajustado un poco para que quepa mejor en el rack de 3
            prods_en_rack = productos_por_rack.get(rack_id, {})

            for z in range(1, niveles + 1):
                if niveles == 1:
                    y = cy_rack
                else:
                    z_relativo = (z - 1) / (niveles - 1)
                    y = cy_rack + separacion * (niveles - 1) / 2 * (1 - 2 * z_relativo)

                pid = prods_en_rack.get(z)
                if pid is None:
                    continue # Rack vacío

                icono_prod = self._obtener_icono_producto(pid)

                if pid in recogidos:
                    color = COLOR_PRODUCTO_RECOGIDO
                elif pid in productos_de_la_wave:
                    color = COLOR_PRODUCTO_PENDIENTE
                else:
                    color = COLOR_PRODUCTO_INVENTARIO

                if icono_prod is not None:
                    self.canvas.create_image(cx_rack, y - (self.celda_px*0.05), image=icono_prod, anchor="center")

                    radio = self.celda_px * 0.06
                    self.canvas.create_oval(
                        cx_rack - radio, y + self.celda_px*0.1 - radio,
                        cx_rack + radio, y + self.celda_px*0.1 + radio,
                        fill=color, outline="white", width=1
                    )
                else:
                    radio = self.celda_px * 0.09
                    dibujar_punto(self.canvas, cx_rack, y, radio=radio, color=color)

        # Picker
        cx, cy = centro(self.estado.nodo_actual)

        if self.estado.espera_restante > 0:
            self.canvas.create_text(
                cx, cy - self.celda_px * 1.8,
                text=f"⏳ {self.estado.espera_restante}",
                fill="#ffb74d",
                font=("sans-serif", 10, "bold"),
                anchor="s"
            )

        direccion = self._calcular_direccion()
        picker_foto = self._obtener_icono_orientado(direccion, alpha=255)

        if picker_foto is not None:
            self.canvas.create_image(cx, cy, image=picker_foto, anchor="center")
        else:
            self._dibujar_picker_stick(cx, cy)

        # Próxima parada
        proxima = None
        for i, idx_parada in enumerate(self.estado.indices_de_paradas):
            if self.estado.indice_actual < idx_parada:
                proxima = self.estado.nodos_paradas[i]
                break

        if proxima is not None:
            pids_parada = self.estado.nodo_a_productos.get(proxima, [])
            if pids_parada:
                prod = self.escenario.warehouse.productos[pids_parada[0]]
                rack = self.escenario.warehouse.racks[prod.rack_id]
                x0, y0, x1, y1 = self.coords[(rack.x, rack.y)]
                if rack.x % 3 == 1:
                    text_x, anchor = x0 - 4, "e"
                else:
                    text_x, anchor = x1 + 4, "w"
                text_y = (y0 + y1) / 2
                self.canvas.create_text(
                    text_x, text_y,
                    text=f"→ {rack.x},{rack.y}",
                    font=("monospace", 7, "bold"),
                    fill="#64b5f6", anchor=anchor,
                )

        # Resaltado
        if self.rack_resaltado is not None:
            rx, ry = self.rack_resaltado
            if (rx, ry) in self.coords:
                x0, y0, x1, y1 = self.coords[(rx, ry)]
                self.canvas.create_rectangle(
                    x0 - 3, y0 - 3, x1 + 3, y1 + 3,
                    outline="#e91e63", width=3,
                )

        self._actualizar_label()
        self._actualizar_panel_info()

    def _redibujar(self) -> None:
        self._redibujar_todo()

    def _actualizar_label(self) -> None:
        if self.estado is None: return
        wave = self.resultados[self.indice_actual][0]
        self.lbl_titulo.configure(
            text=f"Wave {wave.id}  ·  {self.estrategia}  ·  {wave.cantidad_pedidos()} pedidos"
        )
        idx = self.estado.indice_actual
        total = len(self.estado.camino) - 1
        rec = len(self.estado.productos_recogidos())
        tot = len(self.estado.productos_totales)

        txt = (
            f"Wave {self.indice_actual + 1}/{len(self.resultados)}  |  "
            f"paso {idx:>3}/{total:<3}  |  "
            f"productos {rec:>2}/{tot:<2}"
        )

        if self.estado.espera_restante > 0:
            txt += f"  ⏳ (esperando {self.estado.espera_restante})"
        elif self.estado.completada:
            txt += "  ✔"

        self.lbl_estado.configure(text=txt)
        self.btn_prev.configure(state="normal" if self.indice_actual > 0 else "disabled")
        self.btn_next.configure(
            state="normal" if self.indice_actual < len(self.resultados) - 1 else "disabled"
        )

    def _construir_lista_productos(self) -> None:
        for lbl in self.labels_productos.values():
            try: lbl.destroy()
            except Exception: pass
        self.labels_productos.clear()

        if self.estado is None: return

        wave = self.resultados[self.indice_actual][0]
        for pid in sorted(self.estado.productos_totales):
            prod = self.escenario.warehouse.productos[pid]
            rack = self.escenario.warehouse.racks[prod.rack_id]
            cantidad_pedida = sum(
                item.cantidad
                for pedido in wave.pedidos
                for item in pedido.items
                if item.producto_id == pid
            )

            lbl = ctk.CTkLabel(
                self.frame_productos,
                text=(
                    f"● {pid} ({rack.x},{rack.y},{prod.z}) "
                    f"| Stk:{prod.stock} Req:{cantidad_pedida}"
                ),
                anchor="w",
                text_color=COLOR_PRODUCTO_PENDIENTE,
                font=ctk.CTkFont(family="monospace", size=11),
            )
            lbl.pack(fill="x", pady=1)
            self.labels_productos[pid] = lbl

    def _actualizar_panel_info(self) -> None:
        if self.estado is None: return
        wave = self.resultados[self.indice_actual][0]
        idx = self.estado.indice_actual
        total = len(self.estado.camino) - 1
        rec = len(self.estado.productos_recogidos())
        tot = len(self.estado.productos_totales)

        if self.estado.espera_restante > 0:
            self.lbl_info_paso.configure(text=f"Paso: {idx} / {total} (Esperando {self.estado.espera_restante})")
        else:
            self.lbl_info_paso.configure(text=f"Paso: {idx} / {total}")

        self.lbl_info_prod.configure(text=f"Productos: {rec} / {tot}")
        self.lbl_info_prio.configure(text=f"Prioridad máx: {wave.prioridad_maxima()}")

        if total > 0:
            self.progress.set(idx / total)
        else:
            self.progress.set(0)

        recogidos = self.estado.productos_recogidos()
        for pid, lbl in self.labels_productos.items():
            nuevo_color = (
                COLOR_PRODUCTO_RECOGIDO if pid in recogidos else COLOR_PRODUCTO_PENDIENTE
            )
            try:
                current = lbl.cget("text_color")
            except Exception:
                current = None
            if current != nuevo_color:
                lbl.configure(text_color=nuevo_color)

    # --- controles ---

    def toggle_play_pause(self) -> None:
        if self.after_id is not None: self.pause()
        else: self.play()

    def _actualizar_boton_play_pause(self) -> None:
        if self.after_id is not None:
            self.btn_play_pause.configure(text="⏸ Pause")
        else:
            self.btn_play_pause.configure(text="▶ Play")

    def play(self) -> None:
        if self.after_id is not None or self.estado is None or self.estado.completada: return
        self._tick()
        self._actualizar_boton_play_pause()

    def _tick(self) -> None:
        if self.estado is None or not self.estado.avanzar():
            self.after_id = None
            self._actualizar_boton_play_pause()
            return
        self._redibujar()
        if self.estado.completada:
            self.after_id = None
            self._actualizar_boton_play_pause()
        else:
            delay = self.delay_caminar
            if self.estado.espera_restante > 0:
                delay = self.delay_esperar
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
            self._redibujar()

    def step_atras(self) -> None:
        self.pause()
        if self.estado is not None and self.estado.retroceder():
            self._redibujar()

    def reset(self) -> None:
        self.pause()
        if self.estado is not None:
            self.estado.reiniciar()
            self._redibujar()

    def wave_anterior(self) -> None:
        if self.indice_actual > 0: self._cargar_wave(self.indice_actual - 1)

    def wave_siguiente(self) -> None:
        if self.indice_actual < len(self.resultados) - 1: self._cargar_wave(self.indice_actual + 1)

    # --- guardar / cargar sesión ---

    def guardar_sesion(self) -> None:
        from tkinter import filedialog

        from warehouse.io.exportador import exportar_escenario
        from warehouse.warehouse.escenario import Sesion

        directorio_sesiones = Path(__file__).parent.parent / "data" / "sesiones"
        directorio_sesiones.mkdir(parents=True, exist_ok=True)

        path = filedialog.asksaveasfilename(
            initialdir=directorio_sesiones,
            initialfile=f"{self.escenario.nombre}.json",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            title="Guardar sesión como...",
        )
        if not path: return

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
        import subprocess
        import sys
        from tkinter import filedialog

        from warehouse.io.cargador_json import cargar_escenario

        self.pause()
        directorio_sesiones = Path(__file__).parent.parent / "data" / "sesiones"
        directorio_sesiones.mkdir(parents=True, exist_ok=True)

        path = filedialog.askopenfilename(
            initialdir=directorio_sesiones,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            title="Cargar sesión",
        )
        if not path: return

        try:
            cargar_escenario(path)
        except Exception as e:
            messagebox.showerror("Error al cargar", f"No se pudo cargar:\n{e}")
            return

        if not messagebox.askokcancel("Confirmar carga", "Se reiniciará la app. ¿Continuar?"):
            return

        ruta_script = Path(__file__).resolve()
        log_path = Path(__file__).parent.parent / "data" / "sesiones" / "ultimo_lanzamiento.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "w") as log:
            subprocess.Popen(
                [sys.executable, str(ruta_script), "--cargar", path],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        self.root.destroy()

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

        primer_producto = resultados[0]
        rack = self.escenario.warehouse.racks[primer_producto.rack_id]
        self.rack_resaltado = (rack.x, rack.y)
        self._redibujar_todo()

    def _limpiar_busqueda(self, event) -> None:
        self.entry_busqueda.delete(0, tk.END)
        self.lbl_resultados_busqueda.configure(text="")
        self.rack_resaltado = None
        self._redibujar_todo()


if __name__ == "__main__":
    main()

