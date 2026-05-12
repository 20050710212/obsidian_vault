# 面向卫星通信极低码率语音编解码器标准化的重点研究内容

## 一、AI 技术对极低码率语音编解码器的增益研究

### 1.1 研究 AI codec 在 0.5–3 kbit/s 区间的质量增益

极低码率语音通信的核心矛盾是：卫星链路可用净载荷码率很低，但实时语音仍需要保持可懂度、自然度和基本通信质量。TR 26.940 将 GEO 场景下的总传输数据率假设为 **1–3 kbit/s**，并指出当前 3GPP 语音 codec 最低码率 AMR-NB 4.75 kbit/s 仍高于该传输能力，因此需要研究新的 ULBC codec。0

AI codec 的主要优势在于，它不完全依赖传统参数语音模型，而是通过端到端学习获得更高效的语音表征。SoundStream 论文提出使用全卷积 encoder/decoder 与 residual vector quantizer 端到端联合训练，并通过 adversarial loss 与 reconstruction loss 从量化 embedding 中生成高质量音频；该模型支持 3–18 kbit/s 可变码率，并可在智能手机 CPU 上实时运行。([arxiv.org](https://arxiv.org/abs/2107.03312?utm_source=chatgpt.com))

TR 26.940 的听感测试也显示，AI codec 在低码率下相对传统 vocoder 具有明显质量优势。例如，Codec2 在 0.7、1.2、2.4 kbit/s 下均显著差于 AMR 4.75 kbit/s；而 SemantiCodec、Lyra V2、LPCNet、Mimi 0.55 kbit/s 可达到接近 AMR-WB 6.65 kbit/s 的质量，Mimi 1.1 kbit/s、DAC-IBM 1.5 kbit/s、SNAC 0.98 kbit/s 甚至接近或略优于 EVS 9.6 kbit/s。TR 26.940 据此认为，AI 方案相对传统超低码率方案可带来约 2 MOS 或以上质量增益。1

### 1.2 研究生成式编码对“低比特表示—高质量重建”的作用

生成式编码的本质是将低码率 bitstream 视为语音内容、韵律、说话人特征或声学 token 的压缩表示，再由神经解码器生成波形或声学特征。SoundStream、EnCodec、DAC 等神经音频 codec 均采用 autoencoder + vector quantization 的基本结构；EnCodec 官方说明其由 autoencoder 与 residual vector quantization bottleneck 组成，产生多个固定词表的并行 audio token streams。([audiocraft.metademolab.com](https://audiocraft.metademolab.com/encodec.html?utm_source=chatgpt.com))

该方向对卫星通信有两点价值。第一，生成式解码器可在极低码率下补偿传统参数模型难以表达的自然度和宽带细节。第二，离散 token 便于进一步结合信道保护、丢包隐藏、重复传输和熵编码。Descript Audio Codec 的论文与代码说明其为 improved RVQGAN，采用 RVQGAN 结构进行高保真音频压缩；TR 26.940 对 DAC 的分析也说明，DAC 将输入下采样为 latent representation，再通过 RVQ 量化，每个 codebook 对应约 10 bit 或 0.5 kbit/s，从而支持不同码率组合。([arxiv.org](https://arxiv.org/pdf/2306.06546?utm_source=chatgpt.com)) 2

### 1.3 研究 RVQ、可伸缩码率与固定码率专用训练的取舍

RVQ 是当前神经音频 codec 的主流量化机制之一。SoundStream 使用 RVQ，并通过 structured dropout 训练一个可变码率模型；论文指出，该模型可在 3–18 kbit/s 之间运行，且相对固定码率模型质量损失很小。([arxiv.org](https://arxiv.org/abs/2107.03312?utm_source=chatgpt.com)) EnCodec 也采用 quantized latent space 和流式 encoder-decoder 结构，并引入语言模型式 entropy coding 进一步压缩 token 序列；EnCodec 论文报告，entropy coding 可在不改变 decoder 的情况下进一步降低码率，但会增加编码端复杂度和时延。([arxiv.org](https://arxiv.org/pdf/2210.13438?utm_source=chatgpt.com))

但 TR 26.940 对 DAC 和 DAC-IBM 的比较提醒，标准化不能简单选择“可伸缩码率模型”。TR 26.940 指出，同一架构下，面向固定 1.5 kbit/s、speech data fine-tuned 的 DAC-IBM 显著优于默认可伸缩 DAC；文档结论明确指出，bitrate scalability 在低码率下可能带来显著性能代价，而针对特定 operating mode 训练的模型更高效。3

因此，立项中建议将量化机制细化为三类研究任务：

| 研究任务 | 目的 | 标准化关注点 |
|---|---|---|
| RVQ / 多级 VQ | 将语音压缩成多层离散 token | codebook 数量、token rate、码率粒度 |
| Entropy coding | 利用 token 统计冗余进一步降码率 | 是否增加时延、是否影响实时性、丢包后同步恢复 |
| 固定码率专用训练 | 面向 0.8/1.2/2.4 kbit/s 等目标点优化 | 比可伸缩模型更适合标准候选筛选 |

### 1.4 研究 AI codec 的鲁棒性风险：hallucination、说话人保持和非语音输入

AI codec 的风险不只是“音质差”，还包括传统 codec 不明显的问题。TR 26.940 第 9 章明确将 hallucination，即 word/phone confusion，列为超低码率语音编码可能的质量损伤，并指出 hallucination 是 ML-based coding system 特有问题，而不是 AMR、AMR-WB、EVS 等传统信号处理 codec 的典型问题。4

因此，项目不应只做 MOS 排名，还应专门研究：

- 词错误、音素错误、语义保持；
- 说话人身份保持；
- 情绪和韵律保持；
- noisy speech、music、background sound、overlapping talker 下的异常生成；
- 紧急呼叫中背景声音是否被错误消除或错误生成。

## 二、编解码器设计约束与端侧部署研究

### 2.1 建立 codec 设计约束全集

TR 26.940 第六章列出的 ULBC 设计约束包括：bit rates、sample rate and audio bandwidth、frame length、complexity and memory demands、algorithmic delay、PLC、noise suppression、DTX/VAD/CNG、non-speech robustness。该集合可直接作为国家卫星通信 ULBC 标准的设计约束框架。5

建议将设计约束细化为以下标准化条目：

| 类别 | 建议研究项 |
|---|---|
| 基本 codec 参数 | 采样率、音频带宽、帧长、look-ahead、算法时延 |
| 码率参数 | 固定码率、可变码率、DTX 平均码率、SID/CNG 比特开销 |
| 模型参数 | 参数量、模型大小、权重量化精度、激活精度 |
| 计算复杂度 | MAC/s、MMACS、GFLOP/frame、RTF |
| 存储需求 | ROM、RAM、scratch buffer、state memory |
| 端侧部署 | CPU、DSP、NPU、混合后端、fallback 策略 |
| 功耗 | active power、DRAM 访问功耗、NPU 启动开销 |
| 实时性 | 单帧 worst-case 推理时间、连续运行稳定性、tail latency |

### 2.2 模型大小与内存约束

TR 26.940 明确指出，codec/model size 是复杂度和内存评估中较通用的参考指标，因为它直接影响内存需求和功耗；大模型会引起更频繁 DRAM 访问，从而提高功耗。6

该点对端侧部署非常关键。DAC 在 TR 26.940 中被分析为 76.9M 参数、293 MB 模型大小；其 20 ms frame 约 1.4 GFLOP，320 ms frame 约 31.6 GFLOP。TR 26.940 的实测结果显示，该模型在 Snapdragon 8 Gen 2 上所有测试配置均未达到实时，最好 RTF 仍为 2.125。7

因此，立项中建议规定候选 codec 必须提交：

1. 模型参数量；
2. 权重文件大小；
3. 运行时 RAM 峰值；
4. persistent state memory；
5. 每帧 scratch buffer；
6. encoder / decoder 分别的模型大小；
7. 是否支持 INT8、INT16、FP16、FP32；
8. 不同精度下的质量损失和 RTF 变化。

### 2.3 复杂度指标：不能只看 TOPS，应同时看 RTF 和实测功耗

TR 26.940 指出，AI codec 的核心计算是矩阵乘和 MAC operations，NPU/TPU 通常使用 TOPS 表示算力；但文档也强调，NPU 实际性能不能只由 raw TOPS 决定，如果计算图存在不规则、顺序依赖或不支持算子，可能出现 CPU fallback，从而降低性能。8

这一点也得到硬件评估领域的支持。Sze 等人在 IEEE Solid-State Circuits Magazine 文章《How to Evaluate Deep Neural Network Processors: TOPS/W Alone Considered Harmful》中指出，仅用 TOPS/W 评价 DNN 处理器是不充分的，因为实际性能还受数据流、存储访问、利用率、模型结构和数值精度影响。TR 26.940 也引用该类观点，并指出外部 DRAM 操作可能主导实际功耗。9

因此，标准化项目建议采用“三层复杂度指标”：

| 层级 | 指标 | 用途 |
|---|---|---|
| 理论复杂度 | MAC/s、GFLOP/frame、参数量 | 初筛模型复杂度 |
| 实测复杂度 | RTF、单帧平均/最大推理时间、tail latency | 判断实时性 |
| 能效指标 | mW、mJ/frame、mJ/speech-second | 判断端侧可部署性 |

### 2.4 部署硬件：CPU、DSP、NPU 都应作为标准化对象

TR 26.940 对 Lyra V2 的代码级分析显示，Lyra V2 使用 TFLite + XNNPACK CPU backend，无 NNAPI、Hexagon、CoreML、TPU delegate，且线程数为 1；其在 2021 年高端手机 CPU 上 20 ms frame 平均总处理时间约 0.525 ms，对应约 38× real-time。Google 官方 Lyra V2 资料也报告，在 Pixel 6 Pro 上编码和解码 20 ms audio frame 仅需 0.57 ms，约 35× real-time。10 ([opensource.googleblog.com](https://opensource.googleblog.com/2022/09/lyra-v2-a-better-faster-and-more-versatile-speech-codec.html?utm_source=chatgpt.com))

这说明，端侧部署并不必然依赖 NPU。相反，CPU-only 路径可作为互通和低门槛部署的 baseline。与此同时，TR 26.940 也指出，DSP 具有低硅面积、低功耗、低发热、单线程实时同步等优势，ULBC 也应考虑 DSP-enabled UE。11

建议立项中明确三类实现等级：

| 等级 | 部署目标 | 标准化意义 |
|---|---|---|
| Level 0 | CPU-only 实时 | 最低互通门槛 |
| Level 1 | CPU + DSP 优化 | 低功耗语音主路径 |
| Level 2 | CPU/DSP/NPU 混合 | 高质量或增强功能路径 |

## 三、大时延、抖动和丢包下的编码表现研究

### 3.1 建立 GEO/MEO/LEO 不同卫星链路的时延模型

TR 26.940 对 GEO 口到耳时延进行了分解，包含 UE delay、codec frame size、algorithmic delay、jitter buffer、vendor-specific delay、GEO propagation delay、core network delay、transcoding delay 等。文档指出，其 M2E 估计假设 jitter-free 和无网络拥塞，但实际部署中会出现 jitter 和网络条件变化。12

3GPP TS 22.261 对卫星接入时延也给出要求，例如 GEO 卫星接入端到端时延可达约 277 ms，MEO 约 203 ms，LEO 约 31 ms；这些值说明不同轨道类型对 codec frame、jitter buffer 和交互体验的约束不同。([itecspec.com](https://itecspec.com/3gpp/22.261/s/7.4.2?utm_source=chatgpt.com))

因此，项目应至少建立三组链路模型：

| 链路 | 重点约束 |
|---|---|
| GEO | 极大传播时延，优先降低 codec 和 buffering 额外时延 |
| MEO | 中等传播时延，允许一定 bundling，但需控制交互质量 |
| LEO | 传播时延较低，但 Doppler、切换和链路波动可能更复杂 |

### 3.2 研究 voice bundling period、frame size 与协议开销的折中

TR 26.940 指出，GEO 链路码率受限，为降低协议开销，需要考虑更大 frame size、更大 voice bundling period 或 frame aggregation。文档考虑 80、160、320 ms 三种 voice bundling period，并指出不含传播时延的空口时延等于 bundling period。13

该问题对标准化非常关键：更长 bundling 可降低 header overhead、提高频谱效率，但会增加口到耳时延，并可能恶化 PLC。建议项目研究以下组合：

| Codec frame | Bundling period | 研究目的 |
|---:|---:|---|
| 20 ms | 80 ms | 接近传统语音帧，PLC 友好 |
| 40 ms | 80/160 ms | 低码率与时延折中 |
| 80 ms | 160 ms | 降低协议开销 |
| 160 ms | 160/320 ms | 极低码率高压缩场景 |
| 320 ms | 320 ms | 仅作为上限或非实时参考 |

### 3.3 研究 jitter buffer 与 packet loss concealment 的联合设计

RTP/RTCP 是实时媒体传输的基础协议。RFC 3550 明确指出，interarrival jitter 可作为短期网络拥塞指标，packet loss 反映持续拥塞，而 jitter 可在丢包发生前提示瞬时拥塞。([datatracker.ietf.org](https://datatracker.ietf.org/doc/html/rfc3550?utm_source=chatgpt.com)) 3GPP MTSI/EVS 体系中也已有 packet loss handling、jitter buffer management、EVS lost packet concealment、CNG、DTX 等标准化组件；3GPP 26 系列列出了 TS 26.447 EVS lost packet concealment、TS 26.448 EVS jitter buffer management、TS 26.449 CNG、TS 26.450 DTX。([3gpp.org](https://www.3gpp.org/dynareport/26-series.htm?utm_source=chatgpt.com))

因此，ULBC 标准化不能只规定 codec bitstream，还要定义接收端时序恢复和丢包处理能力。建议研究：

1. 固定 jitter buffer 与自适应 jitter buffer；
2. 80/160/320 ms bundling 下的最小 playout delay；
3. 连续丢包、随机丢包、突发丢包、乱序、重复包；
4. token 级 PLC，而不仅是 waveform 级 PLC；
5. RVQ 多层 token 的 unequal error protection；
6. 低优先级 codebook 丢失时的 graceful degradation；
7. CNG / DTX 与 packet loss concealment 的状态机关系。

### 3.4 研究 AI codec 的 loss-aware training

TR 26.940 的 DAC PLC 实验显示，在 80 ms packet 中，连续 4 个 20 ms block 丢失并使用前一 block 替代是一种基本 PLC 方式；interleaved drop and repeat 可将连续丢失扩散到两个 packet 中，实验中 error rate 越高，interleaving 收益越明显。14

更重要的是，TR 26.940 明确指出，实验中的 DAC 模型并未针对 packet error loss 训练，因此可通过合适训练或设计提升 error resilience；文档结论还指出，最佳编码性能需要针对特定 bitrate 和特定 BLER 进行训练。15

因此，项目应将“loss-aware training”列为 AI codec 候选技术要求，包括：

- 随机 token dropout 训练；
- burst loss pattern 训练；
- RAN trace-driven loss training；
- codebook-level erasure training；
- encoder-side redundancy；
- decoder-side generative concealment；
- BLER-aware bitrate allocation。

## 四、指标体系与测试方法研究

### 4.1 建立“质量—可懂度—身份—鲁棒性—复杂度”五类指标

TR 26.940 第 9 章指出，ULBC 可能带来的损伤包括 listening-only quality loss、audio bandwidth loss、intelligibility impairment、speaker identifiability impairment、prosodic impairment、hallucination，以及对 non-speech input 的敏感性。16

因此，指标体系不能只包含 MOS。建议分为五类：

| 指标类别 | 典型指标 |
|---|---|
| 听感质量 | MOS、DMOS、MUSHRA、ACR、DCR |
| 可懂度 | MRT/DRT、ASR WER、人工转写准确率 |
| 说话人保持 | speaker similarity MOS、speaker verification EER |
| 鲁棒性 | noisy speech MOS、packet loss MOS、tandeming MOS |
| 部署复杂度 | RTF、mW、mJ/frame、RAM、ROM、模型大小 |

### 4.2 主观测试：ACR/DCR 是基础，但需要扩展

ITU-T P.800 是传统语音质量主观测试基础，其中 DCR 方法使用高质量固定参考，对被测系统的退化程度进行五级评分，适用于评估类似数字语音处理算法之间的小退化。([itu.int](https://www.itu.int/rec/dologin_pub.asp?id=T-REC-P.800-199608-I%21%21PDF-E&lang=e&type=items&utm_source=chatgpt.com)) TR 26.940 也指出，AMR、AMR-WB、EVS 标准化中使用过 P.800 ACR 和 DCR，ACR 常用于 clean speech，DCR 常用于 SWB clean speech、mixed-bandwidth、speech + background noise、mixed/music 质量评价。17

但 ULBC 需要扩展测试方法。TR 26.940 建议考虑 DRT、MRT、speaker similarity MOS、speaker verification/identification、prosodic naturalness MOS、intonation recognition、transcription test、phoneme recognition、ASR test 等方法。18

### 4.3 噪声测试：按噪声类型和 SNR 分层

TR 26.940 建议参考 EVS 测试框架，在 clean speech、stationary noise、non-stationary noise 下测试 ULBC；示例条件包括 stationary noise 如 car noise，SNR 15 dB，以及 non-stationary noise 如 street/babble，SNR 20–25 dB。19 3GPP TR 26.952 的 EVS 性能表征也包含 office noise 20 dB SNR 条件下的 EVS-SWB noisy speech performance 测试。([etsi.org](https://www.etsi.org/deliver/etsi_tr/126900_126999/126952/17.00.00_60/tr_126952v170000p.pdf?utm_source=chatgpt.com))

对于包含 noise suppression 的系统，应引入 ITU-T P.835。P.835 明确面向包含 noise suppression algorithm 的 speech communication system，采用三个独立评分维度：speech signal quality、background noise quality 和 overall quality。([itu.int](https://www.itu.int/rec/dologin_pub.asp?id=T-REC-P.835-200311-I%21%21PDF-E&lang=e&type=items&utm_source=chatgpt.com))

因此，建议标准化测试矩阵如下：

| 测试场景 | SNR | 方法 | 输出指标 |
|---|---:|---|---|
| Clean speech | - | P.800 ACR/DCR | MOS/DMOS |
| Car noise | 15 dB | P.800 DCR/P.835 | speech MOS、noise MOS、overall MOS |
| Street/Babble | 20–25 dB | P.800 DCR/P.835 | noisy MOS、可懂度 |
| 低 SNR 扩展 | -5 到 15 dB | P.835/ASR | WER、hallucination rate |
| Emergency background | 按场景 | 专项主观测试 | 背景信息保留度 |

### 4.4 客观指标：用于表征和一致性测试，不用于最终选择

TR 26.940 对 PESQ、POLQA、ViSQOL-S、WARP-Q、DNSMOS、NISQA、NORESQA、UTMOS、SCOREQ、NOMAD、SSLMOS 等指标做了相关性分析，但结论是：codec selection 中 subjective testing 仍是 golden reference，objective metrics 不推荐作为 codec selection criteria，也不推荐用于 codec tuning；不过客观指标可用于 codec characterization 和 conformance testing。20

ITU-T P.862 PESQ 当前状态为 withdrawn，P.863 POLQA 是后续更主要的语音客观质量标准；因此，立项材料中不宜把 PESQ 作为唯一评价依据。([itu.int](https://www.itu.int/rec/t-rec-p.862?utm_source=chatgpt.com))

### 4.5 建议形成的指标体系交付物

最终建议输出四类标准化文档：

1. **主观测试规范**
   - ACR、DCR、P.835；
   - clean/noisy/loss/tandem/emergency 场景；
   - 多语言、多说话人、多设备声学条件。

2. **客观指标使用指南**
   - POLQA、ViSQOL、DNSMOS、ASR WER、speaker verification；
   - 明确“可用于筛查和表征，不作为最终选择唯一依据”。

3. **复杂度与部署测试规范**
   - CPU/DSP/NPU 三后端；
   - RTF、tail latency、RAM、ROM、功耗；
   - 连续运行稳定性和 thermal throttling。

4. **卫星信道鲁棒性测试规范**
   - RAN trace；
   - BLER；
   - jitter；
   - burst loss；
   - bundling period；
   - PLC/CNG/DTX 状态机。

## 建议立项表述

本项目建议以 TR 26.940 为基础，结合 ITU-T P.800/P.835、3GPP EVS 性能评价体系、RTP/RTCP 网络抖动统计机制，以及 SoundStream、Lyra V2、EnCodec、DAC 等 AI codec 公开研究，开展面向单一国家卫星通信系统的极低码率语音编解码器标准化研究。项目重点不只是提出一个低码率模型，而是建立完整的“AI 编码技术—端侧部署约束—卫星信道鲁棒性—主客观测试体系”闭环。TR 26.940 已证明 AI codec 在 1 kbit/s 级别具备显著质量潜力，但也指出当前 AI codec 仍缺少完整的 channel resilience、DTX/CNG、移动端复杂度约束和标准化测试体系；因此，该项目具备明确的技术必要性和标准化价值。