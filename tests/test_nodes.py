import base64
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('comfyui_api429', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
import sys
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from comfyui_api429.client import Client, API429Error
from comfyui_api429.nodes import API429GenerateImage

class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.payload = {'model': 'test', 'prompt': 'test'}

    def test_no_post_without_approval(self):
        with self.assertRaises(API429Error):
            Client('test-key', self.tmp.name, transport=lambda *a: self.fail()).generate(self.payload,'one',False)

    def test_repeated_run_reuses_response_and_has_no_secret(self):
        calls=[]
        def transport(*args):
            calls.append(args[0]);return 200,{}, {'data': []}
        c=Client('test-key',self.tmp.name,transport)
        c.generate(self.payload,'one',True);c.generate(self.payload,'one',True)
        self.assertEqual(calls,['POST'])
        self.assertNotIn('test-key',next(Path(self.tmp.name).glob('*.json')).read_text())
        with self.assertRaises(API429Error):c.generate({'prompt':'changed'},'one',True)

    def test_unknown_post_is_never_repeated(self):
        calls=[]
        def transport(*args):calls.append(args[0]);raise API429Error('timeout')
        c=Client('test-key',self.tmp.name,transport)
        for _ in range(2):
            with self.assertRaises(API429Error):c.generate(self.payload,'one',True)
        self.assertEqual(calls,['POST'])

    def test_resume_async_without_post(self):
        calls=[]
        def transport(method,*args):
            calls.append(method)
            return (202,{}, {'id':'job-123'}) if method=='POST' else (200,{}, {'data':[]})
        c=Client('test-key',self.tmp.name,transport)
        with self.assertRaises(API429Error):c.generate(self.payload,'one',True,wait_seconds=0)
        self.assertEqual(c.generate(self.payload,'one',False),{'data':[]})
        self.assertEqual(calls,['POST','GET'])

    def test_foreign_poll_url_rejected(self):
        c=Client('test-key',self.tmp.name,lambda *args:(202,{}, {'result_url':'https://evil.invalid/result'}))
        with self.assertRaises(API429Error):c.generate(self.payload,'one',True)

    def test_image_is_comfy_tensor(self):
        b=io.BytesIO();Image.new('RGB',(3,2),(255,0,0)).save(b,format='PNG')
        with patch('comfyui_api429.nodes.Client.generate',return_value={'data':[{'b64_json':base64.b64encode(b.getvalue()).decode()}]}):
            image,=API429GenerateImage().generate('test','hello','1024x1024','one',True)
        self.assertEqual(tuple(image.shape),(1,2,3,3));self.assertEqual(image.dtype.__str__(),'torch.float32')
        self.assertEqual(image[0,0,0].tolist(),[1.,0.,0.])

    def test_url_only_does_not_trigger_download(self):
        with patch('comfyui_api429.nodes.Client.generate',return_value={'data':[{'url':'https://example.com/a.png'}]}):
            with self.assertRaises(API429Error):API429GenerateImage().generate('test','hello','1024x1024','one',True)

    def test_saved_workflow_has_no_key_widget(self):
        self.assertNotIn('api_key',API429GenerateImage.INPUT_TYPES()['required'])

if __name__=='__main__':unittest.main()
