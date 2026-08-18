# Vast GPU install plan

This plan is intentionally blocked until real workflow exports, weight filenames, download sources, and custom-node requirements are supplied. Do not replace UNKNOWN values with guesses.

## 1. Vast instance requirements

- Select a CUDA-capable NVIDIA instance only after the workflow/model VRAM requirements are known.
- Required VRAM, system RAM, disk capacity, and GPU model: **UNKNOWN / DECISION REQUIRED**.
- Persistent storage is recommended because model files may be large; the exact size is currently **UNKNOWN**.

## 2. Ubuntu, CUDA, and Python requirements

- Exact Ubuntu, CUDA, PyTorch, and Python compatibility must come from the selected model/workflow documentation.
- Current repository Python packages are listed in `requirements.txt`; they do not install ComfyUI or GPU PyTorch.
- Run the structured preflight after installation to verify `nvidia-smi`, CUDA, PyTorch CUDA, ffmpeg, and ffprobe.

## 3. Clone the repository

Clone the approved repository and check out the reviewed commit. No repository URL is embedded here because deployment ownership and target remote must be confirmed.

## 4. Install Python dependencies

Create an isolated environment and install the reviewed application dependencies. Install the GPU-compatible PyTorch build only after CUDA compatibility is decided.

## 5. Install ComfyUI

ComfyUI source/version and installation path are **DECISION REQUIRED**. Set `COMFYUI_PATH` after installation.

## 6. Install custom nodes

Read `configs/comfy_custom_nodes.json`. Its status is currently `UNKNOWN`; do not install guessed repositories or execute guessed commands.

## 7. Download models

Run `python scripts/download_models.py --dry-run`. It must fail with `download source missing` until verified sources, filenames, destinations, and checksums are added to `configs/model_manifest.json`.

## 8. Place weights at verified paths

Use only `expected_weight_files` and `expected_paths` from the reviewed model manifest. They are currently unknown. Add checksums before real download/install.

## 9. Copy workflows

Place exported ComfyUI API JSON files in `workflows/` using each service's `expected_filename`. Only Motion currently has an evidenced expected filename: `wan_animate_2_api.json`. Do not create placeholder workflows.

## 10. Run preflight

Set `COMFYUI_PATH`, `COMFYUI_INPUT_DIR`, and `COMFYUI_OUTPUT_DIR`, then call the admin-only Railway endpoint `/api/health/preflight` or execute `runtime_readiness.runtime_preflight()` locally.

## 11. Start ComfyUI

Start it using the command supported by the selected, pinned ComfyUI version. Command and flags are **DECISION REQUIRED**.

## 12. Start the GPU worker

The current `worker_comfyui.py` is a skeleton and must not be treated as production-ready until real node mappings and response handling are implemented.

## 13. Register the worker with Railway

Configure server-side worker URL/token variables and heartbeat authentication. Never expose worker tokens to the browser.

## 14. Run smoke tests

Verify health, heartbeat, claim/submit, status normalization, timeout, refund-once behavior, and rejection of input/demo output without running a paid production job first.

## 15. Run one real test job

After all manifests and preflight report ready, run one controlled job per service and validate media type, output uniqueness, History visibility, credit charge once, and failure refund once.
