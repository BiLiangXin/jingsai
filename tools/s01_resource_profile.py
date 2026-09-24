"""SYNTHETIC_ONLY_RESOURCE_PROFILE. No dataset loader or predictive metrics."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import torch
from mosei.s01.contracts import ARCHITECTURES, configure_runtime, synthetic_batch
from mosei.s01.engine import optimizer_step
from mosei.s01.models import R01Model, parameter_count
from mosei.s01.protocol import ValidationLibrary, train_availability


def sync(device):
    if device == "cuda":
        torch.cuda.synchronize()


def environment():
    result = dict(python=platform.python_version(), pytorch=torch.__version__,
                  cuda_runtime=torch.version.cuda, cudnn=torch.backends.cudnn.version(),
                  cuda_available=torch.cuda.is_available(), gpu_count=torch.cuda.device_count(),
                  platform=platform.system(), torch_num_threads=torch.get_num_threads(), gpus=[])
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        result["gpus"].append(dict(index=i, name=p.name, total_vram_bytes=p.total_memory,
                                   compute_capability=[p.major, p.minor]))
    if os.name == "nt":
        script = "@{cpu=(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors); ram_bytes=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory} | ConvertTo-Json -Depth 4 -Compress"
        info = subprocess.check_output(["powershell", "-NoProfile", "-Command", script], text=True)
        result.update(json.loads(info))
    disk = shutil.disk_usage(ROOT)
    result["workspace_volume_free_bytes"] = disk.free
    result["deterministic_algorithms"] = torch.are_deterministic_algorithms_enabled()
    result["cudnn_benchmark"] = torch.backends.cudnn.benchmark
    result["tf32_matmul"] = torch.backends.cuda.matmul.allow_tf32
    return result


def measure(architecture, batch_size, device, repeats=10):
    batch = synthetic_batch(batch_size, 9001, dense=True).to(device)
    model = R01Model(architecture, 17).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
    for _ in range(3):
        optimizer_step(model, optimizer, batch)
    sync(device)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    times = []
    for _ in range(repeats):
        sync(device); start = time.perf_counter()
        optimizer_step(model, optimizer, batch)
        sync(device); times.append(time.perf_counter() - start)
    peak = torch.cuda.max_memory_allocated() if device == "cuda" else None
    reserved = torch.cuda.max_memory_reserved() if device == "cuda" else None
    forwards = []
    with torch.no_grad():
        model.eval()
        for _ in range(repeats):
            sync(device); start = time.perf_counter()
            model(batch.inputs())
            sync(device); forwards.append(time.perf_counter() - start)
    value = dict(architecture=architecture, batch_size=batch_size, status="PASS", device=device,
                 warmup_steps=3, measured_steps=repeats, support_positions=50, dtype="float32",
                 step_seconds=times, step_median_seconds=statistics.median(times),
                 step_max_seconds=max(times), forward_seconds=forwards,
                 forward_median_seconds=statistics.median(forwards), forward_max_seconds=max(forwards),
                 throughput_samples_per_second=batch_size / statistics.median(times),
                 peak_allocated_bytes=peak, peak_reserved_bytes=reserved, parameters=parameter_count(model),
                 loss_and_gradients_finite=True, predictive_metrics=None)
    del optimizer, model, batch
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    return value


def profile(output):
    configure_runtime()
    def fingerprints():
        files = list((ROOT / "src/mosei/s01").glob("*.py")) + [Path(__file__), ROOT / "research/r01/reference.py"]
        return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    source_before = fingerprints()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    value = dict(kind="SYNTHETIC_ONLY_RESOURCE_PROFILE", classification="NOT_MODEL_EXPERIMENT",
                 predictive_metrics=None, label="NO_PREDICTIVE_METRICS", environment=environment(),
                 synchronization="torch.cuda.synchronize before/after perf_counter region; synchronous CPU calls",
                 official_data_loaded=False, samples=[], oom_boundary=None, training_authorized=False,
                 batch_sweep_scope="8,16,32,64,128,256 for temporal gate/capacity models; bounded search, not hardware maximum")
    if device == "cuda":
        free, total = torch.cuda.mem_get_info()
        value["initial_cuda_memory"] = dict(free_bytes=free, total_bytes=total)
    for architecture in ("B-T", "B-A", "B-V", "B-CAT", "C0", "R0", "R1", "R2", "R1-CAP"):
        sizes = (8, 16, 32, 64, 128, 256) if architecture in ("R2", "R1-CAP") else (32,)
        for batch_size in sizes:
            try:
                result = measure(architecture, batch_size, device)
            except torch.cuda.OutOfMemoryError:
                result = dict(architecture=architecture, batch_size=batch_size, device=device, status="OOM")
                value["oom_boundary"] = dict(architecture=architecture, first_observed_oom_batch=batch_size)
                gc.collect(); torch.cuda.empty_cache()
            value["samples"].append(result)
            print(json.dumps({k: result.get(k) for k in ("architecture", "batch_size", "status", "step_median_seconds", "peak_allocated_bytes")}), flush=True)
            output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
            if result["status"] != "PASS":
                break
    batch = synthetic_batch(32, 2207, dense=True)
    costs = []
    for epoch in range(5):
        start = time.perf_counter(); train_availability(batch, 17, epoch)
        costs.append(time.perf_counter() - start)
    small = synthetic_batch(8, 1103, dense=True)
    start = time.perf_counter(); library = ValidationLibrary(small)
    value["cpu_mask_profile"] = dict(train_batch32_seconds=costs,
                                      valid_library_8_samples_seconds=time.perf_counter() - start,
                                      conditions=len(library.views), views=sum(map(len, library.views.values())))
    # Keep frozen training batch32; larger profiles measure headroom, not a new optimization search.
    value["recommended_training_batch"] = 32
    value["max_tested_safe_batch"] = min(max(r["batch_size"] for r in value["samples"]
                                           if r["architecture"] == a and r["status"] == "PASS") for a in ("R2", "R1-CAP"))
    value["physical_max_safe_batch"] = "UNKNOWN; no claim beyond bounded tested sizes"
    value["status"] = "SYNTHETIC_ONLY_COMPLETED"
    value["source_sha256"] = source_before
    value["source_unchanged_during_measurement"] = source_before == fingerprints()
    if not value["source_unchanged_during_measurement"]:
        raise ValueError("Profiling source changed during measurement")
    value["command"] = "python -B -X utf8 tools/s01_resource_profile.py --output " + output.relative_to(ROOT).as_posix() if output.is_absolute() else "python -B -X utf8 tools/s01_resource_profile.py --output " + output.as_posix()
    value["exit_code"] = 0
    output.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return value


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError("Preserve existing profile; use a fresh output path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    profile(args.output)
