# scripts/demo_completa.py
"""Demo completa: genera (o carga) un escenario, calcula los recorridos
de todas las waves y las simula con la app de visualización.

Uso:
    python scripts/demo_completa.py --bloques 6 --alto 10 --pedidos 40
    python scripts/demo_completa.py --estrategia orden_pedidos
    python scripts/demo_completa.py --cargar data/sesiones/partida_a.json
"""

import argparse
import random
import sys

from warehouse.algoritmos.recorridos import ESTRATEGIAS, recorrer_wave
from warehouse.dominio.picker import Picker
from warehouse.generacion.generador import ConfigGeneracion, generar_escenario
from warehouse.generacion.validador import validar_escenario
from warehouse.io.cargador_json import cargar_escenario
from warehouse.simulacion.multi_picker import SimulacionMultiPicker
from warehouse.visualizacion.app import SimulacionApp
from warehouse.waves.generador_waves import EstrategiaWaves, generar_waves


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if args.cargar:
        escenario, simulacion = _cargar(args)
    else:
        escenario, simulacion = _generar(args)

    SimulacionApp(
        escenario=escenario,
        simulacion=simulacion,
        estrategia=args.estrategia,
        delay_caminar=args.delay_caminar,
        delay_esperar=args.delay_esperar,
        picker_scale=args.picker_scale,
        rack_scale=args.rack_scale,
    ).run()


def _cargar(args):
    escenario = cargar_escenario(args.cargar)
    if not escenario.waves:
        sys.exit("El archivo no contiene waves. Generá el escenario de cero.")

    # Reconstruir la simulación multi-picker a partir de las waves cargadas
    pickers = escenario.pickers
    waves_con_pickers = []

    for i, w in enumerate(escenario.waves):
        picker = (
            pickers[i % len(pickers)]
            if pickers
            else Picker("PK_default", (0, 0), 500.0)
        )
        # Usamos los resultados que ya vienen guardados en el JSON
        r = escenario.resultados[w.id]
        waves_con_pickers.append((w, r, picker))

    simulacion = SimulacionMultiPicker.desde_waves(
        waves_con_pickers, escenario.warehouse
    )
    return escenario, simulacion


def _generar(args):
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

    max_peso_wave = (
        min([p.capacidad_carga_kg for p in escenario.pickers])
        if escenario.pickers
        else 500.0
    )

    waves = generar_waves(
        escenario.pedidos,
        escenario.warehouse,
        max_pedidos=args.max_pedidos_wave,
        max_productos=args.max_productos_wave,
        max_peso_kg=max_peso_wave,
        estrategia=EstrategiaWaves(args.estrategia_waves),
    )

    # Asignar un picker a cada wave (round robin)
    pickers = escenario.pickers
    waves_con_pickers = []

    # Todos los nodos transitables del warehouse
    nodos_transitables = list(escenario.warehouse._nodo_por_xy.values())

    # Elegir nodos de inicio aleatorios SIN repetir (uno por picker)
    # Si hay más waves que nodos, se repiten
    n_inicios = min(len(waves), len(nodos_transitables))
    inicios_aleatorios = random.sample(nodos_transitables, n_inicios)

    for i, w in enumerate(waves):
        if pickers:
            picker = pickers[i % len(pickers)]
        else:
            picker = Picker(f"PK_{i+1:02d}", (0, 0), 500.0)

        # Asignar el nodo de inicio aleatorio
        nodo_inicio = inicios_aleatorios[i % len(inicios_aleatorios)]

        # (Opcional) Actualizar la posición inicial del picker para que quede en el JSON
        # picker.posicion_inicial = (nodo.posicion.x, nodo.posicion.y)

        r = recorrer_wave(
            w, escenario.warehouse, estrategia=args.estrategia, nodo_inicio=nodo_inicio
        )
        waves_con_pickers.append((w, r, picker))

    # Crear la simulación multi-picker
    simulacion = SimulacionMultiPicker.desde_waves(
        waves_con_pickers, escenario.warehouse
    )

    escenario.waves = waves
    return escenario, simulacion


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--bloques", type=int, default=3)
    p.add_argument("--alto", type=int, default=6)
    p.add_argument("--pasillos-h", type=int, default=0)
    p.add_argument("--pedidos", type=int, default=15)
    p.add_argument("--max-pedidos-wave", type=int, default=3)
    p.add_argument("--max-productos-wave", type=int, default=20)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--productos-por-rack", type=int, default=2)
    p.add_argument("--niveles-por-rack", type=int, default=3)
    p.add_argument(
        "--estrategia", choices=list(ESTRATEGIAS.keys()), default="vecino_mas_cercano"
    )
    p.add_argument(
        "--estrategia-waves",
        choices=[e.value for e in EstrategiaWaves],
        default=EstrategiaWaves.PRIORIDAD_Y_CERCANIA.value,
    )
    p.add_argument("--cargar", type=str, default=None)
    p.add_argument("--delay-caminar", type=int, default=100)
    p.add_argument("--delay-esperar", type=int, default=1000)
    p.add_argument("--picker-scale", type=float, default=2.2)
    p.add_argument("--rack-scale", type=float, default=0.92)
    p.add_argument(
        "--random-start",
        action="store_true",
        default=False,
        help="Hace que los pickers arranquen desde un nodo aleatorio en vez del despacho.",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    main()
