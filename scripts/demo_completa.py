# scripts/demo_completa.py
"""Demo completa con Simulación Dinámica Multi-Agente."""

import argparse
import sys

from warehouse.algoritmos.recorridos import ESTRATEGIAS
from warehouse.generacion.generador import ConfigGeneracion, generar_escenario
from warehouse.generacion.validador import validar_escenario
from warehouse.io.cargador_json import cargar_escenario
from warehouse.simulacion.dinamica import SimulacionDinamica
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
        print("El escenario no tiene waves calculadas. Generando waves...")
        max_peso_wave = (
            max([p.capacidad_carga_kg for p in escenario.pickers])
            if escenario.pickers
            else 500.0
        )
        waves = generar_waves(
            escenario.pedidos,
            escenario.warehouse,
            max_pedidos=escenario.wave_config.max_pedidos,
            max_productos=escenario.wave_config.max_productos,
            max_peso_kg=max_peso_wave,
            estrategia=EstrategiaWaves(args.estrategia_waves),
        )
        escenario.waves = waves

    simulacion = SimulacionDinamica.desde_waves(
        waves=escenario.waves,
        pickers=escenario.pickers,
        warehouse=escenario.warehouse,
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
        max([p.capacidad_carga_kg for p in escenario.pickers])
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
    escenario.waves = waves

    simulacion = SimulacionDinamica.desde_waves(
        waves=waves,
        pickers=escenario.pickers,
        warehouse=escenario.warehouse,
    )
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
    return p.parse_args(argv)


if __name__ == "__main__":
    main()
