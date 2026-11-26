---
title: The Shape of a Signal
author: Ada Lovelace
theme: midnight
clock: true
---

@slide layout=title section="Keynote"

# The Shape of a Signal

Fourier, fast transforms, and why your headphones lie to you

---

@toc title="Roadmap" start=1

## Roadmap

---

## Why care?

Every sound you have ever loved is a sum of **sines**.

- Music is a *spectrum* — energy spread across frequencies
- Compression throws away what you cannot hear
- `ffmpeg` does all of this while you sleep

@note title="A useful lie"
The ear is a Fourier transform made of meat.

---

@slide section="Part I · Analysis"

# The transform

@eq style=double title="Continuous Fourier transform" number=1

$$
\hat{f}(\xi) = \int_{-\infty}^{\infty} f(t)\, e^{-2\pi i \xi t}\,dt
$$

@notes
Pause here. The key idea: a signal and its spectrum are the same object
seen from two sides. Point at the exponent — that is a spinning clock.
@qnotes

and the inverse brings it home:

@eq style=double title="Inverse transform" number=2

$$
f(t) = \int_{-\infty}^{\infty} \hat{f}(\xi)\, e^{2\pi i \xi t}\,d\xi
$$

---

## A worked example

@eq style=rounded title="Two familiar identities" number=3

$$
\begin{aligned}
\sum_{k=0}^{n} ar^k &= a\frac{1-r^{n+1}}{1-r} \\
\frac{d}{dx}\left[\sin x\right] &= \cos x \\
\lim_{x \to 0}\frac{\sin x}{x} &= 1
\end{aligned}
$$

---

## Table styles

@table title="Algorithm comparison" caption="lines=true draws row separators" lines=true

| Transform | Complexity | When |
|:----------|:-----------|:-----|
| DFT | $O(n^2)$ | never |
| FFT | $O(n \log n)$ | always |
| DCT | $O(n \log n)$ | JPEG |
| Wavelet | $O(n)$ | sparse signals |

---

## Compact tables

@table compact=true

| Property | Value |
|:---------|:------|
| Sample rate | 48 kHz |
| Window | Hann |
| Bin width | 23.4 Hz |

---

## Numbers, visually

@chart type=bar title="Transform cost" caption="lower is better"

| Transform | Build (ms) | Query (ms) |
|:----------|-----------:|-----------:|
| DFT       | 42         | 18         |
| FFT       | 9          | 3          |
| Wavelet   | 14         | 6          |

---

## Trends over time

```chart
type=line
title=Throughput over releases
height=6
Version,r1,r2,r3,r4
v1,18,22,27,31
v2,24,29,34,41
```

---

## Where the time goes

@chart type=donut title="One release cycle" caption="engineering hours" height=7 colors="#7aa2f7,#bb9af7,#9ece6a,#e0af68"

| Area     | Hours |
|:---------|------:|
| Research | 28    |
| Build    | 44    |
| Testing  | 19    |
| Docs     | 9     |

---

## Pictures, by path alone

Just drop a path on its own line — relative to this deck — and proscenium paints
it with the Kitty graphics protocol. `![alt](path)` and
`@image path width=30` work too.

assets/demo.png

---

@slide layout=section section="Part II · Implementation"

# Under the hood

---

## Code

```python
import numpy as np

def spectrum(x, rate=48_000):
    window = np.hanning(len(x))
    return np.abs(np.fft.rfft(x * window))

peak = spectrum(samples).argmax()
print(f"{peak * rate / len(samples):.1f} Hz")
```

---

## Guardrails

@warning title="Watch the Nyquist limit"

Energy above half the sample rate folds back into your spectrum. Filter
before you sample, or the alias is permanent.

@tip title="Rule of thumb"

Use a Hann window when the exact frequency matters more than the exact
amplitude.

---

## Side by side

@columns 2

### Two columns

- good for comparisons
- keep headings short
- Rich wraps each column

### When to use them

1. code beside prose
2. two competing ideas
3. before/after results

@qcolumns

---

## Matrices

$$
A = \begin{pmatrix}
a_{11} & a_{12} & \cdots & a_{1n} \\
a_{21} & a_{22} & \cdots & a_{2n} \\
\vdots & \vdots & \ddots & \vdots \\
a_{m1} & a_{m2} & \cdots & a_{mn}
\end{pmatrix}
\qquad
\det(A) = \sum_{\sigma \in S_n} \operatorname{sgn}(\sigma) \prod_{i=1}^{n} a_{i,\sigma(i)}
$$

---

## Long equations

@eq style=square title="2-D Fourier transform"

$$
\int_{-\infty}^{\infty}\int_{-\infty}^{\infty} f(x,y)\,e^{-2\pi i(ux+vy)}\,dx\,dy = F(u,v) = G(u) + H(v) + K(u,v) + L(u,v)
$$

---

## Lists, nested

1. First, sample the signal
   - at 48 kHz
   - with a Hann window
2. Then transform
   ```python
   X = np.fft.rfft(x)
   ```
3. Finally, **listen**

- [x] write the talk
- [x] rehearse it
- [x] panic anyway

---

@slide layout=top section="Builds" transition=rise

## One idea at a time

A build lets the room read before the next claim lands.

@reveal items

- state the claim
- show the evidence
- land the conclusion

Press `space` once per line; `←` walks back. This slide uses `transition=rise`
and a three-step list reveal.

---

@slide layout=split gap=3 divider=true

## Two at once

### Before

- manual notes
- scattered screenshots
- no shared vocabulary

### After

- one source of truth
- live charts and math
- the same story everywhere

---

@slide layout=top

## A slide that keeps going

Scroll with `J` / `K` (or `d` / `u` for a half page). Nothing is cropped — a
dense slide is just a long canvas.

1. Sampling turns the world into numbers
2. Windowing keeps the edges from lying
3. The transform trades time for frequency
4. The inverse transform gets you home

```python
def frame(signal, window):
    return signal * window
```

> A long slide is useful for live coding, guided walkthroughs and dense
> reference material. Press `f` to squeeze the spacing when you want more on
> screen at once, and `w` to choose how wide the content column is.

- more room on wide terminals
- full-width by default, `width: 92` to opt out
- compare view with `c`

---

# Thanks

Questions?
