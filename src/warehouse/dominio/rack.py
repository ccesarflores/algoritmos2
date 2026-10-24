from dataclasses import dataclass


@dataclass
class Rack:
    id: str
    x: int
    y: int
    ancho: int
    alto: int
    niveles: int = 3  # niveles físicos por celda (z = 1..niveles)

    def __post_init__(self) -> None:
        if self.ancho <= 0 or self.alto <= 0:
            raise ValueError("ancho y alto deben ser > 0")
        # El enunciado: uno de los dos lados debe valer exactamente 2
        if not (self.ancho == 2 or self.alto == 2):
            raise ValueError(
                f"Rack {self.id}: uno de ancho/alto debe valer 2 "
                f"(recibí ancho={self.ancho}, alto={self.alto})"
            )
        if self.niveles <= 0:
            raise ValueError("niveles debe ser > 0")

    def celdas(self) -> set[tuple[int, int]]:
        return {
            (cx, cy)
            for cx in range(self.x, self.x + self.ancho)
            for cy in range(self.y, self.y + self.alto)
        }

    def contiene(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.ancho and self.y <= y < self.y + self.alto
