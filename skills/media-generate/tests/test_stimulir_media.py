from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "helpers/stimulir_media.py"
SPEC = importlib.util.spec_from_file_location("stimulir_media", MODULE_PATH)
assert SPEC and SPEC.loader
media = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(media)


class Response:
    def __init__(self, data: bytes):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, size=-1):
        if size < 0:
            size = len(self.data)
        chunk, self.data = self.data[:size], self.data[size:]
        return chunk


class MediaClientTests(TestCase):
    def test_scoped_submit_and_status_use_deployment_identity(self):
        calls = []

        def fake_open(req, timeout):
            calls.append(req)
            return Response(json.dumps({"id": "job", "state": "queued"}).encode())

        client = media.MediaClient(
            "https://hybrie.example", "secret", "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        )
        deployment = {
            "ready": True, "model": "openweight/ACE-Step/acestep-v15-xl-turbo",
            "deployment_id": "music-1", "model_fingerprint": "fingerprint",
            "deployment_revision": "revision",
        }
        job_id = "33333333-3333-3333-3333-333333333333"
        with patch.object(media, "urlopen", fake_open):
            client.submit("audio", deployment, {"kind": "audio_generation", "prompt": "A short cue", "seconds": 10}, job_id=job_id)
            client.status("audio", job_id, "music-1")
        submitted = json.loads(calls[0].data)
        self.assertEqual(calls[0].get_method(), "PUT")
        self.assertEqual(submitted["model_fingerprint"], "fingerprint")
        self.assertEqual(submitted["kind"], "audio_generation")
        self.assertEqual(calls[0].get_header("X-hybrie-business-profile-id"), "11111111-1111-1111-1111-111111111111")
        self.assertEqual(calls[1].get_header("X-hybrie-audio-deployment-id"), "music-1")

    def test_unready_deployment_cannot_submit(self):
        client = media.MediaClient(
            "https://hybrie.example", "secret", "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        )
        with self.assertRaises(ValueError):
            client.submit("audio", {"ready": False}, {"kind": "audio_generation"},
                          job_id="33333333-3333-3333-3333-333333333333")

    def test_artifact_streams_to_destination(self):
        client = media.MediaClient(
            "https://hybrie.example", "secret", "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        )
        with TemporaryDirectory() as folder:
            destination = Path(folder) / "nested" / "clip.mp4"
            with patch.object(media, "urlopen", return_value=Response(b"video bytes")):
                result = client.artifact(
                    "video", "33333333-3333-3333-3333-333333333333", "video-1", destination
                )
            self.assertEqual(result, destination)
            self.assertEqual(destination.read_bytes(), b"video bytes")
            self.assertEqual(list(destination.parent.iterdir()), [destination])
