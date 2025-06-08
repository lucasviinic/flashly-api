import os
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import UploadFile

import firebase_admin
from firebase_admin import credentials, storage
from google.cloud.exceptions import NotFound

from utils.utils import compress_image


def firebase_file_upload(bucket_blob: str, image_id: str, file_image: UploadFile) -> str:
    if not firebase_admin._apps:
        cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS_FILE"))
        firebase_admin.initialize_app(cred, {
            'storageBucket': f"{os.getenv('FIREBASE_PROJECT_ID')}.firebasestorage.app"
        })

    bucket = storage.bucket()
    blob = bucket.blob(f"{bucket_blob}/{image_id}")

    try:
        blob.delete()
    except NotFound:
        pass
    
    compressed_image = compress_image(file_image=file_image, quality=40)

    download_token = str(uuid4())

    blob.metadata = {"firebaseStorageDownloadTokens": download_token}
    blob.upload_from_file(compressed_image, content_type=file_image.content_type)

    image_url = (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/"
        f"{blob.name.replace('/', '%2F')}?alt=media&token={download_token}"
    )

    return image_url
