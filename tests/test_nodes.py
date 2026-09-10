import base64
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "comfyui_api429", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
)
import sys

package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from comfyui_api429.client import API429Error, Client
from comfyui_api429.nodes import API429GenerateImage


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.payload = {"model": "test", "prompt": "test"}

    def test_no_post_without_approval(self):
        with self.assertRaises(API429Error):
            Client(
                "test-key", self.tmp.name, transport=lambda *a: self.fail()
            ).generate(self.payload, "one", False)

    def test_repeated_run_reuses_response_and_has_no_secret(self):
        calls = []

        def transport(*args):
            calls.append(args[0])
            return 200, {}, {"data": []}

        c = Client("test-key", self.tmp.name, transport)
        c.generate(self.payload, "one", True)
        c.generate(self.payload, "one", True)
        self.assertEqual(calls, ["POST"])
        self.assertNotIn(
            "test-key", next(Path(self.tmp.name).glob("*.json")).read_text()
        )
        with self.assertRaises(API429Error):
            c.generate({"prompt": "changed"}, "one", True)

    def test_unknown_post_is_never_repeated(self):
        calls = []

        def transport(*args):
            calls.append(args[0])
            raise API429Error("timeout")

        c = Client("test-key", self.tmp.name, transport)
        for _ in range(2):
            with self.assertRaises(API429Error):
                c.generate(self.payload, "one", True)
        self.assertEqual(calls, ["POST"])

    def test_resume_async_without_post(self):
        calls = []

        def transport(method, *args):
            calls.append(method)
            return (
                (202, {}, {"id": "job-123"})
                if method == "POST"
                else (200, {}, {"data": []})
            )

        c = Client("test-key", self.tmp.name, transport)
        with self.assertRaises(API429Error):
            c.generate(self.payload, "one", True, wait_seconds=0)
        self.assertEqual(c.generate(self.payload, "one", False), {"data": []})
        self.assertEqual(calls, ["POST", "GET"])

    def test_foreign_poll_url_rejected(self):
        c = Client(
            "test-key",
            self.tmp.name,
            lambda *args: (202, {}, {"result_url": "https://evil.invalid/result"}),
        )
        with self.assertRaises(API429Error):
            c.generate(self.payload, "one", True)

    def test_image_is_comfy_tensor(self):
        b = io.BytesIO()
        Image.new("RGB", (3, 2), (255, 0, 0)).save(b, format="PNG")
        with patch(
            "comfyui_api429.nodes.Client.generate",
            return_value={
                "data": [{"b64_json": base64.b64encode(b.getvalue()).decode()}]
            },
        ):
            (image,) = API429GenerateImage().generate(
                "test", "hello", "1024x1024", "one", True
            )
        self.assertEqual(tuple(image.shape), (1, 2, 3, 3))
        self.assertEqual(image.dtype.__str__(), "torch.float32")
        self.assertEqual(image[0, 0, 0].tolist(), [1.0, 0.0, 0.0])

    def test_url_only_does_not_trigger_download(self):
        with (
            patch(
                "comfyui_api429.nodes.Client.generate",
                return_value={"data": [{"url": "https://example.com/a.png"}]},
            ),
            self.assertRaises(API429Error),
        ):
            API429GenerateImage().generate("test", "hello", "1024x1024", "one", True)

    def test_saved_workflow_has_no_key_widget(self):
        self.assertNotIn("api_key", API429GenerateImage.INPUT_TYPES()["required"])


class ExpandedNodeTests(unittest.TestCase):
    def test_queue_resumes_partial_results_without_reposting(self):
        from comfyui_api429.nodes import API429ImageQueue

        calls = []
        buffer = io.BytesIO()
        Image.new("RGB", (2, 2)).save(buffer, format="PNG")
        response = {
            "data": [{"b64_json": base64.b64encode(buffer.getvalue()).decode()}]
        }

        def transport(method, path, key, payload=None):
            calls.append(payload["prompt"])
            return 200, {}, response

        with tempfile.TemporaryDirectory() as directory:
            client = Client("test", directory, transport)
            with patch("comfyui_api429.nodes.Client", return_value=client):
                node = API429ImageQueue()
                node.generate_queue("test", "first", "1024x1024", "batch", 2, True)
                outputs = node.generate_queue(
                    "test", "first\nsecond", "1024x1024", "batch", 2, True
                )
                self.assertEqual(len(outputs[0]), 2)
        self.assertEqual(calls, ["first", "second"])

    def test_queue_limit_rejects_before_client_call(self):
        from comfyui_api429.nodes import API429ImageQueue

        with patch("comfyui_api429.nodes.Client") as client:
            with self.assertRaises(API429Error):
                API429ImageQueue().generate_queue(
                    "test", "a\nb", "1024x1024", "batch", 1, True
                )
            client.assert_not_called()

    def test_edit_encodes_reference_and_binds_endpoint(self):
        import torch
        from comfyui_api429.nodes import API429EditImage

        with (
            patch("comfyui_api429.nodes.Client") as factory,
            patch("comfyui_api429.nodes.decode_image", return_value=("output",)),
        ):
            result = API429EditImage().edit(
                "test",
                "change background",
                "1024x1024",
                "edit",
                True,
                torch.ones((1, 2, 3, 3)),
            )
            args = factory.return_value.generate.call_args
            self.assertEqual(args.kwargs["endpoint"], "/v1/images/edits")
            im = Image.open(io.BytesIO(base64.b64decode(args.args[0]["_image_b64"])))
            self.assertEqual(im.size, (3, 2))
            self.assertEqual(result, ("output",))

    def test_edit_receipt_cannot_be_reused_for_other_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Client("test", directory, lambda *args: (200, {}, {"data": []}))
            client.generate(
                {"_image_b64": "original"}, "edit", True, endpoint="/v1/images/edits"
            )
            with self.assertRaises(API429Error):
                client.generate(
                    {"_image_b64": "changed"}, "edit", True, endpoint="/v1/images/edits"
                )


if __name__ == "__main__":
    unittest.main()


class TransportTests(unittest.TestCase):
    def test_edit_multipart_matches_upload_contract(self):
        from unittest.mock import MagicMock

        from comfyui_api429.client import request

        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"data":[]}'
        response.status = 200
        response.headers = {}
        with patch("urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = response
            request(
                "POST",
                "/v1/images/edits",
                "fake-test-key",
                {
                    "model": "gpt-image-2",
                    "prompt": "Blue background",
                    "_image_b64": base64.b64encode(b"PNG bytes").decode(),
                },
            )
            req = opener.return_value.open.call_args.args[0]
            self.assertIn(
                "multipart/form-data; boundary=", req.get_header("Content-type")
            )
            self.assertIn(b'name="image"; filename="reference.png"', req.data)
            self.assertIn(b"PNG bytes", req.data)
            self.assertNotIn(b"fake-test-key", req.data)
            self.assertNotIn(b"_image_b64", req.data)

    def test_price_quote_keeps_conditions_and_totals(self):
        import json
        from unittest.mock import MagicMock

        from comfyui_api429.nodes import API429PriceQuote

        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {
                "generated_at": "test-date",
                "models": [
                    {
                        "id": "FLUX.2-pro",
                        "pricing": {
                            "rates": [
                                {
                                    "metric": "image",
                                    "amount": "0.009",
                                    "per": 1,
                                    "condition": "output_mp=1;reference_mp=0",
                                }
                            ]
                        },
                    }
                ],
            }
        ).encode()
        with patch("urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = response
            result = API429PriceQuote().quote("FLUX.2-pro", 100, 0)["result"][0]
            self.assertIn("output_mp=1;reference_mp=0", result)
            self.assertIn("$0.900", result)
            self.assertIn("not a spending limit", result)
