import json
from pathlib import Path

from warehouse.dominio.estado_pedido import EstadoPedido
from warehouse.dominio.estado_wave import EstadoWave
from warehouse.dominio.item_pedido import ItemPedido
from warehouse.dominio.pedido import Pedido
from warehouse.dominio.picker import Picker
from warehouse.dominio.producto import Producto
from warehouse.dominio.wave import Wave
from warehouse.warehouse.escenario import Escenario, Sesion, WaveConfig
from warehouse.warehouse.warehouse import Warehouse


class ErrorDeCarga(Exception):
    pass


def _construir_warehouse(data_wh: dict) -> Warehouse:
    dim = data_wh["dimensiones"]
    ancho = int(dim["ancho_x"])
    alto = int(dim["largo_y"])

    # 1. Rack cells
    rack_cells: set[tuple[int, int]] = set()
    for r in data_wh.get("racks", []):
        u = r["ubicacion"]
        for cx in range(u["x"], u["x"] + r["ancho"]):
            for cy in range(u["y"], u["y"] + r["alto"]):
                if not (0 <= cx < ancho and 0 <= cy < alto):
                    raise ErrorDeCarga(f"Rack {r['id']} fuera de límites del warehouse")
                rack_cells.add((cx, cy))

    # 2. Transitables = todo menos racks
    transitables = {(x, y) for x in range(ancho) for y in range(alto)} - rack_cells

    w = Warehouse(ancho, alto)
    w.construir_grafo(transitables)

    # 3. Pasillos declarados
    for p in data_wh.get("pasillos", []):
        u = p["ubicacion"]
        try:
            w.agregar_pasillo(
                p["id"], u["x"], u["y"], p["ancho"], p["alto"], p["sentido"]
            )
        except ValueError as e:
            raise ErrorDeCarga(str(e)) from e

    # 4. Racks
    for r in data_wh.get("racks", []):
        u = r["ubicacion"]
        try:
            w.agregar_rack(
                r["id"],
                u["x"],
                u["y"],
                r["ancho"],
                r["alto"],
                niveles=int(r.get("niveles", 4)),
            )
        except ValueError as e:
            raise ErrorDeCarga(str(e)) from e

    # 5. Puertas
    for p in data_wh.get("puertas", []):
        u = p["ubicacion"]
        try:
            w.agregar_puerta(p["id"], u["x"], u["y"], p["tipo"])
        except Exception as e:
            raise ErrorDeCarga(f"Puerta {p.get('id')}: {e}") from e

    # 6. Zonas
    for z in data_wh.get("zonas_despacho", []):
        u = z["ubicacion"]
        p1 = (u["x"], u["y"])
        p2 = (u["x"] + z["ancho"] - 1, u["y"] + z["alto"] - 1)
        try:
            w.agregar_zona_despacho(
                z["id"],
                p1,
                p2,
                puerta_id=z["puerta_id"],
                peso_max_kg=float(z["peso_max_kg"]),
            )
        except Exception as e:
            raise ErrorDeCarga(f"Zona {z.get('id')}: {e}") from e

    return w


def _construir_productos(data: list[dict], w: Warehouse) -> None:
    for p in data:
        for campo in (
            "id",
            "nombre",
            "rack_id",
            "ubicacion",
            "cantidad_disponible",
            "peso_kg",
        ):
            if campo not in p:
                raise ErrorDeCarga(f"Producto sin campo '{campo}': {p}")
        if p["id"] in w.productos:
            raise ErrorDeCarga(f"Producto duplicado: {p['id']}")
        u = p["ubicacion"]
        prod = Producto(
            id=p["id"],
            nombre=p["nombre"],
            rack_id=p["rack_id"],
            x=int(u["x"]),
            y=int(u["y"]),
            z=int(u["z"]),
            cantidad_disponible=int(p["cantidad_disponible"]),
            peso_kg=float(p["peso_kg"]),
        )
        try:
            w.agregar_producto(prod)
        except ValueError as e:
            raise ErrorDeCarga(str(e)) from e


def _construir_pedidos(data: list[dict], w: Warehouse) -> list[Pedido]:
    pedidos: list[Pedido] = []
    for p in data:
        for campo in ("id", "prioridad", "items"):
            if campo not in p:
                raise ErrorDeCarga(f"Pedido sin campo '{campo}': {p}")
        pedido = Pedido(id=p["id"], prioridad=int(p["prioridad"]))
        for item in p["items"]:
            prod_id = item["producto_id"]
            if prod_id not in w.productos:
                raise ErrorDeCarga(
                    f"Pedido {p['id']} referencia producto inexistente: {prod_id}"
                )
            pedido.items.append(
                ItemPedido(producto_id=prod_id, cantidad=int(item["cantidad"]))
            )
        pedidos.append(pedido)
    return pedidos


def _construir_pickers(data: list[dict]) -> list[Picker]:
    return [
        Picker(
            id=p["id"],
            posicion_inicial=(
                int(p["posicion_inicial"]["x"]),
                int(p["posicion_inicial"]["y"]),
            ),
            capacidad_carga_kg=float(p["capacidad_carga_kg"]),
        )
        for p in data
    ]


def cargar_escenario(path: str | Path) -> Escenario:
    path = Path(path)
    if not path.exists():
        raise ErrorDeCarga(f"No existe el archivo: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErrorDeCarga(f"JSON inválido: {e}") from e
    if "warehouse" not in data:
        raise ErrorDeCarga("Falta campo obligatorio: 'warehouse'")

    w = _construir_warehouse(data["warehouse"])
    _construir_productos(data.get("productos", []), w)
    pedidos = _construir_pedidos(data.get("pedidos", []), w)
    pickers = _construir_pickers(data.get("pickers", []))

    cfg = data.get("configuracion", {})
    wave_config = WaveConfig(
        max_pedidos=int(cfg.get("wave_max_pedidos", 3)),
        max_productos=int(cfg.get("wave_max_productos", 20)),
        max_peso_kg=float(cfg.get("wave_max_peso_kg", 500.0)),
    )

    pedidos_por_id = {p.id: p for p in pedidos}
    waves = _construir_waves(data.get("waves", []), pedidos_por_id, w)
    resultados = _construir_resultados(data.get("resultados", {}))

    sesion = None
    if data.get("sesion"):
        s = data["sesion"]
        sesion = Sesion(
            wave_actual=s.get("wave_actual", 0),
            indice_actual=s.get("indice_actual", 0),
            estrategia_recorrido=s.get("estrategia_recorrido", "vecino_mas_cercano"),
        )

    return Escenario(
        nombre=data.get("nombre", path.stem),
        warehouse=w,
        pedidos=pedidos,
        pickers=pickers,
        wave_config=wave_config,
        seed=data.get("seed"),
        waves=waves,
        resultados=resultados,
        sesion=sesion,
    )


def _construir_waves(
    data_waves: list[dict], pedidos_por_id: dict, w: Warehouse
) -> list[Wave]:
    waves: list[Wave] = []
    for wd in data_waves:
        wave = Wave(
            id=wd["id"],
            max_pedidos=wd.get("max_pedidos", 3),
            max_productos=wd.get("max_productos", 20),
        )
        for pid in wd["pedido_ids"]:
            pedido = pedidos_por_id.get(pid)
            if pedido is None:
                raise ErrorDeCarga(
                    f"La wave {wave.id} referencia pedido inexistente: {pid}"
                )
            wave.pedidos.append(pedido)
            pedido.estado = EstadoPedido.EN_WAVE
        estado_str = wd.get("estado", "CERRADA")
        wave.estado = EstadoWave(estado_str)
        for pedido in wave.pedidos:
            if wave.estado == EstadoWave.CERRADA:
                pedido.estado = EstadoPedido.EN_WAVE
            elif wave.estado == EstadoWave.EN_PREPARACION:
                pedido.estado = EstadoPedido.EN_PREPARACION
            elif wave.estado == EstadoWave.COMPLETADA:
                pedido.estado = EstadoPedido.PREPARADO
        waves.append(wave)
    return waves


def _construir_resultados(data_resultados: dict) -> dict:
    from warehouse.algoritmos.recorridos import ResultadoRecorrido

    return {
        wid: ResultadoRecorrido(
            estrategia=r["estrategia"],
            orden_paradas=list(r["orden_paradas"]),
            camino_completo=list(r["camino_completo"]),
            distancia_total=r["distancia_total"],
            nodos_visitados=r["nodos_visitados"],
            aristas_recorridas=r["aristas_recorridas"],
            tiempo_segundos=r["tiempo_segundos"],
            indices_de_paradas=list(r["indices_de_paradas"]),
        )
        for wid, r in data_resultados.items()
    }
