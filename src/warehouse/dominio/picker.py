from dataclasses import dataclass


@dataclass
class Picker:
    id: str
    posicion_inicial: tuple[int, int]
    capacidad_carga_kg: float

    def __post_init__(self) -> None:
        if self.capacidad_carga_kg <= 0:
            raise ValueError("capacidad_carga_kg debe ser > 0")
