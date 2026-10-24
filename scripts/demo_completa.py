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
from warehouse.generacion.generador import ConfigGeneracion, generar_escenario
from warehouse.generacion.validador import validar_escenario
from warehouse.io.cargador_json import cargar_escenario
from warehouse.visualizacion.app import SimulacionApp
from warehouse.waves.generador_waves import EstrategiaWaves, generar_waves


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if args.cargar:
        escenario, resultados = _cargar(args)
    else:
        escenario, resultados = _generar(args)

    SimulacionApp(
        escenario=escenario,
        resultados=resultados,
        estrategia=args.estrategia,
        indice_inicial=args.wave,
        paso_inicial=getattr(args, "_paso_inicial", 0),
        delay_caminar=args.delay_caminar,
        delay_esperar=args.delay_esperar,
        picker_scale=args.picker_scale,
        rack_scale=args.rack_scale,
    ).run()


def _cargar(args):
    escenario = cargar_escenario(args.cargar)
    if not escenario.waves:
        sys.exit("El archivo no contiene waves. Generá el escenario de cero.")
    resultados = [(w, escenario.resultados[w.id]) for w in escenario.waves]
    if escenario.sesion is not None:
        args.estrategia = escenario.sesion.estrategia_recorrido
        args.wave = escenario.sesion.wave_actual
        args._paso_inicial = escenario.sesion.indice_actual
    return escenario, resultados


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
    waves = generar_waves(
        escenario.pedidos,
        escenario.warehouse,
        max_pedidos=args.max_pedidos_wave,
        max_productos=args.max_productos_wave,
        estrategia=EstrategiaWaves(args.estrategia_waves),
    )

    nodos_transitables = list(escenario.warehouse.grafo._nodos.keys())
    resultados = []
    for w in waves:
        nodo_inicio = random.choice(nodos_transitables) if args.random_start else None
        r = recorrer_wave(
            w,
            escenario.warehouse,
            estrategia=args.estrategia,
            nodo_inicio=nodo_inicio,
        )
        resultados.append((w, r))

    escenario.waves = waves
    escenario.resultados = {w.id: r for w, r in resultados}
    return escenario, resultados


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--bloques", type=int, default=3)
    p.add_argument("--alto", type=int, default=4)
    p.add_argument("--pasillos-h", type=int, default=0)
    p.add_argument("--pedidos", type=int, default=40)
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
    p.add_argument("--wave", type=int, default=0)
    p.add_argument("--cargar", type=str, default=None)
    p.add_argument("--delay-caminar", type=int, default=100)
    p.add_argument("--delay-esperar", type=int, default=1000)
    p.add_argument("--picker-scale", type=float, default=2.2)
    p.add_argument("--rack-scale", type=float, default=0.92)
    p.add_argument(
        "--random-start",
        action="store_true",
        default=True,
        help="El picker arranca desde un nodo aleatorio (comportamiento "
        "histórico de la demo). Desactivá con --no-random-start.",
    )
    p.add_argument("--no-random-start", dest="random_start", action="store_false")
    return p.parse_args(argv)


if __name__ == "__main__":
    main()
