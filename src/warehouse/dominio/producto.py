from dataclasses import dataclass


@dataclass
class Producto:
    id: str
    nombre: str
    rack_id: str
    x: int  # celda dentro del rack
    y: int
    z: int  # altura (1..niveles del rack)
    cantidad_disponible: int
    peso_kg: float
    nodo_picking: int = -1  # lo asigna Warehouse.agregar_producto

    def __post_init__(self) -> None:
        if self.z < 1:
            raise ValueError(f"z debe ser >= 1 (recibí {self.z})")
        if self.cantidad_disponible < 0:
            raise ValueError("cantidad_disponible no puede ser negativa")
        if self.peso_kg <= 0:
            raise ValueError("peso_kg debe ser > 0")

    @property
    def stock(self) -> int:
        return self.cantidad_disponible
