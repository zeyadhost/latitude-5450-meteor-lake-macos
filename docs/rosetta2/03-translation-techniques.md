# Rosetta 2: Instruction-Translation Techniques ("the insane tricks")

*Scope.* How Rosetta 2 turns x86-64 machine code into arm64 code: the overall strategy,
register and flag mapping, control flow, the ABI, memory operations, floating point and SIMD,
special instructions and self-modifying code. Related documents in this folder:

- launch flow, AOT/JIT pipeline, files, signals, CPUID plumbing:
  [02-architecture-and-runtime.md][02]
- hardware assists in Apple CPUs (TSO memory ordering, the PF/AF flag extension, the alternate
  floating-point mode, 4 KB pages): [04-hardware-assists.md][04]. They are only summarised here.
- benchmark numbers: [07-performance.md][07]

*Provenance labels.* **[Apple]** = Apple documentation or WWDC session. **[RE: author]** =
third-party reverse-engineering write-up, published disassembly or developer observation
(forum and issue-tracker posts are marked as such and are lower confidence).
**[Benchmark: source]** = a measurement. **[Inferred]** = my own reasoning from the cited
material. Every section ends with a **Reverse direction [Inferred]** line about whether the
idea carries over to an ARM64 → x86-64 translator (the long-term goal of this project; the
target machine is a Meteor Lake laptop, which has AVX2 but no AVX-512 and no APX).

*Version caveat.* Most reverse engineering (RE) was done on an M1 under macOS 11 to 13. The
AVX material comes from macOS 15 on M2 and M4. Rosetta is updated separately from the OS, so
register numbers, offsets and helper names can drift.

*Method.* No Apple binary was disassembled for this document. The few instruction listings
are short excerpts from cited third-party write-ups or from disassembly that a third party
published.

**Jargon used below.**
- **AOT** (ahead-of-time): translate before the code runs. **JIT** (just-in-time): translate
  on demand while the program runs.
- **IR** (intermediate representation): the internal form a compiler optimises. **CFG**
  (control-flow graph): basic blocks plus the edges between them.
- **NZCV**: the arm64 condition-flag register (Negative, Zero, Carry, oVerflow).
- **RAS** (return-address stack): the CPU's predictor for function returns.
- **LSE**: the Armv8.1 atomic instructions (CAS, LDADD, SWP and so on).
- **TSO** (total store order): x86's stronger memory-ordering model.
- **SMC**: self-modifying code.

---

## Key findings

| # | Trick | What it does | Main evidence |
|---|---|---|---|
| 1 | Whole-image AOT, JIT only as a fallback | Translates the whole `__TEXT` once, usually at install or first launch, and keeps code locality | [RE: Johnson][dj], [Apple WWDC20][wwdc10686] |
| 2 | One x86 instruction → a short arm64 sequence, with canonical x86 state at every boundary | Gives precise exceptions, a working debugger and fast translation, at the cost of almost no cross-instruction optimisation | [RE: Johnson][dj] |
| 3 | Fixed register map (RAX..R15 → x0..x15, XMM → v0..v15) | No register allocator and no spills for GPRs; the debugger can read x86 registers directly | [RE: FFRI][ffri1] |
| 4 | x86 flags kept in the real NZCV, carry stored inverted, dead flags elided | Most flag-setting x86 ops become one arm64 op, or a non-flag-setting one | [RE: Johnson][dj] |
| 5 | FEAT_FlagM/FlagM2 (CFINV, RMIF, SETF8/16, AXFLAG/XAFLAG) and Apple's PF/AF extension | Patch the remaining flag differences cheaply; see [04][04] | [RE: Johnson][dj] |
| 6 | CALL/RET → BL/RET plus a private "return stack" of (x86, arm64) address pairs | Keeps the hardware RAS predicting returns while the x86 return address stays on the x86 stack | [RE: Johnson][dj], [RE: lewurm][lewurm], [RE: carsongoodwin32][avxdive] |
| 7 | Inline caches at import stubs and a hashed lookup for other indirect branches | Makes indirect calls cheap; a miss falls back to the JIT | [RE: FFRI][ffri1], [RE: Johnson][dj] |
| 8 | Prologue/epilogue fusion (PUSH/POP → STP/LDP) | One of only two cross-instruction optimisations | [RE: Johnson][dj] |
| 9 | Hardware x86 floating-point mode (non-standard on M1, FEAT_AFP from M3) | Bit-exact SSE NaN/denormal/underflow semantics at no per-instruction cost | [RE: mod_poppo][poppo], [RE: m1n1][m1n1fp] |
| 10 | x87 in full 80-bit software via ~75 runtime helpers; AVX2 as two NEON halves with the upper halves kept in memory | Correct but slow paths (numbers in [07][07]) | [RE: Johnson][dj], [RE: rosettax87][rx87-export], [RE: carsongoodwin32][avxdive] |

---

## 1. Evidence base

| Source | What it examined | macOS / chip | Date |
|---|---|---|---|
| Koh M. Nakagawa, Project Champollion ([part 1][ffri1], [part 2][ffri2]) | AOT Mach-O files, `runtime`, register map, lazy binding, JIT entry, debug variables | Big Sur 11.x, M1 | Feb to May 2021 |
| Dougall Johnson, ["Why is Rosetta 2 fast?"][dj] | AOT output of many binaries; flags, return prediction, FP, prologues, x87 | "an old version of macOS" (11 or 12 era), M1 | Nov 2022 (updated after comments) |
| lewurm, ["Fun with Rosetta 2 and atomic instructions"][lewurm] | Live translated code under LLDB (LOCK XADD, calls, SETcc) | Apple silicon, Feb 2022 (macOS 12 era) | Feb 2022 |
| carsongoodwin32, [rosetta2_avx_dive][avxdive] (published [Ghidra disassembly][avxdive-disasm]) | AOT output of AVX and AVX2 test programs | macOS 15.0 developer beta 1, M2 MacBook Air | Jun 2024 |
| Saagar Jha, Hacker News comments ([2021][sj2021], [2022][sj2022]) | How SMC and guest JITs are handled | M1 era (Big Sur/Monterey) | Nov 2021, May 2022 |
| rosettax87 / rosettax87_jit / x87sidecar ([1][rx87], [2][rx87jit], [3][x87sidecar]) | Hooked Rosetta's x87 helpers; their headers name runtime exports | macOS 15 (offsets for 15.4.1) | 2025 to 2026 |
| mod_poppo, [FEAT_AFP on M4][poppo] | Behavioural tests of x86 versus Arm FP semantics, including under Rosetta | macOS 15.1.1, M4 Pro | Nov 2024 |
| Jim Cownie, ["Fun with Timers and cpuid"][cownie] | CPUID and RDTSC under Rosetta | Big Sur, M1 | Mar 2021 |
| Brendan Shanks (CodeWeavers), [Wine MR 6866][wine6866-list] | `%gs` handling of Wine under Rosetta | macOS 15, Apple silicon | 2025 |
| [Apple: About the Rosetta translation environment][apple-about]; [WWDC20 10686][wwdc10686]; [WWDC20 10214][wwdc10214] | Official behaviour and limits | macOS 11 to 26 (the doc has been revised) | 2020 to 2025 |

---

## 2. Overall translation strategy

### 2.1 Mostly AOT, with a JIT for whatever AOT could not see

- **Problem.** Translating in execution order (the classic dynamic binary translator) costs
  compile time at run time, pollutes caches and scatters code.
- **How.** Rosetta translates the entire text segment up front and only rarely uses its JIT
  ([RE: Johnson][dj]). Apple says translation starts at install time when the App Store or the
  package installer triggers it, otherwise at first launch ("an extra bounce or two in the
  dock"). Code first met at run time is compiled on the fly ([Apple WWDC20 10686][wwdc10686]).
  System libraries come pre-translated in an AOT shared cache ([RE: FFRI part 2][ffri2]; see
  [02][02] §3.4). JIT is used for runtime-generated code, for libraries without an AOT file
  and for jump targets that the AOT lookup tables do not cover ([RE: FFRI part 1][ffri1],
  [RE: Johnson][dj]).
- **Linux note.** Rosetta for Linux VMs was JIT-only at first ([RE: threedots, Jun 2022][threedots]).
  An AOT cache daemon, `rosettad`, which can also `translate` binaries and build a `cfg`, appeared
  with macOS 14 Virtualization.framework caching options ([RE: arianvp gist][arianvp]). Details
  are in the Linux/history document.
- **Reverse direction [Inferred].** This carries over directly. ARM64 Mach-O binaries are just
  as statically analysable, and AOT is even more attractive when the host (x86) is the slower
  machine.

### 2.2 One x86 instruction → one short arm64 sequence; canonical state at every boundary

- **Problem.** Signals, sampling profilers, debuggers and exception unwinding all need the
  exact x86 register state at any point where a fault can occur.
- **How.** Each x86 instruction becomes one or more arm64 instructions, and NOPs are dropped.
  Rosetta keeps a map from arm64 PC to x86 address and "guarantees that the state will be
  canonical between each instruction" ([RE: Johnson][dj]). The x86 → arm64 lookup table only
  holds function starts and otherwise-unreferenced blocks, which keeps it small. The reverse
  map is complete: a top-level binary search, then bit-packed per-instruction deltas
  ([RE: Johnson][dj], including his correction in the comments).
- **What it costs.** Inter-instruction optimisation is almost impossible. Johnson notes
  "surprisingly poor code generation in some cases", but the x86 code already came out of an
  optimising compiler.
- **What it buys.** Each instruction is translated once, so the instruction cache is used well.
  Exceptions are precise with little metadata. LLDB works on x86 processes. Translation is
  fast, which matters because tens of megabytes may be translated at first start and JIT
  latency is critical for JIT-heavy apps ([RE: Johnson][dj]).
- **Reverse direction [Inferred].** The idea carries over, but Johnson himself flags the
  catch. Keeping every guest register in a host register is easy for x86 → ARM (16 GPRs into
  31). For ARM → x86 (31 GPRs into 16) it is "a significant drawback", because many guest
  registers must live in memory ([RE: Johnson][dj]).

### 2.3 Is there an IR?

- Rosetta is not an optimising-IR translator in the LLVM sense. It does keep a decoded,
  block-structured form of the x86 code:
  - `ROSETTA_PRINT_IR` prints the x86 instructions grouped into basic blocks, with
    predecessor lists and per-block flag information ([RE: FFRI part 2][ffri2]).
  - The Linux `rosettad` has a `cfg` subcommand that "constructs a control-flow graph"
    ([RE: arianvp][arianvp]).
  - Runtime exports named by the rosettax87 project include `ir_create`, `module_*`,
    `translator_translate`, `translator_get_branch_slots_*`,
    `translator_get_instruction_offsets` and `translator_apply_fixups`
    ([RE: rosettax87 headers][rx87-export]).
- The CFG is what powers the flag-liveness ("unused flags") analysis and branch-target
  discovery. Code generation itself stays per-instruction ([RE: Johnson][dj]; the structure is
  **[Inferred]**).
- **Reverse direction [Inferred].** Copy this. A CFG plus per-instruction codegen is cheap and
  keeps exceptions precise. Add optimisations only where the canonical-state contract allows
  them, as Rosetta does in §2.4.

### 2.4 The only two cross-instruction optimisations

1. **Unused-flags elimination.** If on every path a flag result is overwritten before it is
   read, the arm64 op is emitted without flag setting (ADD instead of ADDS), with no fix-up.
   Johnson calls this the reason "the vast majority of flag-setting x86 instructions" need no
   flag work ([RE: Johnson][dj]). The x87sidecar authors rely on "Rosetta's own liveness
   analysis" of flags ([RE: x87sidecar][x87sidecar]). Flags that may escape the analysed
   region are computed in full. For example, the epilogue `add rsp,0x30` just before a `ret`
   is emitted as `adds x4,x4,#0x30` followed by `cfinv` in the published macOS 15 listing
   ([RE: carsongoodwin32][avxdive-disasm]; the x86 side is inferred from the register map).
   That suggests a return counts as a flag escape **[Inferred]**.
2. **Prologue/epilogue fusion.** Runs of PUSH/POP and stack-frame setup are merged into paired
   stores and loads, and stack-pointer updates are delayed. In the AOT-to-x86 map the group
   looks like one instruction. Johnson's example ([RE: Johnson][dj]):

   ```
   push rbp / mov rbp,rsp / push rbx / push rax
   →  stur x5,[x4,#-8] ; sub x5,x4,#8 ; stp x0,x3,[x4,#-0x18]!
   ```

   This plays the role of the "stack engine" in x86 hardware. Paired stores execute as one
   operation on M1.

- **Reverse direction [Inferred].** Both carry over. ARM STP/LDP split into two x86 MOVs, or,
  where alignment and atomicity rules allow, one 16-byte SSE move. Flag elision matters even
  more on x86, because nearly every x86 ALU instruction writes flags (§5.8).

### 2.5 Code size and translation speed

- Code expands by about **1.64×** for an sqlite3 binary: 1.05 MB of x86 instructions become
  1.72 MB of arm64 ([RE: Johnson][dj]). Typical costs: a 1-byte PUSH becomes a 4-byte arm64
  instruction, and a read-modify-write x86 instruction becomes at least three arm64
  instructions.
- `.aot` files hold translated code only. Data and constants stay in the original image and
  are referenced in place, which needs no byte swapping because both sides are little-endian
  ([RE: FFRI part 1][ffri1]). As a result an `.aot` can be much smaller than the x86 file it
  replaces: 8,979 bytes for a 31,328-byte `sleep` ([RE: mynavi][mynavi]; whole-file sizes, so
  this is not an instruction expansion factor **[Inferred]**).
- Translation is fast. Translating "a little more than 100 KB" of Intel code took under
  12.5 ms on an M1 ([RE: Eclectic Light][elc-oah]). Startup costs are in [07][07] §2.6.
- **Reverse direction [Inferred].** x86 encodings are variable-length and often shorter than
  4 bytes, so ARM → x86 can stay near 1× in bytes even when it needs more instructions. Code
  size is less of a worry in this direction.

### 2.6 Trade-offs at a glance

| Choice | Buys | Costs |
|---|---|---|
| AOT of the whole image | No warm-up; code locality; translation off the critical path | First-launch delay; disk cache; JIT still needed |
| One-to-one, canonical state | Precise exceptions; debuggable; simple and fast translator | Few optimisations; redundant flag and stack work |
| Fixed register map | No allocator; trivial state reconstruction | Only works because the host has more registers than the guest |
| Hardware assists ([04][04]) | Removes the costliest semantic gaps (ordering, PF/AF, FP corner cases) | Ties the design to Apple's own silicon; weaker in Linux VMs |

---

## 3. Address-space layout and RIP-relative data

- **Problem.** x86-64 code addresses globals RIP-relative (an offset from the current
  instruction). The translated code sits somewhere else and has no "x86 RIP".
- **How.**
  - The original x86 image stays mapped. The translated code is placed right after it, giving
    roughly `[x86 code][data][translated code][runtime support]`. A `RuntimeRoutines` region
    (code from the Rosetta runtime) is mapped right after the translated `__TEXT`
    ([RE: Johnson][dj], [RE: FFRI part 1 vmmap][ffri1], [RE: FFRI part 2][ffri2]).
  - RIP-relative references become `ADRP`+`ADD`/`LDR` pairs that point straight at the original
    data. FFRI's example: `MOVSD XMM0,[rip+…]` becomes `adrp x22,…; ldr d0,[x22,#0xf58]`
    ([RE: FFRI part 1][ffri1]).
  - The runtime is reachable with a direct `BL` ([RE: Johnson][dj]).
  - ADRP reaches ±4 GB. Johnson's post says ±1 GB; a commenter corrected it, and ±4 GB is the
    architectural range ([RE: Johnson, comments][dj]).
- **Reverse direction [Inferred].** This carries over and gets simpler. Place the translated
  x86 code within ±2 GB of the original arm64 image, and an ARM `ADRP`+`ADD`/`LDR` pair
  collapses into a single RIP-relative `LEA`/`MOV`.

---

## 4. Register mapping

### 4.1 Guest registers

| x86-64 | arm64 | Note |
|---|---|---|
| RAX, RCX, RDX, RBX | x0, x1, x2, x3 | In x86 encoding order, not ABI order ([RE: FFRI part 1][ffri1]) |
| RSP | **x4**, not `sp` | See below |
| RBP, RSI, RDI | x5, x6, x7 | |
| R8 to R15 | x8 to x15 | |
| XMM0 to XMM15 | q0 to q15 (= v0 to v15) | ([RE: FFRI part 1][ffri1]) |
| YMM upper halves (macOS 15+) | **memory**, in the per-thread context (x18 + 0x230 + 16·n in the published listing) | ([RE: carsongoodwin32 disassembly][avxdive-disasm]), §10.5 |
| CF, ZF, SF, OF | NZCV (carry stored inverted) | §5 |
| PF, AF | NZCV bits 26 and 27 with Apple's extension (macOS); computed in software in Linux VMs | ([RE: Johnson][dj]); details in [04][04] |
| RIP | no register | Derived from the arm64 PC through the PC map. Explicit x86 addresses, such as return addresses, are materialised with ADRP+ADD |

### 4.2 Registers Rosetta reserves for itself (observed)

The table merges three published listings: FFRI's (Big Sur, M1), lewurm's (2022) and the
macOS 15.0 beta 1 / M2 Ghidra export. In that 2,768-line export the only high registers that
appear are x18 and x21 to x25 (count done for this document). Earlier listings use the same
roles.

| arm64 register | Role | Evidence |
|---|---|---|
| x18 | Base of the per-thread Rosetta context (YMM upper halves at fixed offsets). XNU preserves x18 for translated tasks across context switches | [RE: carsongoodwin32][avxdive-disasm]; XNU detail in [02][02] §5.3 |
| x21 | Pointer to the private **return stack** of (x86 RA, arm64 RA) pairs | [RE: lewurm][lewurm], [RE: carsongoodwin32][avxdive-disasm]; the "Rosetta Return Stack" region in `vmmap` ([RE: FFRI][ffri1]) |
| x22 | Branch target or x86 return address; the runtime resolver returns the arm64 target here; `br x22` | [RE: FFRI part 1][ffri1] |
| x23 to x25 | Scratch: inline-cache compares, return-stack check, x86 and arm64 return addresses | [RE: lewurm][lewurm], [RE: carsongoodwin32][avxdive-disasm] |
| x30 (LR) | Written implicitly by `BL`. Returns use `ret x24`, so the code never relies on LR holding the right value | [RE: carsongoodwin32][avxdive-disasm] |
| v24, v25 | Vector scratch (used for 256-bit halves) | [RE: carsongoodwin32][avxdive-disasm] |
| x16, x17, x19, x20, x26 to x29, v16 to v23, v26 to v31 | Not seen in AOT listings; perhaps used by the runtime, JIT or x87 code | Open question |

**Why RSP is in x4 and not `sp`.** On arm64, SP must be 16-byte aligned whenever it is used as
a load/store base (when alignment checking is on). x64 code only recommends that alignment
([RE: Cawley, FOSDEM 2024][cawley]). A general-purpose register also gives x86 RSP arithmetic
semantics for free **[Inferred]**.

- **Reverse direction [Inferred].** This is the main structural obstacle. ARM64 has 31 GPRs
  plus SP and 32 × 128-bit vector registers; a Meteor Lake x86-64 core has 16 GPRs and 16 YMM
  registers. A fixed one-to-one map is impossible. Options:
  - pin the hottest guest registers (x0 to x7, SP, LR, FP) in host registers;
  - keep the rest in a memory context addressed by one reserved host register (x86 memory
    operands make this relatively cheap);
  - or do per-block register allocation, which partly gives up Rosetta's canonical-state
    simplicity.

  Intel APX (32 GPRs) would help, but Meteor Lake does not have it.

---

## 5. Condition flags

### 5.1 Mapping

| x86 | arm64 representation | Notes |
|---|---|---|
| ZF, SF, OF | Z, N, V | Same meaning for add, subtract and compare ([RE: Johnson][dj]) |
| CF | C, **stored inverted** ("canonical form") | §5.2 |
| PF, AF | NZCV bits 26 and 27 on macOS (Apple extension); software on Linux VMs | §5.6; hardware details in [04][04] |
| DF, IF, TF, AC… | not in NZCV | Presumably kept in the thread context **[Inferred]**; not documented |

### 5.2 Inverted carry and `CFINV`

- **Problem.** x86 subtracts with a *borrow* (CF=1 means a borrow happened); arm64 subtracts
  with a *carry* (C=1 means no borrow). For subtraction the two are opposite; for addition
  they agree.
- **How.** Compares are far more common than flag-consuming adds, so Rosetta makes
  "inverted" the canonical form: arm64 C holds NOT CF. Then CMP/SUB need no fix-up.
  `CFINV` (Armv8.4 FEAT_FlagM, "carry flag invert") is emitted after an add whose carry is used
  or may escape, and before an add-with-carry so its input is right ([RE: Johnson][dj]).
  `CFINV` shows up in real AOT code; FFRI ran into it because Ghidra 9.2.1 could not decode it
  ([RE: FFRI part 1][ffri1]). The `adds x4,x4,#0x30; cfinv` epilogue in §2.4 is a
  live example.
- **[Inferred] corollaries, not documented:**
  - arm64 `ANDS`/`TST` set C=0, which in inverted form means CF=1. x86 logic ops clear CF, so a
    fix-up is needed when CF can escape after a logic op.
  - x86 INC/DEC preserve CF, but arm64 ADDS/SUBS overwrite C, so INC/DEC with a live CF need
    special handling.
- **Reverse direction [Inferred].** This is the mirror image and the trick ports directly. If
  the x86 host's own CF after SUB/CMP stands for NOT(ARM C), then ARM `B.HS/LO/HI/LS` after a
  compare map one-to-one onto x86 `JAE/JB/JA/JBE`. Only ARM ADDS/ADCS-style carries then need
  a `CMC`, or a statically inverted condition when producer and consumer sit in the same
  block.

### 5.3 Shifts and bit insertion: `RMIF`

- **Problem.** x86 shifts move the last bit shifted out into CF, and leave flags untouched when
  the count is zero.
- **How.** `RMIF` (rotate-mask-insert-flags) copies any register bit into any flag, so
  fixed-count shifts are cheap. Variable-count shifts stay expensive when flags escape: a
  count of 0 must leave the flags alone, which needs a conditional branch ([RE: Johnson][dj]).
- **Reverse direction [Inferred].** ARM shifts do not touch flags unless an S form is used. Use
  BMI2 `SHLX/SHRX/SARX/RORX` on the host, which do not write flags (Meteor Lake has BMI2), so
  live ARM flags are not clobbered.

### 5.4 8- and 16-bit operations: `SETF8` and `SETF16`

- **Problem.** arm64 has no 8-bit or 16-bit ALU ops. Doing the work in 32 bits gives the wrong
  N, Z and V for byte or word operations.
- **How.** `SETF8`/`SETF16` set N, Z and V from bit 7 or bit 15 of a result ([RE: Johnson][dj]).
  Preserving the destination's upper bits is a separate problem (§6).
- **Reverse direction [Inferred].** Not needed: ARM has no sub-32-bit ALU operations, so it
  never produces byte or word flags.

### 5.5 Floating-point compares: `AXFLAG` and `XAFLAG`

- `AXFLAG`/`XAFLAG` (FEAT_FlagM2) convert between Arm FP-compare flags and an "external
  format". Johnson notes, by "strange coincidence", that this format is x86's, and Rosetta uses
  the pair for (U)COMISS/D ([RE: Johnson][dj]). How PF is produced for unordered compares is
  not documented (open question).
- **Reverse direction [Inferred].** `UCOMISD`/`COMISD` give x86 flags. Converting them into
  ARM's FCMP NZCV convention (unordered gives C=1, V=1) needs a few SETcc or CMOV-type
  instructions when the flags escape.

### 5.6 PF and AF

- **Problem.** x86 sets PF (parity of the low byte) and AF (carry out of bit 3) on almost every
  ADD and SUB. They are rarely read, but some software does read them. Computing PF in
  software turns one SUB into about five instructions. Johnson's illustration:
  `subs w4,w4,w5; dup v24.16b,w4; cnt v23.16b,v24.16b; umov w22,v24.b[0]; and w22,w22,#1`
  ([RE: Johnson, comments][dj]).
- **How.**
  - **macOS:** an undocumented M1 extension, when enabled, makes ADDS, SUBS and CMP compute PF
    and AF into NZCV bits 26 and 27 "with no performance penalty" ([RE: Johnson][dj]). The
    hardware is covered in [04][04].
  - **Linux VMs:** Rosetta cannot switch the extension on, so it computes PF manually (AF may
    or may not be computed) and relies on unused-flags elimination to keep this rare
    ([RE: Johnson][dj]).
- **Reverse direction [Inferred].** Nothing to do. ARM code never reads PF or AF; x86 computes
  them for free.

### 5.7 Lazy versus eager flags

- Rosetta is **eager-in-hardware with static elision**. Flags live in the real NZCV across
  instruction boundaries, which is part of the canonical state, and are simply not computed
  where liveness analysis proves them dead ([RE: Johnson][dj]).
- This differs from QEMU-style **lazy flags**, where operands and the operation type are saved
  and flags are computed only when a consumer appears ([QEMU translator internals][qemu-int]).
- Box64 moved towards Rosetta's approach in v0.3.2 with "native flags" on ARM64, reporting up
  to +30 % on the 7-zip benchmark ([Benchmark: box86.org, Dec 2024][box64-2024]).
- **Reverse direction [Inferred].** Eager mapping onto the host flags works (§5.2). The hazard
  is the opposite one, covered next.

### 5.8 Reverse-direction hazard: implicit flag writes [Inferred]

ARM only writes NZCV with S-suffixed instructions, while most x86 ALU instructions write
EFLAGS. Translated *non-flag-setting* ARM operations must therefore use flag-neutral host forms
(`LEA` for add and shift-add, `MOV`, `NOT`, BMI2 `SHLX/RORX/MULX`), or spill and reload the
flags. `PUSHF`/`POPF` are slow. `LAHF`/`SAHF` do not cover OF; `SETO` can capture it.
ARM `CCMP`/`CCMN` (conditional compare) and the `CSEL` family need `CMOV` or `SETcc`
sequences.

---

## 6. Operand sizes and partial-register writes

- **Problem.** On x86, 32-bit writes zero-extend into the 64-bit register, but 8-bit and 16-bit
  writes (AL, AX, AH) must **preserve** the untouched bits.
- **How.**
  - 32-bit ops map onto arm64 W registers, which zero-extend in the same way, so there is
    nothing extra to do.
  - Narrow writes are computed in a scratch register and then inserted with bit-field
    instructions. In lewurm's listing `SETNE CL` becomes `cset x22, ne` followed by
    `bfxil x1, x22, #0, #8`: the low byte of x1 (RCX) is replaced and bits 8 to 63 kept
    ([RE: lewurm][lewurm]). Johnson notes that x86's need to keep the high bits is the "small
    catch" of narrow ops ([RE: Johnson][dj]).
  - High-byte registers (AH, BH, CH, DH) presumably use `BFI xN,xS,#8,#8` for writes and
    `UBFX` for reads **[Inferred]**; no published listing shows this.
- **Reverse direction [Inferred].** This direction is easy. ARM W-register writes zero-extend
  just like x86 32-bit writes. ARM's own partial writes (`MOVK`, `BFI`, `BFXIL`) become
  mask/shift/OR sequences or byte/word `MOV`s on x86.

---

## 7. Control flow

### 7.1 Direct jumps and conditional branches

- These become direct `B`/`B.cond` (conditions taken from the canonical NZCV) inside the
  translated image. Branches to targets outside the current translation unit go through slots
  and fixups. The runtime export list includes `translator_get_branch_slots_offset/count`,
  `translator_get_branch_entries` and `translator_apply_fixups`
  ([RE: rosettax87 headers][rx87-export]); what they do exactly is **[Inferred]** from the
  names.
- **Reverse direction [Inferred].** Trivial. x86 has direct `Jcc`/`JMP` with rel8/rel32
  displacements.

### 7.2 Calls and returns: keeping the return predictor working

- **Problem.** The CPU predicts returns well only for matched BL/RET pairs, using its RAS.
  x86 semantics, however, require the x86 return address on the x86 stack, where code may
  read or rewrite it (unwinders, `longjmp`, coroutines). A naive translation (push the x86
  address, then look up the target on return) breaks prediction on every return.
- **How.** CALL becomes `BL` and RET becomes arm64 `RET`. Around them Rosetta keeps a private
  stack (pointed to by x21) of pairs: the expected x86 return address and the arm64 address
  just after the `BL`. Both are pushed on a call and checked on a return ([RE: Johnson][dj]).
  Johnson notes Dolphin (the GameCube/Wii emulator) uses the same trick. A call site in the
  published macOS 15 beta / M2 listing ([RE: carsongoodwin32][avxdive-disasm]; also in
  [lewurm][lewurm]):

  ```
  adrp x24,… ; add x24,x24,#…   // x86 return address (in the original image)
  adr  x25, after_call           // arm64 return address
  stp  x24,x25,[x21,#-0x10]!     // push pair on the Rosetta return stack
  str  x24,[x4,#-8]!             // push x86 RA on the x86 stack (x4 = RSP)
  bl   target
  ```

  And the matching return:

  ```
  ldr  x22,[x4],#8               // pop x86 RA from the x86 stack
  ldp  x23,x24,[x21],#0x10       // pop (expected x86 RA, arm64 RA)
  sub  x25,x22,x23 ; cbnz x25, slow_path
  ret  x24                       // predicted by the RAS that BL filled
  ```

- **On a mismatch** (`longjmp`, exceptions, a rewritten return address) the code calls a
  runtime routine, which looks the target up or JIT-translates it. Correctness is kept and only
  prediction is lost **[Inferred]**. What happens when the private stack overflows during deep
  recursion is not documented.
- **Reverse direction [Inferred].** This is directly reusable in mirror form. ARM keeps the
  return address in LR, not on the stack, so the translator can run a host-private x86 stack
  (the real RSP, while the guest SP lives elsewhere):
  - ARM `BL` becomes x86 `CALL` plus a write of the guest LR;
  - ARM `RET` becomes a validated x86 `RET` (check that guest LR matches the host-stack
    entry).

  Things to watch: Intel CET shadow stacks (Meteor Lake has CET) require CALL/RET to stay
  balanced; ARM tail calls via `BR`; `RET x<n>` with registers other than x30.

### 7.3 Indirect jumps and calls

- **Problem.** The target is an x86 address known only at run time.
- **How.**
  1. **Inline caches at import stubs.** For each lazily bound import, a `__stubs_sh` slot holds
     the last x86 target and its arm64 translation. The stub compares the current x86 target
     with the cached one and on a hit does `br x22`; on a miss it calls the resolver, which
     refills the cache ([RE: FFRI part 1][ffri1], Big Sur). The same compare-then-`br x22`
     pattern appears in the macOS 15 beta listing ([RE: carsongoodwin32][avxdive-disasm]).
  2. **General lookup.** AOT metadata maps x86 → arm64 for function starts and unreferenced
     blocks using a two-level binary search, and branch-target results are cached in a hash
     map ([RE: Johnson][dj]). `vmmap` shows a "Rosetta IndirectBranch" region ([02][02] §4).
  3. **Misses** fall back to the JIT, for example for switch-table targets ([RE: Johnson][dj];
     `translate_indirect_branch` in [RE: FFRI part 1][ffri1]).
- **Reverse direction [Inferred].** Ports directly. The x86 version of an inline cache is
  `CMP`+`JNE`+`JMP`. ARM switch idioms (`ADR`+`LDRB/LDRH`+`ADD`+`BR`) can be recognised ahead
  of time and their tables translated.

### 7.4 Precise exceptions, signals, debugging and profiling

- **How.**
  - State is canonical at every x86 instruction boundary, and each fused group (§2.4) counts
    as one instruction ([RE: Johnson][dj]).
  - The runtime maps a faulting arm64 PC back to an x86 address and rebuilds the x86 register
    file from the fixed map ([RE: Johnson][dj]; [02][02] §5.4 covers the kernel side, e.g.
    `thread_raise_exception`).
  - Export names such as `determine_state_recovery_action` suggest explicit logic for faults
    that land in the middle of a multi-instruction sequence ([RE: rosettax87 headers][rx87-export];
    behaviour **[Inferred]**).
  - Native arm64 code that the tables do not know about breaks this: a signal that arrives
    while the PC is in injected code aborts with "no code fragment associated with the given
    arm pc" ([RE: x87sidecar][x87sidecar]).
  - LLDB sees x86 state through Rosetta's debugserver; DTrace cannot instrument translated
    processes ([02][02] §5.6).
- **Reverse direction [Inferred].** The same design applies: a host-PC → guest-PC map and
  canonical guest state at ARM instruction boundaries. ARM's own exceptions are precise, so
  there is no extra semantic burden.

---

## 8. Calling convention and ABI preservation

- **Problem.** Translated code must call other translated code, the runtime and the kernel,
  and it must stay debuggable.
- **How.**
  - AOT code keeps the **System V AMD64 ABI** on top of the fixed register map. Integer
    arguments go in x7, x6, x2, x1, x8, x9 (RDI, RSI, RDX, RCX, R8, R9), FP arguments in
    q0 to q7, and stack arguments through x4 ([RE: FFRI part 1][ffri1]). This is not AAPCS64,
    so calling native arm64 code would need thunks ([RE: Saagar Jha, HN 2022][sj2022]).
  - Apple forbids mixing arm64 and x86-64 code in one process. Everything is translated,
    including system frameworks (from the AOT shared cache), down to the system-call interface
    ([Apple][apple-about], [Apple WWDC20 10686][wwdc10686]).
  - Calls into the runtime are `BL`s to RuntimeRoutines. The runtime saves the emulated context
    first, because its own code uses AAPCS64 and would clobber x0 to x15
    ([RE: FFRI part 1][ffri1], `resolve_x64_addr`).
- **Contrast.** Microsoft's Arm64EC lets x64 and arm64 code share one process. It has to give
  up some arm64 registers (x13, x14, x23, x24, x28, v16 to v31) and marshal arguments at every
  mode switch ([RE: Cawley, FOSDEM 2024][cawley]). Spink and Franke show that redirecting
  shared-library calls to native host code in a QEMU-based translator gave 2.7× to 6.3×
  average speed-ups ([RE: LCTES 2024][lctes24]).
- **Reverse direction [Inferred].** Two designs are possible for running ARM-only Mac apps on
  Intel macOS:
  - **(a) Rosetta-style whole-process translation.** Simple and robust, but it needs arm64
    builds of every system framework. Intel macOS does not ship them.
  - **(b) Arm64EC/LCTES-style thunks into native x86 frameworks.** Faster, but every call
    crossing must convert the Apple arm64 ABI into SysV x86-64: variadic arguments go on the
    stack on Apple arm64, x18 is reserved, SP must be 16-byte aligned, and struct-return
    conventions differ. Callbacks from x86 back into ARM code need thunks too.

  Apple deliberately avoided (b).

---

## 9. Memory operations

### 9.1 Addressing modes

- x86 `[base + index*scale + disp32]` usually fits arm64 register-offset addressing only when
  the scale equals the access size and there is no displacement. Otherwise an `ADD` (with
  shift) comes first **[Inferred]**; no published RE spells this out.
- Read-modify-write x86 instructions cost at least three arm64 instructions (load, op, store)
  ([RE: Johnson][dj]). Cawley shows the same shape generically for `sub eax,[rsp+259]`:
  `add x16,sp,#259; ldr w16,[x16]; subs w0,w0,w16`. That is an emulator illustration, not
  Rosetta output ([RE: Cawley][cawley]).
- **Reverse direction [Inferred].** x86 addressing is a superset of the common ARM modes.
  ARM pre- and post-index writeback becomes a separate `ADD`/`LEA`, and ARM register-offset
  with `SXTW`/`UXTW` needs a `MOVSXD`/`MOV r32` first.

### 9.2 Memory ordering (summary only; see [04][04])

- Translated processes run with Apple's hardware TSO mode enabled. Ordinary arm64 loads and
  stores then get x86 ordering, so no barriers are inserted ([RE: Johnson][dj]). In Linux VMs
  with the Rosetta share attached, the whole VM runs in TSO mode. Without TSO, Rosetta for
  Linux "explicitly does not provide" x86 ordering ([RE: threedots][threedots]). The
  performance cost is in [07][07].
- **Reverse direction [Inferred].** Free. x86 TSO is stronger than ARM's model, so ARM plain
  loads and stores map to plain MOVs. One exception: an ARM `STLR` followed by an `LDAR` is
  ordered (RCsc), whereas x86 lets a store pass a later load. Such pairs need `XCHG` or
  `MFENCE`. `DMB ISH` becomes `MFENCE` or a locked op; `DMB ISHLD`/`ISHST` cost nothing.

### 9.3 Unaligned accesses

- Normal arm64 loads and stores handle misalignment in hardware. Apple cores also report
  FEAT_LSE2 ("uscat" in Linux `/proc/cpuinfo` on M1-class guests), which gives single-copy
  atomicity for unaligned accesses that stay inside a 16-byte granule
  ([cpuinfo in a Docker forum post][docker-cpu]; [HN cpuinfo][hn-cpuinfo]). x86 unaligned
  MOVs therefore translate one-to-one **[Inferred]**. Whether alignment-checking instructions
  such as `MOVAPS` (which faults on x86 when misaligned) are emulated exactly is not
  documented.
- **Reverse direction [Inferred].** x86 tolerates misalignment, so this is free.

### 9.4 The LOCK prefix and atomics

- `LOCK XADD` becomes `LDADDAL` (an LSE atomic add with acquire+release semantics)
  ([RE: lewurm][lewurm]). `LOCK CMPXCHG` → `CASAL`, `XCHG` → `SWPAL`,
  `LOCK OR/AND/XOR` → `LDSETAL/LDCLRAL/LDEORAL`, and `CMPXCHG16B` → `CASP` are expected but
  not confirmed **[Inferred]**.
- **Split locked operations** (a LOCK op that crosses a cache line): native `ldaddal` on a line
  crossing faulted in lewurm's tests, but the Rosetta-translated LOCK XADD did not. A GraalVM
  SIGBUS reported at a LOCK XADD under Rosetta was never explained
  ([RE: lewurm][lewurm], [GraalVM issue][graal4314]). Treat this as an open question.
- **Reverse direction [Inferred].** ARM LSE atomics map onto LOCK-prefixed x86 ops.
  LDXR/STXR (load/store-exclusive) loops must be emulated with `CMPXCHG`, which is ABA-prone,
  or by pattern-matching the common loop shapes. Intel's split-lock detection can trap or
  throttle misaligned locked operations on newer CPUs.

### 9.5 Segment-relative accesses (fs/gs)

- **Problem.** macOS x86-64 reaches per-thread data through `%gs`; Linux uses `%fs`. Wine also
  needs `%gs` to point at the Windows TEB (thread environment block).
- **How (evidence).**
  - Rosetta tracks a per-thread GS base and honours the private `_thread_set_tsd_base()` call.
    Wine's new GSBASE-swapping scheme works on Apple silicon under macOS 15. Rosetta does,
    however, "not seem to correctly implement the GS.base field of the full thread state"
    passed to signal handlers ([RE: B. Shanks, Wine MR 6866][wine6866-list]).
  - Apple's `libd3dshared` (part of the Game Porting Toolkit) "could activate a special mode
    in Rosetta 2 where code executing in certain regions would use the Windows TEB when
    accessing %gs" ([RE: Wine MR 6866][wine6866-list]). In other words, Rosetta can pick the
    GS base according to which code region is running. A runtime export `abi_for_address`
    hints at the same per-region idea ([RE: rosettax87 headers][rx87-export]; **[Inferred]**).
  - Exports `get_ldt`, `set_ldt`, `mov_segment`, `get_segment_limit` and
    `execution_mode_for_code_segment_selector` indicate LDT emulation and code-segment-dependent
    execution modes ([RE: rosettax87 headers][rx87-export]). That fits Johnson's report that
    Rosetta "apparently supports the full 32-bit instruction set for Wine" ([RE: Johnson][dj]).
    A "Rosetta User LDT" VM tag exists ([02][02] §5.3).
  - On Linux, `arch_prctl(ARCH_SET_FS)` and `fs:` accesses are presumably handled the same way
    **[Inferred]**.
- **Reverse direction [Inferred].** macOS arm64 keeps its thread-specific-data base in
  `TPIDRRO_EL0` ([XNU tsd.h][xnu-tsd]). Intel macOS does not enable user-mode FSGSBASE
  ([DynamoRIO issue][dynamorio1568]), and the host's own `%gs` belongs to libpthread. Keep the
  guest's TPIDR values in the context block and emit explicit base+offset addressing.

---

## 10. Floating point and SIMD

### 10.1 SSE to SSE4.2 → NEON

- Rosetta fully emulates SSE2. "All common operations" become reasonably optimised NEON
  sequences rather than scalar code or helper calls ([RE: Johnson, update][dj]). The advertised
  set before macOS 15 went up to SSE4.2 plus AES and PCLMULQDQ ([RE: Apple forum][aforum];
  AnandTech's "at most SSE4.2", see [07][07]).
- The complex SSE4.2 string compares (`PCMPESTRI/M`, `PCMPISTRI/M`) are runtime helpers
  ([RE: rosettax87 headers][rx87-export]). AES-NI, PCLMULQDQ and CRC32 probably map onto the
  arm64 crypto and CRC instructions **[Inferred]**.
- **Reverse direction [Inferred].** NEON → SSE4/AVX2 works for most ops. Pain points:
  - 32 vector registers versus 16;
  - `TBL`/`TBX`, `LD2/3/4` de-interleaving loads, `UZP/ZIP/TRN`, saturating narrows and
    pairwise ops all need multi-instruction `PSHUFB`/`PACK*`/`PUNPCK*` sequences;
  - SVE and SME are not an issue for macOS apps, except that M4-era Accelerate uses SME
    internally.

### 10.2 x86 versus Arm FP semantics, and how Rosetta matches x86

Behaviour measured on an M4 Pro under macOS 15.1.1 ([RE: mod_poppo][poppo]):

| IEEE-754 "implementation-defined" point | x86 SSE | Arm default | Rosetta 2 |
|---|---|---|---|
| Underflow (tininess) detection | after rounding | before rounding | x86 |
| `fma(0, ∞, qNaN)` raises Invalid? | no | yes | x86 |
| Default NaN from 0/0 | `0xffc00000` (sign set) | `0x7fc00000` | x86 |
| qNaN + sNaN propagation | leftmost NaN | sNaN wins | x86 |
| Flush-to-zero underflow flag and result | x86 rules | Arm rules | x86 |

- **How.** Checking every FP op in software would be very expensive; Apple does it in
  hardware instead ([RE: Johnson][dj]).
  - On M1 the alternate mode is non-standard. Asahi's m1n1 experiments toggle an `AFP` bit in
    `ACTLR_EL1` and an Apple register `AFPCR_EL0` with separate DAZ/FTZ bits
    ([RE: m1n1 fptest.py][m1n1fp]).
  - The mode was later standardised as Armv8.7 **FEAT_AFP** (`FPCR.AH/FIZ/NEP`), which M3 and
    M4 implement ([RE: mod_poppo][poppo]). With `FPCR.AH=1`, `FMIN/FMAX` also adopt x86
    MINSS/MAXSS semantics ([RE: mod_poppo][poppo]).
  - Hardware details are in [04][04]. Snapdragon X also has FEAT_AFP, and Prism's x64 binaries
    reproduce the x86 results there ([reader report under mod_poppo][poppo]).
- **Reverse direction [Inferred].** This direction has no hardware help. x86 has no "Arm FP
  mode", so bit-exact Arm NaN propagation, tininess-before-rounding and FMIN/FMAX semantics
  need extra instructions or checks. FCVTZS saturation versus x86's "integer indefinite"
  (0x80000000) needs fix-ups. `FJCVTZS` (the JavaScript convert) is a multi-instruction
  sequence. Most apps will not care; a "fast but inexact" switch is worth considering.

### 10.3 MXCSR

- Not documented. The natural mapping **[Inferred]** is:
  - rounding control → `FPCR.RMode`;
  - sticky exception flags ↔ FPSR cumulative bits;
  - DAZ/FTZ → `AFPCR` (M1) or `FPCR.FIZ/FZ` with `AH` (M3+).

  x86's "denormal operand" flag has no exact Arm equivalent, and unmasked FP exceptions (rare)
  would need trapping. Open question.

### 10.4 x87 (80-bit floating point)

- **Problem.** Arm has no 80-bit extended format.
- **How.**
  - Rosetta has a "full, slow, software implementation of x87's 80-bit floating point"
    ([RE: Johnson][dj]).
  - The rosettax87 headers list **75 x87 helper routines** exported by Rosetta's runtime
    library (for example `x87_fadd_f32/f64/ST`, `x87_fcos`, `x87_f2xm1`, `x87_fbld`), plus
    `x87_state_from/to_x86_float_state` converters ([RE: rosettax87 headers][rx87-export]).
    So translated x87 instructions call out to helpers that work on an in-memory x87 stack
    **[Inferred from names]**.
  - The x87sidecar `ROSETTA_X87_FAST_ROUND` knob implies the stock helpers dispatch on the x87
    rounding mode ([RE: x87sidecar][x87sidecar]).
- **Alternatives elsewhere.** Windows on Arm translates x87 to 64-bit doubles (kode54's comment
  on [Johnson][dj]). Box64 uses hardware doubles with tricks to keep 80 bits where needed
  ([Benchmark: box86.org 2022][box64-2022]). Community hooks that swap Rosetta's helpers for
  double-precision ones report 4 to 5× on a fsqrt microbenchmark and about 10× on M4
  ([Benchmark: rosettax87][rx87], [box64 #2595][box64-2595]); see [07][07].
- **Reverse direction [Inferred].** Not applicable: ARM code has no x87. The host x87 unit is
  of no use for ARM FP semantics.

### 10.5 AVX and AVX2 (macOS 15 Sequoia and later)

- **Timeline.**
  - 2020 to 2023 (Big Sur to Sonoma): Rosetta "does not support the AVX vector extensions"
    ([Apple WWDC20 10686][wwdc10686]). AVX code crashed with an illegal instruction unless the
    app checked CPUID first.
  - macOS 15 (developer beta June 2024, release September 2024): AVX and AVX2 execute. Apple's
    page now says Rosetta "translates all x86_64 instructions, including ones from the AVX and
    AVX2 instruction set" ([Apple][apple-about]). Game Porting Toolkit 2 advertised it.
  - FMA works under macOS 15.1.1 and reproduces x86 exception semantics ([RE: mod_poppo][poppo]).
- **Not advertised by default on macOS.**
  - Go's runtime notes that on macOS 15 Rosetta supports AVX1 and AVX2, yet "neither CPUID
    nor sysctl says it has AVX", so Go assumes AVX under Rosetta ([Go source][go-cpu]).
  - A 2025 Sequoia check showed `hw.optional.avx1_0: 0` and `avx2_0: 0` under Rosetta
    ([RE: Qiita][qiita-avx]).
  - GPTK 2's README documents `ROSETTA_ADVERTISE_AVX=1`, which makes Rosetta publish the CPUID
    bits "when running in the evaluation environment". The setting "does not modify the
    availability of the instruction set in Rosetta; it only controls whether the processor
    advertises its support" ([GPTK README quoted in Whisky PR #1034][whisky1034]).
  - CrossOver 25 sets it automatically for games that need it ([CodeWeavers][cx25]).
  - This resolves the AVX CPUID conflict listed in [02][02] §6.
- **Linux differs.** Rosetta for Linux advertises `avx avx2 fma f16c bmi1 bmi2` in CPUID and
  in its synthesised `/proc/cpuinfo` ([Benchmark: Geekbench, Oct 2025][gb-m4linux];
  [RE: inoki][inoki]).
- **How it is implemented** (published AOT disassembly, macOS 15.0 beta 1, M2;
  [RE: carsongoodwin32][avxdive-disasm]):
  - every 256-bit op becomes **two 128-bit NEON ops**;
  - the low half lives in v0 to v15 (shared with XMM);
  - the **high half lives in memory** in the per-thread context (x18 + 0x230 + 16·n) and is
    loaded and stored around each AVX instruction, using v24/v25 as scratch;
  - `VZEROUPPER` becomes 16 stores of a zero vector.

  Plausible reason **[Inferred]**: keeping all 32 YMM halves in registers would use every NEON
  register and break the fixed XMM → v0..v15 map that the SSE code generator relies on.
- **Consequence.** The AVX2 path is often slower than the SSE2 path for the same work
  ([07][07] §2.3). CrossOver's maintainer warns that advertising AVX "would cause AVX/2 to be
  used over a possible SSE2 code path" ([Whisky PR #1034][whisky1034]).
- **Conflict on BMI1/BMI2 under macOS.**
  - BetaWiki lists AVX, AVX2, BMI, FMA and F16C ([BetaWiki][betawiki]).
  - Stockfish's AVX2 build, which also uses `-mbmi`, died with "illegal hardware instruction"
    on an M4 under macOS 15.1.1. Maintainers suspected BMI1; this was not confirmed
    ([Stockfish #5707][stockfish]).
  - Apple's page names only AVX/AVX2.
- An early report that Rosetta's AVX2 gives **wrong results** was retracted: the test relied on
  undefined behaviour across inline-asm blocks, which `vzeroupper` exposed
  ([avx dive issue #1][avxdive-i1]).
- **Reverse direction [Inferred].** NEON (128-bit) maps naturally onto XMM/VEX-128. There is no
  need to emulate wider vectors, since ARM code on Apple silicon has no SVE.

### 10.6 Why there is no AVX-512

- **Fact.** Rosetta does not support AVX-512, and apps are told to check `hw.optional.avx512f`
  ([Apple][apple-about]).
- **Likely reasons [Inferred].**
  - AVX-512 means 32 × 512-bit registers (2 KB of state), 8 mask registers, and per-element
    masking, broadcast and embedded rounding on almost every instruction. That would be four
    NEON ops plus memory traffic per instruction, given that 256-bit AVX2 already pushes
    state into memory (§10.5).
  - Apple cores have no regular SVE. M4 has SME with a *streaming* SVE mode (512-bit), but it
    is a separate coprocessor mode with its own register state and mode-switch costs, and it
    does not support SVE outside streaming mode ([RE: tzakharko][tzak]; LLVM comment in
    [Apple forum][llvm-m4]). It is not a general-purpose target.
  - x86 software must already cope with AVX-512 being absent (on most Intel client CPUs, Meteor
    Lake included), so leaving it out costs compatibility very little.

---

## 11. Special instructions

### 11.1 CPUID

- CPUID is a runtime routine (`runtime_cpuid` in [the export list][rx87-export]). Reported
  identity:
  - vendor `GenuineIntel` on M1-era macOS ([RE: Cownie][cownie]) and in Geekbench uploads
    from macOS 13.2 and from Linux Docker in 2025;
  - brand `VirtualApple @ 2.50GHz`;
  - family 6, model 44 (a Westmere number) ([Geekbench M2 Max][gb-m2max],
    [Geekbench M4 Linux][gb-m4linux]).
- Rosetta for Linux's synthesised `/proc/cpuinfo` instead says `vendor_id: VirtualApple`,
  model 142 ([RE: inoki][inoki]). Vendor strings vary by version; see [02][02] §6.
- Feature bits before macOS 15: up to SSE4.2 + AES + PCLMULQDQ, with no POPCNT, AVX or F16C bit
  in `machdep.cpu.features` ([RE: Apple forum][aforum], [RE: R. Lo][medium-lo]). A POPCNT
  build of Stockfish nevertheless ran on macOS 15.1.1 ([Stockfish #5707][stockfish]).
  Invariant TSC is reported; leaf 0x15 is not ([RE: Cownie][cownie]).
- **Reverse direction [Inferred].** ARM exposes features through ID registers
  (`ID_AA64ISAR0_EL1` and friends, trapped and emulated for EL0 by Linux and readable through
  macOS `hw.optional.arm.*` sysctls). The translator should report a consistent synthetic
  feature set, and should not advertise features it emulates slowly.

### 11.2 RDTSC/RDTSCP and time

- Under Rosetta (M1), RDTSC counts in **nanosecond units** (about 1 GHz) but moves in steps of
  about 41 ticks, i.e. the 24 MHz system counter. The "2.50GHz" in the brand string is not the
  TSC rate ([RE: Cownie][cownie]).
- `mach_absolute_time` reports a 1:1 nanosecond timebase to translated processes. Natively on
  M1 it is 125:3 ([RE: Eclectic Light][elc-time]). Apple listed timebase frequency among the
  differences Rosetta hides ([Apple WWDC20 10686][wwdc10686]) and warns that values differ
  between native and translated processes ([Apple][apple-arch]).
- So RDTSC is most likely `CNTVCT_EL0` scaled by 125/3 **[Inferred]**.
- **Reverse direction [Inferred].** ARM `CNTVCT_EL0`/`CNTFRQ_EL0` reads become host RDTSC
  scaled to the counter frequency the guest expects (24 MHz on M1-class Macs; XNU also has a
  1 GHz-timebase path for newer cores that it deliberately disables for translated tasks, see
  [02][02] §5.3). `CNTFRQ_EL0` must report whatever frequency is being emulated.

### 11.3 Integer division

- x86 `DIV/IDIV r64` divides the 128-bit RDX:RAX, which arm64 has no instruction for. Runtime
  helpers `runtime_wide_udiv_64` and `runtime_wide_sdiv_64` exist
  ([RE: rosettax87 headers][rx87-export]).
- x86 raises #DE on divide-by-zero or quotient overflow, while arm64 `UDIV/SDIV` quietly return
  0. The translation must test and raise SIGFPE explicitly **[Inferred]**.
- **Reverse direction [Inferred].** ARM `UDIV/SDIV` must not trap on x86. Guard the x86 `DIV`
  against zero (ARM returns 0) and against `INT_MIN/-1` (ARM returns INT_MIN).

### 11.4 String instructions (REP MOVS/STOS/CMPS/SCAS) and the direction flag

- **No published reverse engineering describes these.** FFRI confirms the decoder parses the
  REP/REPNE prefixes ([RE: FFRI part 1][ffri1]). No string-op helper shows up in the published
  export list, which suggests inline loops, but the list may be incomplete **[Inferred]**.
- Expected approach **[Inferred]**: DF lives in the emulated RFLAGS in the thread context.
  REP MOVS/STOS get fast paths for DF=0 with large counts (LDP/STP or NEON loops) and a
  byte-exact slow path otherwise. All of them must remain restartable at instruction
  granularity, because x86 lets a REP instruction be interrupted mid-way with RCX, RSI and RDI
  updated.
- **Reverse direction [Inferred].** Not applicable: ARM has no string instructions. ARMv8.8
  `CPY*`/`SET*` memcpy/memset instructions, if they ever appear, would map nicely onto
  `REP MOVSB/STOSB`, which Meteor Lake implements quickly (ERMS/FSRM).

### 11.5 SYSCALL and other trapping instructions

- The x86 system-call interface is emulated by the runtime, which issues native `svc #0x80`.
  The rosettax87 loader locates such a routine in `/usr/libexec/rosetta/runtime`
  ([RE: rosettax87 loader comments][rx87]; [Apple WWDC20][wwdc10686]; details in [02][02]
  §5.2). How `INT3`, `UD2`, `HLT` and `INT n` become signals is not documented **[Inferred]**.
- **Reverse direction [Inferred].** ARM `SVC #0x80` (with x16 holding the syscall number on
  macOS) becomes a host `SYSCALL` with renumbering and argument marshalling. `BRK` becomes
  SIGTRAP.

### 11.6 Self-modifying code and guest JITs

- **Problem.** x86 needs no instruction-cache flush. Code can be written and executed straight
  away, so Rosetta must notice changes with no explicit hint ([RE: Saagar Jha, HN 2021][sj2021b]).
- **How** (Saagar Jha's walk-through, M1 era; [HN 2021][sj2021], [HN 2022][sj2022]):
  1. An RWX region requested by the guest is actually mapped RW. It never needs native execute
     permission, because only its translation runs.
  2. Guest writes go through without trapping.
  3. An indirect branch into the region passes through a trampoline. The runtime sees an RWX
     target, creates a JIT translation, and marks the source page read-only.
  4. The next guest write faults. Rosetta's exception server flips the page back to RW and
     invalidates the old translations.
  5. The next branch retranslates. As he notes, "a fresh JIT entry is allocated even though the
     code is the same".

  The Apple Platform Security guide describes the JIT path as translation inside the process,
  with the kernel still checking x86 page hashes as pages fault in ([Apple Platform
  Security][apple-sec]). Native arm64 code pages inside a translated process are mapped with
  `MAP_TRANSLATED_ALLOW_EXECUTE` ([RE: x87sidecar][x87sidecar]; [02][02] §2.4).
- **Known hole.** Writes through a **second mapping** of the same physical page (W^X "double
  mapping") do not fault. The .NET team found Rosetta "is unable to detect when an already
  executed code page is modified" this way in Linux x64 containers, and turned double mapping
  off there ([RE: dotnet/runtime PR #102509, May 2024][dotnet]).
- **Reverse direction [Inferred].** This direction is easier. ARM code *must* announce code
  changes: `IC IVAU`/`DSB`/`ISB`, `sys_icache_invalidate`, and on macOS `MAP_JIT` plus
  `pthread_jit_write_protect_np`. A translator can hook those instead of relying only on page
  protection, but should keep the write-fault mechanism as a backstop for buggy guests.

---

## 12. Other notable details

- **Hardware-specific code generation.**
  - Export names include `translator_use_t8027_codegen` and `translator_set_variant`
    ([RE: rosettax87 headers][rx87-export]). T8027 is the A12X/A12Z inside the 2020
    Developer Transition Kit ([Asahi SoC table][asahi-soc]).
  - The A12 family is Armv8.3 and lacks FEAT_FlagM (CFINV, RMIF, SETF), so it most likely
    needed a separate code generator **[Inferred]**. That would also explain the empty
    `aot_shared_cache.t8027` FFRI saw ([02][02] §8, item 9).
- **Debug knobs.** `ROSETTA_PRINT_IR` dumps translated x86 blocks and `ROSETTA_PRINT_SEGMENTS`
  dumps mappings ([RE: FFRI part 2][ffri2], Big Sur).
- **User mode only.** No kernel extensions and no VM apps that virtualise x86-64
  ([Apple][apple-about]).
- **4 KB pages.** Translated tasks see 4 KB pages on 16 KB-page hardware ([Apple WWDC20][wwdc10686];
  [RE: x87sidecar][x87sidecar]); see [04][04].

---

## 13. Carry-over summary for an ARM64 → x86-64 translator [Inferred]

| Rosetta technique | Carries over? | Why / what changes |
|---|---|---|
| Whole-image AOT plus JIT fallback | **Yes** | ARM Mach-O is as analysable; JIT is still needed for guest JITs |
| One-to-one, canonical state | **Partly** | Fine for exceptions and debugging, but 31 guest GPRs do not fit in 16 host GPRs; needs a memory-backed register file or allocation |
| Fixed register map | **No** (only partly) | Pin hot registers; keep the rest in memory |
| Hardware TSO | **Not needed** | x86 is already stronger; only STLR→LDAR pairs and DMB need care |
| Flags in host flags with inverted carry | **Yes, mirrored** | Map ARM C to NOT CF after compares; watch implicit flag writes (use LEA and BMI2) |
| PF/AF extension | **Not needed** | ARM never reads them |
| BL/RET + private return stack | **Yes, mirrored** | Host CALL/RET on a private stack; check CET shadow-stack interaction |
| Inline caches and hashed indirect lookup | **Yes** | Same structures |
| Prologue/epilogue fusion | **Yes** | STP/LDP → paired MOVs (16-byte moves where legal) |
| Alternate FP mode in hardware | **No** | No x86 equivalent; exact Arm FP semantics cost instructions (offer a fast-inexact mode) |
| NEON ↔ SSE/AVX | **Yes, mostly** | 32 → 16 vector registers; TBL, LD3/LD4 and saturating ops expand |
| SMC detection by write-protect | **Yes, plus a hint** | ARM's explicit cache maintenance gives cheap invalidation hints |
| No ABI mixing | **Design choice** | Without arm64 system frameworks on Intel macOS, thunking (Arm64EC-style) may be unavoidable |

---

## Open questions

1. **String instructions and DF.** How REP MOVS/STOS/CMPS/SCAS and DF=1 are translated (inline
   loops, helpers or fast paths) is unpublished.
2. **Unused registers.** What x16, x17, x19, x20, x26 to x29 and v16 to v31 are used for, if
   anything, beyond the AOT listings seen.
3. **Return-stack overflow.** What happens when the private return stack (x21) overflows or
   underflows, for example under deep recursion or coroutine switching.
4. **PF for FP compares.** How PF is produced for unordered (U)COMISS/D, and whether Apple's
   PF/AF extension also covers FCMP.
5. **MXCSR.** Exact mapping, including the DE flag and unmasked exceptions.
6. **Split-cache-line atomics.** The behaviour of LOCK-prefixed ops that cross a cache line
   (the lewurm and GraalVM observations conflict).
7. **AVX-ADVERTISE default in macOS 26.** Whether `ROSETTA_ADVERTISE_AVX` is still needed, and
   whether BMI1/BMI2/MOVBE/LZCNT are supported on macOS (sources conflict).
8. **Logic ops and INC/DEC with a live CF.** Whether Rosetta emits CFINV, SETF or RMIF sequences
   after `TEST/AND/OR/XOR`, or around INC/DEC, when CF escapes; inferred above, not observed.
9. **Mid-sequence faults.** How faults inside fused prologues or multi-instruction translations
   are rolled forward or back (`determine_state_recovery_action` semantics).
10. **Vendor string.** Whether the CPUID vendor (`GenuineIntel` versus `VirtualApple`) changed on
    macOS as it did in Linux's synthesised `/proc/cpuinfo`.

---

## Sources

Primary reverse-engineering and analysis:

- Dougall Johnson, "Why is Rosetta 2 fast?", 9 Nov 2022, plus comments: <https://dougallj.wordpress.com/2022/11/09/why-is-rosetta-2-fast/>
- Koh M. Nakagawa (FFRI), Project Champollion part 1, 19 Feb 2021: <https://ffri.github.io/ProjectChampollion/part1/>
- Koh M. Nakagawa (FFRI), Project Champollion part 2, 4 Mar 2021: <https://ffri.github.io/ProjectChampollion/part2/>
- lewurm, "Fun with Rosetta 2 and atomic instructions" (gist), 16 Feb 2022: <https://gist.github.com/lewurm/527dd29aec1bd6103548d505146f3c98>
- GraalVM issue #4314 (SIGBUS at LOCK XADD under Rosetta): <https://github.com/oracle/graal/issues/4314>
- carsongoodwin32, rosetta2_avx_dive (README, AOT files, Ghidra listings), Jun 2024: <https://github.com/carsongoodwin32/rosetta2_avx_dive>; published listings: <https://github.com/carsongoodwin32/rosetta2_avx_dive/tree/main/plaintext_disasm>; issue #1 (benchmark UB): <https://github.com/carsongoodwin32/rosetta2_avx_dive/issues/1>
- Saagar Jha, Hacker News comments, 30 Nov 2021: <https://news.ycombinator.com/item?id=29388394>, <https://news.ycombinator.com/item?id=29388820>; 17 May 2022: <https://news.ycombinator.com/item?id=31414019>
- dotnet/runtime PR #102509 "Disable W^X in Rosetta emulated x64 containers on macOS", May 2024: <https://github.com/dotnet/runtime/pull/102509>
- rosettax87 (Lifeisawful), 2025: <https://github.com/Lifeisawful/rosettax87>; export header: <https://github.com/Lifeisawful/rosettax87/blob/main/rosettaRuntime/Export.h>
- rosettax87_jit: <https://github.com/Lifeisawful/rosettax87_jit>
- athei/x87sidecar, 2026: <https://github.com/athei/x87sidecar>
- ptitSeb/box64 issue #2595 (rosettax87 numbers on M4), May 2025: <https://github.com/ptitSeb/box64/issues/2595>
- Asahi Linux m1n1 `fptest.py` (Apple AFP mode, AFPCR_EL0): <https://github.com/AsahiLinux/m1n1/blob/main/proxyclient/experiments/fptest.py>
- mod_poppo, "Testing Armv8.7 FEAT_AFP on Apple M4", 21 Nov 2024 (updated May 2025): <https://zenn.dev/mod_poppo/articles/arm-feat_afp?locale=en>
- Jim Cownie, "Fun with Timers and cpuid", 3 Mar 2021: <https://cpufun.substack.com/p/fun-with-timers-and-cpuid>
- Brendan Shanks, Wine MR 6866 (GSBASE swapping; Rosetta notes), 2025: <https://list.winehq.org/mailman3/hyperkitty/list/wine-gitlab@winehq.org/message/ANZ6FHCAD6L2A5FSJTGG4AAIZ2OUICJU/> (MR: <https://gitlab.winehq.org/wine/wine/-/merge_requests/6866>)
- threedots, "Quick look at Rosetta on Linux", Jun 2022: <https://threedots.ovh/blog/2022/06/quick-look-at-rosetta-on-linux/>
- arianvp, "Rosetta AOT Caching on Linux for Virtualization.Framework" (gist): <https://gist.github.com/arianvp/23bfd2a360116ac80c39f553cae56b3a>
- inoki, "Things You Might Want to Know About Apple's Rosetta 2 for Linux VMs", 28 Feb 2026: <https://blog.inoki.cc/2026/02/28/Apple-Rosetta-Linux-VM-Secret-en/index.html>; HN cpuinfo comment: <https://news.ycombinator.com/item?id=47201288>
- Peter Cawley, "Arm64EC: Microsoft's Emulation Frankenstein", FOSDEM, 4 Feb 2024: <https://archive.fosdem.org/2024/events/attachments/fosdem-2024-1762-arm64ec-microsoft-s-emulation-frankenstein/slides/22690/Arm64EC_slides_only_7shtDgt.pdf>
- T. Spink, B. Franke, "Accelerating Shared Library Execution in a DBT", LCTES 2024: <https://doi.org/10.1145/3652032.3657565>
- mynavi, "「Rosetta 2」はこうなっていた!" (AOT file sizes, DTrace), 4 Dec 2020: <https://news.mynavi.jp/article/osxhack-273/>
- Eclectic Light, "Running Intel code on your M1 Mac: Rosetta 2 and OAH", 22 Jan 2021: <https://eclecticlight.co/2021/01/22/running-intel-code-on-your-m1-mac-rosetta-2-and-oah/>
- Eclectic Light, "Inside M1 Macs: Time and logs", 27 Nov 2020: <https://eclecticlight.co/2020/11/27/inside-m1-macs-time-and-logs/>
- Qiita (STDNUL), "macOS SequoiaのRosetta 2でAVX2が動くらしい件", 24 May 2025: <https://qiita.com/STDNUL/items/a17bbba6202835407e6b>
- Go source `internal/cpu/cpu_x86_darwin.go`: <https://go.dev/src/internal/cpu/cpu_x86_darwin.go>
- Whisky PR #1034 (quotes the GPTK 2 README on `ROSETTA_ADVERTISE_AVX`), Jun to Sep 2024: <https://github.com/Whisky-App/Whisky/pull/1034>
- CodeWeavers, "Experience next level gaming on Mac with CrossOver 25", 11 Mar 2025: <https://www.codeweavers.com/blog/mjohnson/2025/3/11/experience-next-level-gaming-on-mac-with-crossover-25>
- Stockfish issue #5707, Dec 2024: <https://github.com/official-stockfish/Stockfish/issues/5707>
- BetaWiki, macOS Sequoia: <https://betawiki.net/wiki/MacOS_Sequoia>
- Apple Developer Forums thread 693939 (CPU features under Rosetta): <https://developer.apple.com/forums/thread/693939>
- Raymond Lo, "M1 Rosetta 2 limitation: illegal hardware instruction", Dec 2020: <https://medium.com/macoclock/m1-rosetta-2-limitation-illegal-hardware-instruction-a3b48fae02e>
- Geekbench 6, Mac14,6 (M2 Max) under Rosetta, macOS 13.2: <https://browser.geekbench.com/v6/cpu/14955>
- Geekbench 6, Mac mini M4, Linux Docker with Rosetta, Oct 2025: <https://browser.geekbench.com/v6/cpu/14595669>
- Docker forum (M1 Linux `/proc/cpuinfo` flags incl. `uscat`), Mar 2021: <https://forums.docker.com/t/cpu-flags-not-passing-through-into-container-sse-4-2/105499>
- tzakharko, "M4 SME exploration": <https://github.com/tzakharko/m4-sme-exploration/blob/main/reports/01-sme-overview.md>
- Apple Developer Forums thread 757704 (M4 without SVE, LLVM comment): <https://developer.apple.com/forums/thread/757704>
- Asahi Linux, SoC codenames: <https://asahilinux.org/docs/hw/soc/soc-codenames/>
- Apple XNU `libsyscall/os/tsd.h` (arm64 TSD via TPIDRRO_EL0): <https://github.com/apple/darwin-xnu/blob/main/libsyscall/os/tsd.h>
- DynamoRIO issue #1568 (no user-mode RDWRFSGS on OS X): <https://github.com/DynamoRIO/dynamorio/issues/1568>
- QEMU translator internals (lazy condition codes, SMC): <https://people.redhat.com/pbonzini/qemu-test-doc/_build/html/_sources/topics/Translator-Internals.txt>
- box86.org, "Box86/Box64 vs QEMU vs FEX (vs Rosetta2)", 24 Mar 2022: <https://box86.org/2022/03/box86-box64-vs-qemu-vs-fex-vs-rosetta2/>
- box86.org, "New version of box64 v0.3.2 and box86 v0.3.8", 6 Dec 2024: <https://box86.org/2024/12/new-version-of-box64-v0-3-2-and-box86-v0-3-8/>

Apple:

- About the Rosetta translation environment (current revision mentions AVX/AVX2 and macOS 27): <https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment>
- Addressing architectural differences in your macOS code: <https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code>
- WWDC20 10686, "Explore the new system architecture of Apple silicon Macs": <https://developer.apple.com/videos/play/wwdc2020/10686/>
- WWDC20 10214, "Port your Mac app to Apple silicon": <https://developer.apple.com/videos/play/wwdc2020/10214/>
- Apple Platform Security, "Rosetta 2 on a Mac with Apple silicon": <https://support.apple.com/guide/security/rosetta-2-on-a-mac-with-apple-silicon-secebb113be1/web>

Microsoft (contrast):

- How emulation works on Arm (Prism): <https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-x86-emulation>

[02]: 02-architecture-and-runtime.md
[04]: 04-hardware-assists.md
[07]: 07-performance.md
[dj]: https://dougallj.wordpress.com/2022/11/09/why-is-rosetta-2-fast/
[ffri1]: https://ffri.github.io/ProjectChampollion/part1/
[ffri2]: https://ffri.github.io/ProjectChampollion/part2/
[lewurm]: https://gist.github.com/lewurm/527dd29aec1bd6103548d505146f3c98
[graal4314]: https://github.com/oracle/graal/issues/4314
[avxdive]: https://github.com/carsongoodwin32/rosetta2_avx_dive
[avxdive-disasm]: https://github.com/carsongoodwin32/rosetta2_avx_dive/tree/main/plaintext_disasm
[avxdive-i1]: https://github.com/carsongoodwin32/rosetta2_avx_dive/issues/1
[sj2021]: https://news.ycombinator.com/item?id=29388820
[sj2021b]: https://news.ycombinator.com/item?id=29388394
[sj2022]: https://news.ycombinator.com/item?id=31414019
[dotnet]: https://github.com/dotnet/runtime/pull/102509
[rx87]: https://github.com/Lifeisawful/rosettax87
[rx87-export]: https://github.com/Lifeisawful/rosettax87/blob/main/rosettaRuntime/Export.h
[rx87jit]: https://github.com/Lifeisawful/rosettax87_jit
[x87sidecar]: https://github.com/athei/x87sidecar
[box64-2595]: https://github.com/ptitSeb/box64/issues/2595
[box64-2022]: https://box86.org/2022/03/box86-box64-vs-qemu-vs-fex-vs-rosetta2/
[box64-2024]: https://box86.org/2024/12/new-version-of-box64-v0-3-2-and-box86-v0-3-8/
[m1n1fp]: https://github.com/AsahiLinux/m1n1/blob/main/proxyclient/experiments/fptest.py
[poppo]: https://zenn.dev/mod_poppo/articles/arm-feat_afp?locale=en
[whisky1034]: https://github.com/Whisky-App/Whisky/pull/1034
[go-cpu]: https://go.dev/src/internal/cpu/cpu_x86_darwin.go
[qiita-avx]: https://qiita.com/STDNUL/items/a17bbba6202835407e6b
[cx25]: https://www.codeweavers.com/blog/mjohnson/2025/3/11/experience-next-level-gaming-on-mac-with-crossover-25
[stockfish]: https://github.com/official-stockfish/Stockfish/issues/5707
[betawiki]: https://betawiki.net/wiki/MacOS_Sequoia
[cownie]: https://cpufun.substack.com/p/fun-with-timers-and-cpuid
[elc-time]: https://eclecticlight.co/2020/11/27/inside-m1-macs-time-and-logs/
[elc-oah]: https://eclecticlight.co/2021/01/22/running-intel-code-on-your-m1-mac-rosetta-2-and-oah/
[aforum]: https://developer.apple.com/forums/thread/693939
[medium-lo]: https://medium.com/macoclock/m1-rosetta-2-limitation-illegal-hardware-instruction-a3b48fae02e
[gb-m2max]: https://browser.geekbench.com/v6/cpu/14955
[gb-m4linux]: https://browser.geekbench.com/v6/cpu/14595669
[inoki]: https://blog.inoki.cc/2026/02/28/Apple-Rosetta-Linux-VM-Secret-en/index.html
[hn-cpuinfo]: https://news.ycombinator.com/item?id=47201288
[docker-cpu]: https://forums.docker.com/t/cpu-flags-not-passing-through-into-container-sse-4-2/105499
[wine6866-list]: https://list.winehq.org/mailman3/hyperkitty/list/wine-gitlab@winehq.org/message/ANZ6FHCAD6L2A5FSJTGG4AAIZ2OUICJU/
[threedots]: https://threedots.ovh/blog/2022/06/quick-look-at-rosetta-on-linux/
[arianvp]: https://gist.github.com/arianvp/23bfd2a360116ac80c39f553cae56b3a
[cawley]: https://archive.fosdem.org/2024/events/attachments/fosdem-2024-1762-arm64ec-microsoft-s-emulation-frankenstein/slides/22690/Arm64EC_slides_only_7shtDgt.pdf
[lctes24]: https://doi.org/10.1145/3652032.3657565
[mynavi]: https://news.mynavi.jp/article/osxhack-273/
[qemu-int]: https://people.redhat.com/pbonzini/qemu-test-doc/_build/html/_sources/topics/Translator-Internals.txt
[tzak]: https://github.com/tzakharko/m4-sme-exploration/blob/main/reports/01-sme-overview.md
[llvm-m4]: https://developer.apple.com/forums/thread/757704
[asahi-soc]: https://asahilinux.org/docs/hw/soc/soc-codenames/
[xnu-tsd]: https://github.com/apple/darwin-xnu/blob/main/libsyscall/os/tsd.h
[dynamorio1568]: https://github.com/DynamoRIO/dynamorio/issues/1568
[apple-about]: https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment
[apple-arch]: https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code
[wwdc10686]: https://developer.apple.com/videos/play/wwdc2020/10686/
[wwdc10214]: https://developer.apple.com/videos/play/wwdc2020/10214/
[apple-sec]: https://support.apple.com/guide/security/rosetta-2-on-a-mac-with-apple-silicon-secebb113be1/web
