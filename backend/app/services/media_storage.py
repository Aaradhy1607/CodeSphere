import os
import uuid
import logging
from typing import Dict, Any, Tuple
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)

# Base directory for storing user and question uploads
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "questions"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif"
}

# Magic byte signatures
MAGIC_NUMBERS = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp"
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024 # 5 MB

class MediaStorageService:
    """
    Secure Media & Image Storage Service for CodeSphere Questions.
    Provides strict filetype, magic-byte, and size verification to prevent malicious uploads.
    """

    @classmethod
    async def save_question_image(cls, file: UploadFile) -> Dict[str, Any]:
        """
        Validates and saves an uploaded image for question diagram/authoring.
        """
        # 1. Check Content-Type header
        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file format: '{content_type}'. Only PNG, JPEG, WEBP, and GIF images are allowed."
            )

        # 2. Read contents and verify file size
        contents = await file.read()
        file_size = len(contents)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of 5 MB (received {round(file_size / (1024*1024), 2)} MB)."
            )
        if file_size < 10:
            raise HTTPException(status_code=400, detail="Uploaded file is empty or corrupted.")

        # 3. Magic byte signature verification
        valid_signature = False
        for magic_bytes, magic_mime in MAGIC_NUMBERS.items():
            if contents.startswith(magic_bytes):
                valid_signature = True
                break
        
        # WebP second check
        if not valid_signature and contents.startswith(b"RIFF") and b"WEBP" in contents[:16]:
            valid_signature = True

        if not valid_signature and content_type != "image/webp":
            raise HTTPException(
                status_code=400,
                detail="Security validation failed: File binary signature does not match image specification."
            )

        # 4. Generate cryptographically random secure filename
        ext = ALLOWED_MIME_TYPES.get(content_type, ".png")
        unique_filename = f"q_img_{uuid.uuid4().hex}{ext}"
        target_path = os.path.join(UPLOAD_DIR, unique_filename)

        with open(target_path, "wb") as f:
            f.write(contents)

        logger.info(f"[MEDIA STORAGE] Saved question image '{unique_filename}' ({file_size} bytes)")

        # Web accessible path
        image_url = f"/static/uploads/questions/{unique_filename}"
        return {
            "image_url": image_url,
            "filename": unique_filename,
            "original_filename": file.filename or "diagram.png",
            "size_bytes": file_size,
            "mime_type": content_type
        }

media_storage = MediaStorageService()
