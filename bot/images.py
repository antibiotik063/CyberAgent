from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import Settings
from .models import PostDraft


LOCATION_TITLE = "SAMARA"
LOCATION_ADDRESS = "5-\u044f \u043f\u0440\u043e\u0441\u0435\u043a\u0430, 95"


class ImageGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key)

    def generate(self, draft: PostDraft) -> Path:
        prompt = (
            f"{draft.image_prompt}. "
            "Create a vivid premium esports poster with bold cinematic composition, rich contrast, "
            "expensive-looking color grading, glowing highlights, energetic motion, dramatic atmosphere, "
            "deep reds, black chrome, subtle gold accents, polished promotional art direction, "
            "high-end club branding space, 16:9, no watermarks, no news outlet logos, no cheap flat design."
        )
        response = self.client.images.generate(
            model=self.settings.openai_image_model,
            prompt=prompt,
            size="1536x1024",
            quality="high",
            output_format="png",
            background="opaque",
        )
        image_base64 = response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)
        file_name = f"post_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        image_path = self.settings.generated_dir / file_name
        image_path.write_bytes(image_bytes)
        self._apply_branding(image_path)
        return image_path

    def _apply_branding(self, image_path: Path) -> None:
        image = Image.open(image_path).convert("RGBA")
        image = self._overlay_logo(image)
        image = self._overlay_location_badge(image)
        image.convert("RGB").save(image_path, format="PNG")

    def _overlay_logo(self, image: Image.Image) -> Image.Image:
        logo_path = self.settings.club_logo_path
        if not logo_path.exists():
            return image

        logo = Image.open(logo_path).convert("RGBA")
        logo = self._strip_dark_background(logo)
        width, height = image.size
        target_width = max(int(width * 0.22), 250)
        scale = target_width / max(logo.width, 1)
        resized = logo.resize(
            (target_width, max(int(logo.height * scale), 1)),
            Image.Resampling.LANCZOS,
        )

        padding = max(width // 32, 36)
        x = width - resized.width - padding
        y = padding

        shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        alpha = resized.split()[-1].filter(
            ImageFilter.GaussianBlur(radius=max(width // 240, 4))
        )
        shadow_logo = Image.new("RGBA", resized.size, (0, 0, 0, 150))
        shadow_logo.putalpha(alpha)
        shadow_layer.alpha_composite(shadow_logo, (x + 10, y + 12))
        image = Image.alpha_composite(image, shadow_layer)
        image.alpha_composite(resized, (x, y))
        return image

    def _overlay_location_badge(self, image: Image.Image) -> Image.Image:
        width, height = image.size
        title_font = self._load_font(max(width // 42, 24))
        address_font = self._load_font(max(width // 26, 34))

        probe = ImageDraw.Draw(image)
        title_box = probe.textbbox((0, 0), LOCATION_TITLE, font=title_font)
        address_box = probe.textbbox((0, 0), LOCATION_ADDRESS, font=address_font)
        title_height = title_box[3] - title_box[1]
        address_height = address_box[3] - address_box[1]
        text_width = max(title_box[2] - title_box[0], address_box[2] - address_box[0])

        padding_x = max(width // 28, 40)
        padding_y = max(height // 30, 30)
        panel_w = text_width + padding_x * 2 + 28
        panel_h = title_height + address_height + padding_y * 2 + 26
        x = max(width // 26, 40)
        y = height - panel_h - max(height // 24, 42)

        panel = Image.new("RGBA", (panel_w, panel_h), (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle(
            (0, 0, panel_w, panel_h),
            radius=34,
            fill=(7, 9, 16, 210),
            outline=(215, 177, 92, 110),
            width=2,
        )
        panel_draw.rounded_rectangle(
            (0, 0, 20, panel_h),
            radius=18,
            fill=(210, 22, 30, 240),
        )
        panel_draw.polygon(
            [(36, 0), (126, 0), (74, panel_h)],
            fill=(255, 215, 120, 30),
        )
        panel_draw.line(
            (padding_x, padding_y + title_height + 10, panel_w - padding_x, padding_y + title_height + 10),
            fill=(215, 177, 92, 210),
            width=3,
        )
        panel_draw.rounded_rectangle(
            (18, 18, panel_w - 18, panel_h - 18),
            radius=26,
            outline=(255, 255, 255, 18),
            width=1,
        )

        shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        shadow_panel = Image.new("RGBA", (panel_w, panel_h), (0, 0, 0, 0))
        ImageDraw.Draw(shadow_panel).rounded_rectangle(
            (0, 0, panel_w, panel_h),
            radius=34,
            fill=(0, 0, 0, 145),
        )
        shadow_panel = shadow_panel.filter(ImageFilter.GaussianBlur(radius=14))
        shadow_layer.alpha_composite(shadow_panel, (x + 12, y + 16))
        image = Image.alpha_composite(image, shadow_layer)
        image.alpha_composite(panel, (x, y))

        draw = ImageDraw.Draw(image)
        text_x = x + padding_x + 12
        title_y = y + padding_y - 2
        address_y = title_y + title_height + 18

        draw.text(
            (text_x, title_y),
            LOCATION_TITLE,
            font=title_font,
            fill=(245, 233, 206, 230),
        )
        draw.text(
            (text_x, address_y),
            LOCATION_ADDRESS,
            font=address_font,
            fill=(255, 255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 205),
        )
        return image

    def _strip_dark_background(self, logo: Image.Image) -> Image.Image:
        rgb = logo.convert("RGB")
        alpha = Image.new("L", logo.size, 0)
        source_pixels = rgb.load()
        alpha_pixels = alpha.load()
        for y in range(logo.height):
            for x in range(logo.width):
                r, g, b = source_pixels[x, y]
                if max(r, g, b) > 20:
                    alpha_pixels[x, y] = 255

        clean = logo.copy()
        clean.putalpha(alpha)
        bbox = clean.getbbox()
        if bbox is None:
            return clean
        cropped = clean.crop(bbox)

        return cropped

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        preferred = [
            "C:/Windows/Fonts/bahnschrift.ttf",
            "C:/Windows/Fonts/ariblk.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/verdanab.ttf",
        ]
        for path in preferred:
            if Path(path).exists():
                return ImageFont.truetype(path, size=size)
        return ImageFont.load_default()
