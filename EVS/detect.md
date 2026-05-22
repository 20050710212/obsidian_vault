import os
import csv
import wave
import numpy as np
from dataclasses import dataclass


# =========================================================
# 数据结构
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
    is_abnormal: bool
    abnormal_reasons: list


# =========================================================
# 基础函数
# =========================================================
def rms(x, eps=1e-12):
    return np.sqrt(np.mean(x * x) + eps)


def to_mono_float(x):
    """
    输入:
        x: numpy array, shape=(N,) 或 (N,C)
    输出:
        float64 单声道, shape=(N,)
    """
    x = np.asarray(x)

    if x.ndim == 2:
        x = np.mean(x, axis=1)

    # 整数转 float
    if np.issubdtype(x.dtype, np.integer):
        info = np.iinfo(x.dtype)
        max_abs = max(abs(info.min), abs(info.max))
        x = x.astype(np.float64) / max_abs
    else:
        x = x.astype(np.float64)

    return x


def read_wav_file(path):
    """
    读取 wav 文件
    返回:
        audio: float64 单声道
        fs: 采样率
    """
    with wave.open(path, 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        fs = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sampwidth == 1:
        dtype = np.uint8
        x = np.frombuffer(raw, dtype=dtype).astype(np.float64)
        x = (x - 128.0) / 128.0
    elif sampwidth == 2:
        dtype = np.int16
        x = np.frombuffer(raw, dtype=dtype)
    elif sampwidth == 4:
        dtype = np.int32
        x = np.frombuffer(raw, dtype=dtype)
    else:
        raise ValueError(f"不支持的 wav 位宽: {sampwidth * 8} bit")

    if n_channels > 1:
        x = x.reshape(-1, n_channels)

    x = to_mono_float(x)
    return x, fs


def read_pcm_file(path, fs=48000, channels=1, dtype='int16'):
    """
    读取裸 pcm 文件
    参数:
        path: 文件路径
        fs: 采样率
        channels: 通道数
        dtype: 'int16' / 'int32' / 'float32'
    返回:
        audio: float64 单声道
        fs: 采样率
    """
    dtype_map = {
        'int16': np.int16,
        'int32': np.int32,
        'float32': np.float32,
    }

    if dtype not in dtype_map:
        raise ValueError(f"不支持的 pcm dtype: {dtype}")

    x = np.fromfile(path, dtype=dtype_map[dtype])

    if channels > 1:
        x = x.reshape(-1, channels)

    x = to_mono_float(x)
    return x, fs


# =========================================================
# 核心检测函数
# =========================================================
def tone_corr_score(x, fs, freq_hz):
    n = len(x)
    t = np.arange(n) / fs
    s = np.sin(2 * np.pi * freq_hz * t)
    c = np.cos(2 * np.pi * freq_hz * t)

    x0 = x - np.mean(x)
    a = np.dot(x0, s)
    b = np.dot(x0, c)

    amp = np.sqrt(a * a + b * b) / (n + 1e-12)
    norm = rms(x0) + 1e-12
    return amp / norm


def estimate_active_duration(x, frame_len, hop_len, low_ratio=0.25):
    if len(x) < frame_len:
        return 0.0, False, 0.0

    frame_rms = []
    for st in range(0, len(x) - frame_len + 1, hop_len):
        fr = x[st:st + frame_len]
        frame_rms.append(rms(fr))

    frame_rms = np.array(frame_rms)
    med = np.median(frame_rms) + 1e-12
    threshold = low_ratio * med

    active = frame_rms >= threshold
    active_duration_samples = np.sum(active) * hop_len

    longest_drop = 0
    cur = 0
    for i in range(len(active)):
        if not active[i]:
            cur += hop_len
        else:
            if 0 < i < len(active) - 1:
                longest_drop = max(longest_drop, cur)
            cur = 0
    longest_drop = max(longest_drop, cur)

    internal_drop = longest_drop > 0
    return active_duration_samples, internal_drop, longest_drop


def local_search_segment(
    recorded,
    fs,
    freq_hz,
    pred_start,
    tone_len,
    silence_len,
    search_radius,
    step,
    silence_weight=2.0
):
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

    return best_score, best


def detect_bluetooth_playback_quality(
    recorded,
    fs=48000,
    freqs_hz=None,
    seg_ms=200.0,
    tone_ms=100.0,
    silence_ms=100.0,
    search_radius_ms=40.0,
    step_ms=1.0,
    frame_ms=5.0,
    hop_ms=2.5,
    anchor_search_ms=400.0,
    local_alpha=0.7
):
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

    results = []

    # 找第一段锚点
    first_score, first_best = local_search_segment(
        recorded=recorded,
        fs=fs,
        freq_hz=freqs_hz[0],
        pred_start=0,
        tone_len=tone_len,
        silence_len=silence_len,
        search_radius=anchor_search,
        step=step,
        silence_weight=2.0
    )

    if first_best is None:
        raise RuntimeError("无法找到第一段锚点，请检查录音数据。")

    anchor_start = first_best[0]
    prev_start = anchor_start
    prev_score = first_score

    for i in range(len(freqs_hz)):
        f = freqs_hz[i]
        global_pred = anchor_start + i * seg_len

        if i == 0:
            pred = anchor_start
        else:
            alpha = local_alpha if prev_score > 0 else 0.2
            local_pred = prev_start + seg_len
            pred = int(round(alpha * local_pred + (1 - alpha) * global_pred))

        best_score, best = local_search_segment(
            recorded=recorded,
            fs=fs,
            freq_hz=f,
            pred_start=pred,
            tone_len=tone_len,
            silence_len=silence_len,
            search_radius=search_radius,
            step=step,
            silence_weight=2.0
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

        active_samples, internal_drop, longest_drop_samples = estimate_active_duration(
            tone, frame_len=frame_len, hop_len=hop_len, low_ratio=0.25
        )

        tone_duration_ms_est = active_samples * 1000.0 / fs
        silence_duration_ms_est = seg_ms - tone_duration_ms_est
        internal_drop_ms = longest_drop_samples * 1000.0 / fs

        abnormal_reasons = []

        if sil_r > 0.5 * max(tone_r, 1e-12):
            abnormal_reasons.append("silence_too_loud")

        if corr < 0.25:
            abnormal_reasons.append("tone_corr_too_low")

        if tone_duration_ms_est < 85:
            abnormal_reasons.append("tone_too_short")
        elif tone_duration_ms_est > 115:
            abnormal_reasons.append("tone_too_long")

        start_err_ms = abs(det_start - global_pred) * 1000.0 / fs
        if start_err_ms > 50.0:
            abnormal_reasons.append("start_offset_too_large")

        if internal_drop and internal_drop_ms >= 8.0:
            abnormal_reasons.append("internal_drop_in_tone")

        is_abnormal = len(abnormal_reasons) > 0

        results.append(
            SegmentResult(
                index=i,
                freq_hz=float(f),
                pred_start_sample=int(pred),
                detected_start_sample=int(det_start),
                detected_start_ms=det_start * 1000.0 / fs,
                best_score=float(best_score),
                tone_rms=float(tone_r),
                silence_rms=float(sil_r),
                tone_corr=float(corr),
                tone_duration_ms_est=float(tone_duration_ms_est),
                silence_duration_ms_est=float(silence_duration_ms_est),
                internal_drop=bool(internal_drop),
                internal_drop_ms=float(internal_drop_ms),
                is_abnormal=bool(is_abnormal),
                abnormal_reasons=abnormal_reasons
            )
        )

        prev_start = det_start
        prev_score = best_score

    return results


# =========================================================
# 汇总与导出
# =========================================================
def summarize_results(results):
    n = len(results)
    abnormal = [r for r in results if r.is_abnormal]

    summary = {
        "total_segments": n,
        "abnormal_segments": len(abnormal),
        "abnormal_ratio": len(abnormal) / max(n, 1),
        "avg_tone_corr": float(np.mean([r.tone_corr for r in results])),
        "avg_tone_duration_ms": float(np.mean([r.tone_duration_ms_est for r in results])),
        "max_internal_drop_ms": float(np.max([r.internal_drop_ms for r in results])),
    }

    reason_count = {}
    for r in abnormal:
        for k in r.abnormal_reasons:
            reason_count[k] = reason_count.get(k, 0) + 1

    summary["reason_count"] = reason_count
    return summary


def save_results_to_csv(results, csv_path):
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
                int(r.is_abnormal),
                "|".join(r.abnormal_reasons),
            ])


# =========================================================
# 对外接口
# =========================================================
def run_detection_from_wav(
    wav_path,
    out_csv_path=None,
    freqs_hz=None,
):
    recorded, fs = read_wav_file(wav_path)

    if fs != 48000:
        print(f"警告: 当前 wav 采样率是 {fs} Hz，不是 48000 Hz。")

    results = detect_bluetooth_playback_quality(
        recorded=recorded,
        fs=fs,
        freqs_hz=freqs_hz
    )

    summary = summarize_results(results)

    if out_csv_path is not None:
        save_results_to_csv(results, out_csv_path)

    return results, summary


def run_detection_from_pcm(
    pcm_path,
    fs=48000,
    channels=1,
    dtype='int16',
    out_csv_path=None,
    freqs_hz=None,
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

    if out_csv_path is not None:
        save_results_to_csv(results, out_csv_path)

    return results, summary


# =========================================================
# 示例 main
# =========================================================
if __name__ == "__main__":
    freqs = np.linspace(50, 15000, 300)

    # -------- wav 示例 --------
    wav_path = "recorded.wav"
    if os.path.exists(wav_path):
        results, summary = run_detection_from_wav(
            wav_path,
            out_csv_path="result_wav.csv",
            freqs_hz=freqs
        )
        print("WAV SUMMARY:")
        print(summary)

    # -------- pcm 示例 --------
    pcm_path = "recorded.pcm"
    if os.path.exists(pcm_path):
        results, summary = run_detection_from_pcm(
            pcm_path,
            fs=48000,
            channels=1,
            dtype='int16',
            out_csv_path="result_pcm.csv",
            freqs_hz=freqs
        )
        print("PCM SUMMARY:")
        print(summary)