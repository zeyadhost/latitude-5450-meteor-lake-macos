# Rosetta 2: CPU Hardware Assists

*Scope.* The CPU and kernel features that let Rosetta 2 translate x86-64 code to arm64
quickly and correctly on Apple silicon Macs: the memory-ordering (TSO) mode, the
condition-flag instructions, Apple's parity/adjust-flag extension, the x86-style
floating-point modes, 4 KB pages for translated processes, and a few smaller items. Each
section ends with an **On Intel x86 (Meteor Lake)** note that asks whether the reverse
translator this project wants to build (arm64 guest on x86-64 host) needs an equivalent.
Related documents in this folder:

- launch flow, AOT/JIT pipeline, runtime: [02-architecture-and-runtime.md][02]
- how Rosetta actually emits code for flags, memory and floating point (this document
  only covers the hardware those techniques rely on): [03-translation-techniques.md][03]

*What this document is not.* It describes how the hardware works and how kernels and
open-source translators use it. It does not describe running Rosetta outside Apple's
supported setup or getting around any of its checks.

*Provenance labels.*

| Label | Meaning |
|---|---|
| **[Arm spec]** | Arm Architecture Reference Manual (Arm ARM), Arm register/instruction pages, Arm feature documentation |
| **[Apple]** | Apple documentation, WWDC sessions, Apple's published XNU kernel source, patches posted by Apple engineers |
| **[Linux kernel]** | Kernel source and documentation, mailing-list patches and replies (including Asahi Linux's downstream kernel) |
| **[RE: author]** | Reverse engineering or measurement by the named person or team |
| **[Intel spec]** | Intel SDM and Intel extension specifications (often via felixcloutier.com, an unofficial extract of the SDM) |
| **[Project]** | Documentation or source of an emulator or VMM project (FEX-Emu, Box64, QEMU, Microsoft Prism docs) |
| **[Measured]** | Measured for this project on the team's Latitude 5450 (Intel Core Ultra 5 135U, Meteor Lake) |
| **[Inferred]** | My own reasoning from the cited facts; no source states it |
| **[Low confidence]** | Forum posts, comment sections, social media; leads only |

*Chip naming.* LLVM treats M1 as an A14-class core, M2 as A15-class, M3 as A16-class and M4
as its own entry (Armv9.2-class with SME) [62]. "All M-series" below means M1 to M4.

**Jargon used below.**
- **EL0/EL1/EL2**: Arm exception levels: user mode, kernel, hypervisor.
- **IMPDEF** (implementation defined): a register or bit whose meaning the Arm architecture
  leaves to the chip designer. `ACTLR_EL1` (auxiliary control) and `AIDR_EL1` (auxiliary ID)
  are entirely IMPDEF [2].
- **HID registers**: Apple's IMPDEF "hardware implementation defined" registers, mostly
  "chicken bits" that switch micro-architectural features on or off [2].
- **TSO** (total store order): x86's memory model. **RCsc/RCpc**: the two flavours of Arm
  acquire/release ordering (explained in 1.6).
- **NZCV**: the arm64 condition flags. **EFLAGS**: the x86 flags register.
- **Single-copy atomic**: an access that other cores see entirely or not at all.
- **Translation granule**: the page size used by the MMU page tables (4, 16 or 64 KB on Arm).
- **prctl**: a Linux system call for per-process settings. **HWCAP**: Linux's feature bits
  exported to user space.

---

## Key findings

1. **TSO is an Apple IMPDEF mode, not an Arm feature.** `ACTLR_EL1` bit 1 switches the core
   to x86-like ordering and `AIDR_EL1` bit 9 advertises it [2][4][14]. The register is per core,
   so kernels make it per thread by saving and restoring it on every context switch [13][5].
   The instruction pattern that a reverse-engineering tool matches in the M1 macOS kernel sets
   bits 1, 4, 5 and 6 together on the way back to a flagged (Rosetta) thread: TSO, the PF/AF
   extension, Apple's FP mode and an undocumented "PRSV" bit [5][3].
2. **On Linux the TSO control is still downstream only.** Asahi Linux's `PR_SET_MEM_MODEL`
   prctl (used by FEX-Emu) was rejected upstream by the arm64 maintainers in 2024 [20][23].
   Upstream Linux still had no such prctl on 2026-10-31 [26], while Asahi's branch carried it
   rebased on Linux 7.2 [17]. An Apple engineer posted a variant for Linux guests on macOS 14.4+
   [18], and macOS 15 lets hypervisors set a guest's `ACTLR_EL1` [35].
3. **TSO costs about 9% on average for native multithreaded code** (SPEC CPU2017 FP on an M1
   Ultra) [29][30]. Software emulation of TSO on CPUs without the mode costs far more: FEX
   reports close to 10x in the worst cases [68]. Acquire/release instructions on M1 are slower
   than either mode [30].
4. **The standard Arm flag instructions cover most of the x86/Arm flag mismatch.** FEAT_FlagM
   (`CFINV`, `RMIF`, `SETF8`, `SETF16`) and FEAT_FlagM2 (`AXFLAG`, `XAFLAG`) are on every
   M-series chip [82][83][85]. After `FCMP`, `AXFLAG` leaves Z = x86 ZF and C = NOT x86 CF in
   all four compare outcomes, which matches Rosetta's inverted-carry convention [54][97][1].
5. **Apple added hardware PF and AF.** Dougall Johnson found that with an undocumented mode on,
   `ADDS`, `SUBS` and `CMP` write x86's parity and adjust flags into otherwise-reserved NZCV
   bits 26 and 27 [1]. XNU calls the enable bit `ACTLR_EL1_EnAPFLG` [3]; a 2026 test on an M1
   reproduced the effect [7]. Inside Linux VMs Rosetta cannot use it and computes PF in
   software [1].
6. **x86 floating-point semantics come from two different mechanisms.** M1 (and, judging by
   its feature bits, M2) uses Apple's pre-standard mode: `ACTLR_EL1` bit 5 plus an Apple
   `AFPCR_EL0` register with x86-style DAZ/FTZ bits [2][1]. M3 and M4 also implement Arm's
   standard FEAT_AFP (`FPCR.AH`, `FIZ`, `NEP`) and FEAT_RPRES; M2 reports neither [83][84][85].
   With `FPCR.AH=1`, an M4 matches x86 on NaN encoding, NaN propagation, tininess, flush-to-zero,
   `FMA(0,∞,qNaN)` and min/max [10].
7. **Translated macOS processes get real 4 KB pages.** XNU supports a 4 KB user-half page-table
   granule per process while the kernel stays at 16 KB [39][38][3]. `hw.pagesize` reports the
   task's map page size [40], and under Rosetta it reads 4096 [88]. Linux cannot mix page sizes,
   so Asahi runs FEX inside a 4 KB-page micro-VM [89][90].
8. **Other standard features help:** FEAT_LSE2 (unaligned atomicity inside 16-byte blocks),
   FEAT_LRCPC/LRCPC2 (cheap acquire loads) and FEAT_FRINTTS (x86-style out-of-range float-to-int)
   are on all M-series chips [82][83][85][49][60]. macOS defines no capability bit for
   FEAT_LRCPC3 [34][36].
9. **Chip differences that matter here:** M1 = Armv8.4 plus a hand-picked set of v8.5 features
   [62]. On M2 and later, Asahi's KVM patch switches a guest's TSO bit through the
   architectural `ACTLR_EL12` encoding, while M1 needs Apple's IMPDEF encoding; the patch itself
   labels the M2 path "architectural?" [16]. M3 adds FEAT_AFP and FEAT_RPRES [83]. M4 adds SME,
   which nothing public links to Rosetta [62][85].
10. **On Meteor Lake the problems mostly reverse or disappear.** x86 is already TSO, has PF/AF
    and 4 KB pages. The real gaps for an arm64 guest are elsewhere: Arm's *default* FP
    semantics, conditional compare and flag-free ALU ops (APX, absent), and 31 vs 16
    general-purpose registers [Measured][1][107].

---

## Summary table

`*` = inferred, not directly documented for that chip.

| x86→Arm problem | Hardware assist | Kind | M1 | M2 | M3 | M4 | Turned on by |
|---|---|---|---|---|---|---|---|
| Memory ordering | TSO mode (`ACTLR_EL1[1]`) | Apple IMPDEF | yes [2] | yes [16] | yes* | yes* | kernel, per thread |
| Carry sense, bit-to-flag moves, 8/16-bit flags | FEAT_FlagM | Arm v8.4 | yes [82] | yes [83] | yes [83] | yes [85] | always on |
| FP-compare flags in x86 layout | FEAT_FlagM2 | Arm v8.5 | yes [82] | yes [83] | yes [83] | yes [85] | always on |
| PF and AF | APFLG (`ACTLR_EL1[4]`) | Apple IMPDEF | yes [1][7] | ?* | ?* | ?* | kernel |
| x86 NaN/tininess/DAZ/FTZ/min-max | Apple FP mode (`ACTLR_EL1[5]` + `AFPCR_EL0`) | Apple IMPDEF | yes [2] | yes* | ? | ? | kernel |
| same, standard version | FEAT_AFP (`FPCR.AH/FIZ/NEP`) | Arm v8.7 | no [82] | no [83] | yes [83] | yes [85] | user space |
| 12-bit reciprocal estimates | FEAT_RPRES (needs `AH=1`) | Arm v8.7 | no [82] | no [83] | yes [83] | yes [85] | user space |
| x86 "integer indefinite" conversions | FEAT_FRINTTS | Arm v8.5 | yes [82] | yes [83] | yes [83] | yes [85] | always on |
| Unaligned/128-bit atomicity | FEAT_LSE2 | Arm v8.4 | yes [82] | yes [83] | yes [83] | yes [85] | always on |
| Cheap acquire loads (software TSO) | FEAT_LRCPC, LRCPC2 | Arm v8.3/v8.4 | yes [82] | yes [83] | yes [83] | yes [85] | always on |
| 4 KB pages on a 16 KB OS | 4 KB `TCR_EL1.TG0` per process | Arm architecture + XNU | yes [87][88] | yes* | yes* | yes* | kernel |

---

## 1. Memory ordering (TSO)

### 1.1 The problem

x86 implements TSO. Each core's stores become visible to other cores in program order, loads
are not reordered with other loads, and the only visible reordering is a later load passing
an earlier store that is still in the store buffer [94]. The Arm model allows far more
reordering. Apple tells developers that Arm code must order shared accesses explicitly with
barriers or atomics [33]. A translator that turns every x86 `MOV` into a plain `LDR`/`STR`
therefore breaks multithreaded x86 programs. FEX-Emu found, for example, that Unity games
crash without TSO emulation [67].

### 1.2 What is publicly known about Apple's TSO mode

| Fact | Source |
|---|---|
| `ACTLR_EL1` bit 1 enables TSO. XNU names it `ACTLR_EL1_EnTSO`; Apple's Linux patch calls it `ACTLR.TSOEN` | **[RE: Asahi]** [2], **[Apple]** [3][19] |
| `AIDR_EL1` bit 9 says TSO is supported (other bits: 4 AMX, 19 APFLG, 20 "PSRV") | **[RE: Asahi]** [2], **[Linux kernel]** [14] |
| Apple implements an IMPDEF `ACTLR_EL12` (`s3_6_c15_c14_6`) with VHE-style aliasing, so a hypervisor can reach the guest's copy. Guest accesses to `ACTLR_EL1` trap via `HCR_EL2.TACR` and Apple's `HACR_EL2` bit 0 | **[RE: Hector Martin]** [4] |
| Older XNU headers name HID9 bit 16 `TSO_ENABLE`, HID9 bit 26 `TSOAllowDcZvaWC`, HID9 bit 29 `TSOSerializeVLDmicroops`, E-core HID10 bit 49 `DisZVATemporalTSO` and HID11 bit 1 `DisX64NTLnchOpt`. Their exact effects are not documented | **[Apple]** [9], **[RE: Asahi]** [2] |
| With TSO on, ordinary loads and stores get the ordering they would have on x86 | **[RE: Dougall Johnson]** [1], **[RE: Wrenger et al.]** [30] |
| Apple's public statement: Rosetta "fully supports the Intel memory ordering" | **[Apple]** [32] |

*What it guarantees, exactly, is not public.* There is no published formal model. Arm
maintainer Catalin Marinas objected: "I can't even tell exactly what TSO means on the Apple
hardware" [23]. The researchers who benchmarked it say the implementation details and limits
are not public [30]. The HID bit names hint that cache-zeroing (`DC ZVA`), vector loads and
non-temporal stores get special handling in TSO mode [9]. One measurement saw M1 stop issuing
non-temporal store micro-ops when TSO was on [31]. **[Inferred]** A translator author cannot
assume from public sources that every Arm instruction class (SIMD multi-register loads,
`STNP`, `DC ZVA`, exclusives) obeys TSO in this mode.

*Other Arm CPUs.* NVIDIA Denver and Carmel and Fujitsu A64FX are always TSO. Asahi's patch
lists them as "fixed TSO" CPUs [15], and Dougall notes the same [1]. Running with TSO always on
is a valid implementation of the Arm model [20].

### 1.3 Granularity: per core in hardware, per thread in practice

`ACTLR_EL1` belongs to the core. Both macOS and Linux save and restore it on context switch,
which makes TSO a per-thread property. Different cores can be in different modes at the same
time [13][5][25].

**macOS.**
- XNU marks a translated process with the `P_TRANSLATED` flag at exec time **[Apple]** [42].
- The public XNU source defines the `ACTLR_EL1` bit names [3]. It does not contain the code
  that sets them: searching the published tree for TSO finds only the definitions **[Apple]**
  [3].
- **[RE: Saagar Jha]** TSOEnabler, a 2020 kernel extension, works on the M1 kernel by searching
  for this sequence: load a per-thread flag, skip if zero, read `ACTLR_EL1`, `ORR #0x2`,
  `ORR #0x70` [5]. Its README says the kernel sets the register "upon exit from the kernel" for
  Rosetta threads [5]. **[Inferred]** `0x2 | 0x70` = bits 1, 4, 5 and 6. macOS therefore turns
  on TSO, APFLG, Apple FP mode and PRSV together on the return-to-user path of a translated
  thread.

**Linux (Asahi downstream).**
- `prctl(PR_SET_MEM_MODEL, PR_SET_MEM_MODEL_TSO)` and `PR_GET_MEM_MODEL`. Downstream values are
  `PR_SET_MEM_MODEL = 0x4d4d444c` and `PR_GET_MEM_MODEL = 0x6d4d444c`, with `DEFAULT = 0` and
  `TSO = 1` **[Linux kernel]** [12][73]. The call may grant a stronger model than requested and
  fails if TSO is unavailable [12]. The setting is cleared on `execve` [24].
- Detection reads `AIDR_EL1` bit 9 on Apple-implementer CPUs. The thread's `ACTLR_EL1` copy is
  then set and written back [14]. A separate patch saves and restores `ACTLR_EL1` in thread
  state, but only when the system is known to need it, since the register's layout must be
  identical on all cores [13].
- Upstream: Will Deacon raised a "strong objection", arguing native arm64 programs would start
  relying on the toggle [20]. Catalin Marinas refused to accept an ABI for a
  non-architected feature [23]. Marc Zyngier ruled out exposing IMPDEF state to KVM guests and
  suggested enabling TSO for a whole VM from firmware instead [24][25].
- Status: when posted in April 2024 the series had already shipped downstream "to thousands of
  users", some of them running FEX [11]. Asahi's `bits/220-tso` branch still carried the four
  patches plus a KVM patch, rebased on Linux 7.2, in August 2026 [17]. Upstream
  `include/uapi/linux/prctl.h` had no `PR_SET_MEM_MODEL` on 2026-10-31 [26].

**Virtual machines.**
- Asahi's downstream KVM patch (Asahi Lina, May 2024) clears `HCR_EL2.TACR` so the guest can
  write `ACTLR_EL1` directly. It then context-switches the guest copy through Apple's IMPDEF
  `ACTLR_EL12` encoding on M1, and through the architectural `ACTLR_EL12` encoding on M2 and
  later (a path the patch labels "architectural?") **[Linux kernel]** [16]. **[Inferred]** This
  is what lets FEX inside Asahi's 4 KB-page micro-VM (section 4.3) use hardware TSO.
- Apple's Zayd Qumsieh posted patches so Linux guests running on macOS can toggle the bit. They
  need macOS Sonoma 14.4 or later; earlier versions did not allow the guest to change it
  **[Apple]** [18][19].
- macOS 15 added `HV_SYS_REG_ACTLR_EL1` to Hypervisor.framework, so VMMs can set a guest's
  `ACTLR_EL1` **[Apple]** [35].
- **[Low confidence]** A 2021 tool README says Parallels VMs on M1 ran with TSO on by default
  [113]. A 2024 Hacker News comment says Linux VMs ran with TSO on for all processes whenever
  Rosetta was enabled [114]. Neither is confirmed.

### 1.4 How FEX-Emu and Box64 use it on Asahi

- **FEX-Emu.** It calls `PR_GET_MEM_MODEL`. If its own TSO emulation is enabled, it then
  requests TSO; on success it switches off its atomics-based emulation, and threads inherit the
  setting **[Project]** [74][67]. FEX calls hardware TSO both a speed-up and a correctness fix
  [67].
- **Box64.** A code search of the Box64 tree found no use of the prctl **[Inferred]**. Its
  documented answer is `BOX64_DYNAREC_STRONGMEM`: level 0 does nothing (the default), levels
  1–3 add progressively more barriers, and level 4 mimics QEMU's approach [78].

### 1.5 Performance cost of the mode

| Measurement | Result | Source |
|---|---|---|
| SPEC CPU2017 FP speed, 20 threads, M1 Ultra, Asahi 6.3, same binaries with and without TSO | TSO 8.94% slower (geometric mean); weak ordering more than 2x faster in some synthetic tests | **[RE: Wrenger, Töllner, Lohmann]** [29][30] |
| `LDAR`/`STLR`/`LDAPR` microbenchmarks on M1 | acquire/release instructions slower than both plain weak and plain TSO accesses | [30] |
| Hector Martin's summary in the kernel thread | about 9% if TSO were on globally, so "off the table"; microbenchmarks often show TSO beating acquire/release | **[Linux kernel]** [22] |
| Single-copy SPECrate 2006/2017 on an M1 P-core | several benchmarks 11–64% (2006) and 17–38% (2017) slower with TSO | **[RE: Yangyu Chen]** [31] |
| Running an entire VM with TSO on (x86 containers on arm64) | about 25% on some workloads | **[Linux kernel]** Sergio López in [24] |
| FEX software TSO emulation on non-Apple Arm | "near a 10x performance hit" in bad cases, worst with vector-heavy game code | **[Project]** [68] |

The single-thread slowdowns in [31] are much larger than the multithreaded average in [30].
The two studies used different benchmark suites and settings, so treat the larger numbers as
unconfirmed.

### 1.6 What translators do on Arm CPUs without a TSO mode

| Technique | Detail | Source |
|---|---|---|
| Fence everything | QEMU-style: a barrier after every guest memory access. Box64 `STRONGMEM=4` imitates this | [30][78]; Alex Bennée (Linaro, QEMU) confirms it in the same kernel thread **[Linux kernel]** [20] |
| Acquire/release mapping | x86 loads become `LDAPR`/`LDAPUR` (FEAT_LRCPC/LRCPC2, the latter with a −256..255 immediate offset); stores become `STLR`/`STLUR` | **[Project]** [68][70] |
| Why that is enough | `LDAR`/`STLR` are RCsc: a load-acquire cannot move above an earlier store-release. `LDAPR` is RCpc and may move above an earlier `STLR` to a different address | **[Arm spec]** [45][46] |
| | **[Inferred]** Store→load is exactly the one reordering TSO allows, so `LDAPR` + `STLR` gives TSO without paying for sequential consistency | |
| Atomics | x86 `LOCK` operations map to LSE atomics (`CAS`, `LDADD`, `SWP`); Armv8.0 without LSE is "massive impact" | [68] |
| Unaligned accesses | Acquire/release and atomic instructions must be aligned. With FEAT_LSE2 they may be unaligned inside one 16-byte block; crossing it can fault | **[Arm spec]** [49][50] |
| | FEX patches a faulting access into a "half barrier" (`DMB` plus a plain load or store). For unaligned atomics crossing 16 bytes, Windows' Prism pauses every thread in the process (over 1000x slower). A 2026 FEX tool that maps which byte offsets fault shows many still do even with LSE2 | **[Project]** [69][70][81][72] |
| Heuristics | FEX skips TSO for stack accesses and by default for vector and `REP MOVS/STOS` accesses. Prism and FEX use the compiler's PE "volatile metadata" to find accesses that need ordering. Prism exposes "Fast / Strict / Very strict / single core" settings | [69][75][68][79][80] |
| Hardware pitfalls | FEX disabled FEAT_LRCPC2 on many Cortex/Neoverse cores because of a performance erratum, and notes LRCPC on Cortex is barely faster than full atomics | [71][67] |
| What would help more | FEAT_LRCPC3 (Armv8.9, 2022) adds acquire/release pairs and vector forms; FEX said in April 2024 that no shipping hardware had it | [64][68] |

### 1.7 Do the efficiency cores support TSO? (conflicting claims)

- Claims that they do not: an Apple StackExchange comment (2020) [112], an LWN reader comment
  (2024) [25], and TSOEnabler's README, which says enabling TSO pins threads to performance
  cores [5]. All **[Low confidence]**.
- Evidence that they do: TSOEnabler's A12Z (Developer Transition Kit) branch explicitly binds
  the thread to the P cluster, but the M1 version contains no such call [6][5]. On an M1 the
  TSO bit is writable on all eight cores, E-cores included **[RE: generic-account]** [7]. An
  E-core-only HID register has a TSO-related bit [9]. Asahi enables TSO per thread on any core
  [14]. A search of the public XNU tree found no code binding translated threads to P-cores.
- Asahi's micro-VM tool `muvm` defaults to performance cores "if applicable" without saying why
  [93].
- **[Inferred]** The "P-cores only" rule probably dates from the A12Z developer kit. M1 E-cores
  at least implement the bit. Not confirmed for M2–M4.

### On Intel x86 (Meteor Lake)

- **The problem is absent.** x86-TSO is stronger than Arm's model, so plain arm64 `LDR`/`STR`
  become plain `MOV`s [94]. **[Inferred]** The following mapping follows the C/C++11 mapping
  tables [95] and Arm's RCsc rule [45]:
  - `DMB ISHLD` and `DMB ISHST` need no instruction, only a compiler barrier.
  - `DMB ISH` needs `MFENCE` or a locked instruction.
  - `LDAR`, `LDAPR` and `STLR` become plain `MOV`s.
  - **Except:** an `STLR` followed by an `LDAR` must not be reordered. Emit that `STLR` as
    `XCHG`, or as `MOV` + `MFENCE`, exactly as compilers do for a C++ `seq_cst` store.
- **[Inferred]** x86 has no load-linked/store-conditional pair (Arm's `LDXR`/`STXR`), so
  exclusives must become `LOCK CMPXCHG` loops. Section 9 of
  [03-translation-techniques.md][03] covers the software side.
- **16-byte atomicity.** Arm with FEAT_LSE2 makes an aligned 16-byte `LDP`/`STP` single-copy
  atomic [49]. Intel guarantees 16-byte atomicity for aligned `(V)MOVDQA`/`MOVAPS` on CPUs that
  report AVX **[Intel spec]** [109]. Meteor Lake reports AVX and `CMPXCHG16B` **[Measured]**.
- **Transactional memory.** HLE/RTM (TSX) are absent on the Core Ultra 5 135U **[Measured]**,
  so there is nothing to lean on for emulating `LDXR`/`STXR` with transactions.

---

## 2. Condition flags

### 2.1 The mismatch

x86 EFLAGS has six status flags: CF, PF, AF, ZF, SF and OF. PF is set when the low byte of the
result has an even number of 1 bits; AF is the carry or borrow out of bit 3 [96]. Almost every
x86 ALU instruction writes them. Arm has four flags, written only by the "S" instruction
variants. NZCV bits 27:0 are reserved, and architecturally an `MRS NZCV` reads them as zero
[56]. The friction points Dougall Johnson lists [1]:

1. **Carry sense.** Arm subtraction sets C = NOT borrow; x86 sets CF = borrow.
2. **PF and AF** have no Arm counterpart.
3. **8- and 16-bit operations** must produce flags for the narrow result.
4. **Shifts** move a bit into CF and must leave the flags untouched when the count is zero.
5. **FP compares.** `UCOMISS` sets ZF, PF and CF [97]; `FCMP` sets NZCV in a different layout
   [59].

### 2.2 FEAT_FlagM (Armv8.4; optional from v8.1)

| Instruction | Operation (Arm pseudocode) | x86 use |
|---|---|---|
| `CFINV` | C ← NOT C [51] | Rosetta keeps CF in the inverted (subtraction) sense, because `CMP` is far more common than flag-consuming `ADD`. It issues `CFINV` after an `ADD` whose carry is used or escapes, and before add-with-carry [1] |
| `RMIF Xn, #rot, #mask` | rotate Xn right by `#rot`, then copy the low 4 bits into whichever of N/Z/C/V `#mask` selects [52] | move any register bit into any flag, e.g. the bit shifted out by an x86 shift into CF [1] |
| `SETF8 Wn` / `SETF16 Wn` | N ← bit 7 (15); Z ← low 8 (16) bits are zero; V ← bit 8 XOR bit 7 (bit 16 XOR bit 15); C unchanged [53] | flags for x86 8/16-bit arithmetic [1]. **[Inferred]** That V formula is signed overflow when the narrow operands were sign-extended and added in 32 bits |

FlagM is mandatory from Armv8.4 **[Arm spec]** [47]; Linux exposes it as `HWCAP_FLAGM` [27]
and macOS as `hw.optional.arm.FEAT_FlagM` [34]. FEX also emits `RMIF` and `SETF8` when the host
has FlagM, and tracks an inverted carry the way Rosetta does **[Project]** [76]. Dougall notes
that variable-count shifts stay expensive when their flags escape, because a zero count must
leave the flags unchanged, which needs a branch [1].

### 2.3 FEAT_FlagM2 (Armv8.5)

`AXFLAG` sets Z ← Z OR V and C ← C AND NOT V, and clears N and V. `XAFLAG` performs the inverse
conversion [54][55]. Arm describes the target as "an alternative representation required by
some software" [54]. Dougall: "By some strange coincidence, this format is x86" [1]. LLVM names
the feature "AlternativeNZCV" [63].

**[Inferred]** Derived from `FPCompare` [59], `AXFLAG` [54] and `UCOMISS` [97]:

| Compare result | NZCV after `FCMP` | After `AXFLAG` (Z, C) | x86 `UCOMISS` (ZF, PF, CF) |
|---|---|---|---|
| greater | 0010 | 0, 1 | 0, 0, 0 |
| less | 1000 | 0, 0 | 0, 0, 1 |
| equal | 0110 | 1, 1 | 1, 0, 0 |
| unordered | 0011 | 1, 0 | 1, 1, 1 |

In every row Z equals ZF and C equals NOT CF. That is the same inverted-carry convention as
2.2, so x86 `JA`/`JB`/`JE` after `UCOMISS` map onto plain Arm condition codes. PF ("unordered")
does not survive `AXFLAG`, so it must be taken from V first. FEX does exactly this: it notes
that some cores fuse `FCMP`+`AXFLAG`, and that unordered could only be recovered afterwards as
Z && !C, which needs two instructions [76]. `XAFLAG` turns flags in this x86 form back into Arm
compare form [55].

M1 is an Armv8.4 design but includes FlagM2. LLVM's M1 entry lists v8.5 extensions "excluding
BTI", including FlagM2 and FRINTTS [62]. Linux exposes it as `HWCAP2_FLAGM2` [27].

### 2.4 Apple's PF/AF extension ("APFLG")

- **[RE: Dougall Johnson, Nov 2022]** An undocumented M1 extension makes `ADDS`, `SUBS` and
  `CMP` compute PF and AF and store them in NZCV bits 26 and 27 respectively. That gives exact
  emulation at no cost [1]. It cannot be on all the time, because that would break the Arm
  specification, so Rosetta's threads switch it on [1]. Without it, a single subtraction grows to
  about five instructions just to produce PF, before AF is even computed [1].
- **Names.** `ACTLR_EL1_EnAPFLG` = bit 4 **[Apple]** [3]; "Enable APFLG" and `AIDR_EL1` bit 19
  "APFLG" **[RE: Asahi]** [2].
- **Virtual machines.** Rosetta for Linux cannot enable the extension, so it computes PF itself
  (and possibly AF). It relies on its "unused flags" pass to skip most of that work [1].
- **Independent check.** A 2026 Linux module set bit 4 on an M1 running the Asahi kernel. Its
  ADD/SUB tests then reported the expected PF and AF values, and without the bit they reported
  zero **[RE: generic-account]** [7].
- **Not public:** whether logical, 8/16-bit or other flag-setting instructions also produce
  PF/AF; how software reads and saves bits 26–27, given that `MRS NZCV` reads them as zero
  architecturally [56]; and whether M2–M4 behave the same.

### On Intel x86 (Meteor Lake)

- **[Inferred] Mostly absent.** x86 computes every Arm flag. N, Z and V map to SF, ZF and OF.
  For C, either keep Arm's carry in inverted form or flip it with `CMC`, the exact equivalent
  of `CFINV` [104].
- **The reverse hazard: x86 writes flags almost everywhere** [96]. **[Inferred]** A translator
  that holds an Arm guest's NZCV in host EFLAGS must use flag-preserving instructions for Arm
  operations that do not set flags: `LEA`, `MOV`, BMI2 `SHLX`/`SARX`/`SHRX`/`RORX`/`MULX` (no
  flags) [102], ADX `ADCX`/`ADOX` (touch only CF or OF) [103], and `LAHF`/`SAHF` to spill and
  restore. Meteor Lake has BMI1, BMI2, ADX and 64-bit `LAHF`/`SAHF` **[Measured]**.
- **Missing on x86.** Arm's `CCMP`/`CCMN` (conditional compare) and `CSINC`/`CSINV`/`CSNEG`.
  Intel APX adds conditional compare/test, a no-flags form of common instructions and 32
  general-purpose registers [107], but the 135U reports no APX **[Measured]**.
- **Register pressure.** x86-64 has half as many registers as arm64. Dougall calls Rosetta's
  "keep every guest register in a host register" approach a significant drawback for emulating
  arm64 on x86 [1].

---

## 3. Floating point

### 3.1 Where x86 SSE and Arm (default mode) differ

| Behaviour | x86 SSE | Arm, `FPCR.AH = 0` | Source |
|---|---|---|---|
| Tininess (underflow) detection | after rounding | before rounding | [10] |
| `FMA(0, ∞, qNaN)` | no Invalid flag | raises Invalid | [10] |
| NaN generated by an invalid operation | `0xFFC00000` (negative) | `0x7FC00000` (sign = 0) | [10][59] |
| Two NaN inputs, quiet + signalling | first operand wins | the signalling NaN wins | [10][59] |
| Flush-to-zero | separate MXCSR DAZ (inputs, bit 6) and FTZ (outputs, bit 15) | one `FPCR.FZ` flushes inputs and outputs | [106][105][57] |
| `MINSS`/`MAXSS` vs `FMIN`/`FMAX` | returns the second operand if either input is NaN or both are zero | propagates NaN; −0 < +0 | [100][59][10] |
| Scalar op, upper vector lanes | legacy SSE keeps the destination's; VEX copies from source 1 | zeroed | [99][57] |
| Float→int out of range or NaN | `0x80000000` "integer indefinite" | saturates; NaN → 0 | [98][59] |
| Reciprocal estimate | relative error ≤ 1.5×2⁻¹², implementation-specific | exact 8-bit table result | [101][61] |

Most programs never notice these. Dougall notes some do, and that checking them in software
on every FP operation would be expensive; Rosetta handles them in hardware [1]. mod_poppo ran
test programs for these cases under Rosetta 2 on an M4: Rosetta reproduced the x86 result in
every case, and recent Rosetta also handles FMA instructions [10].

### 3.2 Apple's pre-standard mode (M1; M2 by inference)

- `ACTLR_EL1` bit 5 = `EnAFP` **[Apple]** [3]. Asahi: it makes `FPCR.FZ` a don't-care and
  replaces it with `AFPCR_EL0` (`s3_6_c15_c2_5`) DAZ (bit 0) and FTZ (bit 1), the SSE-style
  mode bits **[RE: Asahi]** [2]. Asahi's m1n1 bootloader has a test script for exactly this
  [8].
- Dougall: the M1 predates Armv8.7's standard FEAT_AFP, so Rosetta uses a non-standard
  implementation that also covers NaN bit patterns and tininess [1].
- `ACTLR_EL1` bit 6 = `EnPRSV` ("Enable PRSV"), and `AIDR_EL1` bit 20 "PSRV". No public source
  says what they do [2][3]. **[Inferred hypothesis]** Preserving the upper vector lanes in
  scalar FP operations, the job `FPCR.NEP` does on M3/M4. Going by the kernel code pattern in
  1.3, it is set together with the AFP bit on translated threads [5].
- M2 reports no FEAT_AFP [83]. **[Inferred]** Rosetta on M2 must still rely on Apple's mode.
- **[Inferred]** The `_EL0` suffix suggests user mode can access `AFPCR_EL0`. The m1n1 script
  carries a commented-out EL0 read test [8]. Not confirmed.

### 3.3 FEAT_AFP (standard; optional from Armv8.6, required in Armv8.7 cores with FP)

Presence: `ID_AA64MMFR1_EL1.AFP` [48]. Linux exposes `HWCAP2_AFP` [27]; macOS exposes
`hw.optional.arm.FEAT_AFP`, detected from the same ID field [36][37]. The controls are three
`FPCR` bits: FIZ (bit 0), AH (bit 1) and NEP (bit 2). User mode can write `FPCR` [57], and Linux
saves it per thread with the FP registers [28], so **no kernel support is needed beyond the
HWCAP**. That is the key practical difference from Apple's `ACTLR`-based mode.

| Bit | Effect relevant to x86 | Source |
|---|---|---|
| **AH** | Default NaN gets sign 1 (`0xFFC00000`) | **[Arm spec]** [59], [65] |
| | When both inputs are NaN, the first operand's NaN is used, quieted | [59] |
| | Tininess is detected after rounding | [65][10] |
| | `FZ` now flushes only outputs (x86 FTZ) | [57][59] |
| | `FMIN`/`FMAX` return the second operand for NaN inputs (raising Invalid) and for zeros of different sign, as x86 `MINSS` does | [59][100] |
| | `FMA(0,∞,qNaN)` no longer raises Invalid | [10][65] |
| | Estimate instructions use round-to-nearest and flush, without exceptions | [61][57] |
| | Side effect that is *not* x86-like: `FABS`/`FNEG` leave a NaN's sign alone | [10] |
| **FIZ** | Flush denormal inputs to zero (x86 DAZ) | [57][59] |
| **NEP** | Scalar operations merge the upper lanes from an input register instead of zeroing them (see table below) | [57][58] |

Mapping MXCSR to FPCR with `AH = 1` **[Inferred]** from [57][106]: DAZ → `FIZ`, FTZ → `FZ`,
rounding control → `RMode` (both architectures have the same four modes).

Where `NEP` takes the upper lanes from **[Arm spec]** [58] (QEMU implements the same rules [66]):

| Instruction class | Upper lanes come from | x86 counterpart **[Inferred]** |
|---|---|---|
| 2-input arithmetic (`FADD`, `FSUB`, `FMUL`, `FDIV`, `FMIN`, `FMAX`, …) | first source `Rn` | VEX `VADDSS dst, src1, src2` copies from src1 [99]; legacy SSE keeps dst, which is src1 |
| 2-input compares (`FCMEQ`, `FCMGE`, `FCMGT`, `FACGE`, `FACGT`) | second source `Rm` | `CMPLTSS a,b` becomes `FCMGT b,a`; the swapped operands put the x86 first operand in `Rm` |
| 1-input ops (`FSQRT`, `FRINT*`, `FCVT`, `SCVTF`, `FRECPE`, …) | destination `Rd` | legacy `SQRTSS xmm1, xmm2` keeps xmm1's upper lanes |
| `FMADD` family | the addend `Ra` | — |
| `FMLA`/`FMLS` by element | destination | — |

**FEAT_RPRES.** When `AH = 1`, single-precision `FRECPE` and `FRSQRTE` return 12 fraction bits
instead of 8 **[Arm spec]** [61][65]. That is close to x86 `RCPSS`/`RSQRTSS` precision
(≤ 1.5×2⁻¹²) [101]. **[Inferred]** It cannot be bit-identical, because x86 leaves the exact
estimate to each implementation [101].

**Experiments.** On an M4 Pro, `AH = 1` made every tested behaviour except `FABS`/`FNEG` match a
Zen 4 x86 machine **[RE: mod_poppo]** [10]. A reader repeated the test on a Snapdragon X Elite
and found FEAT_AFP there too, with Windows' x64 emulator reproducing x86 results
**[Low confidence]**, comment on [10].

**Translators.** FEX sets `NEP` and `AH` (and `FIZ` when the guest enables DAZ) on entry to
JIT code and clears all three on exit [77]. With AFP available, x86 `MIN`/`MAX` become
`FMIN`/`FMAX`, which leave NZCV alone; without it they need an `FCMP` that clobbers the flags
[76]. Box64 lists `afp` among the optional host extensions it uses [78].

### 3.4 FEAT_FRINTTS (Armv8.5): x86-style float-to-int overflow

`FRINT32Z`/`FRINT64Z` (and the `…X` forms) round to an integral FP value that fits in 32 or
64 bits. For infinity, NaN or out-of-range input they return the most negative integer and
raise Invalid **[Arm spec]** [60]. Plain `FCVTZS` instead saturates and turns NaN into 0 [59].
x86 `CVTTSS2SI` returns `0x80000000` (or `0x8000000000000000`) for out-of-range input [98].
**[Inferred]** `FRINT32Z` followed by `FCVTZS` therefore yields x86's "integer indefinite" in
two instructions with no compare. FEX uses FRINTTS in its conversion paths when the host has
it [76]. No public source shows Rosetta doing the same. All M-series have FRINTTS (the M1's
Linux feature list includes `frint`) [82][62].

### 3.5 Chip support

| | M1 | M2 | M3 | M4 |
|---|---|---|---|---|
| Apple FP mode (`ACTLR_EL1[5]` + `AFPCR_EL0`) | yes [2] | probably* | ? | ? |
| FEAT_AFP | no (`afp` absent from Linux features) [82] | no (sysctl 0 on M2 Ultra) [83] | yes (M3 Max) [83][84] | yes (M4 Pro) [84][85] |
| FEAT_RPRES | no [82] | no [83] | yes [83] | yes [85] |
| FEAT_FRINTTS | yes [82] | yes [83] | yes [83] | yes [85] |

**Open:** whether Rosetta on M3/M4 uses the standard `FPCR` bits or still Apple's `ACTLR` mode.

### On Intel x86 (Meteor Lake)

- **The problem reverses.** **[Inferred]** x86 SSE behaviour is fixed and corresponds to Arm's
  `AH = 1` model. An arm64 guest normally runs with `AH = 0`, so a translator on x86 must
  rebuild Arm's *default* behaviour in software wherever exactness matters:
  - NaN choice when both inputs are NaN, and SNaN priority;
  - the sign of generated NaNs (fix `0xFFC00000` → `0x7FC00000`);
  - `FMIN`/`FMAX`/`FMINNM`/`FMAXNM` semantics;
  - saturating float→int with NaN → 0;
  - FZ flushing before rounding versus x86 FTZ after rounding;
  - the UFC/Invalid flag differences.
- **Scalar upper lanes.** Arm zeroes them; legacy SSE preserves the destination's and VEX
  copies src1's [99]. **[Inferred]** The translator must zero the upper lanes unless it knows
  they are already zero (for example after a scalar load).
- **Hardware that would help, but is absent.** AVX10.2 adds saturating float→int conversions
  that return 0 for NaN, and IEEE 754-2019 minimum/maximum (`VMINMAX*`) [108]. The 135U has no
  AVX-512 and no AVX10 **[Measured]**.
- **Partial help.** MXCSR's separate DAZ and FTZ bits can express Arm's `FZ` (both), `FIZ` and
  `AH`-mode `FZ` [106][105]. Arm's default-NaN mode (`FPCR.DN`) and the saturation flag
  (`FPSR.QC`) have no x86 counterpart **[Inferred]** [57].
- **Estimates.** Arm's `FRECPE`/`FRSQRTE` results are defined bit-exactly by pseudocode tables
  [61]; x86 estimates are approximate and vary by implementation [101]. **[Inferred]**
  Bit-exact emulation needs a software table.

---

## 4. Page size

### 4.1 The problem

x86-64 software assumes 4 KB pages. Apple silicon macOS uses 16 KB, and Apple tells developers
to read `vm_page_size` rather than assume [33][32]. Code that bakes in 4 KB alignment for
`mmap`, `mprotect`, guard pages or JIT regions breaks on 16 KB pages [86].

### 4.2 macOS: real 4 KB page tables for translated processes

- **Developer Transition Kit (A12Z, 2020).** Rosetta ran x86 code on 16 KB pages. Apple's DTK
  release notes, as quoted in a Chromium commit, said applications depending on a 4K page size
  would not run [86].
- **M1 and later.** WWDC 2020: "the CPU on Apple Silicon Macs will support 4 kB pages for
  translated processes" **[Apple]** [32]. GitHub user zwarich, commenting on a .NET issue:
  Rosetta uses 4 KB pages on M1, and 16 KB was a DTK limitation [87].
- **Observed.** Under Rosetta, `getpagesize()` (via `hw.pagesize`) returns 4096 while
  `vm_kernel_page_size` returns 16384 [88].
- **Mechanism visible in Apple's published XNU source** **[Apple]**:
  - The pmap (XNU's page-table layer) has a 4 KB page-table geometry, `pmap_pt_attr_4k`,
    whose `TCR` value selects a 4 KB translation granule (`TG0`) for the user half of the
    address space. The kernel half keeps its 16 KB granule (`TG1`) [39][3].
  - `PMAP_CREATE_FORCE_4K_PAGES` selects that geometry, and the exec loader then gives the VM
    map a 4 KB page shift [38]. There is a 4 KB-page commpage [39] and a 4 KB shared-region
    variant [41].
  - `hw.pagesize` returns the calling task's map page size [40], so the 4096 seen under Rosetta
    means the translated process's map really is 4 KB.
  - `vm_kernel_page_size` stays 16 KB for translated processes [88]. **[Inferred]** The kernel
    still manages physical memory in 16 KB units and maps 4 KB slices of them.
- **Not visible.** In the published tree, 4 KB mode is selected only by a private `posix_spawn`
  flag (`_POSIX_SPAWN_FORCE_4K_PAGES`) [38][42]; the trigger for translated processes does not
  appear. **[Inferred]** Either the launch path sets that flag, or Apple left the logic out of
  the published source, as it did with the TSO code (1.3).
- The older "fourk pager", which emulated 4 KB-aligned mappings on 16 KB systems, is gone: the
  loader now rejects mis-aligned binaries [38].

### 4.3 Linux on Apple silicon

- Asahi kernels use 16 KB pages because the IOMMUs (DART) only handle 16 KB. 4 KB kernels boot
  but need hacks and lose GPU acceleration. Asahi notes that XNU solves this with per-process
  page sizes, which Linux lacks [89][21].
- So Asahi runs x86 software (FEX, or Box64 as an option) inside **muvm**, a micro-VM whose
  guest kernel uses 4 KB pages, with the GPU paravirtualised through DRM native context
  [90][91][93]. Asahi rejected emulating 4 KB pages inside FEX in favour of the VM, and closed
  FEX's issue as "not planned" [92].
- 32-bit Windows games can now skip muvm, because Windows gives every allocation 64 KB
  granularity. Programs that hard-code 4 KB still need the VM [91].

### On Intel x86 (Meteor Lake)

- x86-64 paging offers only 4 KB, 2 MB and 1 GB pages **[Intel spec]** [110].
- **[Inferred]** This is the easy direction. arm64 guests expect 4, 16 or 64 KB pages, all
  multiples of 4 KB. The translator reports the guest's page size and rounds or aligns `mmap`,
  `mprotect` and `munmap` to it. Every guest-aligned range is also host-aligned, so no hardware
  help is needed. The hard case, a guest wanting *smaller* pages than the host, which is
  Rosetta's case, does not arise.

---

## 5. Other features researchers have linked to Rosetta

| Item | What is known | Source |
|---|---|---|
| FEAT_LSE2, FEAT_LRCPC, FEAT_LRCPC2 | On every M-series chip; Apple documents the `hw.optional.arm.*` keys. LSE2 makes unaligned accesses inside a 16-byte block single-copy atomic, and aligned 16-byte `LDP`/`STP` atomic | [34][82][83][85], **[Arm spec]** [49] |
| FEAT_LRCPC3 | No macOS capability bit exists for it | **[Apple]** [36], **[Inferred]** |
| x18 | XNU preserves register x18 across context switches for translated threads (x86-64 translation always switches it) | **[Apple]** [43] |
| Timebase | XNU keeps translated tasks on the "Apple timebase" even when a native task built with a recent SDK would get the 1 GHz timebase | **[Apple]** [44] |
| `ACTLR_EL12` | Apple IMPDEF encoding on M1; Asahi uses the architectural encoding on M2 and later | **[RE: Hector Martin]** [4], **[Linux kernel]** [16] |
| Hypervisor access | macOS 14.4+ lets Linux guests toggle TSO; macOS 15 exposes `HV_SYS_REG_ACTLR_EL1` | **[Apple]** [18][35] |
| HID9/EHID10/HID11 TSO-named bits | Bit names only (1.2). A July 2020 tweet, quoted in a blog, told people reversing TSOEnabler to start from references to HID9 (`S3_0_c15_c9_0`). **[Inferred]** That suggests the A12Z kit switched TSO through HID9 rather than `ACTLR_EL1` | **[Apple]** [9], **[Low confidence]** [111] |
| Snapdragon X (non-Apple) | AnandTech reportedly said Qualcomm Oryon has hardware help for x86 floating point and memory ordering; not detailed publicly | **[Low confidence]** [115] |

### Chip-by-chip differences

| | M1 | M2 | M3 | M4 |
|---|---|---|---|---|
| LLVM base ISA | Armv8.4 + v8.5 subset (FlagM2, FRINTTS, SB, SSBS, …; no BTI) [62] | Armv8.6 (BF16, I8MM) [62] | Armv8.6 [62] | Armv8.7 in LLVM, "technically v9.2a"; SME/SME2 [62] |
| TSO mode | documented (Asahi, XNU) [2][3] | yes (Asahi KVM handles M2+) [16] | yes* | yes* |
| Guest `ACTLR` switching | IMPDEF `ACTLR_EL12` | architectural `ACTLR_EL12` [16] | as M2* | as M2* |
| PF/AF extension | documented [1][7] | ? | ? | ? |
| FP mode | Apple `ACTLR`/`AFPCR` [2] | Apple mode* (no FEAT_AFP) [83] | FEAT_AFP + RPRES [83] | FEAT_AFP + RPRES [85] |
| FlagM/FlagM2/FRINTTS/LSE2/LRCPC2 | yes [82] | yes [83] | yes [83] | yes [85] |

LLVM also has an `apple-m5` entry (adding MTE, CSSC, HBC and more) [62]. Nothing public ties
those features to Rosetta.

---

## 6. What this means for an arm64 → x86-64 translator on Meteor Lake

CPUID on the target laptop (Core Ultra 5 135U), read with a small self-written probe under
Windows 11 **[Measured]**. A hypervisor such as Hyper-V/VBS can hide some bits, so treat 0 as
"not visible to user code".

| Feature | Present | Why it matters |
|---|---|---|
| AVX, AVX2, FMA3, F16C | 1 | 128/256-bit SIMD for NEON; fused multiply-add for Arm `FMADD` |
| CMPXCHG16B | 1 | `CASP`, 16-byte exclusives |
| BMI1, BMI2, ADX, LZCNT | 1 | flag-free shifts and multiplies; `CLZ`; carry chains |
| LAHF/SAHF in 64-bit mode | 1 | cheap flag spills |
| SHA, VAES, GFNI | 1 | Arm SHA/AES instructions; GFNI can help with bit reversal (`RBIT`) **[Inferred]** |
| AVX-VNNI | 1 | dot products (`SDOT`/`UDOT` analogues) |
| AVX-512F, AVX10 | 0 | no masked ops, no AVX10.2 saturating converts or min/max |
| APX | 0 | no 32 GPRs, no conditional compare, no no-flags forms |
| HLE/RTM (TSX) | 0 | no hardware transactions |
| Hybrid flag | 1 | P-cores and E-cores in one package |

| Rosetta-side assist | Reverse-direction status **[Inferred]** |
|---|---|
| TSO mode | Not needed: x86 is TSO. Only `STLR`→`LDAR` (and `DMB ISH`) need `XCHG`/`MFENCE` [95][45] |
| FlagM / FlagM2 | Mostly unnecessary: x86 has the flags and `CMC`. The real costs are x86's implicit flag writes and the missing `CCMP` |
| PF/AF extension | Not needed: Arm has no PF/AF |
| AFP / NEP / RPRES / FRINTTS | Reversed: Arm-default FP semantics, upper-lane zeroing and saturating conversions need software sequences on Meteor Lake |
| 4 KB pages | Not needed: the host already has the smaller page |
| Register file | Gap: 31 arm64 GPRs on 16 x86 GPRs means spilling, unlike Rosetta [1] |

---

## Open questions

1. **What does Apple's TSO mode cover exactly?** No formal model has been published [23][30].
   Do SIMD multi-register accesses, `STNP`, `DC ZVA`, `LDP`/`STP` pairs and exclusives all obey
   it, and is it identical on M1–M4? The HID bit names suggest special cases [9].
2. **Do E-cores run TSO threads?** Claims conflict (1.7). Is P-core binding an A12Z-era leftover?
3. **What does `PRSV` (`ACTLR_EL1` bit 6, `AIDR_EL1` bit 20) do?** Judging by the kernel code
   pattern it is set alongside the FP bit for translated threads [5]; upper-lane preservation
   is only a hypothesis.
4. **On M3/M4, does Rosetta use standard `FPCR.AH/FIZ/NEP` or Apple's `ACTLR` FP mode?** No RE
   found either way.
5. **APFLG details:** which instructions write PF/AF, how the bits are saved and restored given
   that `MRS NZCV` architecturally reads them as zero [56], and whether M2–M4 have it.
6. **Which code path makes macOS translated processes 4 KB?** Only a private spawn flag is
   visible in the published XNU [38].
7. **TSO in Linux VMs before macOS 14.4.** Were guests run with TSO always on, as two
   low-confidence sources suggest [113][114]? Does Rosetta for Linux use TSO when available?
8. **Size of the TSO penalty:** about 9% multithreaded [30] versus up to 64% single-threaded in
   some benchmarks [31]. The methods differ, and nothing reconciles them.
9. **Split locks.** How does Rosetta handle x86 `LOCK` operations that cross a 16-byte block or
   a cache line? Nothing public describes it.
10. **Minor conflicts found:**
    - Wrenger et al. call the M1 an ARMv8.3-A design [30], while LLVM models it as v8.4 plus
      some v8.5 features [62].
    - A 2022 comment by Dougall describes PF as set for an odd number of 1 bits [1]; Intel
      defines it as set for an even number [96]. The main text of [1] is unaffected.

---

## Sources

Reverse engineering and Rosetta-specific
- [1] Dougall Johnson, "Why is Rosetta 2 fast?" (2022-11-09, with later updates and author
  comments). https://dougallj.wordpress.com/2022/11/09/why-is-rosetta-2-fast/
- [2] Asahi Linux documentation, "System Registers". https://asahilinux.org/docs/hw/cpu/system-registers/
- [3] Apple XNU source, `osfmk/arm64/proc_reg.h` (xnu-12377.1.9).
  https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/proc_reg.h
- [4] Hector Martin, "Apple TSO" (gist, 2023). https://gist.github.com/marcan/9ab73ca0614864bea0eea9e953c074d3
- [5] Saagar Jha, TSOEnabler (README and M1 source). https://github.com/saagarjha/TSOEnabler
- [6] Saagar Jha, TSOEnabler `t8020` (A12Z DTK) branch source.
  https://github.com/saagarjha/TSOEnabler/blob/t8020/TSOEnabler/TSOEnabler.c
- [7] generic-account, "m1-secret-extension-enable-linux" (2026).
  https://github.com/generic-account/m1-secret-extension-enable-linux
- [8] Asahi Linux m1n1, `proxyclient/experiments/fptest.py`.
  https://github.com/AsahiLinux/m1n1/blob/main/proxyclient/experiments/fptest.py
- [9] Apple XNU source, `pexpert/pexpert/arm64/apple_arm64_regs.h` (xnu-7195.81.3).
  https://github.com/apple-oss-distributions/xnu/blob/xnu-7195.81.3/pexpert/pexpert/arm64/apple_arm64_regs.h
- [10] mod_poppo (だめぽ), "Testing Armv8.7 FEAT_AFP on Apple M4: Floating-Point Operation
  Differences Between x86 and Arm" (Zenn, 2024-11-21; updated 2025-05-21, including reader
  comments). https://zenn.dev/mod_poppo/articles/arm-feat_afp?locale=en

Linux kernel and mailing lists
- [11] Hector Martin, "[PATCH 0/4] arm64: Support the TSO memory model" (2024-04-11), LWN copy.
  https://lwn.net/Articles/969484/
- [12] Hector Martin, "[PATCH 1/4] prctl: Introduce PR_{SET,GET}_MEM_MODEL".
  https://lists.openwall.net/linux-kernel/2024/04/11/41
- [13] Hector Martin, "[PATCH 3/4] arm64: Introduce scaffolding to add ACTLR_EL1 to thread state".
  https://lists.openwall.net/linux-kernel/2024/04/11/44
- [14] Hector Martin, "[PATCH 4/4] arm64: Implement Apple IMPDEF TSO memory model control".
  https://lists.openwall.net/linux-kernel/2024/04/11/45
- [15] Asahi Linux kernel, "arm64: Implement PR_{GET,SET}_MEM_MODEL for always-TSO CPUs".
  https://github.com/AsahiLinux/linux/commit/9dfe372a62d2
- [16] Asahi Lina, "KVM: arm64: Expose TSO capability to guests and context switch" (2024-05-25).
  https://github.com/AsahiLinux/linux/commit/e62bae1fc060
- [17] Asahi Linux kernel, branch `bits/220-tso` (rebased on Linux 7.2, 2026-08).
  https://github.com/AsahiLinux/linux/commits/bits/220-tso
- [18] Zayd Qumsieh (Apple), "[PATCH 0/3] tso: aarch64: Expose TSO for virtualized linux on Apple Silicon".
  https://lists.infradead.org/pipermail/linux-arm-kernel/2024-April/919137.html
- [19] Zayd Qumsieh, "[PATCH 1/3] tso: aarch64: allow linux kernel to read/write ACTLR.TSOEN".
  https://lkml.iu.edu/hypermail/linux/kernel/2404.1/04591.html
- [20] Will Deacon, "Re: [PATCH 0/4] arm64: Support the TSO memory model" (with Alex Bennée's
  QEMU remark in the same thread on Patchew). https://lists.openwall.net/linux-kernel/2024/04/11/952 ;
  https://patchew.org/linux/20240411-tso-v1-0-754f11abfbff@marcan.st/
- [21] Hector Martin, reply (pragmatic argument; 16 KB-only IOMMUs; 4 KB VMs).
  https://lists.openwall.net/linux-kernel/2024/04/11/1075
- [22] Hector Martin, reply (about 9% figure). https://lists.openwall.net/linux-kernel/2024/04/11/1930
- [23] Catalin Marinas, reply (NAK). https://lists.openwall.net/linux-kernel/2024/04/19/983
- [24] Marc Zyngier, reply quoting Sergio López and Hector Martin (2024-05-06).
  https://lkml.iu.edu/2405.0/05240.html
- [25] Jonathan Corbet, "Support for the TSO memory model on Arm CPUs", LWN (2024-04-26), and
  reader comments. https://lwn.net/Articles/970907/
- [26] Linux upstream `include/uapi/linux/prctl.h` (checked 2026-10-31, tree at 7.4-rc1 merge window).
  https://github.com/torvalds/linux/blob/master/include/uapi/linux/prctl.h
- [27] Linux `Documentation/arch/arm64/elf_hwcaps.rst`.
  https://github.com/torvalds/linux/blob/master/Documentation/arch/arm64/elf_hwcaps.rst
- [28] Linux `arch/arm64/include/uapi/asm/ptrace.h` (`struct user_fpsimd_state`).
  https://github.com/torvalds/linux/blob/master/arch/arm64/include/uapi/asm/ptrace.h

Measurements
- [29] L. Wrenger, D. Töllner, D. Lohmann, "TOSTING: Investigating Total Store Ordering on ARM"
  (ARCS 2023). https://www.sra.uni-hannover.de/Publications/2023/tosting-arcs23/
- [30] L. Wrenger, D. Töllner, D. Lohmann, "Analyzing the memory ordering models of the Apple M1",
  Journal of Systems Architecture (2024). https://doi.org/10.1016/j.sysarc.2024.103102
- [31] Yangyu Chen, "Is TSO a historical burden for modern CPU? Case study on Apple M1".
  https://blog.cyyself.name/tso-apple-m1/

Apple
- [32] WWDC20 session 10214, "Port your Mac app to Apple silicon" (transcript).
  https://developer.apple.com/videos/play/wwdc2020/10214/
- [33] Apple, "Addressing architectural differences in your macOS code".
  https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code
- [34] Apple, "Determining instruction set characteristics".
  https://developer.apple.com/documentation/kernel/1387446-sysctlbyname/determining_instruction_set_characteristics
- [35] Apple, `HV_SYS_REG_ACTLR_EL1` (Hypervisor framework, macOS 15.0+).
  https://developer.apple.com/documentation/hypervisor/hv_sys_reg_actlr_el1
- [36] Apple XNU source, `osfmk/arm/cpu_capabilities_public.h`.
  https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm/cpu_capabilities_public.h
- [37] Apple XNU source, `osfmk/arm/commpage/commpage.c` (FEAT_AFP detection).
  https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm/commpage/commpage.c
- [38] Apple XNU source, `bsd/kern/mach_loader.c`.
  https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/mach_loader.c
- [39] Apple XNU source, `osfmk/arm64/sptm/pmap/pmap.c`.
  https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/sptm/pmap/pmap.c
- [40] Apple XNU source, `bsd/kern/kern_mib.c`.
  https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_mib.c
- [41] Apple XNU source, `osfmk/vm/vm_shared_region.c`.
  https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/vm/vm_shared_region.c
- [42] Apple XNU source, `bsd/kern/kern_exec.c`.
  https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exec.c
- [43] Apple XNU source, `osfmk/arm64/pcb.c`.
  https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/pcb.c
- [44] Apple XNU source, `osfmk/arm64/machine_task.c`.
  https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/machine_task.c

Arm
- [45] Arm, "Learn the architecture: Memory Systems, Ordering, and Barriers", Load-Acquire and
  Store-Release. https://support.arm.com/documentation/102336/0101/Load-Acquire-and-Store-Release-instructions
- [46] Arm Community blog, "When a barrier does not block: the pitfalls of partial order" (2025).
  https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/when-a-barrier-does-not-block-the-pitfalls-of-partial-order
- [47] Arm, "Feature names in A-profile architecture": Armv8.4.
  https://developer.arm.com/documentation/109697/latest/Feature-descriptions/The-Armv8-4-architecture-extension
- [48] Arm, "Feature names in A-profile architecture": Armv8.7.
  https://developer.arm.com/documentation/109697/latest/Feature-descriptions/The-Armv8-7-architecture-extension
- [49] Arm ARM B2.2.1, "Requirements for single-copy atomicity".
  https://support.arm.com/documentation/ddi0487/md/-Part-B-The-AArch64-Application-Level-Architecture/-Chapter-B2-The-AArch64-Application-Level-Memory-Model/-B2-2-Atomicity-in-the-Arm-architecture/-B2-2-1-Requirements-for-single-copy-atomicity
- [50] Arm ARM B2.8.2, "Alignment of data accesses".
  https://support.arm.com/documentation/ddi0487/md/-Part-B-The-AArch64-Application-Level-Architecture/-Chapter-B2-The-AArch64-Application-Level-Memory-Model/-B2-8-Alignment-support/-B2-8-2-Alignment-of-data-accesses
- [51] Arm A64 ISA, `CFINV`. https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/CFINV--Invert-carry-flag-
- [52] Arm A64 ISA, `RMIF`. https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/RMIF--Rotate--mask-insert-flags-
- [53] Arm A64 ISA, `SETF8`, `SETF16`. https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/SETF8--SETF16--Evaluation-of-8-bit-or-16-bit-flag-values-
- [54] Arm A64 ISA, `AXFLAG`. https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/AXFLAG--Convert-floating-point-condition-flags-from-Arm-to-external-format-
- [55] Arm A64 ISA, `XAFLAG`. https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/XAFLAG--Convert-floating-point-condition-flags-from-external-format-to-Arm-format-
- [56] Arm ARM C5.2.11, NZCV. https://support.arm.com/documentation/ddi0487/md/-Part-C-The-AArch64-Instruction-Set/-Chapter-C5-The-A64-System-Instruction-Class/-C5-2-Special-purpose-registers/-C5-2-11-NZCV--Condition-Flags
- [57] Arm A-profile registers, FPCR. https://developer.arm.com/documentation/ddi0601/latest/AArch64-Registers/FPCR--Floating-point-Control-Register
- [58] Arm C1-Pro Core TRM, FPCR (the full `FPCR.NEP` register list).
  https://support.arm.com/documentation/107771/0103/AArch64-registers/AArch64-Generic-System-Control-registers-summary/FPCR--Floating-point-Control-Register
- [59] Arm A64 shared pseudocode, floating-point functions (`FPToFixed`, `FPUnpack`,
  `FPProcessNaNs`, `FPDefaultNaN`, `FPCompare`, `FPMin`).
  https://support.arm.com/documentation/111182/2025-09_ASL1/Shared-Pseudocode/shared-functions-float
- [60] Arm A64 ISA, `FRINT32Z` (FEAT_FRINTTS). https://support.arm.com/documentation/ddi0602/2026-09/SIMD-FP-Instructions/FRINT32Z--scalar---Floating-point-round-to-32-bit-integer-toward-zero--scalar--
- [61] Arm ARM J1.4, `FPRecipEstimate` pseudocode (FEAT_RPRES).
  https://support.arm.com/documentation/ddi0487/md/-Part-J-Architectural-Pseudocode/-Chapter-J1-A-profile-Architecture-Pseudocode/-J1-4-Shared-pseudocode/-J1-4-364-FPRecipEstimate

Toolchains and emulators
- [62] LLVM, `llvm/lib/Target/AArch64/AArch64Processors.td`.
  https://github.com/llvm/llvm-project/blob/main/llvm/lib/Target/AArch64/AArch64Processors.td
- [63] LLVM, `llvm/lib/Target/AArch64/AArch64Features.td`.
  https://github.com/llvm/llvm-project/blob/main/llvm/lib/Target/AArch64/AArch64Features.td
- [64] LLVM review D138579, "Assembly support for FEAT_LRCPC3". https://reviews.llvm.org/D138579
- [65] Peter Maydell, "[PATCH v2 00/69] target/arm: FEAT_AFP and FEAT_RPRES" (QEMU, 2025).
  https://patchew.org/QEMU/20250201164012.1660228-1-peter.maydell@linaro.org/
- [66] QEMU commit "target/arm: Handle FPCR.NEP for 3-input scalar operations".
  https://github.com/qemu/qemu/commit/0378199dc2fdf90550f9a819701b0c1709b34eab
- [67] FEX-Emu, "FEX 2306 Tagged" (2023). https://fex-emu.com/FEX-2306/
- [68] FEX-Emu, FEX-2404 release notes. https://github.com/FEX-Emu/FEX/releases/tag/FEX-2404
- [69] FEX-Emu, "FEX 2405 Tagged". https://fex-emu.com/FEX-2405/
- [70] FEX-Emu, "FEX 2501 Tagged". https://fex-emu.com/FEX-2501/
- [71] FEX-Emu, "FEX 2512 Tagged". https://fex-emu.com/FEX-2512/
- [72] FEX-Emu, "FEX 2604 Tagged". https://fex-emu.com/FEX-2604/
- [73] FEX source, `FEXCore/include/FEXCore/Utils/PrctlUtils.h`.
  https://github.com/FEX-Emu/FEX/blob/main/FEXCore/include/FEXCore/Utils/PrctlUtils.h
- [74] FEX source, `Source/Tools/FEXInterpreter/FEXInterpreter.cpp`.
  https://github.com/FEX-Emu/FEX/blob/main/Source/Tools/FEXInterpreter/FEXInterpreter.cpp
- [75] FEX source, `FEXCore/Source/Interface/Config/Config.json.in`.
  https://github.com/FEX-Emu/FEX/blob/main/FEXCore/Source/Interface/Config/Config.json.in
- [76] FEX source, `FEXCore/Source/Interface/Core/OpcodeDispatcher.h` (and the `FRINTTS`, `rmif`,
  `setf8` uses in the same directory). https://github.com/FEX-Emu/FEX/blob/main/FEXCore/Source/Interface/Core/OpcodeDispatcher.h
- [77] FEX source, `FEXCore/Source/Interface/Core/ArchHelpers/Arm64Emitter.cpp`.
  https://github.com/FEX-Emu/FEX/blob/main/FEXCore/Source/Interface/Core/ArchHelpers/Arm64Emitter.cpp
- [78] Box64, `docs/USAGE.md`. https://github.com/ptitSeb/box64/blob/main/docs/USAGE.md
- [79] Microsoft Learn, "Adjust emulation settings on Arm".
  https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-program-compat-troubleshooter
- [80] Microsoft Learn, "/volatileMetadata". https://learn.microsoft.com/en-us/cpp/build/reference/volatile?view=msvc-170
- [81] NVIDIA, "Memory Ordering and Other Porting Issues", Windows on Arm porting guide.
  https://docs.nvidia.com/rtx-spark/rtx-spark-porting-guide/latest/portingandemulation/volatilesoutlinedatomics.html

Feature dumps
- [82] M1 `/proc/cpuinfo` under Asahi Linux (sysinfo issue #1073).
  https://github.com/GuillaumeGomez/sysinfo/issues/1073
- [83] llama.cpp PR #10543 (M3 Max and M2 Ultra `sysctl hw.optional.arm` output).
  https://github.com/ggerganov/llama.cpp/pull/10543
- [84] mod_poppo, "M4 Mac miniを買った" (M4 Pro sysctl; M3 store-demo observation).
  https://blog.miz-ar.info/2024/11/m4-mac-mini/
- [85] Qiita, "Apple Silicon M4はM3シリーズからSME命令などが足されている" (M4 Pro sysctl).
  https://qiita.com/zacky1972/items/69fd802fd41ae4d7d469

Page size
- [86] Chromium commit 4ebd0722 ("mac: Make the system page size a run-time property"), quoting
  the DTK release notes. https://chromium.googlesource.com/chromium/src/+/4ebd0722856c86d339a13242bb2f5de77466895a
- [87] dotnet/runtime issue #44897 (comment by Cameron Zwarich, 2020-11-26).
  https://github.com/dotnet/runtime/issues/44897
- [88] gopsutil PR #1334 (page sizes under Rosetta). https://github.com/shirou/gopsutil/pull/1334
- [89] Asahi Linux documentation, "Broken Software". https://asahilinux.org/docs/sw/broken-software/
- [90] Asahi Linux, "AAA gaming on Asahi Linux" (2024-10). https://asahilinux.org/2024/10/aaa-gaming-on-asahi-linux/
- [91] Asahi Linux, "Progress Report: Linux 6.16" (2025-08). https://asahilinux.org/2025/08/progress-report-6-16/
- [92] FEX-Emu issue #1921, "4k page emulation". https://github.com/FEX-Emu/FEX/issues/1921
- [93] AsahiLinux/muvm README. https://github.com/AsahiLinux/muvm

Intel and x86
- [94] P. Sewell et al., "x86-TSO: A Rigorous and Usable Programmer's Model for x86
  Multiprocessors", CACM (2010). https://dl.acm.org/doi/fullHtml/10.1145/1785414.1785443
- [95] "C/C++11 mappings to processors" (Cambridge). https://www.cl.cam.ac.uk/~pes20/cpp/cpp0xmappings.html
- [96] Intel SDM Vol. 1 §3.4.3.1, status flags (mirror).
  https://xem.github.io/minix86/manual/intel-x86-and-64-manual-vol1/o_7281d5ea06a5b67a-76.html
- [97] `UCOMISS` (felixcloutier.com). https://www.felixcloutier.com/x86/ucomiss
- [98] `CVTTSS2SI`. https://www.felixcloutier.com/x86/cvttss2si
- [99] `ADDSS`. https://www.felixcloutier.com/x86/addss
- [100] `MINSS`. https://www.felixcloutier.com/x86/minss
- [101] `RCPSS`. https://www.felixcloutier.com/x86/rcpss
- [102] `SARX/SHLX/SHRX`. https://www.felixcloutier.com/x86/sarx:shlx:shrx
- [103] `ADCX`. https://www.felixcloutier.com/x86/adcx
- [104] `CMC`. https://www.felixcloutier.com/x86/cmc
- [105] Intel, "Set the FTZ and DAZ Flags".
  https://www.intel.com/content/www/us/en/docs/dpcpp-cpp-compiler/developer-guide-reference/2026-0/set-the-ftz-and-daz-flags.html
- [106] Intel SDM Vol. 1 §10.2.3, MXCSR (mirror).
  https://xem.github.io/minix86/manual/intel-x86-and-64-manual-vol1/o_7281d5ea06a5b67a-240.html
- [107] Intel, "Introducing Intel Advanced Performance Extensions (Intel APX)".
  https://www.intel.com/content/www/us/en/developer/articles/technical/advanced-performance-extensions-apx.html
- [108] Intel AVX10.2 Architecture Specification, with the x86-64.net summary used here.
  https://cdrdv2-public.intel.com/836199/361050-intel-avx10.2-spec.pdf ; https://x86-64.net/isa/avx10-2/
- [109] GCC patch "libatomic: Improve 16-byte atomics on Intel AVX [PR104688]", quoting the Intel SDM.
  https://www.mail-archive.com/gcc-patches@gcc.gnu.org/msg280720.html
- [110] Intel SDM Vol. 3A Table 4-1, page sizes per paging mode, reproduced in IIT CS450 slides.
  https://moss.cs.iit.edu/cs450/slides/08-vm-d.pdf

Low-confidence leads
- [111] vickieGPT, "The measurement of TSO on M1 Max" (2021), quoting a July 2020 tweet by
  @never_released. https://asplos.dev/wordpress/2021/12/16/the-measurement-of-tso-on-m1-max/
- [112] Apple StackExchange comment by jksoegaard (2020-12-06).
  https://apple.stackexchange.com/posts/407733/timeline
- [113] losfair/tsotest README. https://github.com/losfair/tsotest
- [114] Hacker News comment (2024-01-20). https://news.ycombinator.com/item?id=39064974
- [115] Real World Technologies forum, quoting AnandTech on Oryon (2024-06).
  https://www.realworldtech.com/forum/?curpostid=218321&threadid=218321

[02]: 02-architecture-and-runtime.md
[03]: 03-translation-techniques.md
[1]: https://dougallj.wordpress.com/2022/11/09/why-is-rosetta-2-fast/
[2]: https://asahilinux.org/docs/hw/cpu/system-registers/
[3]: https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/proc_reg.h
[4]: https://gist.github.com/marcan/9ab73ca0614864bea0eea9e953c074d3
[5]: https://github.com/saagarjha/TSOEnabler
[6]: https://github.com/saagarjha/TSOEnabler/blob/t8020/TSOEnabler/TSOEnabler.c
[7]: https://github.com/generic-account/m1-secret-extension-enable-linux
[8]: https://github.com/AsahiLinux/m1n1/blob/main/proxyclient/experiments/fptest.py
[9]: https://github.com/apple-oss-distributions/xnu/blob/xnu-7195.81.3/pexpert/pexpert/arm64/apple_arm64_regs.h
[10]: https://zenn.dev/mod_poppo/articles/arm-feat_afp?locale=en
[11]: https://lwn.net/Articles/969484/
[12]: https://lists.openwall.net/linux-kernel/2024/04/11/41
[13]: https://lists.openwall.net/linux-kernel/2024/04/11/44
[14]: https://lists.openwall.net/linux-kernel/2024/04/11/45
[15]: https://github.com/AsahiLinux/linux/commit/9dfe372a62d2
[16]: https://github.com/AsahiLinux/linux/commit/e62bae1fc060
[17]: https://github.com/AsahiLinux/linux/commits/bits/220-tso
[18]: https://lists.infradead.org/pipermail/linux-arm-kernel/2024-April/919137.html
[19]: https://lkml.iu.edu/hypermail/linux/kernel/2404.1/04591.html
[20]: https://lists.openwall.net/linux-kernel/2024/04/11/952
[21]: https://lists.openwall.net/linux-kernel/2024/04/11/1075
[22]: https://lists.openwall.net/linux-kernel/2024/04/11/1930
[23]: https://lists.openwall.net/linux-kernel/2024/04/19/983
[24]: https://lkml.iu.edu/2405.0/05240.html
[25]: https://lwn.net/Articles/970907/
[26]: https://github.com/torvalds/linux/blob/master/include/uapi/linux/prctl.h
[27]: https://github.com/torvalds/linux/blob/master/Documentation/arch/arm64/elf_hwcaps.rst
[28]: https://github.com/torvalds/linux/blob/master/arch/arm64/include/uapi/asm/ptrace.h
[29]: https://www.sra.uni-hannover.de/Publications/2023/tosting-arcs23/
[30]: https://doi.org/10.1016/j.sysarc.2024.103102
[31]: https://blog.cyyself.name/tso-apple-m1/
[32]: https://developer.apple.com/videos/play/wwdc2020/10214/
[33]: https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code
[34]: https://developer.apple.com/documentation/kernel/1387446-sysctlbyname/determining_instruction_set_characteristics
[35]: https://developer.apple.com/documentation/hypervisor/hv_sys_reg_actlr_el1
[36]: https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm/cpu_capabilities_public.h
[37]: https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm/commpage/commpage.c
[38]: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/mach_loader.c
[39]: https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/sptm/pmap/pmap.c
[40]: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_mib.c
[41]: https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/vm/vm_shared_region.c
[42]: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exec.c
[43]: https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/pcb.c
[44]: https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/machine_task.c
[45]: https://support.arm.com/documentation/102336/0101/Load-Acquire-and-Store-Release-instructions
[46]: https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/when-a-barrier-does-not-block-the-pitfalls-of-partial-order
[47]: https://developer.arm.com/documentation/109697/latest/Feature-descriptions/The-Armv8-4-architecture-extension
[48]: https://developer.arm.com/documentation/109697/latest/Feature-descriptions/The-Armv8-7-architecture-extension
[49]: https://support.arm.com/documentation/ddi0487/md/-Part-B-The-AArch64-Application-Level-Architecture/-Chapter-B2-The-AArch64-Application-Level-Memory-Model/-B2-2-Atomicity-in-the-Arm-architecture/-B2-2-1-Requirements-for-single-copy-atomicity
[50]: https://support.arm.com/documentation/ddi0487/md/-Part-B-The-AArch64-Application-Level-Architecture/-Chapter-B2-The-AArch64-Application-Level-Memory-Model/-B2-8-Alignment-support/-B2-8-2-Alignment-of-data-accesses
[51]: https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/CFINV--Invert-carry-flag-
[52]: https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/RMIF--Rotate--mask-insert-flags-
[53]: https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/SETF8--SETF16--Evaluation-of-8-bit-or-16-bit-flag-values-
[54]: https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/AXFLAG--Convert-floating-point-condition-flags-from-Arm-to-external-format-
[55]: https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/XAFLAG--Convert-floating-point-condition-flags-from-external-format-to-Arm-format-
[56]: https://support.arm.com/documentation/ddi0487/md/-Part-C-The-AArch64-Instruction-Set/-Chapter-C5-The-A64-System-Instruction-Class/-C5-2-Special-purpose-registers/-C5-2-11-NZCV--Condition-Flags
[57]: https://developer.arm.com/documentation/ddi0601/latest/AArch64-Registers/FPCR--Floating-point-Control-Register
[58]: https://support.arm.com/documentation/107771/0103/AArch64-registers/AArch64-Generic-System-Control-registers-summary/FPCR--Floating-point-Control-Register
[59]: https://support.arm.com/documentation/111182/2025-09_ASL1/Shared-Pseudocode/shared-functions-float
[60]: https://support.arm.com/documentation/ddi0602/2026-09/SIMD-FP-Instructions/FRINT32Z--scalar---Floating-point-round-to-32-bit-integer-toward-zero--scalar--
[61]: https://support.arm.com/documentation/ddi0487/md/-Part-J-Architectural-Pseudocode/-Chapter-J1-A-profile-Architecture-Pseudocode/-J1-4-Shared-pseudocode/-J1-4-364-FPRecipEstimate
[62]: https://github.com/llvm/llvm-project/blob/main/llvm/lib/Target/AArch64/AArch64Processors.td
[63]: https://github.com/llvm/llvm-project/blob/main/llvm/lib/Target/AArch64/AArch64Features.td
[64]: https://reviews.llvm.org/D138579
[65]: https://patchew.org/QEMU/20250201164012.1660228-1-peter.maydell@linaro.org/
[66]: https://github.com/qemu/qemu/commit/0378199dc2fdf90550f9a819701b0c1709b34eab
[67]: https://fex-emu.com/FEX-2306/
[68]: https://github.com/FEX-Emu/FEX/releases/tag/FEX-2404
[69]: https://fex-emu.com/FEX-2405/
[70]: https://fex-emu.com/FEX-2501/
[71]: https://fex-emu.com/FEX-2512/
[72]: https://fex-emu.com/FEX-2604/
[73]: https://github.com/FEX-Emu/FEX/blob/main/FEXCore/include/FEXCore/Utils/PrctlUtils.h
[74]: https://github.com/FEX-Emu/FEX/blob/main/Source/Tools/FEXInterpreter/FEXInterpreter.cpp
[75]: https://github.com/FEX-Emu/FEX/blob/main/FEXCore/Source/Interface/Config/Config.json.in
[76]: https://github.com/FEX-Emu/FEX/blob/main/FEXCore/Source/Interface/Core/OpcodeDispatcher.h
[77]: https://github.com/FEX-Emu/FEX/blob/main/FEXCore/Source/Interface/Core/ArchHelpers/Arm64Emitter.cpp
[78]: https://github.com/ptitSeb/box64/blob/main/docs/USAGE.md
[79]: https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-program-compat-troubleshooter
[80]: https://learn.microsoft.com/en-us/cpp/build/reference/volatile?view=msvc-170
[81]: https://docs.nvidia.com/rtx-spark/rtx-spark-porting-guide/latest/portingandemulation/volatilesoutlinedatomics.html
[82]: https://github.com/GuillaumeGomez/sysinfo/issues/1073
[83]: https://github.com/ggerganov/llama.cpp/pull/10543
[84]: https://blog.miz-ar.info/2024/11/m4-mac-mini/
[85]: https://qiita.com/zacky1972/items/69fd802fd41ae4d7d469
[86]: https://chromium.googlesource.com/chromium/src/+/4ebd0722856c86d339a13242bb2f5de77466895a
[87]: https://github.com/dotnet/runtime/issues/44897
[88]: https://github.com/shirou/gopsutil/pull/1334
[89]: https://asahilinux.org/docs/sw/broken-software/
[90]: https://asahilinux.org/2024/10/aaa-gaming-on-asahi-linux/
[91]: https://asahilinux.org/2025/08/progress-report-6-16/
[92]: https://github.com/FEX-Emu/FEX/issues/1921
[93]: https://github.com/AsahiLinux/muvm
[94]: https://dl.acm.org/doi/fullHtml/10.1145/1785414.1785443
[95]: https://www.cl.cam.ac.uk/~pes20/cpp/cpp0xmappings.html
[96]: https://xem.github.io/minix86/manual/intel-x86-and-64-manual-vol1/o_7281d5ea06a5b67a-76.html
[97]: https://www.felixcloutier.com/x86/ucomiss
[98]: https://www.felixcloutier.com/x86/cvttss2si
[99]: https://www.felixcloutier.com/x86/addss
[100]: https://www.felixcloutier.com/x86/minss
[101]: https://www.felixcloutier.com/x86/rcpss
[102]: https://www.felixcloutier.com/x86/sarx:shlx:shrx
[103]: https://www.felixcloutier.com/x86/adcx
[104]: https://www.felixcloutier.com/x86/cmc
[105]: https://www.intel.com/content/www/us/en/docs/dpcpp-cpp-compiler/developer-guide-reference/2026-0/set-the-ftz-and-daz-flags.html
[106]: https://xem.github.io/minix86/manual/intel-x86-and-64-manual-vol1/o_7281d5ea06a5b67a-240.html
[107]: https://www.intel.com/content/www/us/en/developer/articles/technical/advanced-performance-extensions-apx.html
[108]: https://cdrdv2-public.intel.com/836199/361050-intel-avx10.2-spec.pdf
[109]: https://www.mail-archive.com/gcc-patches@gcc.gnu.org/msg280720.html
[110]: https://moss.cs.iit.edu/cs450/slides/08-vm-d.pdf
[111]: https://asplos.dev/wordpress/2021/12/16/the-measurement-of-tso-on-m1-max/
[112]: https://apple.stackexchange.com/posts/407733/timeline
[113]: https://github.com/losfair/tsotest
[114]: https://news.ycombinator.com/item?id=39064974
[115]: https://www.realworldtech.com/forum/?curpostid=218321&threadid=218321
