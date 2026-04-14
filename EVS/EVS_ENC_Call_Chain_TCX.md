``` mermaid
flowchart TD

A[input speech frame]

A --> B[pre_proc_fx]

B --> C[evs_enc_fx]

C --> D[speech_music_classif_fx]

D --> E[enc_acelp_tcx_main]

E --> F{TCX mode}

F -->|openloop| G[core_encode_openloop]

F -->|twodiv| H[core_encode_twodiv]

G --> I[tcx_ltp_encode]

I --> J[TCX MDCT]

J --> K[spectrum shaping]

K --> L[MSLVQ spectral quantization]

L --> M[arithmetic coding]

H --> N[split frame]

N --> O[encode first half TCX]

N --> P[encode second half TCX]

O --> J
P --> J

M --> Q[bitstream write]
```

``` mermaid
flowchart TD

A[core_encode_twodiv]

A --> B[detect transient]

B --> C[split frame]

C --> D[encode first TCX block]

C --> E[encode second TCX block]

D --> F[MDCT]

E --> F

F --> G[spectrum quantization]

G --> H[entropy coding]
```

``` mermaid

flowchart TD

A[core_encode_openloop]

A --> B[open-loop pitch analysis]

B --> C[TCX LTP encoding]

C --> D[MDCT transform]

D --> E[spectrum normalization]

E --> F[spectral quantization]

F --> G[entropy coding]
```

TCX（Transform Coded eXcitation） 是 EVS 中的一种 频域编码方式，属于 LP + transform hybrid coding。
基本思想：
TCX并不是纯transform codec，而是 LP + MDCT混合结构。
预测：

residual = speech − LP_prediction
这样可以：
去除谱包络
降低MDCT编码复杂度
与ACELP保持兼容
TCX可以理解为：
“LP预测 + MDCT频域编码的transform codec，用于EVS中非语音和高码率信号编码。”
``` mermaid
flowchart TD

A[core_encode_openloop]

A --> B[open loop pitch analysis]

B --> C{coder_type}

C -->|ACELP| D[coder_acelp]

C -->|TCX| E[coder_tcx]

D --> F[ACELP excitation search]

F --> G[gain quantization]

G --> H[bitstream write]

E --> I[TCX MDCT transform]

I --> J[spectral quantization]

J --> K[arithmetic coding]

K --> H

```
``` mermaid
flowchart TD

A[core_encode_openloop]

A --> B[LP parameter preparatio]

B --> C[open-loop pitch estimatio]

C --> D[voicing estimation]

D --> E{coder_type}

E -->|ACELP| F[coder_acelp]

E -->|TCX| G[coder_tcx]


%% ACELP path
F --> F1[ACELP frame preparation]
F1 --> F2[acelp_core_enc_fx]

F2 --> F3[LSF interpolation]

F3 --> F4[subframe loop]

F4 --> F5[find_targets_fx]

F5 --> F6[pitch search]

F6 --> F7[adaptive excitation]

F7 --> F8[innovation search]

F8 --> F9[gain quantization]

F9 --> F10[synthesis update]

F10 --> F11[write indices]


%% TCX path
G --> G1[TCX frame preparation]

G1 --> G2[LPC residual calculation]

G2 --> G3[TCX LTP analysis]

G3 --> G4[windowing]

G4 --> G5[MDCT transform]

G5 --> G6[spectral shaping]

G6 --> G7[MSLVQ quantization]

G7 --> G8[entropy coding]

G8 --> F11
```