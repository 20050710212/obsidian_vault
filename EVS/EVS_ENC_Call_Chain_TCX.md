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

A[core_encode_openloop<br/>lib_enc/core_enc_ol.c:32]

A --> B[LPC quantization<br/>lpc_quantization / lsf_stab_fx<br/>core_enc_ol.c:153-205]

B --> C{st->core_fx}

C -->|ACELP_CORE| D[Generate interpolated LPCs A_q<br/>int_lsp4_fx or int_lsp_fx<br/>core_enc_ol.c:213-222]

D --> E[Compute ACELP target bits<br/>subtract LPC/header/IGF/RF/PLC bits<br/>core_enc_ol.c:224-247]

E --> F[Reset TBE encoder if last core != ACELP<br/>TBEreset_enc_fx<br/>core_enc_ol.c:249-253]

F --> G[coder_acelp<br/>lib_enc/cod_ace.c:21<br/>called at core_enc_ol.c:257-277]

G --> G1[BITS_ALLOC_config_acelp<br/>configure ACELP framing<br/>cod_ace.c:87-95]
G1 --> G2[Copy/prepare excitation & synthesis memories<br/>cod_ace.c:121-143]
G2 --> G3[Residual computation for all subframes<br/>Residu3_fx<br/>cod_ace.c:134-143]
G3 --> G4[Optional energy prediction coding<br/>Es_pred_enc_fx<br/>cod_ace.c:145-159]
G4 --> G5[Subframe loop<br/>cod_ace.c:171-565]

G5 --> G51[find_targets_fx<br/>target xn/cn and h1<br/>cod_ace.c:209-226]
G51 --> G52[Mode2_gp_clip<br/>gain clipping decision<br/>cod_ace.c:236-241]
G52 --> G53{acelp_cfg->ltp_bits}

G53 -->|with pitch| G54[Mode2_pit_encode<br/>closed-loop pitch search/encode<br/>cod_ace.c:250-273]
G54 --> G55[E_ACELP_adaptive_codebook<br/>adaptive excitation + y1 + gain_pit<br/>cod_ace.c:275-295]

G53 -->|no pitch| G56[Set gain_pit/y1/exc to zero path<br/>cod_ace.c:300-312]

G55 --> G57[Optional TBE excitation seed<br/>tbe_celp_exc<br/>cod_ace.c:315-318]
G56 --> G57

G57 --> G58[E_ACELP_innovative_codebook<br/>innovation/codebook search<br/>cod_ace.c:322-354]
G58 --> G59[E_ACELP_xy2_corr<br/>correlations for gain coding<br/>cod_ace.c:356-361]
G59 --> G60[Optional Gaussian excitation<br/>gauss_L2<br/>cod_ace.c:364-390]
G60 --> G61[encode_acelp_gains<br/>pitch/code gains quantization<br/>cod_ace.c:392-411]
G61 --> G62[E_UTIL_voice_factor<br/>voice factor / tilt update<br/>cod_ace.c:420-434]
G62 --> G63[Update mem_w0<br/>cod_ace.c:438-453]
G63 --> G64[Form total excitation exc/exc2<br/>cod_ace.c:457-484]
G64 --> G65[Optional prep_tbe_exc_fx<br/>prepare BWE excitation<br/>cod_ace.c:486-507]
G65 --> G66[E_UTIL_enhancer<br/>excitation enhancement / phase dispersion<br/>cod_ace.c:509-529]
G66 --> G67[E_UTIL_synthesis<br/>synthesis of subframe<br/>cod_ace.c:531-545]
G67 --> G68[Update per-subframe state<br/>cod_ace.c:547-565]

G68 --> G69[Update LPD memories / ZIR / old_Aq / Es_pred<br/>cod_ace.c:571-605]

C -->|TCX_20_CORE| H[Prepare TCX LPC if enabled<br/>E_LPC_int_lpc_tcx / Q_lsf_tcxlpc / etc.<br/>core_enc_ol.c:314-355]

H --> I[Compute TCX target bits<br/>subtract header/RF/mode/overlap/LTP bits<br/>core_enc_ol.c:362-395]

I --> J[coder_tcx<br/>lib_enc/cod_tcx.c:2074<br/>called at core_enc_ol.c:397-414]

J --> J1[WindowSignal / wtda_fx<br/>windowing path<br/>cod_tcx.c:2120-2197]
J1 --> J2[TCX_MDCT or edct_fx<br/>MDCT/DCT transform<br/>cod_tcx.c:2137-2197]
J2 --> J3[attenuateNbSpectrum if NB<br/>cod_tcx.c:2200-2208]
J3 --> J4[AnalyzePowerSpectrum<br/>cod_tcx.c:2210-2231]
J4 --> J5[SetTnsConfig + TNSAnalysis if allowed<br/>cod_tcx.c:2232-2248]
J5 --> J6[ProcessIGF if enabled<br/>cod_tcx.c:2250-2253]
J6 --> J7[ShapeSpectrum<br/>cod_tcx.c:2255-2261]
J7 --> J8[EncodeTnsData<br/>cod_tcx.c:2266-2269]
J8 --> J9[QuantizeSpectrum<br/>cod_tcx.c:2271-2290]
J9 --> J10[Update LPDmem nbits<br/>cod_tcx.c:2292]
J10 --> K[coder_tcx_post<br/>tcx_encoder_memory_update<br/>core_enc_ol.c:416<br/>cod_tcx.c:2303-2327]
```

code_tcx 十个左右的流程
``` mermaid

flowchart TD

A[coder_tcx]

A --> B[Frame initialization<br/>frame length / bit budget]

B --> C[Time-domain windowing<br/>WindowSignal / wtda_fx]

C --> D[Frequency transform<br/>TCX_MDCT or edct_fx]

D --> E[Spectrum preprocessing<br/>NB attenuation + power spectrum analysis]

E --> F[TNS analysis and filtering]

F --> G[IGF processing<br/>]

G --> H[Spectral shaping<br/>LPC-based MDCT shaping]

H --> I[Spectrum quantization<br/>QuantizeSpectrum]

I --> J[Bit accounting and memory update<br/>coder_tcx_post]
```

coder_acelp

``` mermaid
flowchart TD

A[coder_acelp]

A --> B[ACELP bit allocation<br/>configure ACELP frame]

B --> C[Initialize excitation and synthesis memories]

C --> D[Compute LPC residual signal]

D --> E[Optional energy prediction encoding]

E --> F[Subframe encoding loop]

F --> G[Target vector computation<br/>find_targets_fx]

G --> H[Pitch search and adaptive excitation]

H --> I[Innovation codebook search]

I --> J[Gain quantization<br/>pitch + code gains]

J --> K[Excitation synthesis and state update]
```