# src/warehouse/visualizacion/render.py
import tkinter as tk

from warehouse.dominio.tipo_nodo import TipoNodo
from warehouse.warehouse.warehouse import Warehouse

# --- Paleta oscura moderna ---
COLORES_TIPO = {
    TipoNodo.PASILLO: "#2d2d2d",
    TipoNodo.RACK: "#5d4037",
    TipoNodo.DESPACHO: "#1b5e20",
    TipoNodo.PUERTA: "#e65100",
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
    """
    Dibuja el warehouse centrado en el canvas.
    El canvas debe tener width/height configurados.
    """
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
        outline="",  # Sin borde exterior
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
            outline="",  # <-- Quitamos las líneas de la grilla
        )

    # Racks (no están en el grafo)
    # Guardamos las coordenadas de TODAS las celdas del rack.
    for rack in warehouse.racks.values():
        for cx, cy in rack.celdas():
            coords[(cx, cy)] = celda_a_px(cx, cy)

    return coords


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


def dibujar_zonas(
    canvas: tk.Canvas,
    warehouse: Warehouse,
    coords: dict[tuple[int, int], tuple[float, float, float, float]],
) -> None:
    for zona in warehouse.zonas.values():
        x0, y0, _, _ = coords[(zona.p1[0], zona.p1[1])]
        _, _, x1, y1 = coords[(zona.p2[0], zona.p2[1])]
        canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            outline="#66bb6a",
            width=2,
            dash=(4, 4),
        )


def crear_panel_leyenda(parent: tk.Widget) -> tk.Frame:
    """Crea un frame con la leyenda de colores (paleta oscura)."""
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

    items = [
        ("Pasillo", COLORES_TIPO[TipoNodo.PASILLO], ""),
        ("Rack", COLORES_TIPO[TipoNodo.RACK], ""),
        ("Estante vacío", "", "#a0a0a0"),
        ("Zona de despacho", COLORES_TIPO[TipoNodo.DESPACHO], "#66bb6a"),
        ("Puerta", COLORES_TIPO[TipoNodo.PUERTA], ""),
        ("Producto en inventario", COLOR_PRODUCTO_INVENTARIO, ""),
        ("Producto pendiente", COLOR_PRODUCTO_PENDIENTE, ""),
        ("Producto recogido", COLOR_PRODUCTO_RECOGIDO, ""),
        ("Picker", COLOR_PICKER, COLOR_PICKER_BORDE),
        ("Recorrido hecho", COLOR_RECORRIDO_HECHO, ""),
        ("Recorrido pendiente", COLOR_RECORRIDO_PENDIENTE, ""),
    ]

    for texto, color, borde in items:
        fila = tk.Frame(frame, bg=COLOR_CANVAS_FONDO)
        fila.pack(fill="x", pady=2)

        swatch = tk.Canvas(
            fila,
            width=20,
            height=20,
            bg=COLOR_CANVAS_FONDO,
            highlightthickness=0,
        )
        swatch.pack(side="left", padx=(0, 8))
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
