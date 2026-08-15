import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings


class ImageStorageError(Exception):
    pass


def object_storage_settings():
    if settings.OBJECT_STORAGE_ENABLED:
        return {
            "enabled": True,
            "endpoint_url": settings.OBJECT_STORAGE_ENDPOINT_URL,
            "access_key_id": settings.OBJECT_STORAGE_ACCESS_KEY_ID,
            "secret_access_key": settings.OBJECT_STORAGE_SECRET_ACCESS_KEY,
            "bucket_name": settings.OBJECT_STORAGE_BUCKET_NAME,
            "region": settings.OBJECT_STORAGE_REGION,
            "public_base_url": settings.OBJECT_STORAGE_PUBLIC_BASE_URL,
        }
    if settings.R2_STORAGE_ENABLED:
        return {
            "enabled": True,
            "endpoint_url": settings.R2_ENDPOINT_URL,
            "access_key_id": settings.R2_ACCESS_KEY_ID,
            "secret_access_key": settings.R2_SECRET_ACCESS_KEY,
            "bucket_name": settings.R2_BUCKET_NAME,
            "region": "auto",
            "public_base_url": settings.R2_PUBLIC_BASE_URL,
        }
    return {"enabled": False}


def object_storage_client(config):
    return boto3.client(
        "s3",
        endpoint_url=config["endpoint_url"],
        aws_access_key_id=config["access_key_id"],
        aws_secret_access_key=config["secret_access_key"],
        region_name=config["region"],
        config=Config(
            connect_timeout=5,
            read_timeout=10,
            retries={"max_attempts": 2, "mode": "standard"},
            s3={"addressing_style": "virtual"},
        ),
    )


def store_uploaded_image(filename, payload, content_type):
    config = object_storage_settings()
    if not config["enabled"]:
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (settings.UPLOAD_DIR / filename).write_bytes(payload)
        return f"/assets/uploads/{filename}"

    try:
        client = object_storage_client(config)
        client.put_object(
            Bucket=config["bucket_name"],
            Key=filename,
            Body=payload,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except (BotoCoreError, ClientError, ValueError) as error:
        raise ImageStorageError from error

    if config["public_base_url"]:
        return f"{config['public_base_url']}/{filename}"
    return f"/assets/uploads/{filename}"


def create_uploaded_image_download_url(filename):
    config = object_storage_settings()
    try:
        return object_storage_client(config).generate_presigned_url(
            "get_object",
            Params={"Bucket": config["bucket_name"], "Key": filename},
            ExpiresIn=300,
        )
    except (BotoCoreError, ClientError, ValueError) as error:
        raise ImageStorageError from error
