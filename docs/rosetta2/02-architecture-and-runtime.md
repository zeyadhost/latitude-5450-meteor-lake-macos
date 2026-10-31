# Rosetta 2 — Software Architecture and Runtime

*Scope of this document:* the **components**, the **launch/runtime flow** of a translated
x86-64 process, and the **files** involved. Instruction-selection techniques, the hardware
assists (TSO, flag extensions, 4 KB pages), Apple's official positioning, and the
Linux/VM story are covered by sibling documents and only cross-referenced here.

*Provenance labels used throughout:*
**[Apple]** = Apple documentation/source · **[XNU source]** = Apple's open-source XNU
(file/function cited; tag noted) · **[RE: author]** = named reverse-engineering work ·
**[Community]** = forum/issue-tracker observation, lower confidence · **[Inferred]** = my
own reasoning from the above. Internals changed across macOS releases, so findings carry a
version note where it matters.

*Terminology.* "arm64" = native Apple-silicon code; "x86-64" = the Intel code being
translated; **AOT** = ahead-of-time (translate-before-run); **JIT** = just-in-time
(translate-on-demand); **OAH** = Apple's internal name for Rosetta (the daemon is `oahd`,
the cache lives under `/var/db/oah`, and `IMGPF_ROSETTA`/`P_TRANSLATED` are the kernel
flags). The origin of "OAH" is unknown.

XNU code in this document was read from tag **`xnu-12377.121.6`** (macOS 26.x era) unless
noted; I spot-checked older tags (`xnu-7195.*` = Big Sur 11, `xnu-8019/8020` = Monterey 12,
`xnu-8792/8796` = Ventura 13, `xnu-11215` = Sequoia 15) where version drift mattered.

---

## 1. Components and where they live

Rosetta is **not** part of the sealed System volume. It is installed on demand onto the
Data volume and can be updated out of band from macOS itself. **[RE: Howard Oakley/Eclectic
Light]** Internally everything is branded "OAH". **[RE: Oakley]**

### 1.1 On-disk layout

| Path | What it is | Notes |
|---|---|---|
| `/Library/Apple/usr/libexec/oah/` | Primary Rosetta component dir (Big Sur). Holds `libRosettaRuntime`, and (Monterey+) `runtime`, `translate_tool`, `RosettaLinux`, `debugserver`. | **[RE: FFRI]**, **[Community: Apple SE]** |
| `/usr/libexec/rosetta/` | Component dir used from **Monterey 12** onward: `oahd`, `oahd-helper`, `oahd-root-helper`, `runtime`, `translate_tool`, `debugserver`. | The `oahd-helper` location moved here from the `oah` dir between Big Sur and Monterey. **[Community: Apple SE]**, **[RE: blacktop ipsw-diffs]** |
| `/Library/Apple/usr/lib/libRosettaAot.dylib` | Library linked by `oahd-helper` (the translator). | In the `com.apple.pkg.RosettaUpdateAuto` receipt. **[Community: Apple SE bom]**, **[RE: ipsw-diffs oahd-helper deps]** |
| `/Library/Apple/usr/share/rosetta/rosetta` | Small data/marker file installed with the package. | **[Community]** |
| `/var/db/oah/` (a.k.a. `/private/var/db/oah/`) | **Per-machine AOT cache.** Contains `Oah.version` and one subdir per translated image, named by a SHA-256 "AOT lookup hash"; each holds the `*.aot` file. | A **Data Vault**, inaccessible to everything but the Rosetta service even as root. **[Apple]**, **[RE: FFRI]** |
| `/System/Library/dyld/aot_shared_cache` | **AOT shared cache** — the pre-translated counterpart of the x86-64 `dyld_shared_cache`. ~2+ GB; `file` reports `data`. Per-SoC variant seen as `aot_shared_cache.t8027`. | **[RE: FFRI part2]** |
| `/System/Library/dyld/dyld_shared_cache_x86_64`, `…_x86_64h` | The Intel dyld shared caches retained on Apple silicon so translated code can use them. | **[RE: FFRI]**; retention on AS confirmed by **[RE: CryptexFixup]** |

The daemon's launchd plist is `com.apple.oahd.plist`; macOS sandbox profiles reference it at
both `/System/Library/LaunchDaemons/com.apple.oahd.plist` and
`/Library/Apple/System/Library/LaunchDaemons/com.apple.oahd.plist`. **[Community: Nix sandbox
profile]**

### 1.2 The executables and their roles

| Component | Arch | Role |
|---|---|---|
| **`oahd`** | arm64 | The OAH **management daemon** (launchd job, runs as user `_oahd`). A translated process's runtime asks it, over Mach IPC, whether an AOT translation exists for a given image; `oahd` locates or creates it and hands back a read-only file descriptor. **[Apple]**, **[RE: FFRI]** |
| **`oahd-helper`** | arm64 | The **translator**. `oahd` forks/execs it with two file descriptors (source x86-64 image, destination AOT file); it links `libRosettaAot.dylib` and writes the translated Mach-O. **[RE: FFRI]**, **[RE: ipsw-diffs]** |
| **`oahd-root-helper`** | arm64 | Privileged helper for `oahd`. **[RE: ipsw-diffs]** (exact duties not reverse-engineered here — **[Inferred]** it performs the root-only Data-Vault/cache operations). |
| **`runtime`** | arm64 | The **in-process Rosetta runtime** mapped into every translated process. Sets up emulation, talks to `oahd`, maps/links AOT output, and does JIT translation. It is an executable image, **not** a dylib. **[RE: FFRI part1]** |
| **`libRosettaRuntime`** | arm64 | The runtime payload file whose presence sandbox code and tools test to detect "Rosetta installed". Closely related to `runtime` (see §7 open questions). **[Community]**, **[XNU test harness]** |
| **`translate_tool`** | arm64 | CLI that translates an x86-64 executable **without running it** (sends the fd to `oahd` via `fileport_makeport`). Used to pre-warm the cache. **[RE: FFRI "Dirty Bin Cache"]** |
| **`debugserver`** | arm64 | Rosetta-specific debug stub at `/Library/Apple/usr/libexec/oah/debugserver`, used by LLDB to debug translated processes at x86-64 level. **[RE: FFRI appendix]**, **[LLVM source]** |
| **`RosettaLinux`** | — | Rosetta for Linux VMs (Ventura+). Out of scope here; see the Linux sibling doc. **[RE: Oakley]** |

### 1.3 Installation and update

- Rosetta is absent on a fresh Apple-silicon Mac. It installs via the first-run popup, or
  `softwareupdate --install-rosetta [--agree-to-license]`; **no root required**.
  **[RE: FFRI]**, **[Community]**
- The installer package is `com.apple.pkg.RosettaUpdateAuto`; its bill-of-materials lists
  `libRosettaAot.dylib`, `oah/libRosettaRuntime`, and `share/rosetta/rosetta`.
  **[Community: Apple SE `lsbom`]**
- **Delivery mechanism (Ventura 13+):** Rosetta is carried in the **Apple-silicon OS
  cryptex** (the `OS.dmg` cryptex), which is also why Apple silicon keeps a pre-AVX2
  x86-64 dyld shared cache around. This is established indirectly by OpenCore Legacy
  Patcher's `CryptexFixup` kext, which forces the installer to use the "Apple Silicon
  Cryptex (OS.dmg)" variant specifically to obtain Rosetta. **[RE: Acidanthera CryptexFixup]**
  Because it is a cryptex/on-demand component on the Data volume, it can update outside a
  full macOS update. **[RE: Oakley]** · Exact cryptex identifier/signing chain: **[Open
  question]**.

### 1.4 Detecting Rosetta / a translated process

- Installed? Test for `libRosettaRuntime`'s existence, or `pgrep oahd` (the daemon only runs
  after the first x86-64 launch). **[Community]**
- Am I translated? `sysctlbyname("sysctl.proc_translated")` → `0` native, `1` translated,
  `-1`/`ENOENT` on non-AS. This OID is implemented in XNU at
  `bsd/kern/kern_sysctl.c` (`sysctl_sysctl_translated`, gated by `CONFIG_ROSETTA`) and
  backed by the `P_TRANSLATED` proc flag. **[Apple]**, **[XNU source: kern_sysctl.c,
  kern_proc.c `proc_is_translated`]**

---

## 2. Launch flow of an x86-64 process (kernel side)

The whole flow is driven by the kernel's image activator, then handed to the arm64 Rosetta
`runtime`. Key XNU facts (file/function cited) follow, then a diagram.

### 2.1 Image activation and the Rosetta flag

1. `exec_mach_imgact()` records `imgp->ip_origcputype`. A fat binary's slice is graded by
   `grade_binary()` → `ml_grade_binary()` (`bsd/dev/arm/kern_machdep.c`); an x86-64 slice is
   acceptable on arm64 macOS. A `posix_spawn` **binpref** (or Finder "Open using Rosetta",
   which uses the same `psa_binprefs` path) can force the x86-64 slice. **[XNU source:
   kern_exec.c]**
2. When the chosen image is x86-64, the kernel sets **`IMGPF_ROSETTA`** (`0x10000000`,
   `bsd/sys/imgact.h`) and, after load, flips **`P_TRANSLATED`** (`0x00020000`,
   `bsd/sys/proc.h`) on the proc: `OSBitOrAtomic(P_TRANSLATED, &p->p_flag)`
   (`kern_exec.c`). The flag is inherited across `fork` (`kern_fork.c`) and reported in
   `proc_info` as `PROC_FLAG_ROSETTA` (`0x2000000`). **[XNU source]**
3. The process's pmap is created with **`PMAP_CREATE_ROSETTA`** (`osfmk/vm/pmap.h`), which
   sets `pmap->is_rosetta = TRUE` (`osfmk/arm64/sptm/pmap/pmap.c`). This flag is what lets
   the VM honour execute permission on translated-process pages (see §2.4) and is propagated
   on `fork` in `vm_map.c`. **[XNU source]**

### 2.2 Loading the x86-64 dyld, then the Rosetta runtime

Inside `parse_machfile()` (`bsd/kern/mach_loader.c`) at depth 1 for the x86-64 main
executable:

4. `load_dylinker()` maps the image's own **x86-64 `dyld`** (from its `LC_LOAD_DYLINKER`).
   Under `CONFIG_ROSETTA`, instead of entering dyld, the kernel stashes an fd and mach-header
   address for it (`result->dynlinker_fd`, `dynlinker_mach_header`) to pass to the runtime
   later. For the x86-64 `LC_UNIXTHREAD`/dyld the kernel notes "Rosetta will parse its load
   commands to get the entry point" and does not use dyld's thread state. **[XNU source:
   mach_loader.c ~line 1700, 3510]**
5. `load_rosetta()` maps the **arm64 Rosetta runtime** from the hard-coded path
   **`/usr/libexec/rosetta/runtime`** (dev/debug builds can substitute
   `/usr/local/libexec/rosetta/runtime_internal` for x86-64 or `…/runtime_arm_internal` for
   arm, selected by `IMGPF_ALT_ROSETTA` or a `PROC_UUID_ALT_ROSETTA_POLICY`). Older XNU
   (`xnu-8792`, Ventura) additionally had an `APPLEVORTEX`-guarded
   `/usr/libexec/rosetta/runtime_t8027` variant. The runtime is loaded just **below the
   shared-cache base** (`SHARED_REGION_BASE_X86_64 = 0x00007FF800000000` for x86-64 targets),
   ASLR-slid, and its entry point becomes the process entry point. **[XNU source:
   mach_loader.c `load_rosetta`, `rosetta_runtime_path`]**, matching Apple's statement that
   the kernel transfers control to the Rosetta runtime "rather than to … `dyld(1)`".
   **[Apple]**
6. The loader reserves a **4 GB gap** (`reserved_aot_size = 0x100000000`) after dyld/main
   "for the worst case static translation size" before placing the user stack. **[XNU
   source: mach_loader.c]**

### 2.3 Handing descriptors to the runtime on the stack

7. Because the runtime must act as loader, `kern_exec.c` opens an fd for the **main x86-64
   binary** and pushes three 8-byte words onto the new user stack: the **dyld fd**, the
   **dyld mach-header address**, and the **main-binary fd** (`thread_adjuserstack(-24)` +
   three `copyoutptr`). Failures raise `EXEC_EXIT_REASON_COPYOUT_ROSETTA`. **[XNU source:
   kern_exec.c ~line 2600]**
8. The thread begins executing at the **arm64 runtime entry**, in a process the kernel marks
   translated. From here the flow is user-space (§3).

### 2.4 Why translated pages may be executable

AOT/JIT output is produced at runtime and must be mapped executable. The runtime maps such
regions with **`MAP_TRANSLATED_ALLOW_EXECUTE`** (`0x20000`, `bsd/sys/mman.h`); `kern_mman.c`
accepts it only if `proc_is_translated(p)` and sets `vmkf_translated_allow_execute`. The VM
entry flag `translated_allow_execute` (`osfmk/mach/vm_statistics.h`) then flows into
`PMAP_OPTIONS_TRANSLATED_ALLOW_EXECUTE` during faults (`osfmk/vm/vm_fault.c`), so the pmap
honours execute on these pages where it otherwise would not. **[XNU source]**

### 2.5 ASCII diagram of the launch flow

```
  user runs an x86-64 Mach-O  (fat slice chosen, or forced via binpref / Finder)
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ XNU image activator  (bsd/kern/kern_exec.c, mach_loader.c)                │
│   • grade_binary(): x86-64 slice OK on arm64 macOS                        │
│   • set IMGPF_ROSETTA → later set P_TRANSLATED on proc                    │
│   • pmap created with PMAP_CREATE_ROSETTA (is_rosetta = TRUE)             │
│   • map x86-64 main executable (depth 1)                                  │
│   • load_dylinker(): map x86-64 dyld; stash its fd + mach-header          │
│   • load_rosetta(): map arm64 /usr/libexec/rosetta/runtime below the      │
│       shared-cache base, ASLR-slid; reserve 4 GB AOT gap                  │
│   • push on user stack: [dyld fd][dyld mach-hdr][main-binary fd]          │
│   • ENTRY POINT = Rosetta runtime (arm64), NOT dyld                       │
└─────────────────────────────────────────────────────────────────────────┘
                 │ thread starts in arm64 runtime
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Rosetta runtime (in-process, arm64)                                      │
│   • fileport_makeport(main-binary fd) ──Mach IPC──►  oahd (daemon)        │
│                                                        │                  │
│                     computes AOT lookup hash (SHA-256);│                  │
│                     looks in /var/db/oah/<hash>/ ;     │                  │
│                     if miss: fork+exec oahd-helper ───►│ translate x86-64 │
│                     (writes *.aot.in_progress → rename)│  → arm64 .aot    │
│                                                        │                  │
│   ◄───── read-only fd to the .aot (from Data Vault) ───┘                  │
│   • mmap AOT segments: __TEXT (r-x), __LINKEDIT (r), RuntimeRoutines      │
│   • map aot_shared_cache for translated system dylibs                     │
│   • begin executing translated arm64 code                                 │
│   • indirect branches / JIT regions: resolve via x86→AOT address tree;    │
│       translate on demand (translate / translate_indirect_branch)         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. AOT: when translation happens, how output is found and linked

### 3.1 When

Apple describes two paths: **AOT** (binaries "read from storage at times the system deems
optimal") and **JIT**. **[Apple]** In practice translation happens **at (or just before)
first launch**, not at install time, for user binaries: `oahd` discovers a cache miss and
runs `oahd-helper` to produce the `.aot` before the process runs its first translated
instruction. **[RE: FFRI part1]** `oahd-helper` writes `name.aot.in_progress` then atomically
renames to `name.aot`, so a concurrent launch never maps a half-written file. **[RE: FFRI]**
For **system** binaries the translation is **deterministic** and their AOT code-directory
hashes are baked into the static trust cache at macOS build time; the products themselves are
reconstituted on demand rather than shipped. **[Apple]**

### 3.2 The AOT lookup hash (cache key)

`oahd` keys the cache on a SHA-256 "AOT lookup hash" computed from the image's **full path,
Mach-O header + load commands, uid, gid, mtime, ctime, crtime, and file size** — **not** the
code section bytes. **[RE: FFRI "Dirty Bin Cache"]** (The precise field set is from
Nakagawa's reverse engineering; treat the exact list as RE, not spec. That the hash derives
from the original image's identity, not the translated output, matches Apple's description.)
**[Apple]**

### 3.3 AOT file format and linking (from reverse engineering)

- An `.aot` file **is a normal arm64 Mach-O** (`file` reports "Mach-O 64-bit executable
  arm64"); standard tools open it. **[RE: FFRI part1]**
- It carries a Rosetta-specific load command **`LC_AOT_METADATA`** (cmd `0xcacaca01`,
  cmdsize 32), holding an offset+length to the original x86-64 image path and the RVA of the
  x86-64 code section. `otool` cannot pretty-print it. **[RE: FFRI part2]**
- The `.aot` contains **translated code only, no original constant data.** References to
  x86-64 globals/constants are left as references into the still-mapped x86-64 image; because
  x86→arm is same-endian, no data rewriting is needed. **[RE: FFRI part1]**
- **Register ABI:** AOT code uses the System V AMD64 ABI with a fixed x86→arm register map
  (RAX↔x0, RCX↔x1, RDX↔x2, RBX↔x3, **RSP↔x4, RBP↔x5**, RSI↔x6, RDI↔x7, R8–R15↔x8–x15,
  XMM0–15↔q0–15). **[RE: FFRI part1]** The kernel encodes three of these offsets it needs for
  stack walking in `osfmk/kern/cambria_layout.h` (`KCAMBRIA_THCTX_LR_OFFSET=8`,
  `RSP_OFFSET=48`, `RBP_OFFSET=56`); the header says Rosetta static-asserts these values,
  i.e. the kernel and runtime share an ABI contract. **[XNU source]**
- **Translated-code layout & mapping:** the entire text segment is translated up front, one
  (or more) arm64 instruction(s) per x86-64 instruction, **preserving code locality** rather
  than translating in execution order. A map from translated arm64 instruction → original
  x86-64 address is kept so that state is canonical at every instruction boundary (needed for
  exceptions, sampling, and debugging); this is what largely prevents inter-instruction
  optimisation. **[RE: Dougall Johnson]** At load the runtime `mmap`s AOT `__TEXT` as r-x and
  `__LINKEDIT` as r, plus a `RuntimeRoutines` region; `ROSETTA_PRINT_SEGMENTS` dumps the map.
  **[RE: FFRI part2]**
- **Lazy binding / fixups:** the AOT reproduces Mach-O lazy binding. A dedicated `__stubs_sh`
  section acts as the AOT's lazy-pointer table; on first call the runtime's
  `resolve_x64_addr` looks the x86-64 target up in a **red-black tree** mapping x86-64
  addresses → translated addresses (`find_translation_in_tree_x86`) and backfills
  `__stubs_sh`. A miss falls through to JIT `translate`. **[RE: FFRI part1]**

### 3.4 The AOT shared cache (system dylibs)

`aot_shared_cache` is the pre-translated analogue of `dyld_shared_cache`, mapped once and
shared. Header magic `"AotCache"` (`0x6568636143746F41`), followed by a metadata segment with
one `CodeFragmentMetadata` per image (offsets/sizes of the x86-64 code, the arm64 code, a
**branch-data** blob and an **instruction map** that relate x86-64 and arm64 addresses),
then the AOT segment (runtime routines + system dylib AOTs), then a code signature. **[RE:
FFRI part2]** So yes — the x86-64 dyld shared cache **is** translated, via this companion
cache, and translated processes re-use it instead of translating libc/Foundation/etc. per
process. XNU's stackshot/kcdata plumbing has matching `kSharedCacheAOT` and
`dyld_aot_cache_uuid_info` (x86 slid base+UUID paired with AOT slid base+UUID) so crash/trace
tools can report both caches. **[XNU source: osfmk/kern/kcdata.h]**

### 3.5 Code signing of AOT output

This is the most robustly documented security property:

- A privileged user-space entity signs each AOT artifact with a **device-specific key held
  by the Secure Enclave**, released only to that entity via a restricted entitlement. The
  AOT's code directory embeds the **original x86-64 image's cdhash**; this signature is the
  **supplemental signature**. At execution the kernel enforces the AOT's own cdhashes
  (rooted in the device key), *not* the x86-64 image's. **[Apple]**
- In XNU this is the **supplemental signature** path: `fcntl(F_ADDFILESUPPL)`
  (`bsd/sys/fcntl.h` = 104) → `ubc_cs_blob_add_supplement()` (`bsd/kern/ubc_subr.c`), which
  checks the supplement's **linkage hash** matches a cdhash attached to the original image and
  rejects it otherwise. The code-signing enums name it explicitly:
  `CS_LINKAGE_APPLICATION_ROSETTA` / `CS_LINKAGE_APPLICATION_ROSETTA_AOT`
  (`osfmk/kern/cs_blobs.h`), and `CS_SUPPORTSLINKAGE`. For translated processes the kernel
  will fall back to the supplemental blob when a file has no normal blob
  (`proc_is_translated(current_proc())` guards in `ubc_subr.c`). **[XNU source]** This
  supplemental-signature mechanism shipped in the **first Big Sur** (verified: `F_ADDFILESUPPL`
  and `CONFIG_SUPPLEMENTAL_SIGNATURES` exist in `xnu-7195`). **[XNU source]**
- If a process queries the kernel for a translated executable's identity/entitlements, it
  gets the **original x86-64 image's** properties back. **[Apple]**
- Rosetta also disables **multi-level code-signing hashing** on Apple silicon because it
  "creates issues" (`ubc_subr.c` comment). **[XNU source]**
- The AOT cache is a **Data Vault**; the Rosetta service mediates access by handing out
  read-only fds, keeping its IPC surface deliberately narrow. **[Apple]**

> Security-research note (kept deliberately high-level): Nakagawa's "Dirty Bin Cache"
> (Black Hat Asia 2023) showed the cache key omitting the code section enabled an
> AOT-cache-collision class of attack ("AOT poisoning"); Apple hardened it (e.g.
> CVE-2022-42789, APFS timestamp fixes in 11.6/12.0.1, Ventura 13). The architectural
> takeaways relevant here are only: (a) the lookup hash is identity-based, not
> content-of-code-based; (b) the supplemental-signature check is the integrity backstop.
> **[RE: FFRI "Dirty Bin Cache"]** Exploit mechanics are out of scope.

---

## 4. The JIT path (dynamically generated / self-modifying x86-64 code)

Apple confirms Rosetta can translate apps that contain JIT compilers (e.g. JS engines), but
not AVX-512 and not VM apps that virtualize x86-64, nor kernel extensions. **[Apple]**

- The same `runtime` that loads AOT output also contains the **JIT translator** (`translate`,
  `translate_indirect_branch`, `decode_opcode`, `decode_operand_*`). When an indirect
  branch/call targets an x86-64 address with no known translation, the runtime translates it
  on the fly and records it in the x86→arm tree, so subsequent hits are a lookup, not a
  retranslation. **[RE: FFRI part1]**, **[RE: Dougall Johnson]**
- AOT is strongly preferred; JIT is used "relatively rarely", which avoids both compile cost
  and i-cache/d-cache pollution at startup. **[RE: Dougall Johnson]**
- **Detection of guest-generated code / W^X:** guest JITs allocate RWX or toggle W/X on their
  code pages; the runtime maps its own executable output with
  `MAP_TRANSLATED_ALLOW_EXECUTE` (§2.4). The VM-tag namespace reserves distinct regions for
  the runtime's working set — `VM_MEMORY_ROSETTA_EXECUTABLE_HEAP` is even labelled
  "Rosetta JIT" in `libsyscall`'s tag table (`VM_MEMORY_ROSETTA` 230 … `_JIT`/executable-heap
  234, plus `_THREAD_CONTEXT` 231, `_INDIRECT_BRANCH_MAP` 232, `_RETURN_STACK` 233,
  `_USER_LDT` 235, `_ARENA` 236). These show up in `vmmap` as "Rosetta JIT", "Rosetta
  IndirectBranch", "Rosetta Return Stack", etc. **[XNU source: osfmk/mach/vm_statistics.h,
  libsyscall/mach/mach_vm.c]**, **[RE: FFRI part1 `vmmap`]**
- **Invalidation of stale translations for self-modifying code** is the known weak spot: the
  .NET runtime found that **Rosetta (in Linux x64 containers) does not detect modification of
  an already-executed code page** when a second virtual mapping is written, so .NET must
  disable its W^X double-mapping there (`DOTNET_EnableWriteXorExecute=0`). This bounds how
  aggressively translations are cached vs. re-checked. **[RE/Community: dotnet/runtime
  PR #102509]** The exact macOS-native (non-Linux) invalidation trigger is **[Open
  question]**.

---

## 5. Runtime/OS interface: syscalls, Mach, signals, threads, debugging

### 5.1 IPC between the process and `oahd`

The runtime passes the x86-64 image fd to `oahd` by wrapping it in a Mach port with
`fileport_makeport`, and receives the AOT fd back with `fileport_makefd`. **[RE: FFRI
part2]**, **[Apple]** (names the "Rosetta system service" IPC query). There is also a
reserved kernel trap namespace for cross-arch use: syscall **38 `sys_crossarch_trap`**
(`bsd/kern/kern_crossarch.c`, `bsd/sys/crossarch.h`, namespace `CROSSARCH_ROSETTA = 0`) — in
the open-source tree it returns `ENOTSUP`, i.e. the hook exists but the payload is not in the
public source. **[XNU source]**

### 5.2 Syscalls and the x86-64 syscall ABI

A translated process issues x86-64 `syscall`/Mach-trap instructions; the runtime's
`runtime_syscall` path (a named section in the `runtime` binary) marshals these to the arm64
kernel ABI. **[RE: ipsw-diffs section names]**, **[Inferred]** from the section layout.
Mach message policy explicitly carves out translated tasks: the kernel keeps an
**`IPC_SPACE_POLICY_TRANSLATED`** bit (`osfmk/ipc/ipc_types.h`) set for translated tasks
(`ipc_policy.c`), and legacy `mach_msg_trap()` is permitted for them (`MACH64_POLICY_
TRANSLATED`) because "those apps likely can't be fixed anymore". Several IPC hardening checks
(e.g. reply-port semantics, exception-port identity protection) are relaxed when
`task_is_translated()`. **[XNU source: osfmk/ipc/ipc_policy.c, osfmk/mach/message.h]**

### 5.3 commpage, CPU timebase, TLS / the `gs` segment

- XNU carries a dedicated **x86-64 commpage** definition for translated processes
  (`osfmk/arm/cpu_x86_64_capabilities.h`): a simulated comm page at the "cast-in-stone"
  x86-64 address `0x7fffffe00000`, version 14, with an x86-style capabilities word that
  includes a bit **`x86_64_kIsTranslated = 0x4000...`** and `x86_64_kFastThreadLocalStorage`.
  The file is explicitly commented "Cambria specific" for the page-shift field. **[XNU
  source]**
- Rosetta tasks are pinned to the **Apple timebase** rather than the ARMv9.4 1 GHz timebase:
  `machine_task.c` computes `uses_1ghz_timebase && !task_is_translated(task)` and
  `osfmk/arm64/pcb.c` notes the context-switch path "implicitly switches x18 regardless"
  for translated tasks and force-preserves x18. So Rosetta reserves **x18** for its own use.
  **[XNU source]**
- **TLS / `gs`:** the reserved VM tag `VM_MEMORY_ROSETTA_USER_LDT` ("Rosetta User LDT") and
  the fast-TLS capability bit indicate the runtime emulates the x86-64 `%gs`-based
  thread-local storage with its own per-thread LDT-like region. Exact mechanism not
  reverse-engineered here. **[XNU source: tag]**, **[Inferred]**

### 5.4 Signals, exceptions, and mapping a fault back to x86-64 state

- To deliver a synchronous fault into the guest, XNU exposes a Rosetta-only MIG routine
  **`thread_raise_exception`** (`osfmk/mach/thread_act.defs`, impl in
  `osfmk/kern/thread_act.c`, both under `CONFIG_ROSETTA`): it is callable only by a
  translated task on itself, and delivers an exception through the host exception ports. This
  lets the runtime surface a translated-code fault as the x86-64 exception the guest handler
  expects. **[XNU source]**
- The kernel knows the **Rosetta thread-context** layout (`cambria_layout.h`, §3.3) and
  includes it in `backtrace.c`, so kernel backtraces/stackshots can walk a translated thread
  and recover x86-64 frame pointers. Stackshots tag translated tasks
  `kTaskExecTranslated`/`kTaskIsTranslated` and carry AOT cache UUIDs. **[XNU source:
  osfmk/kern/backtrace.c, kern_stackshot.c, kcdata.h]**
- A dedicated **`Rosetta Thread Context`** and **`Rosetta Return Stack`** region appear per
  process in `vmmap` (tags 231/233). **[RE: FFRI]**
- `OS_REASON_ROSETTA` (34) exists as a crash/exit reason namespace. **[XNU source:
  bsd/sys/reason.h]**
- `ucontext`/signal-handler register images: a translated process's handler expects an
  x86-64 `mcontext`; reconstructing it from the live arm64 state is the runtime's job (built
  on the instruction→x86-address map that guarantees canonical state at boundaries). Precise
  structure handling not reverse-engineered here. **[RE: Dougall Johnson]** (canonical state),
  **[Inferred]**.

### 5.5 Threads, fork/exec, arch mixing

- **No arch mixing:** the kernel forbids mixing arm64 and x86-64 in one process; Rosetta
  applies to the whole process including dynamically loaded modules. **[Apple]** This is
  enforced structurally because the whole process is a translated pmap with the x86-64
  shared cache mapped.
- `fork` copies `P_TRANSLATED` and the Rosetta pmap flag to the child (§2.1). An `exec` of a
  native arm64 image clears `P_TRANSLATED`. **[XNU source: kern_fork.c, kern_exec.c]**
- **arm64→arm64 "Rosetta":** XNU references an **"ARM2ARM Rosetta"** and an alternate runtime
  (`runtime_arm_internal`), used for internal readiness tooling (e.g. MTE emulation shims),
  not general use. This shows the runtime is arch-parametric, not strictly x86-only. **[XNU
  source: kern_exec.c comment, mach_loader.c]**
- `task_restartable_ranges_register` returns `KERN_RESOURCE_SHORTAGE` for translated tasks —
  a documented workaround for an Obj-C/"Cambria" interaction (rdar noted in source). **[XNU
  source: osfmk/kern/restartable.c]**

### 5.6 Debugging (LLDB) and `ptrace`

- LLDB cannot be the native debugserver for a translated target. Both LLDB and the low-level
  `debugserver` check `P_TRANSLATED` (via `kinfo_proc.kp_proc.p_flag` or
  `sysctl.proc_translated`) and, if set, re-exec the **Rosetta debugserver** at
  `/Library/Apple/usr/libexec/oah/debugserver` with `--native-regs
  --handoff-attach-from-native`. The Rosetta debugserver translates x86-64-level debug
  operations (breakpoints, stepping, register reads) to arm64 underneath, so the x86-64 view
  is transparent to LLDB. **[LLVM source: ProcessGDBRemote.cpp, DNB.cpp]**, **[RE: FFRI
  appendix]**
- Consequence for tooling: launching the x86-64 binary via a small **arm64** `exec` wrapper
  makes LLDB attach with the *native* debugserver and debug at the **arm64 instruction
  level** (seeing the runtime itself). **[RE: FFRI appendix]**
- **DTrace cannot instrument translated processes** ("DTrace cannot instrument translated
  processes"). **[RE: FFRI appendix]**

---

## 6. CPUID / what a translated process sees

A translated process sees a synthetic x86-64 CPU. This changed across Rosetta versions, and
sources genuinely conflict on specifics:

- **Vendor string (CPUID leaf 0):** **older** Rosetta reported `"GenuineIntel"`; **newer**
  Rosetta reports `"VirtualApple"`. Both are documented in a CPUID leaf reference and
  corroborated by multiple projects. **[Community: arch86 CPUID table; dotnet/runtime
  PR #102509; lomp]** One 2023 source still observed `"GenuineIntel"` at that time — hence
  the version split. **[Community: lomp comment]**
- **Brand string (CPUID leaf 0x80000002–4 / `machdep.cpu.brand_string`):**
  `"VirtualApple @ 2.50GHz"`, widely observed (osquery, Go cpuid, Nomad, minikube,
  dotnet). **[Community]** Note `arch -x86_64 sysctl -n machdep.cpu.brand_string` on an M1
  returns `"Apple M1"` (the OID reflects the host, not the CPUID string) — so the
  `VirtualApple…` value specifically comes from the emulated CPUID instruction, and the two
  can disagree. **[Community: Homebrew PR #12417]**
- **`hw.cputype` / `hw.cpufamily` / cpu_subtype:** on Big Sur, a translated process observed
  `hw.cputype = CPU_TYPE_X86 (7)`, `hw.cpufamily = INTEL_WESTMERE`, and tools reported
  cpu_subtype `"Intel 80486"` / type `i486` (the latter is a tool artifact of reading CPUID
  on an emulated CPU). **[Community: Stack Overflow 2020; osquery #7053]** Whether the
  reported family stayed Westmere across later macOS is **not confirmed** here.
- **Feature bits:** SSE/SSE2/SSE3/SSSE3/SSE4.1/SSE4.2/AES/CMPXCHG16B present; **AVX/AVX2
  advertised as translatable by Apple but reported Unsupported by at least one game's CPUID
  probe**; **AVX-512 unsupported** (Apple: check `hw.optional.avx512f`, which is absent).
  **[Apple]**, **[Community: Valve CS:GO issue shows AVX/AVX2 Unsupported]** The AVX/AVX2
  discrepancy (Apple says translated, a CPUID probe says unsupported) is a genuine conflict —
  likely the probe reads the emulated CPUID feature bits while Rosetta still *executes* AVX2;
  **[Inferred]**, flagged as **[Open question]**.
- **RDTSC:** the brand-string frequency is **not** the emulated RDTSC tick rate, so timing
  code must measure rather than parse the brand string. **[Community: lomp]**

---

## 7. Observable artefacts and tools people used

- **Endpoint Security** event monitor (FFRI's `EventMonitor`) to watch `exec`/`fork`/`lookup`/
  `create`/`rename`/`mmap` around `oahd`/`oahd-helper`. **[RE: FFRI]**
- **`vmmap`** shows the mapped x86-64 image, the `.aot`, the `runtime`, the 2+ GB
  `aot_shared_cache`, and the named Rosetta regions (Thread Context, Return Stack, JIT). **[RE:
  FFRI]**
- **Runtime debug env vars** (the runtime sets globals from `ROSETTA_*`): `ROSETTA_PRINT_IR`
  (dumps the translated x86-64 IR/basic blocks to stderr), `ROSETTA_PRINT_SEGMENTS`
  (prints mapping of runtime/AOT/shared-cache), plus `ROSETTA_ALLOW_GUARD_PAGES`,
  `ROSETTA_DISABLE_EXCEPTIONS`, `ROSETTA_AOT_ERRORS_ARE_FATAL`. **[RE: FFRI part2]**
- **`translate_tool`** to translate without executing; **FFRI Ghidra patches** (adds `cfinv`
  to SLEIGH; a custom CSPEC encoding the x86→arm register ABI) and **AotSharedCacheExtractor**
  (parses `aot_shared_cache`). **[RE: FFRI]**
- **`blacktop/ipsw` diffs** track the Rosetta binaries' sections/UUIDs across macOS builds —
  useful to watch `runtime`'s named sections (`runtime_entry`, `runtime_syscall`,
  `runtime_savedreg`, `debug_thread`, `rosetta_version`) evolve. **[RE: blacktop/ipsw-diffs]**
- **XNU open source** (`apple-oss-distributions/xnu`): grep `CONFIG_ROSETTA`, `IMGPF_ROSETTA`,
  `P_TRANSLATED`, `task_is_translated`, `cambria`. **[XNU source]**

---

## 8. Open questions / unconfirmed / conflicting

1. **`runtime` vs `libRosettaRuntime`.** FFRI analyses `runtime` (an executable); sandbox/tool
   detection keys on `libRosettaRuntime`; the installer BOM lists `oah/libRosettaRuntime`;
   Monterey+ also has `oah/runtime` and `/usr/libexec/rosetta/runtime`. The exact relationship
   (same payload under two names? loader vs. mapped-in blob?) is unresolved here. The XNU
   kernel definitively loads `/usr/libexec/rosetta/runtime`. **[XNU source]** vs **[Community]**
2. **Cryptex identity.** That Rosetta ships in the Apple-silicon OS cryptex is inferred from
   CryptexFixup + Oakley; the exact cryptex name, signing/measurement, and update cadence vs.
   RSR were not pinned down.
3. **Path-split timeline.** Big Sur used `/Library/Apple/usr/libexec/oah/`; Monterey added
   `/usr/libexec/rosetta/`. Whether one is a symlink/firmlink to the other, and whether the
   kernel's hard-coded `/usr/libexec/rosetta/runtime` is a firmlink on Big Sur, is unconfirmed.
4. **Self-modifying-code invalidation (native macOS).** Confirmed weak/absent for the Linux
   container double-mapping case (dotnet); the native trigger for invalidating a stale
   translation is not established.
5. **CPUID feature reporting for AVX/AVX2.** Apple says AVX/AVX2 are translated; at least one
   CPUID probe reports them Unsupported. Mechanism/version dependence unresolved.
6. **`hw.cpufamily` over time.** Westmere seen on Big Sur; later-macOS value unverified.
7. **`sys_crossarch_trap` payload.** The public XNU returns `ENOTSUP`; the real translated
   build's behaviour is not in open source.
8. **`oahd-root-helper` exact duties** and the precise `gs`/TLS (User LDT) emulation are
   inferred from tags/names, not reverse-engineered here.
9. **AOT shared cache `.t8027` variant / `APPLEVORTEX` runtime** — the SoC these target and
   why a separate pre-translated cache exists is not pinned down (the empty `aot_shared_cache.t8027`
   FFRI observed suggests a placeholder per SoC family). **[RE: FFRI]**, low confidence.

---

## 9. Sources

**[Apple] — primary**
- Apple Platform Security: "Rosetta 2 on a Mac with Apple silicon" (AOT/JIT paths, supplemental
  signature, Secure Enclave device key, Data Vault, static trust cache, IPC query).
  https://support.apple.com/guide/security/rosetta-2-on-a-mac-with-apple-silicon-secebb113be1/web
- Apple Developer: "About the Rosetta translation environment" (no arch mixing; no AVX-512;
  can't translate kexts / x86-64 VMs; `sysctl.proc_translated`).
  https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment

**[XNU source]** — `apple-oss-distributions/xnu`, tag `xnu-12377.121.6` (cross-checked
`xnu-7195.*`, `8019/8020`, `8792`, `11215`). Repo: https://github.com/apple-oss-distributions/xnu
- `bsd/kern/mach_loader.c` — `load_rosetta`, `rosetta_runtime_path`
  (`/usr/libexec/rosetta/runtime`), `IMGPF_ROSETTA`, 4 GB AOT gap, x86-64 dyld fd handoff.
- `bsd/kern/kern_exec.c` — `P_TRANSLATED` set, stack handoff of dyld/main fds,
  `EXEC_EXIT_REASON_COPYOUT_ROSETTA`, "ARM2ARM Rosetta".
- `bsd/sys/imgact.h` (`IMGPF_ROSETTA` 0x10000000, `IMGPF_ALT_ROSETTA`), `bsd/sys/proc.h`
  (`P_TRANSLATED`), `bsd/kern/kern_proc.c` (`proc_is_translated`), `bsd/kern/kern_sysctl.c`
  (`sysctl.proc_translated`), `bsd/kern/kern_fork.c`, `bsd/sys/proc_info_private.h`
  (`PROC_FLAG_ROSETTA`), `bsd/sys/reason.h` (`OS_REASON_ROSETTA`).
- `bsd/sys/mman.h` + `bsd/kern/kern_mman.c` — `MAP_TRANSLATED_ALLOW_EXECUTE`.
- `osfmk/vm/pmap.h`, `osfmk/arm64/sptm/pmap/pmap.c`, `osfmk/vm/vm_fault.c`,
  `osfmk/vm/vm_map.c` — `PMAP_CREATE_ROSETTA`, `is_rosetta`, `translated_allow_execute`.
- `osfmk/kern/cs_blobs.h`, `bsd/kern/ubc_subr.c`, `bsd/sys/fcntl.h` (`F_ADDFILESUPPL`),
  `bsd/kern/kern_descrip.c` — supplemental signature / linkage hash.
- `osfmk/mach/vm_statistics.h`, `libsyscall/mach/mach_vm.c` — `VM_MEMORY_ROSETTA*` tags.
- `osfmk/kern/cambria_layout.h`, `osfmk/kern/backtrace.c`, `osfmk/kern/kcdata.h`
  (`kSharedCacheAOT`, `dyld_aot_cache_uuid_info`), `osfmk/kern/kern_stackshot.c`.
- `osfmk/mach/thread_act.defs` + `osfmk/kern/thread_act.c` (`thread_raise_exception`),
  `osfmk/ipc/ipc_policy.c`/`ipc_types.h`/`osfmk/mach/message.h` (`IPC_SPACE_POLICY_TRANSLATED`),
  `osfmk/kern/restartable.c`, `osfmk/kern/task.c` (`task_is_translated`),
  `osfmk/arm64/machine_task.c` + `pcb.c` (timebase, x18), `osfmk/arm/cpu_x86_64_capabilities.h`
  (x86-64 commpage, `x86_64_kIsTranslated`), `osfmk/arm64/x86_64_compat.c`,
  `bsd/sys/crossarch.h` + `bsd/kern/kern_crossarch.c`.
- XNU test harness: `tests/posix_spawn_alt_rosetta.c` (references
  `/Library/Apple/usr/libexec/oah/libRosettaRuntime`, `/usr/local/libexec/rosetta/runtime_internal`),
  `tests/nox86exec_helper.c`, `tests/cpucount.c`, `tests/iokit/rosetta_map_mmio.c`.

**[RE: Koh M. Nakagawa / FFRI — "Project Champollion"]** (named, primary RE)
- Part 1 (AOT files, register ABI, `runtime`, lazy binding, JIT decode): https://ffri.github.io/ProjectChampollion/part1/
- Part 2 (`oahd` IPC via `fileport_make{port,fd}`, `LC_AOT_METADATA` = 0xcacaca01, debug env
  vars, `aot_shared_cache` format): https://ffri.github.io/ProjectChampollion/part2/
- Appendix (arm64-level debugging via wrapper, oah `debugserver`, Ghidra `cfinv`/CSPEC):
  https://ffri.github.io/ProjectChampollion/appendix/
- Repo + tools: https://github.com/FFRI/ProjectChampollion
- "Dirty Bin Cache" (Black Hat Asia 2023) — AOT lookup-hash fields, `translate_tool`,
  components list, supplemental-signature backstop:
  https://www.ffri.jp/assets/files/research/research_papers/AS-23-Koh-Dirty-Bin-Cache-A-New-Code-Injection-Poisoning-Binary-Translation-Cache.pdf

**[RE: Dougall Johnson]** — "Why is Rosetta 2 fast?" (whole-text up-front AOT, 1:N mapping,
canonical state / instruction map, inter-instruction optimisations, flag/TSO/hardware
context): https://dougallj.wordpress.com/2022/11/09/why-is-rosetta-2-fast/

**[RE: Howard Oakley / Eclectic Light]** — OAH naming, Data-volume/on-demand install,
`com.apple.oahd.plist`, `/usr/share/rosetta`, RosettaLinux:
- https://eclecticlight.co/2021/01/22/running-intel-code-on-your-m1-mac-rosetta-2-and-oah/
- https://eclecticlight.co/2022/12/10/explainer-rosetta-2/

**[RE: Acidanthera CryptexFixup]** — Rosetta in the Apple-silicon OS cryptex; retained
pre-AVX2 x86-64 shared cache: https://github.com/acidanthera/CryptexFixup

**[LLVM source]** — Rosetta `debugserver` selection by `P_TRANSLATED`/`sysctl.proc_translated`:
`lldb/source/Plugins/Process/gdb-remote/ProcessGDBRemote.cpp`,
`lldb/tools/debugserver/source/DNB.cpp` (https://github.com/llvm/llvm-project).

**[Community]** (lower confidence, cited inline)
- CPUID vendor/brand string: arch86 CPUID leaf table (GenuineIntel→VirtualApple split);
  dotnet/runtime PR #102509 (VirtualApple brand, W^X in Rosetta Linux containers);
  parallel-runtimes/lomp `src/stats-timing.cc` (GenuineIntel observation, RDTSC caveat);
  osquery #7053 / Stack Overflow 65346260 (hw.cputype=7/Westmere, i486 subtype); Valve CS:GO
  issue #3114 (AVX/AVX2 "Unsupported").
- Component paths / install: Apple SE 406787 (oahd-helper path move Big Sur→Monterey),
  Apple SE 427970 (`RosettaUpdateAuto` BOM; `libRosettaRuntime` detection; `pgrep oahd`),
  Homebrew `extend/os/mac/hardware/cpu.rb` + PR #12417 (`ROSETTA_RUNTIME_PATH`,
  brand_string reflects host not CPUID), NixOS/nix PR #16067 + `sandbox-defaults.sb`
  (`libRosettaRuntime` existence test; `com.apple.oahd.plist` sandbox paths).
- `blacktop/ipsw-diffs` macOS trees — Rosetta binary section/symbol inventories
  (`/usr/libexec/rosetta/{oahd,oahd-helper,oahd-root-helper,runtime,translate_tool,debugserver}`).
