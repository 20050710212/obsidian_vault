# 1. EVS 总体结构
EVS Encoder 每帧先做信号分析，然后在 MODE1(ACELP/HQ) 或 MODE2(TCX) 之间选择编码路径。
```mermaid
flowchart TD

A[evs_enc_fx<br>EVS编码入口]

A --> B[pre_proc_fx<br>语音分析+模式决策]

B --> C{codec_mode}

C -->|MODE1| D[ACELP_CORE<br>语音预测编码]

C -->|MODE1| E[HQ_CORE<br>MDCT音频编码]

C -->|MODE2| F[TCX_20_CORE<br>频域编码]

D --> G[bitstream writing]

E --> G

F --> G
```

# 2. Model=1, ACELP call chain
ACELP 是典型 analysis-by-synthesis 编码结构，通过 pitch codebook + innovation codebook 组合重建语音。
``` mermaid
flowchart TD

A[evs_enc_fx]

A --> B[pre_proc_fx<br>语音分析<br>VAD + pitch]

B --> C[decision_matrix_enc_fx<br>编码模式决策]

C --> D[acelp_core_enc_fx<br>ACELP编码入口]

D --> E[coder_acelp<br>ACELP主编码循环]

E --> F[find_targets_fx<br>构造预测误差目标]

F --> G[pitch search<br>自适应码本搜索]

G --> H[innovation search<br>固定码本搜索]

H --> I[gain quantization<br>增益量化]

I --> J[bitstream writing]
```

# 3. MODE=1 MDCT/HQ Call chain
HQ 编码类似 AAC 的 MDCT 结构，适合音乐类信号。
``` mermaid
flowchart TD

A[evs_enc_fx]

A --> B[pre_proc_fx<br>语音/音乐分类]

B --> C[decision_matrix_enc_fx<br>选择HQ_CORE]

C --> D[hq_core_enc_fx<br>HQ编码入口]

D --> E[detect_transient_fx<br>瞬态检测]

E --> F[wtda_fx<br>窗函数+重叠]

F --> G[direct_transform_fx<br>MDCT变换]

G --> H{bitrate}

H --> I[hq_lr_enc_fx<br>低码率HQ编码]

H --> J[hq_hr_enc_fx<br>高码率HQ编码]

I --> K[bitstream writing]

J --> K
```

# 4. MODE=2 TCX call chain
TCX 是 ACELP 与 HQ 之间的过渡编码模式，兼顾语音和音乐质量。
TCX 是 EVS 的 transform coder。
``` mermaid
flowchart TD

A[evs_enc_fx]

A --> B[pre_proc_fx<br>信号分析]

B --> C[codec_mode = MODE2]

C --> D[enc_acelp_tcx_main<br>MODE2编码入口]

D --> E[core_encode_openloop<br>核心编码流程]

E --> F[coder_tcx<br>TCX编码主体]

F --> G[WindowSignal<br>窗函数]

G --> H[MDCT<br>频域变换]

H --> I[TNSAnalysis<br>时间噪声整形]

I --> J[ShapeSpectrum<br>频谱整形]

J --> K[QuantizeSpectrum<br>频谱量化]

K --> L[bitstream writing]
```

# 5. Mode Switch
EVS 的核心是 signal-driven codec switching，根据信号类型和码率动态选择编码模式。
``` mermaid
flowchart TD

A[input speech]

A --> B[signal_clas_fx<br>信号分类]

B --> C[speech_music_classif_fx<br>语音/音乐分类]

C --> D[decision_matrix_enc_fx<br>根据bitrate选择编码模式]

D --> E{core type}

E -->|speech| F[ACELP_CORE]

E -->|music| G[HQ_CORE]

E -->|mixed| H[TCX_20_CORE]

H --> I[codec_mode = MODE2]

F --> J[MODE1]

G --> J
```