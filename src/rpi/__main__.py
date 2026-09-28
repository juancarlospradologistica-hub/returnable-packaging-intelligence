"""
CLI del generador sintético MB51.

Uso:
    uv run python -m rpi                          # defaults completos
    uv run python -m rpi --months 6 --seed 99     # horizonte corto
    uv run python -m rpi --plants 3 --country MX  # solo 3 plantas MX
    uv run python -m rpi --loss-rate 0.01         # merma media 1% por viaje
    uv run python -m rpi --output data/custom     # directorio distinto
"""

from __future__ import annotations

import argparse
import sys

from rpi.config import Country, GeneratorConfig
from rpi.generator import generate


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m rpi",
        description="Genera dataset MB51 sintético para el pipeline RPI.",
    )
    p.add_argument("--months", type=int, default=None, metavar="N",
                   help="Horizonte en meses (default: 18).")
    p.add_argument("--plants", type=int, default=None, metavar="N",
                   help="Número de plantas. Si se omite, usa las 14 canónicas.")
    p.add_argument("--country", type=str, default=None, choices=["MX", "US", "NI"],
                   metavar="CC", help="Filtrar plantas por país (MX, US, NI).")
    p.add_argument("--loss-rate", type=float, default=None, metavar="RATE",
                   help="Merma media por viaje (default: 0.005).")
    p.add_argument("--seed", type=int, default=None, metavar="N",
                   help="Semilla aleatoria (default: 42).")
    p.add_argument("--output", type=str, default="data/raw", metavar="DIR",
                   help="Directorio de salida del Parquet (default: data/raw).")
    return p.parse_args(argv)


def build_config(args: argparse.Namespace) -> GeneratorConfig:
    base = GeneratorConfig()

    plants = base.plants
    if args.country:
        plants = [p for p in plants if p.country == Country(args.country)]
        if not plants:
            print(f"Error: no hay plantas para el país {args.country}.", file=sys.stderr)
            sys.exit(1)

    if args.plants is not None:
        if args.plants < 1:
            print("Error: --plants debe ser >= 1.", file=sys.stderr)
            sys.exit(1)
        plants = plants[: args.plants]

    # model_validate en lugar de model_copy: model_copy no corre los validadores
    # y una merma que dispara rate_high > 0.5 pasaría sin error.
    data = base.model_dump()
    data["plants"] = [p.model_dump() for p in plants]
    if args.months is not None:
        data["horizon_months"] = args.months
    if args.loss_rate is not None:
        data["loss"]["rate_mean"] = args.loss_rate
    if args.seed is not None:
        data["random_seed"] = args.seed
    return GeneratorConfig.model_validate(data)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    cfg = build_config(args)
    print(
        f"Plantas: {len(cfg.plants)} | Meses: {cfg.horizon_months} | "
        f"Corte: {cfg.reference_date} | Merma media: {cfg.loss.rate_mean:.2%} | "
        f"Seed: {cfg.random_seed}"
    )
    generate(cfg=cfg, output_dir=args.output)


if __name__ == "__main__":
    main()
