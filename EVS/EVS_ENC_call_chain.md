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

``` mermaid
flowchart TD

A["EVS Encoder"]

A --> B["MODE1<br>低延迟编码"]

A --> C["MODE2<br>高音质编码"]

B --> D["ACELP Core<br>语音预测编码"]

B --> E["HQ Core<br>MDCT音频编码"]

D --> F["Inactive"]
D --> G["Unvoiced"]
D --> H["Voiced"]
D --> I["Generic"]
D --> J["Transition"]
D --> K["Audio"]
```

``` mermaid
flowchart TD
A[MODE2]

A --> B{tcxonly}

B -->|0| C[core_encode_openloop]

C --> D{core_fx}

D -->|ACELP| E[ACELP coder]

D -->|TCX| F[coder_tcx]

B -->|1| G[core_encode_twodiv]

G --> F
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

, 
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


# decision matrix switch
1. 如果是
``` mermaid
flowchart TD

A["decision_matrix_enc_fx<br>决策入口<br>初始化 core/ext/hq_type"]

A --> B{"DTX 且<br>SID / FRAME_NO_DATA ?"}
B -->|是| C["ACELP_CORE<br>若 Fs>=32k 且 BW>=SWB<br>ext = SWB_CNG<br>rf_mode=0<br>return"]
B -->|否| D{"SC-VBR ?"}

D -->|是| E["进入 SC-VBR 分支<br>固定 core = ACELP_CORE<br>return"]
D -->|否| F{"bwidth_fx"}

F -->|NB| G["NB 分支"]
F -->|WB| H["WB 分支"]
F -->|SWB / FB| I["SWB/FB 分支"]

G --> J["收尾：若 core=HQ_CORE<br>设置 hq_core_type"]
H --> J
I --> J

J --> K["core_brate = total_brate - extl_brate<br>若 ini_frame==0<br>同步 last_core/last_ext"]
```

# SC-VBR 完整决策树
``` mermaid
flowchart TD

A["SC-VBR 分支入口<br>core = ACELP_CORE<br>core_brate = 7.2k<br>total_brate = 7.2k"]

A --> B{"ppp_mode_fx == 1 ?"}
B -->|是| C["PPP 模式<br>core_brate = PPP_NELP_2k80"]
B -->|否| D{"(coder_type=UNVOICED/TRANSITION 且 sp_aud_decision1=0)<br>或 bwidth != NB ?"}

D -->|否| E["保持 7.2k ACELP"]
D -->|是| F{"UNVOICED 且 vad=1<br>且满足 NELP 条件 ?"}

F -->|是| G["NELP 模式<br>nelp_mode=1<br>core_brate = PPP_NELP_2k80"]
F -->|否| H{"TRANSITION<br>或 (UNVOICED 且 nelp_mode!=1)<br>或 ((AUDIO/INACTIVE) 且 bwidth!=NB) ?"}

H -->|是| I["静音/弱活动部分<br>core_brate = 8.0k<br>total_brate = 8.0k"]
H -->|否| E
```

# 主决策树
``` mermaid
flowchart TD

A["非 DTX / 非 SC-VBR<br>进入带宽主决策"]

A --> B{"bwidth == NB ?"}
B -->|是| C["默认 core = ACELP_CORE"]
C --> D{"total_brate >= HQCORE_NB_MIN_RATE<br>且 sp_aud_decision1 == 1 ?"}
D -->|是| E["core = HQ_CORE"]
D -->|否| F["保持 ACELP_CORE"]

B -->|否| G{"bwidth == WB ?"}
G -->|是| H["默认 core = ACELP_CORE"]

H --> I{"(total_brate >= HQCORE_WB_MIN_RATE 且 sp_aud_decision1==1)<br>或 total_brate >= HQ_96k ?"}
I -->|是| J["core = HQ_CORE"]
I -->|否| K{"total_brate < 9.6k ?"}
K -->|是| L["ext = WB_BWE"]
K -->|否| M{"9.6k <= total_brate <= 16.4k ?"}
M -->|否| N["保持 ACELP，无额外 WB ext 设置"]
M -->|是| O{"sp_aud_decision1==1<br>或 coder_type==INACTIVE<br>或 (sp_aud_decision1==0 且 sp_aud_decision2==1) ?"}
O -->|是| P["ext = WB_BWE<br>ext_brate = 0.35k"]
O -->|否| Q["ext = WB_TBE<br>ext_brate = 1.05k"]

G -->|否| R{"bwidth == SWB 或 FB ?"}
R -->|是| S{"(total_brate >= HQCORE_SWB_MIN_RATE 且 sp_aud_decision1==1)<br>或 total_brate >= HQ_96k ?"}
S -->|是| T["core = HQ_CORE"]
S -->|否| U["core = ACELP_CORE"]

U --> V{"13.2k <= total_brate < 48k ?"}
V -->|否| W{"total_brate >= 48k ?"}
W -->|是| X["ext = SWB_BWE_HIGHRATE<br>ext_brate = SWB_BWE_16k<br>若 FB -> ext = FB_BWE_HIGHRATE"]
W -->|否| Y["无额外 SWB/FB ext 设置"]

V -->|是| Z{"(sp_aud_decision1==1 或 coder_type==INACTIVE<br>或 (sp_aud_decision1==0 且 sp_aud_decision2==1))<br>且 GSC_noisy_speech_fx == 0 ?"}
Z -->|是| AA["SWB_BWE 路<br>ext = SWB_BWE<br>ext_brate = 1.6k<br>若 FB 且 total_brate>=24.4k -> FB_BWE 1.8k"]
Z -->|否| AB["TBE 路<br>ext = SWB_TBE<br>ext_brate = 1.6k<br>若 total_brate>=24.4k -> 2.8k<br>若 FB 且 total_brate>=24.4k -> FB_TBE 3.0k"]
```


sharpFlag是个什么标志，为啥在preproces做了多次判断？