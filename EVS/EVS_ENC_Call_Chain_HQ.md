``` mermaid
flowchart TD
    A["pre_proc_fx()
: decision_matrix_enc_fx()"] --> B{"core_fx == HQ_CORE ?"}
    B -- "否" --> X["非 MODE1 HQ"]
    B -- "是" --> C["可选: mdct_classifier_fx() / MDCT_selector()"]
    C --> D{"最终仍是 HQ_CORE ?"}
    D -- "否" --> Y["切到 TCX_20_CORE / MODE2"]
    D -- "是" --> E["evs_enc_fx()"]
    E --> F["signalling_enc_fx()"]
    F --> G["core_switching_pre_enc_fx()"]
    G --> H["hq_core_enc_fx()"]
    H --> I["detect_transient_fx()"]
    I --> J["wtda_fx()"]
    J --> K["可选: core_switching_hq_prepare_enc_fx()"]
    K --> L["direct_transform_fx()"]
    L --> M{"hq_core_type"}
    M -- "LOW_RATE_HQ_CORE" --> N["hq_lr_enc_fx()"]
    M -- "NORMAL_HQ_CORE" --> O["hq_hr_enc_fx()"]
    N --> P["core_switching_post_enc_fx()"]
    O --> P
```

``` mermaid
flowchart TD

A["hq_core_enc_fx()"]

A --> B["detect_transient_fx()"]
B --> C["wtda_fx()"]

C --> D["core_switching_hq_prepare_enc_fx() (可选)"]

D --> E["direct_transform_fx()"]

E --> F{"hq_core_type"}

F -->|LOW_RATE_HQ_CORE| G["hq_lr_enc_fx()"]

F -->|NORMAL_HQ_CORE| H["hq_hr_enc_fx()"]


H --> I["hq_classifier_enc_fx()"]

I --> J["hq_configure_fx()"]

J --> K["interleave_spectrum_fx() (transient only)"]

K --> L["calc_norm_fx()"]

L --> M["diff_envelope_coding_fx()"]

M --> N["encode_envelope_indices_fx()"]

N --> O["hq_bit_allocation_fx()"]

O --> P{"HQ mode"}

P -->|HVQ| Q["hvq_enc_fx()"]

P -->|PVQ| R["pvq_core_enc_fx()"]

Q --> S["noise_adjust_fx()"]
R --> S

S --> T["编码结束"]
```

(1) detect_transient_fx()
功能：
检测当前帧是否为 transient（瞬态）信号
例如：
鼓
敲击
爆破音
瞬态信号需要不同的频谱处理方式。

(2) wtda_fx()
Windowing + Time Domain Aliasing
作用：
对信号加窗
处理重叠帧
这是 MDCT 的标准预处理步骤。

(3) core_switching_hq_prepare_enc_fx()
当上一帧不是 HQ（例如 ACELP）时：
需要做 core switching 处理。
目的：
防止模式切换产生失真
保持连续性
(4) direct_transform_fx()
执行 MDCT 变换

time domain signal
        ↓
frequency spectrum
这是 HQ 编码最核心的一步。
(5) hq_core_type 判断
HQ 有两个类型：
类型
用途
LOW_RATE_HQ_CORE
较低码率 HQ
NORMAL_HQ_CORE
高码率 HQ
对应函数：

hq_lr_enc_fx()
hq_hr_enc_fx()
高码率HQ流程（hq_hr_enc_fx）
(6) hq_classifier_enc_fx()
分析频谱结构：
分类为：
generic
harmonic
HVQ
transient
不同类别使用不同编码策略。
(7) hq_configure_fx()
根据：
分类
码率
采样率
配置：
频带划分
envelope参数
量化参数
(8) interleave_spectrum_fx()
仅在 transient模式 使用。
目的：
减少 MDCT 的 pre-echo 问题。
(9) calc_norm_fx()
计算每个频带的 能量归一化值
用于 envelope 编码。
(10) diff_envelope_coding_fx()
对 envelope 做：

差分编码
优点：
减少比特
envelope变化通常平滑
(11) encode_envelope_indices_fx()
将 envelope 参数写入 bitstream。
(12) hq_bit_allocation_fx()
进行 频带比特分配
输入：
envelope
分类结果
码率
输出：
每个band分配多少bit
(13) HVQ / PVQ 选择
HVQ
用于：
谐波结构很强的信号
例如：
音乐
乐器
函数：

hvq_enc_fx()
PVQ
用于：
一般频谱
函数：

pvq_core_enc_fx()
(14) noise_adjust_fx()
在高频加入适量噪声。
作用：
提高主观音质
避免高频空洞

``` mermaid
flowchart TD

A["hq_lr_enc_fx()"]

A --> B["peak_avrg_ratio_fx() (条件满足时)"]

B --> C["hq2_core_configure_fx()"]

C --> D["p2a_threshold_quant_fx()"]

D --> E{"是否short-domain"}

E -->|是| F["spt_shorten_domain_pre_fx()"]

F --> G["spt_shorten_domain_set_fx()"]

G --> H["hq2_bit_alloc_fx()"]

E -->|否| H

H --> I{"是否harmonic"}

I -->|是| J["hq2_bit_alloc_har_fx()"]

I -->|否| K["hq2_bit_alloc_fx()"]

J --> L["tcq_core_LR_enc_fx()"]
K --> L

L --> M["mdct_spectrum_denorm_fx()"]

M --> N["mdct_spectrum_fine_gain_enc_fx()"]

N --> O{"是否short-domain"}

O -->|是| P["spt_shorten_domain_band_restore_fx()"]

O -->|否| Q["hq2_noise_inject_fx()"]

P --> Q

Q --> R{"是否SWB"}

R -->|是| S["swb_bwe_enc_lr_fx()"]

R -->|否| T["updat_prev_frm_fx()"]

S --> T
```
``` mermaid
flowchart TD

A["HQ_CORE_TYPE"]

A -->|LOW_RATE_HQ_CORE| B["HQ_LR Encoder"]

A -->|NORMAL_HQ_CORE| C["HQ_HR Encoder"]

%% HQ_LR
B --> B1["Spectrum analysis"]
B1 --> B2["Bit allocation"]
B2 --> B3["TCQ spectrum quantization"]
B3 --> B4["Noise injection / BWE"]
B4 --> Z["Bitstream"]

%% HQ_HR
C --> C1["Spectrum classification"]
C1 --> C2["Envelope coding"]
C2 --> C3["Bit allocation"]
C3 --> C4{"Quantization"}

C4 -->|PVQ| C5["PVQ encoding"]
C4 -->|HVQ| C6["HVQ encoding"]

C5 --> C7["Noise adjustment"]
C6 --> C7

C7 --> Z
```
