import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from botocore.exceptions import EndpointConnectionError
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings

from blog.models import SiteSetting


TEST_IMAGE_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAFgwJ/lkXc5QAAAABJRU5ErkJggg=="
)


def upload_image(client, name="test.png"):
    return client.post(
        "/api/uploads",
        data=json.dumps(
            {
                "name": name,
                "type": "image/png",
                "data": base64.b64encode(TEST_IMAGE_BYTES).decode("ascii"),
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer test-admin-token",
    )


class DatabaseConfigurationTests(SimpleTestCase):
    def test_database_url_selects_postgresql_backend(self):
        environment = os.environ.copy()
        environment.update(
            {
                "DATABASE_URL": "postgresql://blog_user:secret@db.example.com:5432/turboblog?sslmode=require",
                "DJANGO_SETTINGS_MODULE": "turboblog.settings",
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json; import django; django.setup(); "
                    "from django.conf import settings; "
                    "print(json.dumps(settings.DATABASES['default']))"
                ),
            ],
            cwd=Path(__file__).resolve().parent.parent,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        database = json.loads(result.stdout)

        self.assertEqual(database["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(database["HOST"], "db.example.com")
        self.assertEqual(database["NAME"], "turboblog")
        self.assertEqual(database["OPTIONS"]["sslmode"], "require")

    def test_required_database_url_rejects_sqlite_fallback(self):
        environment = os.environ.copy()
        environment.update(
            {
                "DATABASE_URL": "",
                "REQUIRE_DATABASE_URL": "1",
                "DJANGO_SETTINGS_MODULE": "turboblog.settings",
                "R2_STORAGE_ENABLED": "0",
            }
        )
        result = subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            cwd=Path(__file__).resolve().parent.parent,
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "REQUIRE_DATABASE_URL=1 requires DATABASE_URL",
            result.stderr,
        )


class UploadPersistenceTests(SimpleTestCase):
    def test_uploaded_image_is_served_from_configured_upload_dir(self):
        with tempfile.TemporaryDirectory() as upload_dir, override_settings(
            ADMIN_TOKEN="test-admin-token",
            UPLOAD_DIR=Path(upload_dir),
            R2_STORAGE_ENABLED=False,
        ):
            client = Client()
            upload_response = upload_image(client, "persistent.png")

            self.assertEqual(upload_response.status_code, 201)
            image_url = upload_response.json()["image"]["url"]
            image_response = client.get(image_url)

            self.assertEqual(image_response.status_code, 200)
            self.assertEqual(b"".join(image_response.streaming_content), TEST_IMAGE_BYTES)


class R2UploadTests(SimpleTestCase):
    r2_settings = {
        "ADMIN_TOKEN": "test-admin-token",
        "R2_STORAGE_ENABLED": True,
        "R2_ENDPOINT_URL": "https://account-id.r2.cloudflarestorage.com",
        "R2_ACCESS_KEY_ID": "test-access-key",
        "R2_SECRET_ACCESS_KEY": "test-secret-key",
        "R2_BUCKET_NAME": "turboblog-uploads",
        "R2_PUBLIC_BASE_URL": "https://images.example.com",
    }

    def test_uploaded_image_is_stored_in_r2_and_returns_public_url(self):
        r2_client = MagicMock()

        with override_settings(**self.r2_settings), patch(
            "boto3.client", return_value=r2_client
        ):
            response = upload_image(Client(), "cloud image.png")

        self.assertEqual(response.status_code, 201)
        image = response.json()["image"]
        self.assertTrue(image["url"].startswith("https://images.example.com/"))
        r2_client.put_object.assert_called_once()
        upload = r2_client.put_object.call_args.kwargs
        self.assertEqual(upload["Bucket"], "turboblog-uploads")
        self.assertEqual(upload["Body"], TEST_IMAGE_BYTES)
        self.assertEqual(upload["ContentType"], "image/png")
        self.assertTrue(upload["Key"].endswith("-cloud-image.png"))

    def test_r2_failure_returns_service_unavailable_error(self):
        r2_client = MagicMock()
        r2_client.put_object.side_effect = EndpointConnectionError(
            endpoint_url=self.r2_settings["R2_ENDPOINT_URL"]
        )

        with override_settings(**self.r2_settings), patch(
            "boto3.client", return_value=r2_client
        ):
            response = upload_image(Client())

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"],
            "Object storage is temporarily unavailable.",
        )

    def test_invalid_r2_client_configuration_returns_service_unavailable_error(self):
        with override_settings(**self.r2_settings), patch(
            "boto3.client", side_effect=ValueError("Invalid endpoint URL")
        ):
            response = upload_image(Client(raise_request_exception=False))

        self.assertEqual(response.status_code, 502)


class RailwayBucketUploadTests(SimpleTestCase):
    private_storage_settings = {
        "ADMIN_TOKEN": "test-admin-token",
        "OBJECT_STORAGE_ENABLED": True,
        "OBJECT_STORAGE_ENDPOINT_URL": "https://s3.us-west-2.railway.app",
        "OBJECT_STORAGE_ACCESS_KEY_ID": "test-access-key",
        "OBJECT_STORAGE_SECRET_ACCESS_KEY": "test-secret-key",
        "OBJECT_STORAGE_BUCKET_NAME": "railway-uploads",
        "OBJECT_STORAGE_REGION": "us-west-2",
        "OBJECT_STORAGE_PUBLIC_BASE_URL": "",
    }

    def test_private_bucket_upload_uses_stable_url_and_redirects_to_presigned_download(self):
        storage_client = MagicMock()
        storage_client.generate_presigned_url.return_value = (
            "https://s3.us-west-2.railway.app/railway-uploads/signed-image"
        )

        with override_settings(**self.private_storage_settings), patch(
            "boto3.client", return_value=storage_client
        ):
            client = Client()
            upload_response = upload_image(client, "private image.png")

            self.assertEqual(upload_response.status_code, 201)
            image_url = upload_response.json()["image"]["url"]
            self.assertTrue(image_url.startswith("/assets/uploads/"))

            download_response = client.get(image_url)

        self.assertEqual(download_response.status_code, 302)
        self.assertEqual(
            download_response["Location"],
            "https://s3.us-west-2.railway.app/railway-uploads/signed-image",
        )

    def test_private_bucket_download_failure_returns_service_unavailable_error(self):
        storage_client = MagicMock()
        storage_client.generate_presigned_url.side_effect = ValueError("Invalid endpoint URL")

        with override_settings(**self.private_storage_settings), patch(
            "boto3.client", return_value=storage_client
        ):
            response = Client(raise_request_exception=False).get(
                "/assets/uploads/private-image.png"
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"],
            "Object storage is temporarily unavailable.",
        )


class RenderPublicUrlTests(TestCase):
    def test_seed_uses_render_external_hostname_for_public_url(self):
        with patch.dict(
            os.environ,
            {"RENDER_EXTERNAL_HOSTNAME": "turboblog-example.onrender.com"},
            clear=False,
        ):
            call_command("seed_initial_data", verbosity=0)

        self.assertEqual(
            SiteSetting.objects.get(pk=1).public_url,
            "https://turboblog-example.onrender.com",
        )

    def test_seed_preserves_existing_site_settings(self):
        SiteSetting.objects.create(
            pk=1,
            title="Custom title",
            description="Custom description",
            public_url="https://blog.example.com",
        )

        with patch.dict(
            os.environ,
            {"RENDER_EXTERNAL_HOSTNAME": "turboblog-example.onrender.com"},
            clear=False,
        ):
            call_command("seed_initial_data", verbosity=0)

        site = SiteSetting.objects.get(pk=1)
        self.assertEqual(site.title, "Custom title")
        self.assertEqual(site.description, "Custom description")
        self.assertEqual(site.public_url, "https://blog.example.com")
