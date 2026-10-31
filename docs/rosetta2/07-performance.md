# Rosetta 2: Performance

*Scope.* How fast translated x86-64 code runs on Apple silicon compared with native arm64
builds; where it is slow and why; what Apple tells developers; and how Rosetta compares with
other translators, including ARM → x86 translators, which are the direction this project
cares about. Mechanisms are explained in [03-translation-techniques.md][03]. Hardware assists
(TSO, PF/AF flags, alternate FP mode) are in [04-hardware-assists.md][04]. The runtime is in
[02-architecture-and-runtime.md][02].

*Provenance labels.* **[Apple]** = Apple documentation or WWDC. **[Benchmark: source]** = a
measurement (who ran it is in the link). **[RE: author]** = reverse-engineering or developer
analysis. **[Inferred]** = my reasoning.

*How to read the numbers.*
- "Rosetta/native" means translated-x86 speed as a fraction of the native arm64 build **on
  the same Mac** (1.0 = parity). Times are converted so that higher is better.
- Many data points are single user uploads or blog posts, not controlled studies. Geekbench
  minor versions, compilers and libraries differ between the x86 and arm64 builds, so part of
  any gap comes from compilers and code paths rather than from Rosetta.
- The macOS version and chip are given wherever the source states them.

---

## Summary

| Workload class | Rosetta / native (same Mac) | Representative evidence |
|---|---|---|
| General CPU suites, M1 era | **~0.73 to 0.79** | Geekbench 5, MacBook Air M1, macOS 11 ([MacRumors][mr-gb5], [Tencent][qq]) |
| SPEC CPU, M1 | **0.7 to 0.8 typical**; >0.9 when memory-bound; about 0.5 for 502.gcc_r | [AnandTech][anand-rosetta] |
| Integer apps and interpreters | **~0.71 to 0.84** | 7-zip 0.71 (M1), LuaJIT suite 0.75 (M1 Max), sysbench in a Linux VM 0.84 (M1 Max) ([box86.org][box-2022], [Cawley][cawley], [docker #6641][docker6641]) |
| Modern SIMD/ML-heavy suites | **~0.48 to 0.51** overall; subtests from 0.07 to 0.95 | Geekbench 6, M2 Max, macOS 13 ([GB6 Rosetta][gb6-ros], [GB6 native][gb6-nat]) |
| JIT-heavy apps (browsers, JVM, emulators) | **~0.36 to 0.75** | Chrome 0.55 to 0.60; JVM builds 0.36 to 0.53; Dolphin ~0.65 to 0.76 |
| x87-heavy code | Stock helpers are **4 to 10× slower** than double-precision replacements | [rosettax87][rx87], [box64 #2595][box64-2595] |
| AVX2 code paths (macOS 15+) | **~2.7 to 3× slower than the same program's SSE2 path** under Rosetta | [avx-dive issue #1 comments][avxdive-i1], [Qiita][qiita-avx] |
| GPU-bound apps and games | **~1.0** | GFXBench under Rosetta, no penalty ([AnandTech][anand-gpu]); Baldur's Gate 3 within 2 to 4 fps ([iThinkDiff][bg3]) |
| First launch | ~20 s for an Office app (2020); <12.5 ms for ~100 KB of code | [MacRumors][mr-office], [Eclectic Light][elc-oah] |

Headline: Rosetta usually delivers **70 to 80 % of native** on classic integer and FP code,
close to 100 % on memory-bound or GPU-bound work, and much less on JIT-on-JIT, x87, AVX2 and
modern SIMD/ML-heavy code. On M1 even the translated speed beat contemporary Intel Macs in
single-thread work.

---

## 1. Rosetta versus native on the same Mac

### 1.1 Launch era: M1, macOS 11 (Nov 2020 to 2021)

| Benchmark | Machine / OS | Native | Rosetta | Ratio | Source |
|---|---|---|---|---|---|
| Geekbench 5 single / multi | MacBook Air M1 8 GB, macOS 11.0 | 1687 / 7433 | 1313 / 5888 | 0.78 / 0.79 | [Benchmark: MacRumors, 15 Nov 2020][mr-gb5] |
| Geekbench 5 single / multi (second sample) | MacBook Air M1, macOS 11 | 1750 / 7633 | 1282 / 5792 | 0.73 / 0.76 | [Benchmark: Tencent News, 18 Nov 2020][qq] |
| Geekbench 5 "Clang" subtest | MacBook Air M1 (two separate uploads) | 1682 (GB 5.4.1, macOS 11.2.3) | 1253 (GB 5.3.1 x86) | ~0.74 | [Benchmark: GB native][gb5-nat], [GB Rosetta][gb5-ros] |
| SPEC2006 / SPEC2017 | Mac mini M1, macOS 11 | — | — | Memory-heavy tests ">90%"; worst are compute-bound 456.hmmer and 464.h264ref; 470.lbm (tight loop) low; **502.gcc_r 49.87 %**; fp2017 "70-80%" | [Benchmark: AnandTech, 17 Nov 2020][anand-rosetta] |
| Chrome: Speedometer 2.0 / JetStream2 / MotionMark 1.1 | M1 Mac, Nov 2020 | 210 / 156.9 / 726.4 | 116 / 93.1 / 435.7 | 0.55 / 0.59 / 0.60 | [Benchmark: Ars Technica][ars-chrome] via [MacRumors][mr-chrome] |
| 7-zip 21 built-in benchmark | MacBook Pro M1, macOS (Mar 2022) | 47,239 | 33,746 | 0.71 | [Benchmark: box86.org][box-2022] |
| Python pyperformance (about 60 tests) | M1, macOS 11.1 | — | — | Native typically 1.3 to 1.6× faster (ratio ~0.63 to 0.77); interpreter **startup 2.8 to 3.1× faster** natively (~0.33) | [Benchmark: diewland][pyperf] |
| Gradle build (x86 AdoptOpenJDK vs arm64 Azul) | M1, May 2021 | 8 s | 22 s | 0.36 | [Benchmark: gradle #17323][gradle] |
| `sbt clean compile` (JDK 11, x86 vs arm64) | Apple silicon, Nov 2021 | 12.9 s | 24.5 s | 0.53 | [Benchmark: A. Huélamo][sbt] |
| `flow check` (OCaml tool) | M1, May 2021 | 1.58 s | 3.52 s | 0.45 | [Benchmark: facebook/flow #8664][flow] |
| Dolphin GC/Wii emulator, 5 scenes (fps; x86-64 JIT under Rosetta vs native AArch64 JIT) | MacBook Air M1 | 120 / 111 / 50 / 80 / 39 | 79 / 72 / 37 / 61 / 49 | 0.66 / 0.65 / 0.74 / 0.76 / 1.26 | [Benchmark: Dolphin progress report][dolphin-pr] (values read off the chart; the last scene is an MMU title the AArch64 JIT then ran in its interpreter); the native-port PR claims "30-50%" speed-up ([PR #9441][dolphin-9441]) |
| SIMD audio plug-in | Mac mini M1, Jan 2021 | — | — | "no discernible difference" | [Benchmark: Physical Audio][physaudio] |
| Apple's own demo (local 10 MB transfer test) | Apple silicon development Mac, Jun 2020 | 21 ms | 29 ms | 0.72 | [Apple WWDC20 10214][wwdc10214] |
| Geekbench 5 on the DTK (A12Z, Big Sur beta) | Developer Transition Kit, Jun 2020 | — | ~830 / ~2,800 | ~26 % / 38 % behind a native iPad Pro (different OS and clocks) | [Benchmark: HotHardware][dtk-hh], [EveryMac][dtk-em] |

Notes:
- AnandTech required the x86 build to stay within SSE4.2, the ceiling at the time
  ([AnandTech][anand-rosetta]).
- Their Cinebench R23 run under Rosetta "is not only able to keep up with past Mac iterations
  but still also beat them" ([AnandTech, page 2][anand-p2]). I could not find a primary source
  for the exact Cinebench numbers, so they are omitted.

### 1.2 Later chips (2023 to 2025)

**Geekbench 6 on M2 Max.** Rosetta: GB 6.0.0 x86, macOS 13.2 ([upload][gb6-ros]). Native:
GB 6.1.0, macOS 13.4 ([upload][gb6-nat]). Overall **0.48 single-core, 0.51 multi-core**.
Single-core subtests:

| Subtest | Ratio | Subtest | Ratio |
|---|---|---|---|
| Navigation | 0.95 | Ray Tracer | 0.57 |
| PDF Renderer | 0.85 | HDR | 0.55 |
| Clang | 0.76 | Horizon Detection | 0.48 |
| Asset Compression | 0.75 | Background Blur | 0.41 |
| HTML5 Browser | 0.69 | Structure from Motion | 0.28 |
| File Compression | 0.67 | Photo Filter | 0.24 |
| Object Remover | 0.67 | Photo Library | 0.23 |
| Text Processing | 0.66 | **Object Detection** | **0.07** |

Interpretation **[Inferred]**: the scalar and integer subtests (Navigation, PDF, Clang) stay in
Rosetta's usual 0.7 to 0.95 band. The image and ML subtests collapse. Under macOS 13 the x86
build could not use AVX, so it fell back to SSE-only kernels, while the native build uses NEON
(and dot-product and similar extensions). This gap is largely about code paths, not the
translator; but it is exactly what a user experiences.

**Other later-chip data.**
- **Stockfish 17, M4, macOS 15.1.1 (Dec 2024)**, single-core nodes/s: arm64 1,830,739;
  x86-64 baseline 647,787 (**0.35**); x86-64 POPCNT build 1,085,328 (**0.59**). The AVX2 build
  died with "illegal hardware instruction" ([Benchmark: Stockfish #5707][stockfish]). Chess
  search leans on POPCNT and bit tricks, so missing or emulated bit instructions hurt.
- **LuaJIT benchmark suite, M1 Max (FOSDEM, Feb 2024):** native 33 s, Rosetta 44 s
  (**0.75**) ([Benchmark: P. Cawley][cawley]).
- **Trivial counting loop, M4, macOS 15.5:** native 16.30 × 10⁹ increments, Rosetta
  15.66 × 10⁹ (**0.96**). A best case with no instruction expansion
  ([Benchmark: MacRumors forum][mr-forum]).

**Linux VMs (Rosetta for Linux).**
- sysbench CPU, 4 threads, M1 Max, macOS 13.0: native 30,333 events/s, Rosetta 25,567
  (**0.84**), QEMU 1,068 ([Benchmark: docker/for-mac #6641][docker6641]).
- Prime sieve (Phoronix test), M1, 2023: native 26.5 s, Rosetta 32.3 s (**0.82**), QEMU
  253.7 s ([Benchmark: P. Thomas][pthomas]).
- Geekbench 6 x86 in a Lima VM on M1, macOS 15.5: 911 / 3013, against 2345 / 8348 for native
  macOS (**0.39 / 0.36**) ([Benchmark: lima #3726][lima3726]). See §2.8 for why VMs do worse.
- Mac mini M4, Docker on Debian 13, Oct 2025: Geekbench 6 x86 1647 / 7302
  ([upload][gb6-m4linux]) against roughly 3,720 / 14,680 for a native M4 Air (EveryMac
  averages, [EveryMac][em-air]), i.e. **about 0.44 / 0.50**. Here Linux Rosetta advertises AVX2
  and the benchmark probably took its slower AVX2 paths **[Inferred]** (§2.3).

### 1.3 GPU-bound applications and games

- GFXBench Aztec Ruins on M1 showed no penalty: "GPU performance is all but identical"
  between native and translated ([Benchmark: AnandTech][anand-gpu]).
- Rise of the Tomb Raider (an x86 game under Rosetta) reached 39.6 fps at 1080p Enthusiast on
  a Mac mini M1 ([AnandTech][anand-gpu]).
- When Baldur's Gate 3 shipped a native build in 2021, the gain over the Rosetta build was
  "2-4 fps" ([Benchmark: iThinkDiff][bg3]).
- Apple claimed at launch that some of the most graphically demanding apps would run faster
  under Rosetta on M1 than natively on Intel Macs with integrated graphics
  ([Apple Newsroom, Nov 2020][apple-news]).

### 1.4 Versus the Intel Macs it replaced

- Rosetta's 1313 single-core Geekbench 5 score on an M1 Air beat every Intel Mac, including the
  2020 27-inch iMac with a Core i9-10910 ([Benchmark: MacRumors][mr-gb5]).
- Renaissance JVM suite (Nov 2020): the x86 JVM under Rosetta on an M1 MacBook Pro was about
  14 % slower in total than an Intel MacBook Pro, while the native JVM was 36 % faster. One
  test ("movie lens") was 4× slower under Rosetta ([Benchmark: nequalsonelifestyle][renaissance]).
- Dolphin's x86 JIT under Rosetta "easily ran most games at full speed and handily outran
  like-class Intel Macs" ([Dolphin blog][dolphin-blog]).

---

## 2. Where Rosetta is slow, and why

| # | Class | Symptom | Mechanism | Evidence |
|---|---|---|---|---|
| 2.1 | **x87 floating point** | Old games and 32-bit-era code crawl | Full 80-bit soft-float through about 75 runtime helpers ([03][03] §10.4) | 4 to 10× from community replacements |
| 2.2 | **JIT-heavy apps** | Browsers 0.55 to 0.60, JVM 0.36 to 0.53, stutter | A JIT on top of a JIT: guest code is generated at run time, then translated by Rosetta's JIT (not AOT); write-fault and re-translate cycles; extra lookup cost | Chrome, Gradle, sbt, Dolphin "jitter from Jitting a JIT" |
| 2.3 | **AVX/AVX2** | Before macOS 15: illegal instruction or SSE fallback. After: AVX2 slower than SSE2 | YMM upper halves kept in memory; two NEON ops per AVX op | Microbenchmarks below |
| 2.4 | **Modern SIMD/ML kernels** | GB6 image/ML subtests 0.07 to 0.4 | x86 binaries get SSE-era paths; NEON-specific native paths are much faster | GB6 M2 Max (§1.2) |
| 2.5 | **Branchy, large-code workloads** | 502.gcc_r at 0.5 | Indirect branches, code-size expansion (~1.6×) and almost no cross-instruction optimisation | [AnandTech][anand-rosetta], [RE: Johnson][dj] |
| 2.6 | **First launch / re-translation** | Bouncing dock icon; CPU churn after OS updates | AOT translation of tens of MB, re-done when the cache is invalidated | Office ~20 s; 17 to 20 min of `oahd-helper` |
| 2.7 | **Memory-ordering tax** | A few to about 20 % on store-heavy multi-threaded code | Hardware TSO is always on for translated code ([04][04]) | TOSTING: −8.94 % geomean |
| 2.8 | **Linux VMs** | Lower ratios than on macOS | PF/AF computed in software; TSO for the *whole VM*; AVX2 advertised | lima, threedots, Johnson |

### 2.1 x87

- Rosetta keeps exact 80-bit semantics in software, "full, slow" by Johnson's description
  ([RE: Johnson][dj]).
- rosettax87 swaps Rosetta's x87 helpers for "less precise but significantly faster" double-based
  handlers. On an fsqrt loop it measured 229,731 versus 48,517 ticks (**~4.7×**; chip not
  stated, Apr 2025) ([Benchmark: rosettax87][rx87]). A user reported **~10×** on M4
  (123,040 → 12,222 ticks) ([Benchmark: box64 #2595][box64-2595]).
- Follow-up projects JIT-compile x87 blocks into AArch64 and target games such as World of
  Warcraft under Wine ([x87sidecar][x87sidecar]).
- **Why it matters [Inferred]:** x87 survives in 32-bit Windows games (via CrossOver/Wine) and
  in old compilers' `long double`. Every x87 op is a helper call with memory traffic.

### 2.2 JIT-heavy applications and self-modifying code

- **Code that does not exist at install time cannot be AOT-translated.** It goes through
  Rosetta's JIT, whose per-block translation time and code quality matter far more than for
  AOT code ([RE: Johnson][dj]). For a guest JIT, every write to a translated code page triggers
  a fault, a permission flip and a later re-translation, and a "fresh JIT entry" is created even
  for identical code ([RE: Saagar Jha][sj2021]).
- **Measured:**
  - Chrome 0.55 to 0.60 ([Ars][ars-chrome]);
  - JVM builds 0.36 to 0.53 ([gradle][gradle], [sbt][sbt]); BellSoft reported "a few times
    difference" on DaCapo ([BellSoft][bellsoft]);
  - Dolphin native JIT 30 to 50 % faster, and under Rosetta "jitter from Jitting a JIT"
    ([Dolphin blog][dolphin-blog]).
- **Interpreters without a JIT do better.** CPython runs at ~0.63 to 0.77 apart from startup
  ([pyperf][pyperf]); the LuaJIT suite at 0.75 ([Cawley][cawley]).

### 2.3 AVX and AVX2

- **Before macOS 15** (Big Sur to Sonoma), Rosetta did not support AVX ([Apple WWDC20][wwdc10686]).
  Well-behaved apps checked CPUID and used SSE paths; games that required AVX crashed
  ([AppleGamingWiki][agw]).
- **macOS 15 and later** execute AVX/AVX2 but do not advertise them by default; see
  [03][03] §10.5 for `ROSETTA_ADVERTISE_AVX`. Measured cost of the 256-bit path:
  - M1, macOS 15.2, clang `-O2`, integer-sum microbenchmark: SSE2 0.140 s, AVX-128 0.127 s,
    **AVX2 0.344 s** ([Benchmark: issue comment by O2S-C][avxdive-i1]).
  - Random-number generation (Qiita, May 2025): the AVX2 path ran about **3× slower than SSE2**
    (183 to 207 ms versus 52 to 77 ms) ([Benchmark: Qiita][qiita-avx]).
  - macOS 15.0 developer beta, M2 Air, unoptimised build: AVX2 ~13 % slower than SSE2
    ([Benchmark: carsongoodwin32][avxdive]).
- **Why.** Each AVX2 op is two NEON ops plus loads and stores of the upper half held in the
  thread context in memory ([RE: published disassembly][avxdive-disasm]; [03][03] §10.5).
  CrossOver's maintainer warned that advertising AVX would push apps off faster SSE2 paths
  ([Whisky PR #1034][whisky1034]).
- **Practical effect.** AVX2 support on macOS 15 is a *compatibility* feature: games that
  refuse to start without AVX now run (GPTK 2 era). It is not a speed feature.

### 2.4 Modern SIMD- and ML-heavy kernels

- GB6 Object Detection ran at 0.07 and Photo Filter/Library at about 0.24 on M2 Max (§1.2).
  GB5 on M1 already showed weaker results for AES-XTS (0.55), HTML5 (0.59) and Machine Learning
  (0.59) than for many scalar subtests (0.78 to 0.90, e.g. text compression, navigation, PDF);
  SQLite (0.64) and text rendering (0.68) sat in between ([GB5 native][gb5-nat] versus
  [GB5 Rosetta][gb5-ros]; cross-upload comparison).
- Cause **[Inferred]**: hand-tuned x86 SIMD (SSE4.2 at best before macOS 15) is translated
  instruction by instruction, with no cross-instruction scheduling, while the native build can
  use NEON idioms or Apple frameworks (Accelerate, Core ML) that Rosetta cannot route x86 calls
  into, because the whole process is translated.

### 2.5 Branchy, large-code workloads

- SPEC2017 502.gcc_r reached only 49.87 % of native, "probably due to high code complexity
  and just overall uncommon code patterns" ([AnandTech][anand-rosetta]). The likely drivers:
  - indirect branches that need hash lookups ([03][03] §7.3);
  - ~1.6× code expansion pressuring the instruction cache ([RE: Johnson][dj]);
  - few cross-instruction optimisations ([03][03] §2.2).
- **Caution.** Sometimes the x86 build under Rosetta beats the native build because the x86
  compiler generated better code. An igraph routine ran in 0.155 s under Rosetta versus 0.445 s
  natively, traced to arm64 loop-unrolling decisions ([LLVM Discourse][llvm-igraph]).

### 2.6 First launch and re-translation

- Microsoft initially said Office apps would bounce in the dock for "approximately 20 seconds"
  on first launch while Rosetta translated. It later softened that to "will take longer"
  ([MacRumors, Nov 2020][mr-office]).
- A small binary (about 100 KB of x86 code) translates in under 12.5 ms ([Eclectic Light][elc-oah]).
- Bulk work is visible: after a SIP mode change on an M1 Mac mini running macOS 12.5,
  `oahd`/`oahd-helper` churned for about 17 minutes ([Apple StackExchange][se-oahd]).
- Apple's documentation warns that "the translation process takes time, so a person might
  perceive that translated apps launch or run more slowly at times" ([Apple][apple-about]).
  Apple translates at install time when the App Store or the package installer is used
  ([Apple WWDC20 10686][wwdc10686]).
- **Comparison.** Windows' older emulator built its translation cache during or after runs:
  fast first start, slower until cached. Rosetta's AOT front-loads the cost
  ([RE: FFRI part 2][ffri2]).

### 2.7 Memory-ordering (TSO) tax

- Translated code always runs with Apple's hardware TSO mode on (mechanism in [04][04]).
  TOSTING toggled TSO system-wide on an M1 Ultra (Asahi Linux 6.1, SPECspeed 2017 FP peak,
  20 threads):
  - geometric mean fell from **86.57 to 78.83 (−8.94 %)**;
  - 644.nab_s fell from 171.34 to 137.43 (about −20 %);
  - in microbenchmarks, stores and fetch-adds were "generally and sometimes drastically
    slower" under TSO.

  ([Benchmark: Wrenger et al., ARCS 2023][tosting])
- This is the price of *not* inserting barriers. Software barriers cost far more; TOSTING
  notes that x86 emulators without hardware TSO "basically insert a fence after every memory
  instruction".

### 2.8 Linux VMs

Three effects stack up:
1. Rosetta cannot switch on Apple's PF/AF extension inside a VM, so it computes PF in software
   when the flag is live ([RE: Johnson][dj]).
2. While the Rosetta share is attached, "all of the VM runs in Total Store Ordering mode"
   ([RE: threedots][threedots]). That plausibly explains why simply attaching Rosetta slowed
   *native* arm64 code inside a Lima VM: Geekbench 6 arm64 fell from 2177/6869 to 1201/4919,
   and `cryptsetup` AES-CBC decryption from 5,787 to 2,118 MiB/s
   ([Benchmark: lima #1269][lima1269], [lima #3726][lima3726]). Cause **[Inferred]**; Lima's
   maintainers only advise enabling Rosetta when needed.
3. Linux Rosetta advertises AVX2 ([03][03] §10.5), so software may pick the slow AVX2 paths
   **[Inferred]**.

Integration bugs can dominate as well: an OrbStack workaround once made Rosetta builds 34 %
slower than QEMU, until a fix in OrbStack 1.1.0 ([OrbStack #792][orb792]).

### 2.9 Where Rosetta is close to native

- Memory-bound code (SPEC ">90%", [AnandTech][anand-rosetta]).
- GPU-bound games and apps (§1.3).
- Simple loops (0.96, §1.2).
- Some SIMD audio code (Physical Audio).
- Johnson notes that IDA Pro gained little going native ([RE: Johnson][dj]).

Apple's wide cores absorb much of the extra instruction count: the M1 has "a remarkable
ability to avoid being throughput-bound, even with all the extra instructions Rosetta 2
generates" ([RE: Johnson][dj]).

---

## 3. Apple's own performance guidance to developers

- **Rosetta is a bridge, not a target.** The 2020 documentation said Rosetta "is not a
  substitute for creating a native version of your app" ([quoted by OSnews][osnews]).
  Today's page says Rosetta stays a general-purpose tool through **macOS 27**, after which
  only a subset aimed at older games remains ([Apple][apple-about]).
- **Ship universal binaries.** Apple called universal apps "the fastest, most powerful Mac
  apps available" ([Apple Newsroom][apple-news]).
- **Benchmark and tune native code.** Native code generally performs best. Replace
  Intel-specific SSE/AVX assembly with Arm implementations, or use Accelerate and other Apple
  APIs ([Apple WWDC20 10214][wwdc10214]).
- **Expect first-launch delay.** Install through the App Store or a package installer so that
  translation happens at install time ([Apple WWDC20 10686][wwdc10686], [Apple][apple-about]).
- **Graphics.** For translated Metal apps, "translation and consistency features will cost
  you some performance"; recompile with the new SDK ([Apple WWDC20 10632][wwdc10632]).
- **Feature checks.** Check before using unsupported vector extensions; today only AVX-512 is
  off-limits, via `hw.optional.avx512f` ([Apple][apple-about]). Detect translation with
  `sysctl.proc_translated` ([Apple][apple-about]).

---

## 4. Comparison with other translators

### 4.1 Summary

Where possible these are same-hardware ratios against native. Different hardware and OSes
make cross-row comparisons rough.

| Translator | Direction / platform | Approach (one line) | Reported performance vs native | Source and date |
|---|---|---|---|---|
| **Rosetta 2** | x86-64 → arm64; macOS and Linux VMs | Whole-image AOT plus JIT; fixed register map; Apple hardware assists | 0.71 (7-zip, M1); 0.75 (LuaJIT, M1 Max); 0.84 (sysbench, Linux VM) | §1 |
| **QEMU user mode (TCG)** | any → any | Generic JIT through the TCG IR; flags and memory ordering in software | 0.035 (sysbench, M1 Max VM); 0.10 (prime sieve, M1); 0.16 (7-zip x86-64 on Raspberry Pi 400) | [docker #6641][docker6641], [P. Thomas][pthomas], [box86.org][box-2022] |
| **FEX-Emu** (2203) | x86/x86-64 → arm64 Linux | JIT with an IR | 0.26 (7-zip, Pi 400, 2022) | [box86.org 2022][box-2022] |
| **Box64** | x86-64 → arm64 Linux | Dynarec; wraps native host libraries | 0.53 (7-zip, Pi 400); 0.57 (7-zip, M1 Asahi) in 2022. Faster than Rosetta on 7-zip in Dec 2024, slower on dav1d | [box86.org 2022][box-2022], [box86.org 2024][box-2024] |
| **Microsoft x64 emulation (pre-Prism)** | x64 → arm64 Windows | JIT with a cache service | **0.35** (LuaJIT, Windows VM on M1 Max, Feb 2024) | [Cawley][cawley] |
| **Microsoft Prism** (24H2+) | x64 → arm64 Windows | JIT with cached blocks, "tuned specifically for Qualcomm Snapdragon" | ~0.62 (Cinebench 2024), ~0.5 (Blender), ~0.97 (DaVinci Resolve) on Snapdragon X Elite | [Signal65 2025][signal65] |
| **Intel Houdini** | arm/arm64 → x86 Android | Proprietary; described as an interpreter in 2021 | **0.72** (7-zip arm64 on x86-64, 2025); 2013-14 Atom era: from about 30 % slower up to 3× slower | [cnRrex][unidbg], [apedroid][apedroid], [CommonsWare][commonsware], [The Register][reg2014] |
| **Google ndk_translation** | arm64 → x86-64 Android emulator | Proprietary DBT | **0.52** (same 7-zip test) | [cnRrex][unidbg] |

### 4.2 QEMU user mode

- **Same Mac, Rosetta for Linux versus QEMU.** Rosetta is consistently several to more than
  20× faster:
  - sysbench CPU 24× (M1 Max) ([docker #6641][docker6641]);
  - with one thread, M1 Pro, macOS 13.2.1: UnixBench 1.83×, sysbench CPU 22.6×, sysbench
    memory 7.26×, 7-zip 2.57× ([Benchmark: milldea][milldea]);
  - Docker's 4.26 notes cite a Linux kernel build going from 39 to 17 minutes, a PostHog build
    from 17 to under 6 minutes and a Sylius build from 20 to 6 minutes. The wording does not make
    clear which baselines were QEMU and which were Docker's older Rosetta integration
    ([Docker Desktop 4.26 blog][docker426]).
- A 2025 test of *full-system* QEMU (an x86 Debian VM under UTM) against Docker+Rosetta gave
  UnixBench 283.6 versus 3,205.1 on an M2 and 87.1 versus 4,179.1 on an M4 ([Qiita][qiita-utm]).
  That compares system emulation with user-mode translation, so it overstates the gap.
- **Why QEMU is slower [Inferred]** (mechanisms from its documentation): a generic two-stage IR,
  lazily computed flags kept in memory ([QEMU internals][qemu-int]), fences instead of hardware
  TSO ([TOSTING][tosting]), and no AOT.

### 4.3 FEX-Emu and Box64

- **Raspberry Pi 400 (Cortex-A72), Ubuntu 21.10, Mar 2022**, 7-zip score versus a native
  aarch64 build (5,787): QEMU x86-64 931, FEX x86-64 1,486, Box64 3,084. dav1d single-thread:
  QEMU 11.24, FEX 27.28, Box64 49.72 versus native 185.57 ([Benchmark: box86.org][box-2022]).
- **Box64 versus Rosetta on M1 (2022):** Rosetta 0.71 of macOS native, Box64 0.57 of Asahi
  native. FEX could not run on Asahi's 16 KB pages at the time ([box86.org][box-2022]).
- By Dec 2024, after "native flags" (ARM flags standing in for x86 flags, worth up to +30 % on
  7-zip) and a rework of strong-memory emulation, Box64 beat Rosetta on 7-zip but trailed on
  dav1d ([box86.org][box-2024]).
- Box64 hands much library work to native host libraries; Rosetta never mixes. So these are not
  like-for-like comparisons of the translator alone **[Inferred]**.

### 4.4 Microsoft (Windows on Arm)

- **Before Prism.** The LuaJIT suite on the same M1 Max: Windows-native arm64 37 s, emulated
  x64 106 s (0.35). macOS Rosetta reached 0.75 on the same machine. The Arm64EC build, which
  mixes native and emulated code, reached 38 s ([Benchmark: Cawley][cawley]).
- **Prism (Windows 11 24H2, 2024).**
  - Microsoft claims 10 to 20 % more speed on the same hardware ([Ars Technica][ars-prism]) and
    that it "is as efficient as Rosetta 2" ([Windows Central][wc-prism]).
  - An independent check found only modest gains over the old emulator on a Surface Pro X:
    +10 % Speedometer 3, +8 % Cinebench R23 single-core, +4.5 % multi-core
    ([The Verge][verge-prism]).
  - Microsoft says Prism is tuned for Snapdragon, and "some performance features within Prism
    require hardware features only available in the Snapdragon X series" ([Microsoft Learn][ms-prism]).
    Snapdragon X implements FEAT_AFP, and Prism's x64 results match x86 FP semantics
    ([reader report under mod_poppo][poppo]). That is the same kind of hardware help Rosetta
    uses.
  - AVX/AVX2/BMI/FMA/F16C support entered preview in Nov 2024 and shipped to all 24H2+ devices
    in late 2025 (on by default for 64-bit apps) ([Microsoft, Dec 2025][ms-avx],
    [TechRadar][tr-avx]).
- **Caveat.** No apples-to-apples Prism-versus-Rosetta test on identical silicon exists,
  because the OS differs and Windows VMs on Macs do not get Snapdragon-specific assists.

### 4.5 ARM → x86: Intel Houdini and Google ndk_translation (the reverse direction)

- **Modern data (May 2025, Android emulator on Hyper-V, host CPU not stated).** Single-thread
  7-zip, arm64 build translated versus a native x86-64 build:
  - Houdini 12: **0.72** overall, with codec-dependent results from 0.51 to 0.90;
  - Google ndk_translation: **0.52**;
  - QEMU 10: **0.27**.

  ([Benchmark: cnRrex/unidbg-benchmark-test][unidbg])
- **Atom era (2013 to 2014, 32-bit ARM to x86).**
  - Epic Citadel ran more than 40 % better as native x86 than translated ([apedroid][apedroid]).
  - A SQLCipher test suite took about 3× longer under libhoudini ([CommonsWare][commonsware]).
  - ARM-sourced tests reported 20 to 40 % frame-rate drops, more stutter and higher power draw
    ([PCPer][pcper2014], [The Register][reg2014]). These are vendor claims.
- **Design note.** NCC Group's DEF CON 29 analysis describes Houdini as an interpreter (a state
  machine over ARM opcodes) with no JIT ([RE: Brian Hong][houdini-dc29]). A 0.72 ratio would be
  remarkable for a pure interpreter, so newer releases may differ **[Inferred]**; treat this as
  unresolved.

### 4.6 Mixed-mode and library acceleration

- Arm64EC (native and emulated code in one process) brought the LuaJIT suite to within 3 % of
  native ([Cawley][cawley]).
- A QEMU-based translator that sends shared-library calls to native host libraries sped up
  x86 programs on Arm by 2.7× to 6.3× on average, and up to 28× ([LCTES 2024][lctes24]).
- Rosetta deliberately gives this up; Apple forbids mixing ([Apple][apple-about]).

### 4.7 Low-confidence microbenchmark: AVX2 FMA throughput

A community test (Nov 2024) measured peak AVX2 FMA GFLOPS (fp32):

| Setup | fp32 GFLOPS |
|---|---|
| M1 Rosetta | 32.9 |
| M4 Rosetta | 49.2 |
| M1 + Parallels Linux + FEX | 45.9 |
| M1 + Parallels + Prism | 38.0 |
| M1 + Parallels + ExaGear | 38.4 |
| M1 + Parallels + QEMU | 0.47 |

Source: [FydeOS community][fydeos]. Methodology is thin and one Box64 figure was flagged as
anomalous by the author. For scale, native NEON FMLA on an M4 P-core peaks around
107 GFLOPS ([tnzr.org][tnzr]).

---

## 5. What this implies for an ARM64 → x86-64 translator [Inferred]

1. **Expect lower ratios than Rosetta.** The best published ARM → x86 figure for integer code
   is Houdini's ~0.72, and Google's translator reaches ~0.52 (§4.5). The reverse direction
   needs no TSO or PF/AF hardware, but it does pay for register pressure (31 → 16 GPRs), flag
   clobbering and NEON → SSE/AVX2 expansion ([03][03] §13).
2. **Do AOT by default and hide it at install time.** Rosetta shows first launch is the most
   visible cost; Office's ~20 s became a support note.
3. **Make the JIT path fast.** JavaScriptCore, V8, the JVM and game engines will hit it. JIT
   paths are where Rosetta drops to 0.35 to 0.6.
4. **Do not advertise features you emulate slowly.** Rosetta's AVX2 shows that advertising can
   make apps slower; prefer an honest feature set with a per-app override.
5. **Prioritise SIMD quality.** The worst Rosetta ratios (0.07 to 0.4) are in image and ML
   kernels. For ARM apps the equivalent is NEON-heavy code: codecs, Accelerate-style DSP,
   Metal shader-prep code.
6. **Consider library thunking** (Arm64EC/LCTES-style) for hot system frameworks if
   whole-process translation is impractical on Intel macOS. The published gains (2.7 to 6×)
   dwarf code-generation tweaks.
7. **Benchmark set to adopt:** Geekbench 6 subtests, 7-zip, the LuaJIT suite, a JS benchmark
   (Speedometer/JetStream), a JVM build, a Dolphin-style JIT-on-JIT case, and a GPU-bound game.
   These are the axes along which Rosetta's behaviour is documented.

---

## Open questions

1. **No independent SPEC-class study after M1.** I found no controlled SPEC or SPEC-like study
   of Rosetta on M2 to M5 or on macOS 14 to 26. Later-chip figures are Geekbench uploads and
   anecdotes.
2. **No longitudinal data.** Has Rosetta's code generation improved across macOS releases on
   the same chip? Nobody seems to have measured it.
3. **AVX2 on newer chips.** AVX2 cost on M4/M5 versus M1, and whether any newer Rosetta keeps
   YMM upper halves in registers or uses SME/SSVE on M4 (no evidence either way).
4. **Energy.** No public measurement of the energy cost of Rosetta-translated code on Apple
   silicon; only ARM's 2014 claims about Houdini exist.
5. **Prism vs Rosetta.** There is no fair comparison on identical hardware (different OS, and
   Windows VMs lack Snapdragon assists). Microsoft's "as efficient as Rosetta 2" is unverified.
6. **Translation throughput.** MB/s for large apps on current Macs, and the size of the AOT
   cache in typical use, are only anecdotal.
7. **Houdini's design.** Interpreter (DEF CON 2021) versus high measured efficiency (2025):
   which Houdini versions JIT?
8. **Dolphin numbers.** The figures were read off a rendered chart; the series order was
   inferred from the chart's label sequence.

---

## Sources

Apple:

- About the Rosetta translation environment: <https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment>
- WWDC20 10686, "Explore the new system architecture of Apple silicon Macs": <https://developer.apple.com/videos/play/wwdc2020/10686/>
- WWDC20 10214, "Port your Mac app to Apple silicon": <https://developer.apple.com/videos/play/wwdc2020/10214/>
- WWDC20 10632, "Optimize Metal Performance for Apple silicon Macs": <https://developer.apple.com/videos/play/wwdc2020/10632/>
- Apple Newsroom, "macOS Big Sur is here", 12 Nov 2020: <https://www.apple.com/newsroom/2020/11/macos-big-sur-is-here/>
- OSnews quoting the original 2020 Rosetta page: <https://www.osnews.com/story/131950/about-the-rosetta-translation-environment/>

Benchmarks and measurements:

- AnandTech, "The 2020 Mac Mini Unleashed", Rosetta2 page, 17 Nov 2020 (archived): <https://web.archive.org/web/20210201183558/https://www.anandtech.com/show/16252/mac-mini-apple-m1-tested/6>; GPU page: <https://web.archive.org/web/20210201183558/https://www.anandtech.com/show/16252/mac-mini-apple-m1-tested/3>; benchmarks page: <https://web.archive.org/web/20210201183558/https://www.anandtech.com/show/16252/mac-mini-apple-m1-tested/2>
- MacRumors, Geekbench 5 under Rosetta, 15 Nov 2020: <https://www.macrumors.com/2020/11/15/m1-chip-emulating-x86-benchmark/>
- Tencent News, MacBook Air M1 review, 18 Nov 2020: <https://news.qq.com/rain/a/20201118A001IN00>
- Geekbench 5 Rosetta upload (MacBook Air M1): <https://browser.geekbench.com/v5/cpu/4773720>; native upload (macOS 11.2.3): <https://browser.geekbench.com/v5/cpu/7919467>
- Geekbench 6 Rosetta upload (M2 Max, macOS 13.2): <https://browser.geekbench.com/v6/cpu/14955>; native upload (M2 Max, macOS 13.4): <https://browser.geekbench.com/v6/cpu/1962643>
- Geekbench 6, Mac mini M4, Linux Docker with Rosetta, Oct 2025: <https://browser.geekbench.com/v6/cpu/14595669>
- EveryMac, Apple-silicon MacBook Air Geekbench averages: <https://everymac.com/mac-benchmarks/all-apple-silicon-macbook-air-benchmarks.html>
- Ars Technica, native Chrome on M1, 19 Nov 2020: <https://arstechnica.com/gadgets/2020/11/google-chrome-is-available-as-an-apple-m1-native-app-today/>; MacRumors summary with numbers, 20 Nov 2020: <https://www.macrumors.com/2020/11/20/chrome-m1-macs-80-percent-faster/>
- box86.org, "Box86/Box64 vs QEMU vs FEX (vs Rosetta2)", 24 Mar 2022: <https://box86.org/2022/03/box86-box64-vs-qemu-vs-fex-vs-rosetta2/>
- box86.org, box64 v0.3.2 notes, 6 Dec 2024: <https://box86.org/2024/12/new-version-of-box64-v0-3-2-and-box86-v0-3-8/>
- diewland, pyperformance x86 (Rosetta) vs arm64: <https://github.com/diewland/py-rosetta2-vs-arm>
- gradle/gradle issue #17323, May 2021: <https://github.com/gradle/gradle/issues/17323>
- Alberto Huélamo, "Native Apple Silicon JDKs", 29 Nov 2021: <https://alhuelamo.com/posts/2021/11/native-apple-silicon-jdks/>
- facebook/flow issue #8664, May 2021: <https://github.com/facebook/flow/issues/8664>
- nequalsonelifestyle, Renaissance on Apple silicon, 24 Nov 2020: <https://www.nequalsonelifestyle.com/2020/11/24/apple-silicon-benchmarks-pt7-renaissance/>
- BellSoft, Liberica on Apple silicon: <https://bell-sw.com/announcements/2021/03/12/Liberica-on-Apple-Silicon/>
- Dolphin, "Temptation of the Apple", 24 May 2021: <https://dolphin-emu.org/blog/2021/05/24/temptation-of-the-apple-dolphin-on-macos-m1/>; April/May 2021 progress report: <https://dolphin-emu.org/blog/2021/06/06/dolphin-progress-report-april-and-may-2021/>; PR #9441: <https://github.com/dolphin-emu/dolphin/pull/9441>
- Physical Audio, SIMD on M1, 10 Jan 2021: <https://physicalaudio.co.uk/testing-simd-performance-on-apples-new-m1-processor/>
- HotHardware, DTK benchmarks, 30 Jun 2020: <https://hothardware.com/news/apple-developer-transition-kit-surface-pro-x-microsoft-a12z-bionic>; EveryMac DTK estimate: <https://everymac.com/mac-answers/apple-silicon-faq/apple-silicon-macos-ios-app-compatibility-performance-rosetta-2-windows.html>
- Stockfish issue #5707, Dec 2024: <https://github.com/official-stockfish/Stockfish/issues/5707>
- MacRumors forum (counter-loop test, M4, macOS 15.5), Jul 2025: <https://forums.macrumors.com/threads/how-did-they-make-the-change-between-processors-without-a-hitch.2461020/page-2>
- iThinkDiff, Baldur's Gate 3 native vs Rosetta, Jul 2021: <https://www.ithinkdiff.com/baldurs-gate-3-performance-native-m1-mac/>
- docker/for-mac issue #6641 (sysbench: QEMU vs Rosetta vs native), Dec 2022: <https://github.com/docker/for-mac/issues/6641>
- Patrick W. Thomas, Docker amd64 via Rosetta vs QEMU, Mar 2023: <https://patrickwthomas.net/macos-docker/>
- milldea, Docker Rosetta vs QEMU benchmarks (M1 Pro), May 2023: <https://note.milldea.com/posts/docker-to-accelerate-intel-based-emulation-with-rosetta>
- Docker Desktop 4.26 blog, Dec 2023: <https://www.docker.com/blog/docker-desktop-4-26/>
- Qiita, UTM (QEMU) vs Docker+Rosetta, Sep 2025: <https://qiita.com/infinite1oop/items/fe28b7e841e406d96d13>
- lima-vm/lima issue #3726, Jul 2025: <https://github.com/lima-vm/lima/issues/3726>; issue #1269: <https://github.com/lima-vm/lima/issues/1269>
- OrbStack issue #792, Nov 2023: <https://github.com/orbstack/orbstack/issues/792>
- L. Wrenger, D. Töllner, D. Lohmann, "TOSTING: Investigating Total Store Ordering on ARM", ARCS 2023: <https://www.sra.uni-hannover.de/Publications/2023/tosting-arcs23/wrenger_23_arcs.pdf>
- rosettax87 (benchmark in README), 2025: <https://github.com/Lifeisawful/rosettax87>; box64 issue #2595 (M4 numbers): <https://github.com/ptitSeb/box64/issues/2595>; x87sidecar: <https://github.com/athei/x87sidecar>
- carsongoodwin32, rosetta2_avx_dive: <https://github.com/carsongoodwin32/rosetta2_avx_dive>; issue #1 with O2S-C's macOS 15.2 timings: <https://github.com/carsongoodwin32/rosetta2_avx_dive/issues/1>; published disassembly: <https://github.com/carsongoodwin32/rosetta2_avx_dive/tree/main/plaintext_disasm>
- Qiita (STDNUL), AVX2 under Sequoia's Rosetta, 24 May 2025: <https://qiita.com/STDNUL/items/a17bbba6202835407e6b>
- Whisky PR #1034 (GPTK README and CrossOver maintainer comment), 2024: <https://github.com/Whisky-App/Whisky/pull/1034>
- AppleGamingWiki, Game Porting Toolkit (AVX games): <http://www.applegamingwiki.com/wiki/Game_Porting_Toolkit>
- MacRumors, Office first-launch translation, 12 Nov 2020: <https://www.macrumors.com/2020/11/12/rosetta-2-translation-can-take-20-seconds/>
- Eclectic Light, "Running Intel code on your M1 Mac: Rosetta 2 and OAH", 22 Jan 2021: <https://eclecticlight.co/2021/01/22/running-intel-code-on-your-m1-mac-rosetta-2-and-oah/>
- Apple StackExchange, oahd-helper CPU after a SIP change, Aug 2022: <https://apple.stackexchange.com/questions/444914/what-is-oahd-helper-and-why-is-it-eating-my-cpu>
- LLVM Discourse, arm64 slower than x86-under-Rosetta (igraph), Oct 2022: <https://discourse.llvm.org/t/code-compiled-for-arm64-much-slower-than-for-x86-64/65680>
- FydeOS community, AVX2 throughput across translators, Nov 2024: <https://community.fydeos.com/t/topic/47282>
- tnzr.org, "Hello SME" M4 microbenchmarks: <https://tnzr.org/sme/micro.html>

Other translators:

- Peter Cawley, "Arm64EC: Microsoft's Emulation Frankenstein", FOSDEM 2024: <https://archive.fosdem.org/2024/events/attachments/fosdem-2024-1762-arm64ec-microsoft-s-emulation-frankenstein/slides/22690/Arm64EC_slides_only_7shtDgt.pdf>
- Ars Technica, Prism, 20 May 2024: <https://arstechnica.com/gadgets/2024/05/microsoft-says-prism-translation-layer-does-for-arm-pcs-what-rosetta-did-for-macs/>
- Windows Central, "What is Microsoft's Prism?", 24 May 2024: <https://www.windowscentral.com/software-apps/what-is-microsoft-prism>
- The Verge, "Windows on Arm finally has legs", 26 Jun 2024: <https://www.theverge.com/2024/6/26/24186432/microsoft-windows-on-arm-qualcomm-copilot-plus-pcs-prism-emulator>
- Microsoft Learn, "How emulation works on Arm": <https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-x86-emulation>
- Microsoft Tech Community, Prism AVX/AVX2 update, 5 Dec 2025: <https://techcommunity.microsoft.com/blog/windowsosplatform/windows-on-arm-runs-more-apps-and-games-with-new-prism-update/4475631>
- TechRadar, Prism AVX in the Oct 2025 update: <https://www.techradar.com/computing/windows/it-took-nearly-a-year-but-microsoft-has-finally-improved-windows-11-to-run-more-pc-games-on-arm-laptops>
- Signal65, "The Improving Landscape of Application Compatibility for Windows and Snapdragon Processors", 2025: <https://signal65.com/wp-content/uploads/2025/06/The-Improving-Landscape-of-Application-Compatibility-for-Windows-and-Snapdragon-Processors.pdf>
- mod_poppo, FEAT_AFP article and reader report on Snapdragon X: <https://zenn.dev/mod_poppo/articles/arm-feat_afp?locale=en>
- cnRrex, unidbg p7zip benchmarks (Houdini, ndk_translation, QEMU), May 2025: <https://github.com/cnRrex/unidbg-benchmark-test> (file `avd-scores-single-thread.txt`)
- Brian Hong (NCC Group), "Sleight of ARM: Demystifying Intel Houdini", DEF CON 29, 2021: <https://media.defcon.org/DEF%20CON%2029/DEF%20CON%2029%20presentations/Brian%20Hong%20-%20Sleight%20of%20ARM%20-%20%20Demystifying%20Intel%20Houdini.pdf>
- apedroid, "Binary translation vs native x86 code", May 2013: <http://blog.apedroid.com/2013/05/binary-translation-vs-native-x86-code.html>
- CommonsWare, "libhoudini: What It Means for Developers", Nov 2013: <https://commonsware.com/blog/2013/11/21/libhoudini-what-it-means-for-developers.html>
- PC Perspective, ARM's binary-translation claims, Apr 2014: <https://pcper.com/2014/04/arm-claims-x86-android-binary-translation-on-intel-soc-hurting-efficiency/>
- The Register, ARM test results vs Intel, May 2014: <https://www.theregister.com/2014/05/02/arm_test_results_attack_intel>
- T. Spink, B. Franke, "Accelerating Shared Library Execution in a DBT", LCTES 2024: <https://doi.org/10.1145/3652032.3657565>
- QEMU translator internals: <https://people.redhat.com/pbonzini/qemu-test-doc/_build/html/_sources/topics/Translator-Internals.txt>

Reverse engineering referenced for mechanisms:

- Dougall Johnson, "Why is Rosetta 2 fast?", 9 Nov 2022: <https://dougallj.wordpress.com/2022/11/09/why-is-rosetta-2-fast/>
- Saagar Jha, HN comment on SMC handling, 30 Nov 2021: <https://news.ycombinator.com/item?id=29388820>
- Koh M. Nakagawa (FFRI), Project Champollion part 2: <https://ffri.github.io/ProjectChampollion/part2/>
- threedots, "Quick look at Rosetta on Linux", Jun 2022: <https://threedots.ovh/blog/2022/06/quick-look-at-rosetta-on-linux/>

[02]: 02-architecture-and-runtime.md
[03]: 03-translation-techniques.md
[04]: 04-hardware-assists.md
[apple-about]: https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment
[wwdc10686]: https://developer.apple.com/videos/play/wwdc2020/10686/
[wwdc10214]: https://developer.apple.com/videos/play/wwdc2020/10214/
[wwdc10632]: https://developer.apple.com/videos/play/wwdc2020/10632/
[apple-news]: https://www.apple.com/newsroom/2020/11/macos-big-sur-is-here/
[osnews]: https://www.osnews.com/story/131950/about-the-rosetta-translation-environment/
[anand-rosetta]: https://web.archive.org/web/20210201183558/https://www.anandtech.com/show/16252/mac-mini-apple-m1-tested/6
[anand-gpu]: https://web.archive.org/web/20210201183558/https://www.anandtech.com/show/16252/mac-mini-apple-m1-tested/3
[anand-p2]: https://web.archive.org/web/20210201183558/https://www.anandtech.com/show/16252/mac-mini-apple-m1-tested/2
[mr-gb5]: https://www.macrumors.com/2020/11/15/m1-chip-emulating-x86-benchmark/
[qq]: https://news.qq.com/rain/a/20201118A001IN00
[gb5-ros]: https://browser.geekbench.com/v5/cpu/4773720
[gb5-nat]: https://browser.geekbench.com/v5/cpu/7919467
[gb6-ros]: https://browser.geekbench.com/v6/cpu/14955
[gb6-nat]: https://browser.geekbench.com/v6/cpu/1962643
[gb6-m4linux]: https://browser.geekbench.com/v6/cpu/14595669
[em-air]: https://everymac.com/mac-benchmarks/all-apple-silicon-macbook-air-benchmarks.html
[ars-chrome]: https://arstechnica.com/gadgets/2020/11/google-chrome-is-available-as-an-apple-m1-native-app-today/
[mr-chrome]: https://www.macrumors.com/2020/11/20/chrome-m1-macs-80-percent-faster/
[box-2022]: https://box86.org/2022/03/box86-box64-vs-qemu-vs-fex-vs-rosetta2/
[box-2024]: https://box86.org/2024/12/new-version-of-box64-v0-3-2-and-box86-v0-3-8/
[pyperf]: https://github.com/diewland/py-rosetta2-vs-arm
[gradle]: https://github.com/gradle/gradle/issues/17323
[sbt]: https://alhuelamo.com/posts/2021/11/native-apple-silicon-jdks/
[flow]: https://github.com/facebook/flow/issues/8664
[renaissance]: https://www.nequalsonelifestyle.com/2020/11/24/apple-silicon-benchmarks-pt7-renaissance/
[bellsoft]: https://bell-sw.com/announcements/2021/03/12/Liberica-on-Apple-Silicon/
[dolphin-blog]: https://dolphin-emu.org/blog/2021/05/24/temptation-of-the-apple-dolphin-on-macos-m1/
[dolphin-pr]: https://dolphin-emu.org/blog/2021/06/06/dolphin-progress-report-april-and-may-2021/
[dolphin-9441]: https://github.com/dolphin-emu/dolphin/pull/9441
[physaudio]: https://physicalaudio.co.uk/testing-simd-performance-on-apples-new-m1-processor/
[dtk-hh]: https://hothardware.com/news/apple-developer-transition-kit-surface-pro-x-microsoft-a12z-bionic
[dtk-em]: https://everymac.com/mac-answers/apple-silicon-faq/apple-silicon-macos-ios-app-compatibility-performance-rosetta-2-windows.html
[stockfish]: https://github.com/official-stockfish/Stockfish/issues/5707
[mr-forum]: https://forums.macrumors.com/threads/how-did-they-make-the-change-between-processors-without-a-hitch.2461020/page-2
[bg3]: https://www.ithinkdiff.com/baldurs-gate-3-performance-native-m1-mac/
[docker6641]: https://github.com/docker/for-mac/issues/6641
[pthomas]: https://patrickwthomas.net/macos-docker/
[milldea]: https://note.milldea.com/posts/docker-to-accelerate-intel-based-emulation-with-rosetta
[docker426]: https://www.docker.com/blog/docker-desktop-4-26/
[qiita-utm]: https://qiita.com/infinite1oop/items/fe28b7e841e406d96d13
[lima3726]: https://github.com/lima-vm/lima/issues/3726
[lima1269]: https://github.com/lima-vm/lima/issues/1269
[orb792]: https://github.com/orbstack/orbstack/issues/792
[tosting]: https://www.sra.uni-hannover.de/Publications/2023/tosting-arcs23/wrenger_23_arcs.pdf
[rx87]: https://github.com/Lifeisawful/rosettax87
[box64-2595]: https://github.com/ptitSeb/box64/issues/2595
[x87sidecar]: https://github.com/athei/x87sidecar
[avxdive]: https://github.com/carsongoodwin32/rosetta2_avx_dive
[avxdive-i1]: https://github.com/carsongoodwin32/rosetta2_avx_dive/issues/1
[avxdive-disasm]: https://github.com/carsongoodwin32/rosetta2_avx_dive/tree/main/plaintext_disasm
[qiita-avx]: https://qiita.com/STDNUL/items/a17bbba6202835407e6b
[whisky1034]: https://github.com/Whisky-App/Whisky/pull/1034
[agw]: http://www.applegamingwiki.com/wiki/Game_Porting_Toolkit
[mr-office]: https://www.macrumors.com/2020/11/12/rosetta-2-translation-can-take-20-seconds/
[elc-oah]: https://eclecticlight.co/2021/01/22/running-intel-code-on-your-m1-mac-rosetta-2-and-oah/
[se-oahd]: https://apple.stackexchange.com/questions/444914/what-is-oahd-helper-and-why-is-it-eating-my-cpu
[llvm-igraph]: https://discourse.llvm.org/t/code-compiled-for-arm64-much-slower-than-for-x86-64/65680
[fydeos]: https://community.fydeos.com/t/topic/47282
[tnzr]: https://tnzr.org/sme/micro.html
[cawley]: https://archive.fosdem.org/2024/events/attachments/fosdem-2024-1762-arm64ec-microsoft-s-emulation-frankenstein/slides/22690/Arm64EC_slides_only_7shtDgt.pdf
[ars-prism]: https://arstechnica.com/gadgets/2024/05/microsoft-says-prism-translation-layer-does-for-arm-pcs-what-rosetta-did-for-macs/
[wc-prism]: https://www.windowscentral.com/software-apps/what-is-microsoft-prism
[verge-prism]: https://www.theverge.com/2024/6/26/24186432/microsoft-windows-on-arm-qualcomm-copilot-plus-pcs-prism-emulator
[ms-prism]: https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-x86-emulation
[ms-avx]: https://techcommunity.microsoft.com/blog/windowsosplatform/windows-on-arm-runs-more-apps-and-games-with-new-prism-update/4475631
[tr-avx]: https://www.techradar.com/computing/windows/it-took-nearly-a-year-but-microsoft-has-finally-improved-windows-11-to-run-more-pc-games-on-arm-laptops
[signal65]: https://signal65.com/wp-content/uploads/2025/06/The-Improving-Landscape-of-Application-Compatibility-for-Windows-and-Snapdragon-Processors.pdf
[poppo]: https://zenn.dev/mod_poppo/articles/arm-feat_afp?locale=en
[unidbg]: https://github.com/cnRrex/unidbg-benchmark-test
[houdini-dc29]: https://media.defcon.org/DEF%20CON%2029/DEF%20CON%2029%20presentations/Brian%20Hong%20-%20Sleight%20of%20ARM%20-%20%20Demystifying%20Intel%20Houdini.pdf
[apedroid]: http://blog.apedroid.com/2013/05/binary-translation-vs-native-x86-code.html
[commonsware]: https://commonsware.com/blog/2013/11/21/libhoudini-what-it-means-for-developers.html
[pcper2014]: https://pcper.com/2014/04/arm-claims-x86-android-binary-translation-on-intel-soc-hurting-efficiency/
[reg2014]: https://www.theregister.com/2014/05/02/arm_test_results_attack_intel
[lctes24]: https://doi.org/10.1145/3652032.3657565
[qemu-int]: https://people.redhat.com/pbonzini/qemu-test-doc/_build/html/_sources/topics/Translator-Internals.txt
[dj]: https://dougallj.wordpress.com/2022/11/09/why-is-rosetta-2-fast/
[sj2021]: https://news.ycombinator.com/item?id=29388820
[ffri2]: https://ffri.github.io/ProjectChampollion/part2/
[threedots]: https://threedots.ovh/blog/2022/06/quick-look-at-rosetta-on-linux/
