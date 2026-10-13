from dataclasses import dataclass


@dataclass
class Pasillo:
    id: str
    x: int
    y: int
    ancho: int
    alto: int
    sentido: str  # "N" | "S" | "E" | "O" | "AMBOS"

    def __post_init__(self) -> None:
        if self.ancho <= 0 or self.alto <= 0:
            raise ValueError("ancho y alto deben ser > 0")
        if self.sentido not in ("N", "S", "E", "O", "AMBOS"):
            raise ValueError(f"Sentido inválido: {self.sentido}")

    def celdas(self) -> set[tuple[int, int]]:
        return {
            (x, y)
            for x in range(self.x, self.x + self.ancho)
            for y in range(self.y, self.y + self.alto)
        }
