# src/warehouse/visualizacion/render.py
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

from warehouse.dominio.tipo_nodo import TipoNodo
from warehouse.warehouse.warehouse import Warehouse

# --- Paleta oscura moderna ---
COLORES_TIPO = {
    TipoNodo.PASILLO: "#2d2d2d",
    TipoNodo.RACK: "#5d4037",
    TipoNodo.DESPACHO: "#1b5e20",
    TipoNodo.PUERTA: "#1b5e20",  # Mismo verde que despacho (para el fallback)
}

COLOR_BORDE_CELDA = "#3a3a3a"
COLOR_BORDE_RACK = "#8d6e63"
COLOR_BORDE_EXT = "#555555"

COLOR_PICKER = "#42a5f5"
COLOR_PICKER_BORDE = "#ffffff"

COLOR_PRODUCTO_PENDIENTE = "#ff5252"
COLOR_PRODUCTO_RECOGIDO = "#66bb6a"
COLOR_PRODUCTO_INVENTARIO = "#757575"

COLOR_RECORRIDO_HECHO = "#42a5f5"
COLOR_RECORRIDO_PENDIENTE = "#546e7a"

COLOR_CANVAS_FONDO = "#1e1e1e"


def dibujar_warehouse(
    canvas: tk.Canvas,
    warehouse: Warehouse,
    celda_px: int,
    margen: int,
) -> dict[tuple[int, int], tuple[float, float, float, float]]:
    coords: dict[tuple[int, int], tuple[float, float, float, float]] = {}

    ancho_warehouse = warehouse.ancho * celda_px
    alto_warehouse = warehouse.alto * celda_px

    ancho_canvas = int(canvas["width"])
    alto_canvas = int(canvas["height"])

    offset_x = max((ancho_canvas - ancho_warehouse) // 2, margen)
    offset_y = max((alto_canvas - alto_warehouse) // 2, margen)

    def celda_a_px(x: int, y: int) -> tuple[float, float, float, float]:
        x0 = offset_x + x * celda_px
        y0 = offset_y + (warehouse.alto - 1 - y) * celda_px
        return (x0, y0, x0 + celda_px, y0 + celda_px)

    # Rectángulo exterior (fondo del canvas)
    canvas.create_rectangle(
        offset_x - 2,
        offset_y - 2,
        offset_x + ancho_warehouse + 2,
        offset_y + alto_warehouse + 2,
        fill="#252525",
        outline="",
        width=0,
    )

    # Pasillos, despacho, puertas (nodos del grafo)
    for nodo in warehouse.grafo.nodos():
        x, y = nodo.posicion.x, nodo.posicion.y
        coords[(x, y)] = celda_a_px(x, y)
        x0, y0, x1, y1 = coords[(x, y)]
        canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            fill=COLORES_TIPO[nodo.tipo],
            outline="",
        )

    # Racks (coordenadas para las imágenes)
    for rack in warehouse.racks.values():
        for cx, cy in rack.celdas():
            coords[(cx, cy)] = celda_a_px(cx, cy)

    # DIBUJAR ZONAS DE DESPACHO COMPLETAS (Rectángulos)
    dibujar_zonas(canvas, warehouse, coords)

    return coords


def dibujar_zonas(
    canvas: tk.Canvas,
    warehouse: Warehouse,
    coords: dict[tuple[int, int], tuple[float, float, float, float]],
) -> None:
    """Dibuja el rectángulo completo de cada zona de despacho."""
    for zona in warehouse.zonas.values():
        # Obtener coordenadas de las esquinas y ordenarlas para Tkinter
        c1 = coords[(zona.p1[0], zona.p1[1])]
        c2 = coords[(zona.p2[0], zona.p2[1])]

        x0 = min(c1[0], c2[0])
        y0 = min(c1[1], c2[1])
        x1 = max(c1[2], c2[2])
        y1 = max(c1[3], c2[3])

        # Pintamos el fondo verde con efecto de transparencia
        canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            fill="#1b5e20",  # Verde oscuro
            stipple="gray25",  # Transparencia
            outline="#66bb6a",  # Borde verde claro
            width=2,
            dash=(4, 4),
        )


def centro_celda_px(
    coords: dict[tuple[int, int], tuple[float, float, float, float]],
    x: int,
    y: int,
) -> tuple[float, float]:
    x0, y0, x1, y1 = coords[(x, y)]
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def dibujar_punto(
    canvas: tk.Canvas,
    cx: float,
    cy: float,
    radio: float,
    color: str,
) -> None:
    borde = COLOR_PICKER_BORDE
    canvas.create_oval(
        cx - radio,
        cy - radio,
        cx + radio,
        cy + radio,
        fill=color,
        outline=borde if borde else "",
        width=2 if borde else 0,
    )


def dibujar_polilinea(
    canvas: tk.Canvas,
    puntos: list[tuple[float, float]],
    color: str,
    grosor: int = 2,
    dash: tuple[int, int] | None = None,
) -> None:
    if len(puntos) < 2:
        return
    flat = [c for p in puntos for c in p]
    kwargs = {
        "fill": color,
        "width": grosor,
        "capstyle": tk.ROUND,
        "joinstyle": tk.ROUND,
    }
    if dash:
        kwargs["dash"] = dash
    canvas.create_line(*flat, **kwargs)


def crear_panel_leyenda(parent: tk.Widget) -> tk.Frame:
    """Crea un frame con la leyenda de colores e iconos."""
    frame = tk.LabelFrame(
        parent,
        text="Leyenda",
        padx=10,
        pady=8,
        font=("sans-serif", 10, "bold"),
        bg=COLOR_CANVAS_FONDO,
        fg="#ffffff",
        bd=1,
        relief="solid",
    )

    assets_dir = Path(__file__).parent.parent.parent.parent / "assets"

    door_img = None
    picker_img = None
    try:
        if (assets_dir / "door.png").exists():
            door_img = ImageTk.PhotoImage(
                Image.open(assets_dir / "door.png").resize(
                    (20, 20), Image.Resampling.LANCZOS
                )
            )
            frame.door_img = door_img
        if (assets_dir / "picker.png").exists():
            picker_img = ImageTk.PhotoImage(
                Image.open(assets_dir / "picker.png").resize(
                    (20, 20), Image.Resampling.LANCZOS
                )
            )
            frame.picker_img = picker_img
    except Exception as e:
        print(f"Error cargando imágenes en leyenda: {e}")

    items = [
        ("Rack", COLORES_TIPO[TipoNodo.RACK], ""),
        ("Zona de despacho", COLORES_TIPO[TipoNodo.DESPACHO], "#66bb6a"),
        ("Puerta", "#1b5e20", ""),
        ("Picker", COLOR_PICKER, COLOR_PICKER_BORDE),
    ]

    for texto, color, borde in items:
        fila = tk.Frame(frame, bg=COLOR_CANVAS_FONDO)
        fila.pack(fill="x", pady=2)

        swatch = tk.Canvas(
            fila, width=20, height=20, bg=COLOR_CANVAS_FONDO, highlightthickness=0
        )
        swatch.pack(side="left", padx=(0, 8))

        if texto == "Puerta" and door_img is not None:
            swatch.create_image(10, 10, image=door_img)
        elif texto == "Picker" and picker_img is not None:
            swatch.create_image(10, 10, image=picker_img)
        else:
            swatch.create_rectangle(
                3,
                3,
                17,
                17,
                fill=color if color else "",
                outline=borde if borde else color,
                width=1,
            )

        tk.Label(
            fila,
            text=texto,
            anchor="w",
            bg=COLOR_CANVAS_FONDO,
            fg="#dddddd",
            font=("sans-serif", 9),
        ).pack(side="left", fill="x", expand=True)

    return frame


def dibujar_circulo_hueco(
    canvas: tk.Canvas,
    cx: float,
    cy: float,
    radio: float,
    color: str = "#a0a0a0",
) -> None:
    """Dibuja un círculo con solo borde (estante vacío)."""
    canvas.create_oval(
        cx - radio,
        cy - radio,
        cx + radio,
        cy + radio,
        fill="",
        outline=color,
        width=1,
    )
