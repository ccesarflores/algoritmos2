from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from warehouse.dominio.estado_pedido import EstadoPedido
from warehouse.dominio.estado_wave import EstadoWave
from warehouse.dominio.pedido import Pedido

if TYPE_CHECKING:
    from warehouse.dominio.producto import Producto


@dataclass
class Wave:
    id: str
    max_pedidos: int = 3
    max_productos: int = 20
    max_peso_kg: float = 500.0
    pedidos: list[Pedido] = field(default_factory=list)
    estado: EstadoWave = EstadoWave.ABIERTA

    def __post_init__(self) -> None:
        if self.max_pedidos <= 0:
            raise ValueError("max_pedidos debe ser > 0")
        if self.max_productos <= 0:
            raise ValueError("max_productos debe ser > 0")
        if self.max_peso_kg <= 0:
            raise ValueError("max_peso_kg debe ser > 0")

    # --- consultas ---
    def cantidad_pedidos(self) -> int:
        return len(self.pedidos)

    def cantidad_productos(self) -> int:
        return sum(p.cantidad_total_productos() for p in self.pedidos)

    def peso_total(self, productos: dict[str, "Producto"]) -> float:
        """Calcula el peso total de la wave usando el diccionario de productos."""
        total = 0.0
        for pedido in self.pedidos:
            for item in pedido.items:
                total += productos[item.producto_id].peso_kg * item.cantidad
        return total

    def puede_agregar(self, pedido: Pedido) -> bool:
        # Volvemos a la firma original (sin productos)
        if self.estado != EstadoWave.ABIERTA:
            return False
        if len(self.pedidos) + 1 > self.max_pedidos:
            return False
        if (
            self.cantidad_productos() + pedido.cantidad_total_productos()
            > self.max_productos
        ):
            return False
        return True

    def agregar_pedido(self, pedido: Pedido) -> None:
        # Volvemos a la firma original
        if not self.puede_agregar(pedido):
            raise ValueError(
                f"No se puede agregar pedido {pedido.id} a wave {self.id}: "
                f"estado={self.estado.value}, "
                f"pedidos={len(self.pedidos)}/{self.max_pedidos}, "
                f"productos={self.cantidad_productos()}/{self.max_productos}"
            )
        self.pedidos.append(pedido)
        pedido.estado = EstadoPedido.EN_WAVE

    def prioridad_maxima(self) -> int:
        return max((p.prioridad for p in self.pedidos), default=0)

    def ubicaciones_requeridas(self) -> set[str]:
        """IDs de productos que hay que recolectar en esta wave."""
        ids: set[str] = set()
        for p in self.pedidos:
            ids |= p.productos_ids()
        return ids

    def cerrar(self) -> None:
        if self.estado != EstadoWave.ABIERTA:
            raise ValueError(
                f"Solo se puede cerrar una wave ABIERTA, estado actual: {self.estado.value}"
            )
        self.estado = EstadoWave.CERRADA

    def iniciar_preparacion(self) -> None:
        if self.estado != EstadoWave.CERRADA:
            raise ValueError(
                f"Solo se puede preparar una wave CERRADA, estado actual: {self.estado.value}"
            )
        self.estado = EstadoWave.EN_PREPARACION
        for p in self.pedidos:
            p.estado = EstadoPedido.EN_PREPARACION

    def completar(self) -> None:
        if self.estado != EstadoWave.EN_PREPARACION:
            raise ValueError(
                f"Solo se puede completar una wave EN_PREPARACION, estado actual: {self.estado.value}"
            )
        self.estado = EstadoWave.COMPLETADA
        for p in self.pedidos:
            p.estado = EstadoPedido.PREPARADO
