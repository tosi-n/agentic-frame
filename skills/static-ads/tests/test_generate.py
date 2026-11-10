from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/generate.py"
SPEC = importlib.util.spec_from_file_location("static_ads_generate", MODULE_PATH)
assert SPEC and SPEC.loader
generate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate)


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class StaticAdTests(unittest.TestCase):
    def test_request_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ad.json"
            path.write_text(json.dumps({"prompt": "A clear product ad"}))
            with patch.dict(generate.os.environ, {"STIMULIR_IMAGE_MODEL": "gpt-image-2"}):
                result = generate.load_requests(Path(folder))
            self.assertEqual(result[0][1]["model"], "gpt-image-2")
            path.write_text(json.dumps({"prompt": "A clear product ad", "model": "gemini-3-pro-image-preview", "aspect_ratio": "4:5", "image_size": "2K"}))
            self.assertEqual(generate.load_requests(Path(folder))[0][1]["aspect_ratio"], "4:5")
            path.write_text(json.dumps({"prompt": "A clear product ad", "model": "gemini-3-pro-image-preview", "quality": "high"}))
            with self.assertRaises(ValueError):
                generate.load_requests(Path(folder))
            path.write_text(json.dumps({"prompt": "A clear product ad", "input_urls": ["https://example.com"]}))
            with self.assertRaises(ValueError):
                generate.load_requests(Path(folder))

    def test_generation_uses_project_scope_and_decodes_image(self):
        png = b"\x89PNG\r\n\x1a\n" + b"fixture"
        body = {"data": [{"mime_type": "image/png", "b64_json": base64.b64encode(png).decode()}]}
        calls = []

        def fake_open(request, timeout):
            calls.append(request)
            response = Response()
            response.read = lambda: json.dumps(body).encode()
            return response

        with patch.dict(generate.os.environ, {
            "STIMULIR_API_KEY": "test-key",
            "STIMULIR_PROJECT_ID": "project-1",
            "STIMULIR_API_BASE": "https://stimulir.example",
        }), patch.object(generate.request, "urlopen", fake_open):
            result, mime = generate.generate({"model": "gpt-image-2", "prompt": "An ad"})
        self.assertEqual((result, mime), (png, "image/png"))
        self.assertEqual(calls[0].get_header("X-project-id"), "project-1")
        self.assertEqual(calls[0].full_url, "https://stimulir.example/api/v1/inference/images/generations")


if __name__ == "__main__":
    unittest.main()
