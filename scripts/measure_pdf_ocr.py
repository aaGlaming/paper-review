"""Measure one RapidOCR pass on a rendered PDF page; this is not upload-path code."""

from __future__ import annotations

import argparse
import ctypes
import threading
import time
from pathlib import Path
from ctypes import wintypes


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def _rss_bytes() -> int:
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    process = kernel32.GetCurrentProcess()
    ok = psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb)
    if not ok:
        raise ctypes.WinError()
    return counters.WorkingSetSize


class _PeakRss:
    def __init__(self) -> None:
        self.peak = _rss_bytes()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, _rss_bytes())
            self._stop.wait(0.01)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._stop.set()
        self._thread.join()
        self.peak = max(self.peak, _rss_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path, help="200 dpi PNG rendered from one PDF page")
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"image does not exist: {args.image}")

    rss_before = _rss_bytes()
    with _PeakRss() as memory:
        started = time.perf_counter()
        from rapidocr_onnxruntime import RapidOCR

        engine = RapidOCR()
        initialized = time.perf_counter()
        result, _elapsed = engine(str(args.image))
        finished = time.perf_counter()

    text = "\n".join(str(line[1]) for line in (result or []))
    print(f"image_bytes={args.image.stat().st_size}")
    print(f"ocr_init_seconds={initialized - started:.6f}")
    print(f"ocr_run_seconds={finished - initialized:.6f}")
    print(f"ocr_total_seconds={finished - started:.6f}")
    print(f"recognized_nonwhitespace_chars={sum(not ch.isspace() for ch in text)}")
    print(f"rss_before_mb={rss_before / 1024 / 1024:.2f}")
    print(f"peak_rss_mb={memory.peak / 1024 / 1024:.2f}")
    print(f"peak_rss_delta_mb={(memory.peak - rss_before) / 1024 / 1024:.2f}")


if __name__ == "__main__":
    main()
