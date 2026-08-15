import base64
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings

from blog.models import SiteSetting


class UploadPersistenceTests(SimpleTestCase):
    def test_uploaded_image_is_served_from_configured_upload_dir(self):
        image_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
            "AAAADUlEQVR42mP8z8BQDwAFgwJ/lkXc5QAAAABJRU5ErkJggg=="
        )

        with tempfile.TemporaryDirectory() as upload_dir, override_settings(
            ADMIN_TOKEN="test-admin-token",
            UPLOAD_DIR=Path(upload_dir),
        ):
            client = Client()
            upload_response = client.post(
                "/api/uploads",
                data=json.dumps(
                    {
                        "name": "persistent.png",
                        "type": "image/png",
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    }
                ),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-admin-token",
            )

            self.assertEqual(upload_response.status_code, 201)
            image_url = upload_response.json()["image"]["url"]
            image_response = client.get(image_url)

            self.assertEqual(image_response.status_code, 200)
            self.assertEqual(b"".join(image_response.streaming_content), image_bytes)


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
