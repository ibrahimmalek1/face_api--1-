from PIL import Image
import io
import logging
from typing import BinaryIO

logger = logging.getLogger(__name__)

class ImageProcessingService:
    def __init__(self):
        self.MAX_SIZE_BYTES = 1024 * 1024  # 1MB

    def process_image(self, base_image_file: BinaryIO, watermark_bytes: bytes | None = None) -> bytes:
        """
        Standard processing: Always attempts to watermark (if provided) and compress.
        """
        try:
            # 1. Load
            base_img = Image.open(base_image_file).convert("RGBA")

            # 2. Watermark
            if watermark_bytes:
                logger.info("Applying watermark...")
                watermark_img = Image.open(io.BytesIO(watermark_bytes)).convert("RGBA")
                base_img = self._overlay_watermark(base_img, watermark_img)

            final_img_rgb = base_img.convert("RGB")

            # 3. Compress
            return self._compress_to_target_size(final_img_rgb)

        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            base_image_file.seek(0)
            return base_image_file.read()

    def _overlay_watermark(self, base_img: Image.Image, watermark_img: Image.Image) -> Image.Image:
        target_width = int(base_img.width * 0.10)
        aspect_ratio = watermark_img.height / watermark_img.width
        target_height = int(target_width * aspect_ratio)
        watermark_resized = watermark_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        padding = int(base_img.width * 0.02)
        position_x = base_img.width - target_width - padding
        position_y = base_img.height - target_height - padding
        
        transparent_layer = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        transparent_layer.paste(watermark_resized, (position_x, position_y), watermark_resized)
        return Image.alpha_composite(base_img, transparent_layer)

    def _compress_to_target_size(self, img: Image.Image) -> bytes:
        quality = 95
        step = 10
        min_quality = 10 
        img_byte_arr = io.BytesIO()

        if img.width > 3840: img.thumbnail((3840, 3840))

        while quality >= min_quality:
            img_byte_arr.seek(0)
            img_byte_arr.truncate()
            img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
            if img_byte_arr.tell() <= self.MAX_SIZE_BYTES:
                img_byte_arr.seek(0)
                return img_byte_arr.read()
            quality -= step
            
        img_byte_arr.seek(0)
        return img_byte_arr.read()

image_processing_service = ImageProcessingService()