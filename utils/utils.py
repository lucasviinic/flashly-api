import io
from typing import List
import PyPDF2
import tiktoken
import os
from fastapi import HTTPException, UploadFile
from PIL import Image


MAX_FILE_SIZE = 20 * 1024 * 1024  # 5MB

def pdf_to_text(pdf) -> str:
    pdf.seek(0, os.SEEK_END)
    file_size = pdf.tell()
    pdf.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise RuntimeError(f"O arquivo PDF excede o limite de 5MB.")

    text = ''
    try:
        reader = PyPDF2.PdfReader(pdf)
        for page_num in range(len(reader.pages)):
            text += reader.pages[page_num].extract_text()
    except Exception as e:
        raise RuntimeError(f"Error processing PDF file: {e}")

    return text

def fragment_text(text_content: str) -> List[str]:
    token_count = token_counter(text_content)
    max_token = int(os.getenv('MAX_TOKENS'))
    
    if token_count <= max_token:
        return [text_content]
    
    num_parts = (token_count // max_token) + (1 if token_count % max_token else 0)
    tokens_per_part = token_count // num_parts

    words = text_content.split()
    fragments = [
        " ".join(words[i:i+tokens_per_part]) for i in range(0, len(words), tokens_per_part)
    ]

    return fragments

def token_counter(text: str) -> int:
    coder = tiktoken.encoding_for_model('gpt-4-turbo')
    token_list = coder.encode(text)
    size = len(token_list)
    
    return size

def validate_file_size(file_obj, max_size_mb: int) -> None:
    """
    Validates whether the file is smaller than or equal to the specified limit.

    Parameters:
        - file_obj: file object to be validated.
        - max_size_mb: maximum size allowed in megabytes.

    Throws HTTPException if the file exceeds the allowed size.
    """

    file_obj.seek(0, os.SEEK_END)
    file_size = file_obj.tell()
    file_obj.seek(0)
    
    max_size_bytes = max_size_mb * 1024 * 1024

    return file_size > max_size_bytes

def compress_image(file_image: UploadFile, quality: int = 70) -> io.BytesIO:
    """
    Abstracts image compression using the Pillow library.

    Parameters:
        - file_image: UploadFile type object.
        - quality: quality of the compressed JPEG image (default 70).

    Returns:
        - BytesIO object containing the compressed image.

    Throws HTTPException if an error occurs during compression.
    """
    try:
        image = Image.open(file_image.file)
        
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        
        compressed_io = io.BytesIO()
        image.save(compressed_io, format="JPEG", quality=quality, optimize=True)
        compressed_io.seek(0)
        return compressed_io
    except Exception:
        raise HTTPException(status_code=400, detail="error compressing image")