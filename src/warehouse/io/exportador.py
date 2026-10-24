import json
from pathlib import Path

from warehouse.warehouse.escenario import Escenario


def _producto_a_dict(p) -> dict:
    return {
        "id": p.id,
        "nombre": p.nombre,
        "rack_id": p.rack_id,
        "ubicacion": {"x": p.x, "y": p.y, "z": p.z},
        "cantidad_disponible": p.cantidad_disponible,
        "peso_kg": p.peso_kg,
    }


def _pedido_a_dict(p) -> dict:
    return {
        "id": p.id,
        "prioridad": p.prioridad,
        "items": [
            {"producto_id": it.producto_id, "cantidad": it.cantidad} for it in p.items
        ],
    }


def escenario_a_dict(escenario: Escenario) -> dict:
    w = escenario.warehouse

    racks = [
        {
            "id": r.id,
            "ubicacion": {"x": r.x, "y": r.y},
            "ancho": r.ancho,
            "alto": r.alto,
            "niveles": r.niveles,
        }
        for r in sorted(w.racks.values(), key=lambda r: r.id)
    ]
    zonas = [
        {
            "id": z.id,
            "puerta_id": z.puerta_id,
            "ubicacion": {"x": z.p1[0], "y": z.p1[1]},
            "ancho": z.p2[0] - z.p1[0] + 1,
            "alto": z.p2[1] - z.p1[1] + 1,
            "peso_max_kg": z.peso_max_kg,
        }
        for z in sorted(w.zonas.values(), key=lambda z: z.id)
    ]
    puertas = [
        {
            "id": p.id,
            "tipo": p.tipo,
            "ubicacion": {"x": p.posicion.x, "y": p.posicion.y},
        }
        for p in sorted(w.puertas.values(), key=lambda p: p.id)
    ]
    pasillos = [
        {
            "id": p.id,
            "ubicacion": {"x": p.x, "y": p.y},
            "ancho": p.ancho,
            "alto": p.alto,
            "sentido": p.sentido,
        }
        for p in sorted(w.pasillos.values(), key=lambda p: p.id)
    ]
    productos = [
        _producto_a_dict(p) for p in sorted(w.productos.values(), key=lambda p: p.id)
    ]
    pedidos = [_pedido_a_dict(p) for p in escenario.pedidos]

    pickers = [
        {
            "id": pk.id,
            "posicion_inicial": {
                "x": pk.posicion_inicial[0],
                "y": pk.posicion_inicial[1],
            },
            "capacidad_carga_kg": pk.capacidad_carga_kg,
        }
        for pk in escenario.pickers
    ]

    waves_dict = [
        {
            "id": wv.id,
            "estado": wv.estado.value,
            "max_pedidos": wv.max_pedidos,
            "max_productos": wv.max_productos,
            "pedido_ids": [p.id for p in wv.pedidos],
        }
        for wv in escenario.waves
    ]
    resultados_dict = {
        wid: {
            "estrategia": r.estrategia,
            "orden_paradas": list(r.orden_paradas),
            "camino_completo": list(r.camino_completo),
            "distancia_total": r.distancia_total,
            "nodos_visitados": r.nodos_visitados,
            "aristas_recorridas": r.aristas_recorridas,
            "tiempo_segundos": r.tiempo_segundos,
            "indices_de_paradas": list(r.indices_de_paradas),
        }
        for wid, r in escenario.resultados.items()
    }
    sesion_dict = None
    if escenario.sesion is not None:
        sesion_dict = {
            "wave_actual": escenario.sesion.wave_actual,
            "indice_actual": escenario.sesion.indice_actual,
            "estrategia_recorrido": escenario.sesion.estrategia_recorrido,
        }

    return {
        "nombre": escenario.nombre,
        "seed": escenario.seed,
        "warehouse": {
            "dimensiones": {"ancho_x": w.ancho, "largo_y": w.alto},
            "racks": racks,
            "zonas_despacho": zonas,
            "puertas": puertas,
            "pasillos": pasillos,
        },
        "pickers": pickers,
        "productos": productos,
        "pedidos": pedidos,
        "configuracion": {
            "wave_max_pedidos": escenario.wave_config.max_pedidos,
            "wave_max_productos": escenario.wave_config.max_productos,
            "wave_max_peso_kg": escenario.wave_config.max_peso_kg,
        },
        "waves": waves_dict,
        "resultados": resultados_dict,
        "sesion": sesion_dict,
    }


def exportar_escenario(escenario: Escenario, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = escenario_a_dict(escenario)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
