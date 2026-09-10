# API429 for ComfyUI

One API image-generation node for ComfyUI, with durable result reuse and async-job resume. Outputs a standard `IMAGE` tensor for Save Image or downstream nodes. Uses ComfyUI's supported V1 custom-node interface.

![Actual Nano Banana output from the macOS integration test](example_workflows/generate-image.jpg)

## Install

Clone `https://github.com/veresk06/comfyui-api429.git` or copy this entire folder into `ComfyUI/custom_nodes/comfyui-api429`. In the Python environment used by ComfyUI, install `requirements.txt`, then restart ComfyUI.

Set `API429_API_KEY` in the **server process environment** before starting ComfyUI. Do not put the key in a workflow, prompt, screenshot or public repository. For portable Windows installations set the variable in the launcher environment; use the bundled Python for dependencies.

Import `example_workflows/generate-image.json`. Select an exact model ID accessible to your key (`GET /v1/models`), prompt and supported size. Default: Nano Banana 2 `gemini-3.1-flash-image`, 1024×1024. Enable `allow_paid_generation` only when ready to spend credits, then Queue. Each new run ID creates at most one POST from this local state store.

## Reuse and recovery

- Same run ID + same parameters: reuses the saved response or resumes polling the existing job.
- New image: deliberately choose a new unique run ID. This is a billing identity, **not a seed** and not provider-side idempotency.
- A timeout before receiving a job ID blocks automatic resubmission. Check account history/support before making another run ID.
- A crash may leave a `.lock`; reconcile that run before manually removing it. Never delete the state folder as a retry mechanism.
- State lives in `~/.api429-comfyui` (override with `API429_STATE_DIR`). It contains responses/images; protect it and preserve it across restarts. Keys are not stored. Use one persistent state store per ComfyUI installation; another machine/store can submit another request.
- Polling follows only the API429 `/v1/balancer/jobs/{id}/result` route. It never sends your key to an image host or a redirect.

## Preview scope

Text-to-image, one result per run, base64 image response. Models and sizes are not guaranteed for every key. No image editing, URL-only image downloads, video, automatic POST retries, or claims of complete model compatibility. An unsupported response is retained for recovery instead of generating again. Only run trusted workflows on your ComfyUI server: imported workflows can enable paid nodes.

Offline tests exercise paid-call prevention, result reuse, unknown-outcome handling, async resume, polling URL validation and real Torch image tensors. Live-tested on macOS with ComfyUI 0.35.0: `gemini-3.1-flash-image` returned one 1024×1024 image through this node and Save Image on 11 September 2026. Other models are not certified by this test. Registry availability is tracked separately.

[Get an API429 key](https://api429.com/?utm_source=github&utm_medium=integration&utm_campaign=comfyui) · [API429 models and rates](https://api429.com/en/models) · [API documentation](https://api429.com/en/docs) · [ComfyUI node API](https://docs.comfy.org/custom-nodes/backend/server_overview)

## По-русски

Скопируйте папку в `ComfyUI/custom_nodes/comfyui-api429`, установите зависимости в Python самого ComfyUI и перезапустите его. Ключ задайте через переменную окружения `API429_API_KEY` на сервере.

Импортируйте `example_workflows/generate-image.json`: узел API429 соединён с Save Image. Проверьте модель и размер, затем включите разрешение платной генерации. Один новый `run_id` соответствует одному запросу. Для восстановления оставляйте тот же ID и параметры; для новой картинки задавайте новый ID намеренно. При неизвестном исходе сначала проверьте историю API429. Папка состояния содержит изображения, но не ключ.

Это предварительная интеграция генерации по тексту, не подтверждение поддержки всех моделей или публикации в Comfy Registry.
