1. 第一个mermaid
``` mermaid
flowchart TD

A[Input speech frame] --> B[Signal buffer update]
B --> C[CLDFB analysis]
C --> D[VAD estimation]
D --> E[DTX hangover processing]
E --> F[Energy estimation]
F --> G[Speech / Music classification]
G --> H[Pitch / periodicity analysis]
H --> I[Core mode preparation]
I --> J[Update encoder states]
```

``` mermaid
flowchart TD

A[Input speech frame] --> B[CLDFB analysis]
B --> C[Resample + Preemphasis]
C --> D[Spectral analysis]
D --> E[Noise pre-estimation]
E --> F[VAD decision]
F --> G[LP analysis]
G --> H[Pitch analysis]
H --> I[Noise estimation update]
I --> J[Signal classification]
J --> K[Core preparation]
```
