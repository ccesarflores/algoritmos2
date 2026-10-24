from dataclasses import dataclass


@dataclass
class Rack:
    id: str
    x: int
    y: int
    niveles: int = 3  # cantidad de estantes físicos del rack
