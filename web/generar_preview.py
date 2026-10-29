"""Genera la imagen social de la portada con las fuentes locales."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/imagenes/social-preview-portada.png"


def font(name, size, weight=None):
    value = ImageFont.truetype(str(ROOT / "web/fonts" / name), size)
    if weight:
        value.set_variation_by_name(weight)
    return value


def build():
    image = Image.new("RGB", (1200, 630), "#f8f9f6")
    draw = ImageDraw.Draw(image)
    ink, green, muted = "#19231d", "#173c2c", "#536b58"
    draw.rounded_rectangle((70, 62, 114, 106), radius=10, fill=green)
    draw.line([(82, 75), (90, 73), (92, 76), (92, 94), (83, 92), (82, 93), (82, 75)], fill="#f8f9f6", width=2)
    draw.line([(92, 76), (100, 73), (103, 74), (103, 93), (96, 92), (92, 94)], fill="#f8f9f6", width=2)
    draw.text((126, 63), "Mi grado", fill=ink, font=font("DMSans.ttf", 30, "Bold"))
    draw.text((70, 172), "TU CUADERNO DE ESTUDIO", fill=muted, font=font("DMSans.ttf", 16, "Bold"))
    draw.text((68, 211), "Lo que estudias,", fill=ink, font=font("DMSans.ttf", 66, "Bold"))
    draw.text((68, 290), "en su sitio.", fill=ink, font=font("Lora.ttf", 70, "Regular"))
    draw.text((70, 408), "Organiza tus asignaturas y retoma", fill=muted, font=font("DMSans.ttf", 25))
    draw.text((70, 444), "por donde lo dejaste.", fill=muted, font=font("DMSans.ttf", 25))
    draw.line((70, 532, 1130, 532), fill="#d8e2d7", width=2)
    draw.text((70, 555), "GRATIS  ·  SIN CUENTA  ·  CÓDIGO ABIERTO", fill=muted, font=font("DMSans.ttf", 16, "Bold"))
    draw.rounded_rectangle((805, 132, 1092, 454), radius=22, fill="#e5ede3")
    draw.rounded_rectangle((858, 170, 1044, 418), radius=13, fill=green)
    draw.line((880, 205, 1015, 205), fill="#95b49a", width=3)
    draw.line((880, 234, 1000, 234), fill="#95b49a", width=3)
    draw.line((880, 263, 1020, 263), fill="#95b49a", width=3)
    draw.rounded_rectangle((880, 316, 980, 345), radius=7, fill="#dbe9d8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT, optimize=True)
    return OUT


if __name__ == "__main__":
    print(build())
