"""Carga y cachea las imágenes (sprites) del picker, racks y productos."""

from pathlib import Path

from PIL import Image, ImageTk

ASSETS_DIR = Path(__file__).parent.parent.parent.parent / "assets"


class SpriteLoader:
    def __init__(
        self,
        picker_scale: float = 2.2,
        rack_scale: float = 0.92,
        assets_dir: Path | None = None,
    ) -> None:
        self.picker_scale = picker_scale
        self.rack_scale = rack_scale
        self.assets_dir = assets_dir if assets_dir is not None else ASSETS_DIR
        self.celda_px: int = 30  # lo setea la app

        self.base_picker_img: Image.Image | None = None
        self.picker_cache: dict[str, ImageTk.PhotoImage] = {}
        self.base_rack_img: Image.Image | None = None
        self.rack_cache: dict[str, ImageTk.PhotoImage] = {}
        self.product_imgs: dict[str, Image.Image] = {}
        self.product_cache: dict[str, ImageTk.PhotoImage] = {}

    def set_celda_px(self, valor: int) -> None:
        if valor == self.celda_px:
            return
        self.celda_px = valor
        self.picker_cache.clear()
        self.rack_cache.clear()
        self.product_cache.clear()

    def cargar(self) -> None:
        self._cargar_picker()
        self._cargar_rack()
        self._cargar_productos()

    # --- picker ---

    def _cargar_picker(self) -> None:
        ruta = self.assets_dir / "picker.png"
        if not ruta.exists() or ruta.stat().st_size == 0:
            self.base_picker_img = None
            return
        try:
            img = Image.open(ruta).convert("RGBA")
            px = img.load()
            w, h = img.size
            for y in range(h):
                for x in range(w):
                    r, g, b, a = px[x, y]
                    if abs(r - g) < 4 and abs(g - b) < 4 and 50 < r < 140:
                        px[x, y] = (0, 0, 0, 0)
            self.base_picker_img = img
        except Exception as e:
            print(f"[picker] Error cargando icono ({e}). Uso stick figure.")
            self.base_picker_img = None

    def obtener_picker(
        self, direction: str, alpha: int = 255
    ) -> ImageTk.PhotoImage | None:
        if self.base_picker_img is None:
            return None
        key = f"{direction}_{alpha}_{self.celda_px}"
        if key in self.picker_cache:
            return self.picker_cache[key]
        img = self.base_picker_img.copy()
        max_size = max(1, int(self.celda_px * self.picker_scale))
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        if direction == "left":
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif direction == "up":
            img = img.transpose(Image.Transpose.ROTATE_270)
        elif direction == "down":
            img = img.transpose(Image.Transpose.ROTATE_90)
        if alpha < 255:
            r, g, b, a = img.split()
            a = a.point(lambda p: int(p * (alpha / 255)))
            img = Image.merge("RGBA", (r, g, b, a))
        photo = ImageTk.PhotoImage(img)
        self.picker_cache[key] = photo
        return photo

    # --- rack ---

    def _cargar_rack(self) -> None:
        ruta = self.assets_dir / "rack.png"
        if not ruta.exists() or ruta.stat().st_size == 0:
            self.base_rack_img = None
            return
        try:
            img = Image.open(ruta).convert("RGBA")
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            px = img.load()
            w, h = img.size
            for y in range(h):
                for x in range(w):
                    r, g, b, a = px[x, y]
                    if r < 45 and g < 45 and b < 45:
                        px[x, y] = (0, 0, 0, 0)
            self.base_rack_img = img
        except Exception as e:
            print(f"[rack] Error cargando icono ({e}). Uso rectángulos.")
            self.base_rack_img = None

    def obtener_rack(self) -> ImageTk.PhotoImage | None:
        if self.base_rack_img is None:
            return None
        key = str(self.celda_px)
        if key in self.rack_cache:
            return self.rack_cache[key]
        img = self.base_rack_img.copy()
        size = max(1, int(self.celda_px * self.rack_scale))
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self.rack_cache[key] = photo
        return photo

    # --- productos ---

    def _cargar_productos(self) -> None:
        self.product_imgs = {}
        for tipo in ("lamp", "laptop", "box"):
            ruta = self.assets_dir / f"{tipo}.png"
            if ruta.exists() and ruta.stat().st_size > 0:
                try:
                    self.product_imgs[tipo] = Image.open(ruta).convert("RGBA")
                except Exception as e:
                    print(f"[producto] Error cargando {tipo}.png ({e})")

    def obtener_producto(self, pid: str) -> ImageTk.PhotoImage | None:
        if not self.product_imgs:
            return None
        tipos = list(self.product_imgs.keys())
        tipo = tipos[hash(pid) % len(tipos)]
        key = f"{tipo}_{self.celda_px}"
        if key in self.product_cache:
            return self.product_cache[key]
        img = self.product_imgs[tipo].copy()
        size = max(4, int(self.celda_px * 0.6))
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self.product_cache[key] = photo
        return photo
