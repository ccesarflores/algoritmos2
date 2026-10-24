import random
from dataclasses import dataclass

from warehouse.dominio.pedido import Pedido
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
) -> list[tuple[int, int]]:
    ancho = len(patron)
    posiciones: list[tuple[int, int]] = []
    for y in range(config.alto):
        if _es_fila_pasillo_horizontal(y, config):
            continue
        for x in range(ancho):
            if patron[x] == "R":
                posiciones.append((x, y))
    return posiciones


# --- construcción ---


def _construir_estructura(
    config: ConfigGeneracion, rng: random.Random
) -> tuple[Warehouse, list[str]]:
    ancho = _calcular_ancho(config)
    patron = _patron_columnas(config)
    assert len(patron) == ancho

    w = Warehouse(ancho, config.alto)
    w.construir_grafo(_celdas_transitables(config, patron))

    # zona de despacho en la esquina inferior izquierda
    w.agregar_zona_despacho("A", (0, 0), (config.ancho_pasillo, 0))

    # puerta outbound en la esquina inferior derecha
    w.agregar_puerta("D1", ancho - 1, 0, "OUTBOUND")

    # racks
    posiciones = _posiciones_racks(config, patron)
    rack_ids: list[str] = []
    for i, (x, y) in enumerate(posiciones, start=1):
        rid = f"R{i:03d}"
        w.agregar_rack(rid, x, y, niveles=config.niveles_por_rack)
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
        # Elegir AL AZAR cuáles niveles están ocupados
        niveles_ocupados = sorted(
            rng.sample(
                range(1, config.niveles_por_rack + 1),
                config.productos_por_rack,
            )
        )
        for z in niveles_ocupados:
            prod = Producto(
                id=f"P{pid:04d}",
                nombre=f"Producto {pid}",
                rack_id=rack_id,
                z=z,
                stock=rng.randint(config.stock_min, config.stock_max),
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

    return Escenario(
        nombre=nombre,
        warehouse=w,
        pedidos=pedidos,
        wave_config=WaveConfig(
            max_pedidos=config.max_pedidos_wave,
            max_productos=config.max_productos_wave,
        ),
        seed=config.seed,
    )
