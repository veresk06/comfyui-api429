# API429 for ComfyUI

Generate product photos, creative variations and image batches in ComfyUI through API429. Ready-to-import workflows for **Nano Banana, FLUX.2 Pro and GPT Image** connect remote generation to your existing IMAGE pipeline—without downloading model weights or running inference on your GPU.

Use one API429 account to generate from text, edit a reference image, process a prompt list and inspect current public image prices. API usage is paid; model access and prices depend on the selected model and your account.

![Actual Nano Banana output from the macOS integration test](example_workflows/generate-image.jpg)

[Comfy Registry](https://registry.comfy.org/ru/publishers/api429/nodes/comfyui-api429) · [Пошаговый гайд на русском](https://api429.com/blog/comfyui-nano-banana-api429-workflow)

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

## Ready-to-use workflows

| Workflow | What it does |
| --- | --- |
| `nano-banana.json` | Nano Banana 2 text-to-image → Save Image |
| `flux-2-pro.json` | FLUX.2 Pro text-to-image → Save Image |
| `gpt-image.json` | GPT Image 2 with selectable quality → Save Image |
| `edit-reference.json` | Load one reference → edit by prompt → Save Image |
| `image-queue.json` | One prompt per line → sequential generation → Save Image |
| `current-prices.json` | Current public output-image rates × quantity → Preview as Text |

All files are in `example_workflows/`. Paid generation is disabled by default. The original `generate-image.json` remains compatible. For product catalogs, use a reference edit to vary a scene; for multiple concepts, use the queue. Check each result before using it commercially: likeness, text and product details may change.

### Queue and pricing

`max_images` limits the number of prompts (up to 100), **not the amount charged**. Each request gets its own run ID and saved response. If a later prompt fails, keep the same batch ID and unchanged prompt list to reuse completed requests. PNG files reach Save Image when the whole queue completes; partial results remain in the private state store until recovery.

The price workflow reads the public catalog without a key and shows all per-image pricing conditions. Increment `refresh_id` to refresh. Choose the condition matching resolution, quality and references. Input tokens and other operations can add charges. This is an estimate, not a prepaid quote or an enforced budget. Preview as Text requires a recent ComfyUI release.

### Verified scope

Live-tested on macOS with ComfyUI 0.35.0: Nano Banana 2 (`gemini-3.1-flash-image`) returned one 1024×1024 image through this node and Save Image on 11 September 2026. **FLUX, GPT Image, reference editing and queue behavior have local tests only; no new paid verification was performed for version 0.2.0.** Catalog capabilities are not proof that every key supports every setting.

This version supports one reference per edit, text-to-image, sequential queues and base64 image responses. Video, masks, multiple references and URL-only result downloads are not implemented. Unsupported responses are retained for recovery. Only run trusted workflows: imported workflows can enable paid nodes.

[Get an API429 key](https://api429.com/?utm_source=github&utm_medium=integration&utm_campaign=comfyui) · [API429 models and rates](https://api429.com/en/models) · [API documentation](https://api429.com/en/docs) · [ComfyUI node API](https://docs.comfy.org/custom-nodes/backend/server_overview)

## По-русски

**Изображения для карточек товаров, рекламные вариации и серии генераций — прямо в ComfyUI через API429.** Не нужно скачивать веса моделей: генерация выполняется через API, а результат поступает в стандартный IMAGE и Save Image.

В пакете четыре узла и готовые сценарии для Nano Banana, FLUX.2 Pro, GPT Image, редактирования одного референса, очереди промптов и расчёта стоимости изображений по текущему публичному каталогу. Сравнивайте тарифы с учётом размера, качества и дополнительных расходов.

Ключ задаётся через `API429_API_KEY` в окружении сервера и не попадает в workflow. Для новой генерации задайте новый `run_id`, для восстановления сохраняйте ID и параметры. Очередь сохраняет ответы последовательно; ограничение количества не является денежным лимитом.

Живой тест подтверждён для Nano Banana 2. Новые сценарии проверены локально без платных вызовов. Видео в эту версию не входит.

[Получить ключ API429](https://api429.com/?utm_source=github&utm_medium=integration&utm_campaign=comfyui) · [Инструкция](https://api429.com/blog/comfyui-nano-banana-api429-workflow)
