#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bluetooth playback quality detector for 300-tone test audio.

Test signal assumptions:
- 300 segments
- each segment = 200 ms
- first 100 ms: sine tone
- next 100 ms: silence
- frequencies default to linear spacing from 50 Hz to 15000 Hz
- default sampling rate = 48000 Hz

Main features:
1. for-loop over all 300 segments
2. local re-alignment for each segment
3. dual prediction (local + global) so one bad segment won't derail later detection
4. detect:
   - tone_too_short
   - tone_too_long
   - tone_corr_too_low
   - silence_too_loud
   - start_offset_too_large
   - internal_drop_in_tone
5. export per-segment CSV and abnormal event CSV
6. support WAV and raw PCM input
7. command line interface

Examples:
    python bluetooth_playback_detector.py --wav recorded.wav --out result.csv --events result_events.csv
    python bluetooth_playback_detector.py --pcm recorded.pcm --fs 48000 --channels 1 --dtype int16 --out result.csv --events result_events.csv
"""

import os
import csv
import wave
import argparse
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple

import numpy as np


# =========================================================
# Data structures
# =========================================================
@dataclass
class SegmentResult:
    index: int
    freq_hz: float
    pred_start_sample: int
    detected_start_sample: int
    detected_start_ms: float
    best_score: float
    tone_rms: float
    silence_rms: float
    tone_corr: float
    tone_duration_ms_est: float
    silence_duration_ms_est: float
    internal_drop: bool
    internal_drop_ms: float
    internal_drop_offset_ms: float
    is_abnormal: bool
    abnormal_reasons: List[str]


# =========================================================
# Utility functions
# =========================================================
def rms(x: np.ndarray, eps: float = 1e-12) -> float:
    return float(np.sqrt(np.mean(x * x) + eps))


def to_mono_float(x: np.ndarray) -> np.ndarray:
    """
    Input:
        x: ndarray, shape=(N,) or (N, C)

    Output:
        float64 mono ndarray, shape=(N,)
    """
    x = np.asarray(x)

    if x.ndim == 2:
        x = np.mean(x, axis=1)

    if np.issubdtype(x.dtype, np.integer):
        info = np.iinfo(x.dtype)
        max_abs = max(abs(info.min), abs(info.max))
        x = x.astype(np.float64) / max_abs
    else:
        x = x.astype(np.float64)

    return x


# =========================================================
# Audio file readers
# =========================================================
def read_wav_file(path: str) -> Tuple[np.ndarray, int]:
    """
    Read PCM WAV file.

    Returns:
        audio: float64 mono ndarray
        fs: sample rate
    """
    with wave.open(path, 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        fs = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sampwidth == 1:
        x = np.frombuffer(raw, dtype=np.uint8).astype(np.float64)
        x = (x - 128.0) / 128.0
    elif sampwidth == 2:
        x = np.frombuffer(raw, dtype=np.int16)
    elif sampwidth == 4:
        x = np.frombuffer(raw, dtype=np.int32)
    else:
        raise ValueError(f"Unsupported WAV sample width: {sampwidth * 8} bits")

    if n_channels > 1:
        x = x.reshape(-1, n_channels)

    x = to_mono_float(x)
    return x, fs


def read_pcm_file(path: str, fs: int = 48000, channels: int = 1, dtype: str = 'int16') -> Tuple[np.ndarray, int]:
    """
    Read raw PCM file.

    Args:
        path: file path
        fs: sample rate
        channels: number of channels
        dtype: int16 / int32 / float32

    Returns:
        audio: float64 mono ndarray
        fs: sample rate
    """
    dtype_map = {
        'int16': np.int16,
        'int32': np.int32,
        'float32': np.float32,
    }

    if dtype not in dtype_map:
        raise ValueError(f"Unsupported PCM dtype: {dtype}")

    x = np.fromfile(path, dtype=dtype_map[dtype])

    if channels > 1:
        x = x.reshape(-1, channels)

    x = to_mono_float(x)
    return x, fs


# =========================================================
# Detection primitives
# =========================================================
def tone_corr_score(x: np.ndarray, fs: int, freq_hz: float) -> float:
    """
    Correlation-like score for how much x resembles a sine tone at freq_hz.
    Uses sin/cos basis to avoid phase sensitivity.
    """
    n = len(x)
    t = np.arange(n) / fs
    s = np.sin(2 * np.pi * freq_hz * t)
    c = np.cos(2 * np.pi * freq_hz * t)

    x0 = x - np.mean(x)
    a = np.dot(x0, s)
    b = np.dot(x0, c)

    amp = np.sqrt(a * a + b * b) / (n + 1e-12)
    norm = rms(x0) + 1e-12
    return float(amp / norm)


def estimate_active_duration(
    x: np.ndarray,
    frame_len: int,
    hop_len: int,
    low_ratio: float = 0.25
) -> Tuple[float, bool, float, Optional[int]]:
    """
    Estimate active duration inside a tone region and detect internal drop.

    Returns:
        active_duration_samples
        internal_drop (bool)
        longest_drop_samples
        longest_drop_start_sample (relative to x)
    """
    if len(x) < frame_len:
        return 0.0, False, 0.0, None

    frame_rms = []
    frame_starts = []

    for st in range(0, len(x) - frame_len + 1, hop_len):
        fr = x[st:st + frame_len]
        frame_rms.append(rms(fr))
        frame_starts.append(st)

    frame_rms = np.array(frame_rms, dtype=np.float64)
    frame_starts = np.array(frame_starts, dtype=np.int64)

    med = np.median(frame_rms) + 1e-12
    threshold = low_ratio * med
    active = frame_rms >= threshold

    active_duration_samples = float(np.sum(active) * hop_len)

    longest_drop = 0
    longest_drop_start = None
    cur = 0
    cur_start = None

    for i in range(len(active)):
        if not active[i]:
            if cur == 0:
                cur_start = int(frame_starts[i])
            cur += hop_len
        else:
            if 0 < i < len(active) - 1:
                if cur > longest_drop:
                    longest_drop = cur
                    longest_drop_start = cur_start
            cur = 0
            cur_start = None

    if cur > longest_drop:
        longest_drop = cur
        longest_drop_start = cur_start

    internal_drop = longest_drop > 0
    return active_duration_samples, bool(internal_drop), float(longest_drop), longest_drop_start


def local_search_segment(
    recorded: np.ndarray,
    fs: int,
    freq_hz: float,
    pred_start: int,
    tone_len: int,
    silence_len: int,
    search_radius: int,
    step: int,
    silence_weight: float = 2.0
) -> Tuple[float, Optional[Tuple[int, float, float, float]]]:
    """
    Search around pred_start for the most likely segment:
        [tone 100ms][silence 100ms]
    """
    best_score = -1e18
    best = None

    total_len = tone_len + silence_len
    n = len(recorded)

    left = max(0, pred_start - search_radius)
    right = min(n - total_len, pred_start + search_radius)

    for s in range(left, right + 1, step):
        tone = recorded[s:s + tone_len]
        sil = recorded[s + tone_len:s + total_len]

        tone_r = rms(tone)
        sil_r = rms(sil)
        corr = tone_corr_score(tone, fs, freq_hz)

        score = corr * tone_r - silence_weight * sil_r

        if score > best_score:
            best_score = score
            best = (s, tone_r, sil_r, corr)

    return float(best_score), best


# =========================================================
# Core detector
# =========================================================
def detect_bluetooth_playback_quality(
    recorded: np.ndarray,
    fs: int = 48000,
    freqs_hz: Optional[np.ndarray] = None,
    seg_ms: float = 200.0,
    tone_ms: float = 100.0,
    silence_ms: float = 100.0,
    search_radius_ms: float = 40.0,
    step_ms: float = 1.0,
    frame_ms: float = 5.0,
    hop_ms: float = 2.5,
    anchor_search_ms: float = 400.0,
    local_alpha: float = 0.7,
    silence_weight: float = 2.0,
    tone_corr_threshold: float = 0.25,
    start_offset_threshold_ms: float = 50.0,
    tone_short_threshold_ms: float = 85.0,
    tone_long_threshold_ms: float = 115.0,
    internal_drop_threshold_ms: float = 8.0,
) -> List[SegmentResult]:
    """
    Main detector.

    Args:
        recorded: mono float ndarray
        fs: sample rate
        freqs_hz: frequency list for all segments
    Returns:
        List[SegmentResult]
    """
    if freqs_hz is None:
        freqs_hz = np.linspace(50, 15000, 300)

    recorded = np.asarray(recorded, dtype=np.float64)

    seg_len = int(round(seg_ms * fs / 1000.0))
    tone_len = int(round(tone_ms * fs / 1000.0))
    silence_len = int(round(silence_ms * fs / 1000.0))
    search_radius = int(round(search_radius_ms * fs / 1000.0))
    step = max(1, int(round(step_ms * fs / 1000.0)))
    frame_len = max(1, int(round(frame_ms * fs / 1000.0)))
    hop_len = max(1, int(round(hop_ms * fs / 1000.0)))
    anchor_search = int(round(anchor_search_ms * fs / 1000.0))

    results: List[SegmentResult] = []

    # ------------------------------------------------------------
    # 1) Find first anchor
    # ------------------------------------------------------------
    first_score, first_best = local_search_segment(
        recorded=recorded,
        fs=fs,
        freq_hz=float(freqs_hz[0]),
        pred_start=0,
        tone_len=tone_len,
        silence_len=silence_len,
        search_radius=anchor_search,
        step=step,
        silence_weight=silence_weight,
    )

    if first_best is None:
        raise RuntimeError("Cannot find first segment anchor. Check audio or parameters.")

    anchor_start = first_best[0]
    prev_start = anchor_start
    prev_score = first_score

    # ------------------------------------------------------------
    # 2) for-loop over all segments
    # ------------------------------------------------------------
    for i in range(len(freqs_hz)):
        f = float(freqs_hz[i])

        global_pred = anchor_start + i * seg_len

        if i == 0:
            pred = anchor_start
        else:
            alpha = local_alpha if prev_score > 0 else 0.2
            local_pred = prev_start + seg_len
            pred = int(round(alpha * local_pred + (1.0 - alpha) * global_pred))

        best_score, best = local_search_segment(
            recorded=recorded,
            fs=fs,
            freq_hz=f,
            pred_start=pred,
            tone_len=tone_len,
            silence_len=silence_len,
            search_radius=search_radius,
            step=step,
            silence_weight=silence_weight,
        )

        if best is None:
            det_start = pred
            tone_r = 0.0
            sil_r = 0.0
            corr = 0.0
        else:
            det_start, tone_r, sil_r, corr = best

        tone = recorded[det_start:det_start + tone_len]
        sil = recorded[det_start + tone_len:det_start + tone_len + silence_len]

        active_samples, internal_drop, longest_drop_samples, longest_drop_start = estimate_active_duration(
            tone, frame_len=frame_len, hop_len=hop_len, low_ratio=0.25
        )

        tone_duration_ms_est = active_samples * 1000.0 / fs
        silence_duration_ms_est = seg_ms - tone_duration_ms_est
        internal_drop_ms = longest_drop_samples * 1000.0 / fs
        internal_drop_offset_ms = (
            longest_drop_start * 1000.0 / fs if longest_drop_start is not None else -1.0
        )

        abnormal_reasons: List[str] = []

        # 1) Silence region is too loud
        if sil_r > 0.5 * max(tone_r, 1e-12):
            abnormal_reasons.append("silence_too_loud")

        # 2) Tone correlation too low
        if corr < tone_corr_threshold:
            abnormal_reasons.append("tone_corr_too_low")

        # 3) Tone duration abnormal
        if tone_duration_ms_est < tone_short_threshold_ms:
            abnormal_reasons.append("tone_too_short")
        elif tone_duration_ms_est > tone_long_threshold_ms:
            abnormal_reasons.append("tone_too_long")

        # 4) Start offset too large relative to global prediction
        start_err_ms = abs(det_start - global_pred) * 1000.0 / fs
        if start_err_ms > start_offset_threshold_ms:
            abnormal_reasons.append("start_offset_too_large")

        # 5) Internal drop in tone
        if internal_drop and internal_drop_ms >= internal_drop_threshold_ms:
            abnormal_reasons.append("internal_drop_in_tone")

        is_abnormal = len(abnormal_reasons) > 0

        results.append(
            SegmentResult(
                index=i,
                freq_hz=f,
                pred_start_sample=int(pred),
                detected_start_sample=int(det_start),
                detected_start_ms=float(det_start * 1000.0 / fs),
                best_score=float(best_score),
                tone_rms=float(tone_r),
                silence_rms=float(sil_r),
                tone_corr=float(corr),
                tone_duration_ms_est=float(tone_duration_ms_est),
                silence_duration_ms_est=float(silence_duration_ms_est),
                internal_drop=bool(internal_drop),
                internal_drop_ms=float(internal_drop_ms),
                internal_drop_offset_ms=float(internal_drop_offset_ms),
                is_abnormal=bool(is_abnormal),
                abnormal_reasons=abnormal_reasons,
            )
        )

        prev_start = det_start
        prev_score = best_score

    return results


# =========================================================
# Summary & abnormal events
# =========================================================
def summarize_results(results: List[SegmentResult]) -> Dict:
    """
    Summary metrics over the whole audio.

    avg_tone_corr:
        mean of tone_corr across all segments.
        Higher is generally better.

    abnormal ratio:
        ratio of abnormal segments.

    max_internal_drop_ms:
        maximum detected internal drop duration inside tone regions.
    """
    n = len(results)
    abnormal = [r for r in results if r.is_abnormal]

    summary = {
        "total_segments": n,
        "abnormal_segments": len(abnormal),
        "abnormal_ratio": len(abnormal) / max(n, 1),
        "avg_tone_corr": float(np.mean([r.tone_corr for r in results])) if results else 0.0,
        "avg_tone_duration_ms": float(np.mean([r.tone_duration_ms_est for r in results])) if results else 0.0,
        "max_internal_drop_ms": float(np.max([r.internal_drop_ms for r in results])) if results else 0.0,
    }

    reason_count: Dict[str, int] = {}
    for r in abnormal:
        for k in r.abnormal_reasons:
            reason_count[k] = reason_count.get(k, 0) + 1

    summary["reason_count"] = reason_count
    return summary


def build_abnormal_events(results: List[SegmentResult]) -> List[Dict]:
    """
    Build abnormal event list with time position and reason.

    For most abnormalities:
        time_ms = segment detected start time

    For internal_drop_in_tone:
        time_ms = segment start + drop offset inside tone
    """
    events: List[Dict] = []

    for r in results:
        if not r.is_abnormal:
            continue

        base_time_ms = r.detected_start_ms

        for reason in r.abnormal_reasons:
            detail = ""
            event_time_ms = base_time_ms

            if reason == "tone_too_short":
                detail = f"tone_duration_ms_est={r.tone_duration_ms_est:.2f}"
            elif reason == "tone_too_long":
                detail = f"tone_duration_ms_est={r.tone_duration_ms_est:.2f}"
            elif reason == "tone_corr_too_low":
                detail = f"tone_corr={r.tone_corr:.4f}"
            elif reason == "silence_too_loud":
                detail = f"silence_rms={r.silence_rms:.6f}, tone_rms={r.tone_rms:.6f}"
            elif reason == "start_offset_too_large":
                detail = (
                    f"pred_start_sample={r.pred_start_sample}, "
                    f"detected_start_sample={r.detected_start_sample}"
                )
            elif reason == "internal_drop_in_tone":
                if r.internal_drop_offset_ms >= 0:
                    event_time_ms = base_time_ms + r.internal_drop_offset_ms
                detail = (
                    f"internal_drop_ms={r.internal_drop_ms:.2f}, "
                    f"internal_drop_offset_ms={r.internal_drop_offset_ms:.2f}"
                )

            events.append({
                "time_ms": round(float(event_time_ms), 3),
                "segment_index": int(r.index),
                "freq_hz": round(float(r.freq_hz), 3),
                "reason": reason,
                "detail": detail,
            })

    events = sorted(events, key=lambda x: x["time_ms"])
    return events


# =========================================================
# CSV writers
# =========================================================
def save_results_to_csv(results: List[SegmentResult], csv_path: str) -> None:
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "index",
            "freq_hz",
            "pred_start_sample",
            "detected_start_sample",
            "detected_start_ms",
            "best_score",
            "tone_rms",
            "silence_rms",
            "tone_corr",
            "tone_duration_ms_est",
            "silence_duration_ms_est",
            "internal_drop",
            "internal_drop_ms",
            "internal_drop_offset_ms",
            "is_abnormal",
            "abnormal_reasons",
        ])

        for r in results:
            writer.writerow([
                r.index,
                r.freq_hz,
                r.pred_start_sample,
                r.detected_start_sample,
                r.detected_start_ms,
                r.best_score,
                r.tone_rms,
                r.silence_rms,
                r.tone_corr,
                r.tone_duration_ms_est,
                r.silence_duration_ms_est,
                int(r.internal_drop),
                r.internal_drop_ms,
                r.internal_drop_offset_ms,
                int(r.is_abnormal),
                "|".join(r.abnormal_reasons),
            ])


def save_events_to_csv(events: List[Dict], csv_path: str) -> None:
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time_ms",
            "segment_index",
            "freq_hz",
            "reason",
            "detail",
        ])

        for e in events:
            writer.writerow([
                e["time_ms"],
                e["segment_index"],
                e["freq_hz"],
                e["reason"],
                e["detail"],
            ])


# =========================================================
# High level runners
# =========================================================
def run_detection_from_wav(
    wav_path: str,
    out_csv_path: Optional[str] = None,
    out_event_csv_path: Optional[str] = None,
    freqs_hz: Optional[np.ndarray] = None,
):
    recorded, fs = read_wav_file(wav_path)

    results = detect_bluetooth_playback_quality(
        recorded=recorded,
        fs=fs,
        freqs_hz=freqs_hz
    )

    summary = summarize_results(results)
    events = build_abnormal_events(results)

    if out_csv_path:
        save_results_to_csv(results, out_csv_path)

    if out_event_csv_path:
        save_events_to_csv(events, out_event_csv_path)

    return results, summary, events


def run_detection_from_pcm(
    pcm_path: str,
    fs: int = 48000,
    channels: int = 1,
    dtype: str = 'int16',
    out_csv_path: Optional[str] = None,
    out_event_csv_path: Optional[str] = None,
    freqs_hz: Optional[np.ndarray] = None,
):
    recorded, fs = read_pcm_file(
        pcm_path,
        fs=fs,
        channels=channels,
        dtype=dtype
    )

    results = detect_bluetooth_playback_quality(
        recorded=recorded,
        fs=fs,
        freqs_hz=freqs_hz
    )

    summary = summarize_results(results)
    events = build_abnormal_events(results)

    if out_csv_path:
        save_results_to_csv(results, out_csv_path)

    if out_event_csv_path:
        save_events_to_csv(events, out_event_csv_path)

    return results, summary, events


# =========================================================
# Frequency helpers
# =========================================================
def build_linear_freqs(start_hz: float = 50.0, end_hz: float = 15000.0, count: int = 300) -> np.ndarray:
    return np.linspace(start_hz, end_hz, count)


def build_log_freqs(start_hz: float = 50.0, end_hz: float = 15000.0, count: int = 300) -> np.ndarray:
    return np.geomspace(start_hz, end_hz, count)


def read_freqs_from_txt(path: str) -> np.ndarray:
    freqs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            freqs.append(float(s))
    return np.array(freqs, dtype=np.float64)


# =========================================================
# CLI
# =========================================================
def parse_args():
    parser = argparse.ArgumentParser(description="Bluetooth playback quality detector")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--wav", type=str, help="Input WAV file")
    group.add_argument("--pcm", type=str, help="Input raw PCM file")

    parser.add_argument("--fs", type=int, default=48000, help="PCM sample rate (default: 48000)")
    parser.add_argument("--channels", type=int, default=1, help="PCM channels (default: 1)")
    parser.add_argument("--dtype", type=str, default="int16", choices=["int16", "int32", "float32"], help="PCM dtype")

    parser.add_argument("--out", type=str, default="result.csv", help="Per-segment CSV output path")
    parser.add_argument("--events", type=str, default="result_events.csv", help="Abnormal events CSV output path")

    parser.add_argument("--freq-mode", type=str, default="linear", choices=["linear", "log"], help="Frequency distribution")
    parser.add_argument("--freq-file", type=str, default=None, help="Optional text file of frequencies, one per line")
    parser.add_argument("--freq-start", type=float, default=50.0, help="Start frequency")
    parser.add_argument("--freq-end", type=float, default=15000.0, help="End frequency")
    parser.add_argument("--freq-count", type=int, default=300, help="Number of segments/frequencies")

    parser.add_argument("--print-events", action="store_true", help="Print abnormal events to console")
    parser.add_argument("--print-summary", action="store_true", help="Print summary to console")

    return parser.parse_args()


def main():
    args = parse_args()

    if args.freq_file:
        freqs = read_freqs_from_txt(args.freq_file)
    else:
        if args.freq_mode == "linear":
            freqs = build_linear_freqs(args.freq_start, args.freq_end, args.freq_count)
        else:
            freqs = build_log_freqs(args.freq_start, args.freq_end, args.freq_count)

    if args.wav:
        results, summary, events = run_detection_from_wav(
            args.wav,
            out_csv_path=args.out,
            out_event_csv_path=args.events,
            freqs_hz=freqs,
        )
    else:
        results, summary, events = run_detection_from_pcm(
            args.pcm,
            fs=args.fs,
            channels=args.channels,
            dtype=args.dtype,
            out_csv_path=args.out,
            out_event_csv_path=args.events,
            freqs_hz=freqs,
        )

    if args.print_summary:
        print("SUMMARY:")
        for k, v in summary.items():
            print(f"{k}: {v}")

    if args.print_events:
        print("\nABNORMAL EVENTS:")
        for e in events:
            print(f'{e["time_ms"]} ms: {e["reason"]} (segment={e["segment_index"]}, freq={e["freq_hz"]} Hz, {e["detail"]})')

    print(f"Per-segment CSV saved to: {args.out}")
    print(f"Abnormal events CSV saved to: {args.events}")


if __name__ == "__main__":
    main()
