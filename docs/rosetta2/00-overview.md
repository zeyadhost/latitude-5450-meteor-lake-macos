# Rosetta 2 — how it works, end to end

This chapter follows one Intel (x86-64) app from installation to execution on an Apple silicon Mac,
and links each step to the chapter that documents it in depth. Every fact here is sourced in those
chapters; nothing in this overview is new evidence.

> **Scope.** Public sources only: Apple's documentation, WWDC sessions, Apple's published XNU source,
> the Arm and Intel manuals, and named third-party research. No Apple code is reproduced here.
> Research cut-off: 31 October 2026 (macOS 27.2 "Golden Gate" current).

---

## The design in one sentence

Rosetta 2 translates a whole x86-64 program into ARM64 **ahead of time**, mostly **one x86 instruction
to a few ARM instructions**, keeps the x86 state **exact between every instruction**, and leaves the
messiest compatibility problems (memory ordering, x86 flags, x86 floating-point quirks, 4 KB pages)
to **custom hardware in Apple's CPUs**.

---

## 1. Before the app runs: ahead-of-time translation

| Step | What happens | Chapter |
|---|---|---|
| Install | Apps installed from the App Store or a `.pkg` are translated during installation; other apps on first launch. | [01](01-apple-official.md) |
| Translator | The `oahd` daemon runs `oahd-helper`, which uses `libRosettaAot.dylib` to translate the binary's whole text segment. | [02](02-architecture-and-runtime.md) §1, §3 |
| Output | The result is a normal ARM64 Mach-O (`.aot`) with a private load command (`LC_AOT_METADATA`) that holds the x86↔ARM address maps. | [02](02-architecture-and-runtime.md) §3 |
| Signing | A privileged service signs the `.aot` with a device key held by the Secure Enclave (a "supplemental signature"), which embeds the hash of the original x86 binary. | [01](01-apple-official.md), [02](02-architecture-and-runtime.md) §3 |
| Cache | Translations live in `/var/db/oah/`, a Data Vault that only the Rosetta service can read. It hands out read-only file descriptors. | [02](02-architecture-and-runtime.md) §3 |
| System libraries | The x86-64 dyld shared cache is translated once into an AOT shared cache (`aot_shared_cache`). | [02](02-architecture-and-runtime.md) §3 |
| **Trust-cache trick** | Translation is **deterministic**: the same input gives the same output on every Mac. So Apple translates every system binary at OS build time and puts the translated code's hash in the OS's static trust cache, three hashes per binary (arm64, x86-64, AOT). The translations themselves don't ship; they are rebuilt on demand and still match Apple's signature chain. | [01](01-apple-official.md), [02](02-architecture-and-runtime.md) |

## 2. Launch: the kernel hands control to Rosetta, not dyld

```
execve(x86-64 Mach-O)
   │  XNU: mach_loader.c sees CPU_TYPE_X86_64 on arm64 → IMGPF_ROSETTA
   ▼
load_rosetta()  maps /usr/libexec/rosetta/runtime (ARM64) and makes it the entry point;
   │            the x86-64 dyld is mapped but only passed to the runtime
   │  proc gets P_TRANSLATED; its pmap is created with PMAP_CREATE_ROSETTA
   │  (4 KB user page tables; translated_allow_execute so AOT/JIT pages may run)
   ▼
Rosetta runtime → IPC to the Rosetta service: "is there an AOT translation for this image?"
   ├─ yes → map the signed .aot, link it (lazy binding through stubs + an x86→ARM lookup tree)
   └─ no  → JIT-translate pages as they execute
   ▼
x86 dyld runs (translated) → loads x86 libraries (translated, mostly from the AOT shared cache)
   ▼
main()
```

Every name above appears in Apple's published XNU source; see [02](02-architecture-and-runtime.md) §2.
On every return to a translated thread, the kernel also switches on the CPU modes Rosetta needs
(TSO, the parity/adjust flags, Apple's x86-style floating point). See [04](04-hardware-assists.md) §1.

## 3. Running: the instruction-level tricks

| Trick | What it does | Chapter |
|---|---|---|
| Whole-text AOT, rare JIT | Code stays in one place and is translated once: good for the instruction cache, with no JIT cost on hot paths. | [03](03-translation-techniques.md) §2 |
| Canonical state between instructions | Each x86 instruction maps to a short ARM sequence, and x86 state is exact at every boundary. That gives precise exceptions, sampling profilers and a working lldb. | [03](03-translation-techniques.md) §2 |
| Only two cross-instruction optimisations | Skip computing flags that nobody reads, and merge function prologues/epilogues into paired loads/stores. | [03](03-translation-techniques.md) §2 |
| Fixed register map | RAX–R15 → x0–x15 by x86 encoding order (so RSP is x4, RBP is x5), XMM0–15 → v0–v15. x18 holds the thread context and x21 a private return stack. | [03](03-translation-techniques.md) §4 |
| Code layout for RIP-relative data | Translated code is placed after the original image, so `ADRP`+`ADD` can reach x86 data directly. | [03](03-translation-techniques.md) §3 |
| x86 flags in ARM's NZCV | The carry is stored **inverted** (x86 borrow vs ARM carry), and `CFINV`, `RMIF`, `SETF8`/`SETF16` fix up the rest. | [03](03-translation-techniques.md) §5, [04](04-hardware-assists.md) §2 |
| PF/AF in hardware | An undocumented Apple mode makes `ADDS`/`SUBS` also compute x86's parity and adjust flags, into NZCV bits 26–27. Not available inside Linux VMs, where it's done in software. | [04](04-hardware-assists.md) §2 |
| Return prediction kept alive | x86 CALL/RET become ARM `BL`/`RET`, with a checked stack of (x86 return address, ARM target) pairs, so the CPU's return predictor still works. | [03](03-translation-techniques.md) §7 |
| Indirect branches | Inline caches for import calls; a hashed x86→ARM lookup for other targets; the JIT on a miss. | [03](03-translation-techniques.md) §7 |
| SSE → NEON | All common SSE operations become optimised NEON sequences, not scalar code or helper calls. | [03](03-translation-techniques.md) §10 |
| x87 | A full 80-bit software implementation (about 75 runtime helpers). Correct but slow. | [03](03-translation-techniques.md) §10 |
| AVX/AVX2 (macOS 15+) | Each 256-bit operation is split into two NEON halves, with the upper halves kept in memory. Not advertised in CPUID unless asked, because the AVX2 path is often slower than SSE2. AVX-512 is not supported. | [03](03-translation-techniques.md) §10, [06](06-history-and-timeline.md) §3.4 |
| Memory ordering | Hardware TSO mode, so ordinary ARM loads and stores behave like x86 ones, with no barriers in translated code. | [04](04-hardware-assists.md) §1 |
| FP semantics | An Apple-specific FP mode (on M3/M4, Arm's standard FEAT_AFP) reproduces x86 NaN, underflow and flush-to-zero behaviour exactly. | [04](04-hardware-assists.md) §3 |
| 4 KB pages | Translated processes get real 4 KB user page tables on a 16 KB-page kernel. | [04](04-hardware-assists.md) §4 |

## 4. Talking to the OS

- **System calls and Mach traps:** the runtime converts the x86-64 macOS calling convention to the arm64
  kernel's. [02](02-architecture-and-runtime.md) §5
- **Signals and crashes:** a fault in translated code is mapped back to the x86 instruction and an x86
  register context, so signal handlers and crash reports see x86 state. [02](02-architecture-and-runtime.md) §5
- **Debugging:** lldb uses a Rosetta-aware `debugserver` and sees x86 registers. [02](02-architecture-and-runtime.md) §5
- **CPUID:** translated code sees a virtual CPU (brand `VirtualApple @ 2.50GHz` on recent versions)
  with no AVX-512. [02](02-architecture-and-runtime.md) §6
- **No mixed processes:** a process is entirely arm64 or entirely x86-64; plug-ins must match.
  [01](01-apple-official.md)

## 5. Rosetta for Linux

Since macOS 13 the Virtualization framework can share Rosetta into Linux VMs
(`VZLinuxRosettaDirectoryShare`, registered in the guest with `binfmt_misc`). AOT caching for guests
came in macOS 14 (`rosettad`). In macOS 27 the Linux translator is built into macOS. Inside a VM,
Rosetta can't enable the host CPU's PF/AF mode, so it computes those flags in software.
[05](05-rosetta-for-linux.md)

## 6. How fast, and where it's slow

| Case | Translated speed vs native ARM64 | Chapter |
|---|---|---|
| General CPU work, M1 (Geekbench 5, SPEC) | ~0.73–0.79 | [07](07-performance.md) §1 |
| Geekbench 6, M2 Max | ~0.48 | [07](07-performance.md) §1 |
| JIT-heavy apps (JS engines, JVM) | ~0.35–0.6 | [07](07-performance.md) §2 |
| TSO mode itself | costs ~9% (multithreaded SPEC FP, M1 Ultra) | [04](04-hardware-assists.md) §1 |
| Slow spots | x87, AVX2 paths, JIT churn, first-launch translation (Office took ~20 s at launch) | [07](07-performance.md) §2 |

## 7. History in five lines

68k emulator on PowerPC (1994) → Rosetta 1, PowerPC → x86 from Transitive's QuickTransit (2006, removed
in Lion) → Rosetta 2 with macOS 11 Big Sur (2020) → Rosetta for Linux (macOS 13), AVX/AVX2 (macOS 15) →
general-purpose Rosetta ends after macOS 27; macOS 28 keeps only older games and Linux VMs.
[06](06-history-and-timeline.md)

## 8. The "insane tricks", ranked by how much they matter

1. **Deterministic AOT plus the trust cache:** system translations are pre-verified by Apple at build
   time without shipping them.
2. **Custom silicon for x86 semantics:** TSO, PF/AF flags and x86 floating-point mode, all switched per thread.
3. **Canonical state at every instruction:** debugger, exceptions and profilers just work, and the
   translator stays simple and fast enough to run at install time.
4. **Return-stack pairing:** CALL/RET stay predictable on the ARM core.
5. **Inverted-carry convention:** most compares need no flag fix-up at all.
6. **Unused-flag elimination:** most flag-setting x86 instructions become non-flag-setting ARM ones.
7. **Prologue/epilogue fusion:** a software version of x86's hardware "stack engine".
8. **Layout for `ADRP`:** RIP-relative x86 data stays one instruction pair away.
9. **The kernel loads the runtime instead of dyld:** translation is invisible to the app.
10. **Honest feature advertising:** AVX hidden by default because translating it can be slower than SSE2.
