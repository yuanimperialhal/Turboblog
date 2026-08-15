import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings


class ImageStorageError(Exception):
    pass


def store_uploaded_image(filename, payload, content_type):
    if not settings.R2_STORAGE_ENABLED:
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (settings.UPLOAD_DIR / filename).write_bytes(payload)
        return f"/assets/uploads/{filename}"

    try:
        client = boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(
                connect_timeout=5,
                read_timeout=10,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=filename,
            Body=payload,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except (BotoCoreError, ClientError, ValueError) as error:
        raise ImageStorageError from error

    return f"{settings.R2_PUBLIC_BASE_URL}/{filename}"
