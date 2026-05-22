import numpy as np
from dataclasses import dataclass


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


def rms(x, eps=1e-12):
    return np.sqrt(np.mean(x * x) + eps)


def tone_corr_score(x, fs, freq_hz):
    """
    对一段信号 x 计算目标频率的归一化相关得分。
    使用 sin/cos 双基底，不怕相位未知。
    """
    n = len(x)
    t = np.arange(n) / fs
    s = np.sin(2 * np.pi * freq_hz * t)
    c = np.cos(2 * np.pi * freq_hz * t)

    # 去直流
    x0 = x - np.mean(x)

    a = np.dot(x0, s)
    b = np.dot(x0, c)

    amp = np.sqrt(a * a + b * b) / (n + 1e-12)
    norm = rms(x0) + 1e-12
    return amp / norm


def estimate_active_duration(x, frame_len, hop_len, low_ratio=0.25):
    """
    从一段“应为100ms有音”的区域内，估计有效有音时长，以及内部掉音情况。
    方法：
    - 分帧计算 RMS
    - 用相对阈值（相对于中位数）判断低能量帧
    """
    if len(x) < frame_len:
        return 0.0, False, 0.0

    frame_rms = []
    positions = []
    for st in range(0, len(x) - frame_len + 1, hop_len):
        fr = x[st:st + frame_len]
        frame_rms.append(rms(fr))
        positions.append(st)

    frame_rms = np.array(frame_rms)
    med = np.median(frame_rms) + 1e-12
    threshold = low_ratio * med

    active = frame_rms >= threshold
    active_duration_samples = np.sum(active) * hop_len

    # 找内部最长掉音长度（排除开头结尾）
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
    """
    在 pred_start 附近做局部搜索，找最像：
    [100ms目标正弦][100ms静音]
    的位置。
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

        # 可按需要调整
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
    """
    主检测函数

    recorded: 录到的音频，一维 numpy 数组
    freqs_hz: 长度300的频率数组
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

    results = []

    # ------------------------------------------------------------
    # 1) 先找第一段锚点
    # ------------------------------------------------------------
    # 在开头较大范围内搜索第一段的起点
    first_pred = 0
    first_score, first_best = local_search_segment(
        recorded=recorded,
        fs=fs,
        freq_hz=freqs_hz[0],
        pred_start=first_pred,
        tone_len=tone_len,
        silence_len=silence_len,
        search_radius=anchor_search,
        step=step,
        silence_weight=2.0
    )

    if first_best is None:
        raise RuntimeError("无法找到第一段锚点，请检查录音数据或搜索参数。")

    anchor_start = first_best[0]
    prev_start = anchor_start
    prev_score = first_score

    # ------------------------------------------------------------
    # 2) for循环300次逐段检测
    # ------------------------------------------------------------
    for i in range(len(freqs_hz)):
        f = freqs_hz[i]

        global_pred = anchor_start + i * seg_len

        if i == 0:
            pred = anchor_start
        else:
            # 如果前一段置信度低，则降低对上一段的依赖
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
            # 保底
            det_start = pred
            tone_r = 0.0
            sil_r = 0.0
            corr = 0.0
        else:
            det_start, tone_r, sil_r, corr = best

        # 取检测到的这段
        tone = recorded[det_start:det_start + tone_len]
        sil = recorded[det_start + tone_len:det_start + tone_len + silence_len]

        # 估计有音时长 + 内部掉音
        active_samples, internal_drop, longest_drop_samples = estimate_active_duration(
            tone, frame_len=frame_len, hop_len=hop_len, low_ratio=0.25
        )

        tone_duration_ms_est = active_samples * 1000.0 / fs
        silence_duration_ms_est = seg_ms - tone_duration_ms_est

        internal_drop_ms = longest_drop_samples * 1000.0 / fs

        # --------------------------------------------------------
        # 异常判据（可调）
        # --------------------------------------------------------
        abnormal_reasons = []

        # 1. 静音段过大：表示后100ms不够安静，可能串段/拖尾/异常
        if sil_r > 0.5 * max(tone_r, 1e-12):
            abnormal_reasons.append("silence_too_loud")

        # 2. 目标频率相关性太低
        if corr < 0.25:
            abnormal_reasons.append("tone_corr_too_low")

        # 3. 有音段明显变短/变长
        if tone_duration_ms_est < 85:
            abnormal_reasons.append("tone_too_short")
        elif tone_duration_ms_est > 115:
            abnormal_reasons.append("tone_too_long")

        # 4. 有音内部掉音（例如10ms静音）
        if internal_drop and internal_drop_ms >= 8.0:
            abnormal_reasons.append("internal_drop_in_tone")

        # 5. 起点与全局预测偏差过大
        start_err_ms = abs(det_start - global_pred) * 1000.0 / fs
        if start_err_ms > 50.0:
            abnormal_reasons.append("start_offset_too_large")

        is_abnormal = len(abnormal_reasons) > 0

        res = SegmentResult(
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
        results.append(res)

        # 更新上一段状态
        prev_start = det_start
        prev_score = best_score

    return results