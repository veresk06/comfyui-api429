import base64
import io
import os
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

from .client import API429Error, Client

class API429GenerateImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'model': ('STRING', {'default': 'gemini-3.1-flash-image'}),
            'prompt': ('STRING', {'multiline': True, 'default': 'A ceramic mug on a light studio table, no text'}),
            'size': (['1024x1024', '1536x1024', '1024x1536', '2048x2048'],),
            'run_id': ('STRING', {'default': 'image-001'}),
            'allow_paid_generation': ('BOOLEAN', {'default': False}),
        }}

    RETURN_TYPES = ('IMAGE',)
    FUNCTION = 'generate'
    CATEGORY = 'API429'
    DESCRIPTION = 'One paid image per new run ID. Key is read from API429_API_KEY, never saved in a workflow.'

    def generate(self, model, prompt, size, run_id, allow_paid_generation):
        if not model.strip() or not prompt.strip() or size not in self.INPUT_TYPES()['required']['size'][0]:
            raise API429Error('Model, prompt and a supported size are required.')
        directory = os.environ.get('API429_STATE_DIR', str(Path.home() / '.api429-comfyui'))
        response = Client(os.environ.get('API429_API_KEY', ''), directory).generate(
            {'model': model.strip(), 'prompt': prompt, 'size': size, 'n': 1, 'response_format': 'b64_json'},
            run_id, allow_paid_generation)
        try:
            data = response['data']
            if len(data) != 1 or not isinstance(data[0].get('b64_json'), str):
                raise ValueError()
            raw = base64.b64decode(data[0]['b64_json'], validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                if image.width * image.height > 32_000_000:
                    raise ValueError()
                rgb = ImageOps.exif_transpose(image).convert('RGB')
                tensor = torch.from_numpy(np.asarray(rgb, dtype=np.float32).copy() / 255.0).unsqueeze(0)
            return (tensor,)
        except (KeyError, TypeError, ValueError, OSError, Image.DecompressionBombError):
            raise API429Error('Expected one base64 image. Original response is saved; no new generation is needed. URL-only responses are not supported in this preview.') from None
