# GSM FR Test Vector 文件关系总结

# DISK1：普通 Bit Exact 测试

最容易理解：

```text
.inp → .cod → .out
```

## 文件组队关系

| 输入文件 | 编码输出 | 解码输出 |
|---|---|---|
| Seq01.inp | Seq01.cod | Seq01.out |
| Seq02.inp | Seq02.cod | Seq02.out |
| Seq03.inp | Seq03.cod | Seq03.out |
| Seq04.inp | Seq04.cod | Seq04.out |
| Seq05.inp | Seq05.cod | Seq05.out |

## 使用方式

### Encoder 测试

```text
Seq01.inp
   ↓ encoder
生成 cod
   ↓ compare
Seq01.cod
```

### Decoder 测试

```text
Seq01.cod
   ↓ decoder
生成 PCM
   ↓ compare
Seq01.out
```

## DISK1 本质

```text
普通语音 bit exact 测试
```

---

# DISK2：Homing / Reset 测试

文件关系：

```text
仍然是：
.inp → .cod → .out
```

只是：

```text
输入里包含 homing frame
```

## 文件组队关系

| 输入文件 | 编码输出 | 解码输出 |
|---|---|---|
| Seq01h.inp | Seq01h.cod | Seq01h.out |
| Seq02h.inp | Seq02h.cod | Seq02h.out |

## 使用方式

与 DISK1 完全一样：

### Encoder

```text
Seq01h.inp
   ↓ encoder
生成 cod
   ↓ compare
Seq01h.cod
```

### Decoder

```text
Seq01h.cod
   ↓ decoder
生成 PCM
   ↓ compare
Seq01h.out
```

## DISK2 本质

```text
测试 homing/reset 后
是否还能 deterministic
```

---

# DISK3：Synchronization + Advanced Homing

DISK3 结构最复杂。

实际上分成两部分。

---

# 第一部分：Sync000~159

这些：

```text
不是成对 compare 文件
```

## 文件关系

| 文件 | 含义 |
|---|---|
| Seqsync.inp | synchronization 输入PCM |
| Sync000.cod ~ Sync159.cod | 不同offset产生的编码输出 |

## 使用方式

```text
Seqsync.inp
   ↓ encoder（不同sample offset）
生成
Sync000.cod ~ Sync159.cod
```

然后：

```text
Syncxxx.cod
   ↓ decoder
观察是否触发正确 homing response
```

## 核心特点

```text
没有固定 .out compare 文件
```

因为：

```text
这是 synchronization 搜索
不是 bit exact compare
```

---

# 第二部分：Homing Verification

这一部分：

```text
又重新回到：
.inp → .cod → .out
```

模式。

## 文件组队关系

### 完整三件套

| 输入文件 | 编码输出 | 解码输出 |
|---|---|---|
| Seq03h.inp | Seq03h.cod | Seq03h.out |
| Seq04h.inp | Seq04h.cod | Seq04h.out |

### Decoder-only

| 输入文件 | 解码输出 |
|---|---|
| Homing01.cod | Homing01.out |
| Seq05h.cod | Seq05h.out |

### Encoder-only

| 输入文件 | 编码输出 |
|---|---|
| Seq06h.inp | Seq06h.cod |

## DISK3 第二部分本质

```text
高级 homing/reset verification
```

---

# 最终一页总结（适合演示）

| DISK | 文件关系 | 作用 |
|---|---|---|
| DISK1 | `.inp → .cod → .out` | 普通 bit exact |
| DISK2 | `.inp → .cod → .out` | Homing/reset bit exact |
| DISK3-同步部分 | `Seqsync.inp → Sync000~159.cod` | 搜索正确 frame alignment |
| DISK3-homing部分 | `.inp → .cod → .out` | 高级 homing/reset 测试 |

---

# 给非编解码人员的最简理解

## DISK1

```text
正常功能是否正确
```

## DISK2

```text
reset后是否还能正确工作
```

## DISK3

```text
如何找到正确的20ms帧边界
+
更复杂的reset测试
```
