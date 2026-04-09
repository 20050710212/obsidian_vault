# 背景
1. find tagets 是EVS 的ACELP中最重要的函数，输入是speech 和residual，输出如下。利用这些输出，后续分别做pit_encode_fx, inov_encode_fx
xn: closed-loop pitch search target vector
cn: target vector in residual domain
h1:  impulse response
2. find target的核心变化如下
residual → 1/A(z) → predicted speech
speech − predicted speech → error
error → A(z) → xn (pitch target)
3. 注释中有如下解释Instead of subtracting the zero-input response of filters from the weighted input speech, the above configuration is used to compute the target vector. 本文主要解释该注释。
# ACELP 优化目标
ACELP的target不是speech，而是加权误差信号。冲击响应h(n)是weighted sysnthessi filter的响应，用于adaptive和algebraic codebook搜索，搜索是weighted domain中完成的。

ACELP的目标函数是
$E=\sum[W(z)(s(n)-\hat{s}(n))]^2$
其中 $s(n)$ 原始语音，$\hat{s}(n)$ 是合成语音，$W(z)$ 是感知加权滤波器，定义
$d(n)=W(z)s(n)$   $y(n)=W(z)\hat{s}(n)$ ，
则ACELP的目标函数变为
$E=\sum[d(n)-y(n))]^2$
其中 $d(n)$ 即为weighted speech。

weighted synthesis filter 是IIR
$H_w(z)=\frac{W(z)}{A(z)}$， 而IIR的响应可以分解为零状态响应和零输入响应
$d(n)=d_{zs}(n)+d_{zi}(n)$
其中$d_{zs}(n)$ 为零状态响应， $d_{zi}(n)$ 为零输入响应

编码器搜索的目标是$d_{zs}(n)$， 为什么？
当编码当前子帧时，前面子帧已经合成过，合成滤波器仍保留有过去excitation引入的状态信息，需要减掉这部分信息。
### 显式数学公式
$target = d_{zs}(n)＝d(n)－d_{zi}(n) = H_w(z)s(n) -H_w(z)\{0\} with\ mem\_syn$
### 代码实现公式
$S(z)=\frac{1}{A_q(z)}$
$mem = s_{past}-m_{past}$
$y = S\{r(n)\} with\ mem = y_{zs}(r)+y_{zi}(s_{past}-m_{past})$
residual 经过 weighted synthesis  + speech 的状态响应=weighted speech





