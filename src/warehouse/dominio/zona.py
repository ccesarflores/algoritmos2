from dataclasses import dataclass


@dataclass
class ZonaDespacho:
    id: str
    puerta_id: str
    p1: tuple[int, int]
    p2: tuple[int, int]
    peso_max_kg: float
    nodo_representativo: int = -1
