import random
from dataclasses import dataclass

from warehouse.dominio.pedido import Pedido
from warehouse.dominio.picker import Picker
from warehouse.dominio.producto import Producto
from warehouse.warehouse.escenario import Escenario, WaveConfig
from warehouse.warehouse.warehouse import Warehouse


@dataclass
class ConfigGeneracion:
    # geometría
    n_bloques_racks: int = 3
    ancho_pasillo: int = 3
    ancho_bloque_racks: int = 2
    alto: int = 8
    cada_cuantas_filas_pasillo_horizontal: int = 0  # 0 = solo arriba/abajo

    # productos
    niveles_por_rack: int = 3  # altura física del rack
    productos_por_rack: int = 2  # niveles efectivamente ocupados
    stock_min: int = 10
    stock_max: int = 50
    peso_min_kg: float = 0.5
    peso_max_kg: float = 8.0

    # pedidos
    n_pedidos: int = 10
    max_productos_por_pedido: int = 3

    # waves
    max_pedidos_wave: int = 3
    max_productos_wave: int = 20

    # reproducibilidad
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.n_bloques_racks <= 0:
            raise ValueError("n_bloques_racks debe ser > 0")
        if self.ancho_pasillo <= 0:
            raise ValueError("ancho_pasillo debe ser > 0")
        if self.ancho_bloque_racks <= 0:
            raise ValueError("ancho_bloque_racks debe ser > 0")
        if self.alto < 3:
            raise ValueError("alto debe ser >= 3 (pasillos arriba y abajo + racks)")
        if self.niveles_por_rack <= 0:
            raise ValueError("niveles_por_rack debe ser > 0")
        if self.productos_por_rack > self.niveles_por_rack:
            raise ValueError(
                f"productos_por_rack ({self.productos_por_rack}) no puede ser mayor "
                f"que niveles_por_rack ({self.niveles_por_rack})"
            )
        if self.stock_min > self.stock_max:
            raise ValueError("stock_min no puede ser mayor que stock_max")
        if self.cada_cuantas_filas_pasillo_horizontal < 0:
            raise ValueError("cada_cuantas_filas_pasillo_horizontal debe ser >= 0")


# --- helpers de geometría ---


def _calcular_ancho(config: ConfigGeneracion) -> int:
    return config.ancho_pasillo + config.n_bloques_racks * (
        config.ancho_bloque_racks + config.ancho_pasillo
    )


def _patron_columnas(config: ConfigGeneracion) -> list[str]:
    """Devuelve una lista de 'P' (pasillo) o 'R' (rack) de longitud ancho."""
    patron: list[str] = []
    for _ in range(config.ancho_pasillo):
        patron.append("P")
    for _ in range(config.n_bloques_racks):
        for _ in range(config.ancho_bloque_racks):
            patron.append("R")
        for _ in range(config.ancho_pasillo):
            patron.append("P")
    return patron


def _es_fila_pasillo_horizontal(y: int, config: ConfigGeneracion) -> bool:
    """Devuelve True si la fila y debe ser un pasillo horizontal completo."""
    if y == 0 or y == config.alto - 1:
        return True
    if config.cada_cuantas_filas_pasillo_horizontal <= 0:
        return False
    return y % config.cada_cuantas_filas_pasillo_horizontal == 0


def _celdas_transitables(
    config: ConfigGeneracion, patron: list[str]
) -> set[tuple[int, int]]:
    ancho = len(patron)
    celdas: set[tuple[int, int]] = set()

    for y in range(config.alto):
        if _es_fila_pasillo_horizontal(y, config):
            # Toda la fila es transitable
            for x in range(ancho):
                celdas.add((x, y))
        else:
            # Solo columnas P (pasillos verticales)
            for x in range(ancho):
                if patron[x] == "P":
                    celdas.add((x, y))

    return celdas


def _posiciones_racks(
    config: ConfigGeneracion, patron: list[str]
) -> list[tuple[int, int, int, int]]:
    """Devuelve lista de (x, y, ancho, alto) para cada rack rectangular.

    Estrategia:
      - Cada bloque de columnas R contiguas forma un rack.
      - El rack se corta verticalmente por cada pasillo horizontal.
    """
    ancho = len(patron)
    rectangulos: list[tuple[int, int, int, int]] = []

    # 1. Encontrar bloques de columnas R
    bloques: list[tuple[int, int]] = []  # (x_inicio, ancho_bloque)
    x = 0
    while x < ancho:
        if patron[x] == "P":
            x += 1
            continue
        x_inicio = x
        while x < ancho and patron[x] == "R":
            x += 1
        bloques.append((x_inicio, x - x_inicio))

    # 2. Para cada bloque, cortar verticalmente por pasillos horizontales
    for x_inicio, ancho_bloque in bloques:
        y = 0
        while y < config.alto:
            if _es_fila_pasillo_horizontal(y, config):
                y += 1
                continue
            y_inicio = y
            while y < config.alto and not _es_fila_pasillo_horizontal(y, config):
                y += 1
            alto_rack = y - y_inicio
            rectangulos.append((x_inicio, y_inicio, ancho_bloque, alto_rack))

    return rectangulos


# --- construcción ---


def _construir_estructura(
    config: ConfigGeneracion, rng: random.Random
) -> tuple[Warehouse, list[str]]:
    ancho = _calcular_ancho(config)
    patron = _patron_columnas(config)
    assert len(patron) == ancho

    w = Warehouse(ancho, config.alto)
    w.construir_grafo(_celdas_transitables(config, patron))

    # Puerta outbound en la esquina inferior izquierda, con su zona frente a ella
    w.agregar_puerta("D1", 0, 0, "OUTBOUND")
    w.agregar_zona_despacho(
        "A",
        (1, 0),
        (config.ancho_pasillo, 0),
        puerta_id="D1",
        peso_max_kg=500.0,
    )

    rack_ids: list[str] = []
    for i, (rx, ry, rancho, ralto) in enumerate(
        _posiciones_racks(config, patron), start=1
    ):
        # Validación: uno de los lados debe valer 2
        if not (rancho == 2 or ralto == 2):
            raise ValueError(
                f"Rack generado con dimensiones inválidas: "
                f"ancho={rancho}, alto={ralto}"
            )
        rid = f"R{i:03d}"
        w.agregar_rack(rid, rx, ry, rancho, ralto, niveles=config.niveles_por_rack)
        rack_ids.append(rid)

    return w, rack_ids


def _generar_productos(
    config: ConfigGeneracion,
    w: Warehouse,
    rack_ids: list[str],
    rng: random.Random,
) -> list[Producto]:
    productos: list[Producto] = []
    pid = 1
    for rack_id in rack_ids:
        rack = w.racks[rack_id]
        # Todos los slots (x, y, z) disponibles en este rack
        slots: list[tuple[int, int, int]] = [
            (rx, ry, z)
            for rx in range(rack.x, rack.x + rack.ancho)
            for ry in range(rack.y, rack.y + rack.alto)
            for z in range(1, rack.niveles + 1)
        ]
        n_prods = min(config.productos_por_rack, len(slots))
        elegidos = rng.sample(slots, n_prods)

        for px, py, pz in elegidos:
            prod = Producto(
                id=f"P{pid:04d}",
                nombre=f"Producto {pid}",
                rack_id=rack_id,
                x=px,
                y=py,
                z=pz,
                cantidad_disponible=rng.randint(config.stock_min, config.stock_max),
                peso_kg=round(
                    rng.uniform(config.peso_min_kg, config.peso_max_kg), 2
                ),  # sin el 2, rng.uniform() te va a tirar números como 3.1415926535... y te va a ensuciar los JSON de guardado y los logs. Redondear a 2 decimales (centésimas de kilo) es lo estándar para pesos.
            )
            w.agregar_producto(prod)
            productos.append(prod)
            pid += 1
    return productos


def _generar_pedidos(
    config: ConfigGeneracion,
    productos: list[Producto],
    rng: random.Random,
) -> list[Pedido]:
    pedidos: list[Pedido] = []
    for i in range(1, config.n_pedidos + 1):
        prioridad = rng.randint(1, 5)
        pedido = Pedido(id=f"PED{i:03d}", prioridad=prioridad)

        n_items = rng.randint(1, min(config.max_productos_por_pedido, len(productos)))
        elegidos = rng.sample(productos, n_items)
        for prod in elegidos:
            pedido.agregar_item(prod.id, rng.randint(1, 3))

        pedidos.append(pedido)
    return pedidos


# --- API pública ---


def generar_escenario(config: ConfigGeneracion) -> Escenario:
    rng = random.Random(config.seed)

    w, rack_ids = _construir_estructura(config, rng)
    productos = _generar_productos(config, w, rack_ids, rng)
    pedidos = _generar_pedidos(config, productos, rng)

    nombre = (
        f"gen_b{config.n_bloques_racks}"
        f"_a{config.alto}"
        f"_p{len(productos)}"
        f"_o{len(pedidos)}"
    )
    if config.cada_cuantas_filas_pasillo_horizontal > 0:
        nombre += f"_ph{config.cada_cuantas_filas_pasillo_horizontal}"
    if config.seed is not None:
        nombre += f"_s{config.seed}"

    # Crear 2 pickers por defecto en la zona de despacho
    from warehouse.dominio.picker import Picker

    pickers = [
        Picker(id="PK_01", posicion_inicial=(0, 0), capacidad_carga_kg=500.0),
        Picker(id="PK_02", posicion_inicial=(1, 0), capacidad_carga_kg=500.0),
    ]

    return Escenario(
        nombre=nombre,
        warehouse=w,
        pedidos=pedidos,
        pickers=pickers,
        wave_config=WaveConfig(
            max_pedidos=config.max_pedidos_wave,
            max_productos=config.max_productos_wave,
        ),
        seed=config.seed,
    )
