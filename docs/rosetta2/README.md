# Rosetta 2 research notes

How Apple's Rosetta 2 (the x86-64 → ARM64 translator on Apple silicon Macs) works, compiled from public
sources: Apple's documentation and WWDC sessions, Apple's published XNU source, the Arm and Intel manuals,
and named third-party research. No Apple code is reproduced. Research cut-off: 31 October 2026.

Start with the overview, then read any chapter on its own.

| # | Chapter | Covers |
|---|---|---|
| 00 | [Overview](00-overview.md) | The whole pipeline end to end, and the main tricks ranked |
| 01 | [What Apple has said](01-apple-official.md) | WWDC sessions, developer docs, stated limits by macOS version, detection and control APIs |
| 02 | [Architecture and runtime](02-architecture-and-runtime.md) | Components and paths, launch flow in XNU, AOT files and cache, JIT path, syscalls, signals, debugging, CPUID |
| 03 | [Translation techniques](03-translation-techniques.md) | Register map, flags, control flow, memory operations, SSE/x87/AVX, special instructions |
| 04 | [Hardware assists](04-hardware-assists.md) | TSO memory ordering, flag-manipulation instructions, PF/AF extension, x86-style floating point, 4 KB pages |
| 05 | [Rosetta for Linux](05-rosetta-for-linux.md) | Virtualization framework APIs, guest setup, caching, tools that use it, licence terms |
| 06 | [History and timeline](06-history-and-timeline.md) | 68k emulator, Rosetta 1, Rosetta 2 release by release, related translators |
| 07 | [Performance](07-performance.md) | Benchmarks against native, slow cases, Apple's guidance, comparisons with other translators |

## Provenance labels

Each claim in the chapters carries a label and a link:

| Label | Meaning |
|---|---|
| **[Apple]**, **[Apple doc]**, **[WWDC]**, **[Apple support]** | Apple's own documentation, sessions or support articles |
| **[XNU source]** | Apple's published kernel source (file and function named) |
| **[Arm spec]**, **[Linux kernel]** | Architecture manuals and kernel source or mailing lists |
| **[RE: author]** | Published third-party reverse-engineering research, by named author |
| **[Benchmark: source]**, **[press]**, **[project docs]** | Measurements, news coverage, third-party project documentation |
| **[Inferred]** | Reasoning by the authors of these notes, not a sourced fact |

Each chapter ends with **Open questions** (unconfirmed or conflicting claims) and **Sources**.
