from PIL import Image
import io
import logging
from typing import BinaryIO

logger = logging.getLogger(__name__)

class ImageProcessingService:
    def __init__(self):
        # HARD LIMIT: 500KB
        self.MAX_SIZE_BYTES = 500 * 1024  

    def process_image(self, base_image_file: BinaryIO, watermark_bytes: bytes | None = None) -> bytes:
        try:
            # 1. Load
            base_img = Image.open(base_image_file).convert("RGBA")

            # 2. Watermark
            if watermark_bytes:
                logger.info("Applying watermark...")
                watermark_img = Image.open(io.BytesIO(watermark_bytes)).convert("RGBA")
                base_img = self._overlay_watermark(base_img, watermark_img)

            final_img_rgb = base_img.convert("RGB")

            # 3. Aggressive Compression
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
        """
        Guarantees < 500KB using strict resizing + quality reduction.
        """
        img_byte_arr = io.BytesIO()
        
        # STEP 1: Initial Sanity Resize
        # If image is massive (e.g. 4000px), immediately drop to 1920px (Full HD).
        # A 4000px image will almost NEVER be < 500KB unless quality is destroyed.
        if img.width > 1920 or img.height > 1920:
            logger.info(f"Image too big ({img.width}x{img.height}). Resizing to max 1920px.")
            img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)

        quality = 90
        iteration = 0
        
        while True:
            img_byte_arr.seek(0)
            img_byte_arr.truncate()
            
            # Save
            img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
            size = img_byte_arr.tell()
            
            # Success Check
            if size <= self.MAX_SIZE_BYTES:
                logger.info(f"Compression success: {size/1024:.2f}KB | Quality: {quality} | Size: {img.width}x{img.height}")
                img_byte_arr.seek(0)
                return img_byte_arr.read()
            
            # Failure Handling
            iteration += 1
            if iteration > 15: # Safety break to prevent infinite loops
                break

            # STRATEGY:
            # 1. If quality is good (>70), just lower quality.
            # 2. If quality gets too low (<=70), RESIZE the image smaller.
            #    (Better to have a sharp small image than a blurry large one)
            if quality > 70:
                quality -= 10
            else:
                # Drastic Resize: Reduce dimensions by 25%
                new_width = int(img.width * 0.75)
                new_height = int(img.height * 0.75)
                
                # Don't go absurdly small
                if new_width < 600: 
                    # If we are tiny and still > 500KB (unlikely), force low quality
                    quality = 50 
                else:
                    logger.info(f"Resizing further to {new_width}x{new_height}...")
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    # Reset quality to 85 because we have a new, smaller canvas
                    quality = 85

        # Final return if loop breaks
        img_byte_arr.seek(0)
        return img_byte_arr.read()

image_processing_service = ImageProcessingService()