#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NVENC encoded image client helpers (PyAV decode + seg palette lookup)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

import airsim

try:
    import av
except ImportError:
    av = None

_SEG_RGBS_LINE_RE = re.compile(
    r"^\s*(\d+)\s*\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]\s*$"
)


def _candidate_palette_paths() -> List[Path]:
    here = Path(__file__).resolve()
    roots = [
        here.parent.parent.parent / "docs" / "seg_rgbs.txt",
        here.parent.parent / "docs" / "seg_rgbs.txt",
        Path.cwd() / "docs" / "seg_rgbs.txt",
    ]
    return roots


def load_seg_palette_bgr(path: Optional[Path] = None) -> np.ndarray:
    """Load AirSim 256-entry segmentation palette as BGR uint8 array."""
    candidates = [path] if path else _candidate_palette_paths()
    for cand in candidates:
        if cand is None or not cand.is_file():
            continue
        rgb_table = [(0, 0, 0)] * 256
        with cand.open("r", encoding="utf-8") as fh:
            for line in fh:
                m = _SEG_RGBS_LINE_RE.match(line)
                if m:
                    idx = int(m.group(1))
                    rgb_table[idx] = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
        arr_rgb = np.asarray(rgb_table, dtype=np.uint8)
        return arr_rgb[:, ::-1].copy()
    raise FileNotFoundError("seg_rgbs.txt not found; expected under docs/")


def seg_color_bgr(stencil_id: int, palette_bgr: Optional[np.ndarray] = None) -> Tuple[int, int, int]:
    pal = palette_bgr if palette_bgr is not None else load_seg_palette_bgr()
    return tuple(int(c) for c in pal[stencil_id])


def decode_bitstream_to_bgr(resp: airsim.EncodedImageResponse) -> np.ndarray:
    if av is None:
        raise ImportError("PyAV required for NVENC decode: pip install av")
    raw = resp.bitstream
    if isinstance(raw, str):
        raw = raw.encode("latin-1")
    buf = np.frombuffer(raw, dtype=np.uint8) if isinstance(raw, (bytes, bytearray)) else np.asarray(raw, dtype=np.uint8)
    if buf.size == 0:
        raise ValueError("empty bitstream")
    container = av.open(buf.tobytes(), format="hevc" if resp.encode_mode == airsim.EncodeMode.NvencHevc else "h264")
    for frame in container.decode(video=0):
        return frame.to_ndarray(format="bgr24")
    raise RuntimeError("decoder produced no frames")


class EncodedImageClient:
    def __init__(self, client: airsim.VehicleClient, palette_bgr: Optional[np.ndarray] = None):
        self._client = client
        self._palette_bgr = palette_bgr if palette_bgr is not None else load_seg_palette_bgr()

    def make_scene_request(self, camera_name: str, cq: int = 23) -> airsim.EncodedImageRequest:
        return airsim.EncodedImageRequest(
            camera_name,
            airsim.ImageType.Scene,
            encode_mode=airsim.EncodeMode.NvencH264,
            lossless=False,
            cq_or_qp=cq,
            gop_size=1,
            pix_fmt=airsim.EncodedPixFmt.Yuv420,
        )

    def make_seg_request(self, camera_name: str, strict_iou: bool = True) -> airsim.EncodedImageRequest:
        pix_fmt = airsim.EncodedPixFmt.Gbrp if strict_iou else airsim.EncodedPixFmt.Yuv420
        return airsim.EncodedImageRequest(
            camera_name,
            airsim.ImageType.Segmentation,
            encode_mode=airsim.EncodeMode.NvencHevc,
            lossless=strict_iou,
            cq_or_qp=0,
            gop_size=1,
            pix_fmt=pix_fmt,
        )

    def get_frames_bgr(
        self,
        requests: Sequence[airsim.EncodedImageRequest],
        vehicle_name: str = "",
        external: bool = False,
    ) -> List[np.ndarray]:
        responses = self._client.simGetImagesEncoded(list(requests), vehicle_name=vehicle_name, external=external)
        frames: List[np.ndarray] = []
        for req, resp in zip(requests, responses):
            if resp.message:
                raise RuntimeError(resp.message)
            bgr = decode_bitstream_to_bgr(resp)
            frames.append(bgr)
        return frames
