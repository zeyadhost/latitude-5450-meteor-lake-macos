# Rosetta 2: what Apple itself has said officially

Part of the Rosetta 2 research set in `docs/rosetta2/`. This file covers **only Apple's own public statements**. These include WWDC sessions, developer.apple.com documentation (articles, API reference, release notes, technotes, developer news), Apple Support articles (including the Apple Platform Security and Platform Deployment guides), Apple Newsroom, Apple-published open source, and Apple man pages. Other topics are covered in sibling documents in this folder: architecture and runtime ([02](02-architecture-and-runtime.md)), translation techniques ([03](03-translation-techniques.md)), hardware assists ([04](04-hardware-assists.md)), Rosetta for Linux ([05](05-rosetta-for-linux.md)), history ([06](06-history-and-timeline.md)) and performance ([07](07-performance.md)). Places where this file touches those topics are marked **→ cross-ref**.

*Performance claims are summarized in §7.7; the measured picture is in [07-performance.md](07-performance.md). History before 2020 is in [06-history-and-timeline.md](06-history-and-timeline.md).*

*Research snapshot: 2026-10-31. At that date the shipping releases were macOS Tahoe 26.x and macOS 27 "Golden Gate" (27.2). All URLs were fetched on or shortly before that date. Wayback Machine captures were used to rebuild document history.*

---

## 0. How to read this document

### 0.1 Provenance labels

| Label | Meaning |
|---|---|
| **[Apple doc]** | developer.apple.com documentation, including API reference, release notes and technotes |
| **[WWDC]** | A WWDC session or other Apple developer video. The timestamp is given as `mm:ss` or `h:mm:ss`, and links use the site's `?time=<seconds>` deep link. For the WWDC20 Keynote and WWDC20 Platforms State of the Union, the developer site has no on-page transcript, so those timestamps come from Apple's own English closed-caption track in the same video stream. |
| **[Apple support]** | support.apple.com: support articles, *Apple Platform Security*, *Apple Platform Deployment* |
| **[Apple newsroom]** | apple.com/newsroom press releases |
| **[Apple dev news]** | developer.apple.com/news posts |
| **[Apple OSS]** | Source code Apple publishes: `apple-oss-distributions/*`, `github.com/apple/*`. LLDB code in `llvm/llvm-project` is marked separately as *(LLVM, largely Apple-maintained)*. |
| **[Apple man page]** | macOS manual pages. Where a page is not in Apple's open source, it was read through the `keith.github.io/xcode-man-pages` mirror, and the citation says so. |
| **[Apple forums]** | A reply by an Apple employee on developer.apple.com/forums. These come from Apple staff but are informal, not documentation. |
| **[third-party]** | Not from Apple. Used only where it is the only available copy of Apple text, or for context, and always flagged. |

### 0.2 Jargon used below

- **Slice / universal binary / fat binary**: a Mach-O file (Apple's executable format) can hold several architecture-specific "slices", for example `x86_64` and `arm64`. A file that holds more than one is called *universal* (or *fat*).
- **AOT (ahead-of-time) translation**: translating x86-64 machine code to ARM64 before the code runs, and storing the result.
- **JIT (just-in-time) translation**: translating code while the program runs, on first execution. A *JIT compiler* inside an app (a JavaScript engine, for example) is a different thing: it generates new machine code at runtime, and Rosetta then has to translate that code too.
- **dyld**: the macOS dynamic linker/loader.
- **kext**: kernel extension, code loaded into the kernel. **DriverKit extension (dext)**: a user-space driver.
- **TSO (total store ordering)**: the strong memory-ordering model of x86. ARM64 is weakly ordered by default.
- **CDHash / code directory**: the hash structure that macOS code signing uses to identify and verify a binary. A **trust cache** is a list of CDHashes that the OS trusts by default.
- **Data Vault**: a directory protected by the OS so that only specifically entitled processes can access it.
- **Hardened Runtime**: an opt-in macOS security mode. **MAP_JIT**: an `mmap` flag for regions that hold JIT-generated code. **W^X**: "write xor execute", meaning a page is never writable and executable at the same time.
- **XPC**: Apple's inter-process communication and service framework.
- **DTK**: the Developer Transition Kit, the A12Z-based Mac mini that Apple lent to developers in 2020.
- **binfmt_misc / `update-binfmts`**: the Linux mechanism that maps executable formats to an interpreter program.

---

## 1. Key facts at a glance

1. Apple's core model is **whole-process translation**. A process is either entirely native `arm64` or entirely translated `x86_64`. Mixing the two in one process is not allowed, and plug-ins must match the host's architecture unless they run in a separate process. ([Apple doc: About the Rosetta translation environment](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment); [WWDC20-10214 @04:41](https://developer.apple.com/videos/play/wwdc2020/10214/?time=281))
2. **Hybrid AOT + JIT.** Apps installed from the App Store or from `.pkg` installers are translated in the background at install time. Other apps are translated on first launch. Code generated or loaded at runtime is translated "on the fly". ([WWDC20 State of the Union @0:24:15–0:24:42](https://developer.apple.com/videos/play/wwdc2020/102/?time=1455); [WWDC20 Keynote @1:39:37](https://developer.apple.com/videos/play/wwdc2020/101/?time=5977); [WWDC20-10686 @12:08–13:08](https://developer.apple.com/videos/play/wwdc2020/10686/?time=728))
3. The most detailed official description of the mechanism is in **Apple Platform Security**, on a page dated February 18, 2021. It describes two pipelines, JIT (inside the process, with per-page code-hash checks) and AOT (a privileged Rosetta service, artifacts signed with a device-specific key that the Secure Enclave manages, stored in a Data Vault). The AOT translation is **deterministic**, and the static trust cache records the CDHash of the AOT translation of every system binary. ([Apple support: Rosetta 2 on a Mac with Apple silicon](https://support.apple.com/guide/security/rosetta-2-on-a-mac-with-apple-silicon-secebb113be1/web))
4. **Fidelity guarantee.** Page size, memory ordering, `mach_absolute_time` frequency and floating-point details all differ on Apple silicon, but for translated processes Apple "made sure that everything matches behavior on an Intel-based Mac". Apple explicitly states that translated processes get **4 KB pages** and **Intel memory ordering**. ([WWDC20-10686 @13:37–13:56](https://developer.apple.com/videos/play/wwdc2020/10686/?time=817); [WWDC20-10214 @09:26](https://developer.apple.com/videos/play/wwdc2020/10214/?time=566), [@38:43](https://developer.apple.com/videos/play/wwdc2020/10214/?time=2323))
5. Apple's only official naming of the hardware memory-model switch is in a Linux context. The Virtualization documentation describes an `ACTLR.TSOEN` bit that switches an Apple-silicon CPU into the x86-64 TSO memory model, and ships a Linux kernel patch plus a `prctl(PR_SET_MEM_MODEL, PR_SET_MEM_MODEL_TSO)` interface so that Rosetta in Linux VMs can use it. ([Apple doc: Accelerating the performance of Rosetta](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta)) **→ cross-ref [04-hardware-assists.md](04-hardware-assists.md).**
6. **The documented limitation list barely changed for five years.** Rosetta cannot translate kernel extensions, or virtual-machine apps that virtualize x86-64 platforms. Until autumn 2025 the documentation also said that AVX, AVX2 and AVX-512 were not supported. Between 18 September and 28 October 2025 that changed to "AVX and AVX2 translated; AVX-512 not". ([Apple doc, current](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment); Wayback captures [2025-09-18](https://web.archive.org/web/20250918164601/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json) vs [2025-10-28](https://web.archive.org/web/20251028174555/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json))
7. The documented way to detect translation is `sysctlbyname("sysctl.proc_translated")`, which returns 1 for a translated process, 0 for a native one, and `ENOENT` where the sysctl does not exist. In XNU's open source it is backed by a `P_TRANSLATED` process flag that is also visible in `kinfo_proc`. The documented ways to control the architecture are the Info.plist keys `LSRequiresNativeExecution` and `LSArchitecturePriority`, the Finder "Open using Rosetta" option, `arch(1)`, `posix_spawnattr_setarchpref_np(3)` and `NSWorkspace.OpenConfiguration.architecture`. ([Apple doc](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment); [Apple OSS: xnu `kern_sysctl.c`](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_sysctl.c))
8. **End-of-life is now written down.** macOS Tahoe 26 was the last release for Intel Macs. Rosetta stays a general-purpose tool "through macOS 27". From macOS 28, only "a subset of Rosetta functionality" is kept, for "older unmaintained gaming titles", plus Intel binaries in Linux VMs. macOS 26.4 added warning notifications, and macOS 27 lists Intel apps in Settings and flags them in Get Info. ([WWDC25 State of the Union @54:52](https://developer.apple.com/videos/play/wwdc2025/102/?time=3292); [Apple doc](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment); [macOS 26.4 release notes](https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes); [macOS 27 release notes](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes))
9. **macOS 27 changes the plumbing.** For Linux VMs and containers, Intel-binary translation is "directly integrated" and no longer needs a Rosetta install. A beta-only `game-test-tool` enables "legacy Intel-based games" through a "new underlying system behavior" that *disables Rosetta*. For apps, a `nox86exec=1` boot-arg (macOS 26 and later) makes any would-be-translated process crash at launch. ([Apple doc: Running Intel Binaries in Linux VMs](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms); [macOS 27 release notes](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes); [macOS 26 release notes](https://developer.apple.com/documentation/macos-release-notes/macos-26-release-notes))
10. Apple has **contradicted itself** on the end date. A developer news post on 9 September 2026 says "macOS 26 is the final release supporting Intel Mac computers and Rosetta". Every other Apple source says Rosetta remains through macOS 27. See §9.

---

## 2. Timeline of Apple's official statements

| Date | Source | What Apple said or changed |
|---|---|---|
| 2020-06-22 | WWDC20 Keynote, Platforms State of the Union, Newsroom | Rosetta 2 announced. It translates at install time and translates JIT code on the fly; the company calls it a "transitional technology". [WWDC Keynote @1:39:21](https://developer.apple.com/videos/play/wwdc2020/101/?time=5961), [WWDC State of the Union @0:23:35](https://developer.apple.com/videos/play/wwdc2020/102/?time=1415), [Apple newsroom](https://www.apple.com/newsroom/2020/06/apple-announces-mac-transition-to-apple-silicon/) |
| 2020-06 | WWDC20 sessions 10214, 10686, 10631, 10632 | Developer-level details: whole-process translation, no kexts, no AVX, no virtualization, 4 KB pages, Intel memory ordering, Metal consistency workarounds. (Links in §3.1.) |
| by 2020-06-22 | Apple doc *About the Rosetta Translation Environment* | The URL was captured by the Wayback Machine on that day. The earliest archived content (Nov 2020) holds the limitation list that lasted until 2025. [Wayback 2020-11-01](https://web.archive.org/web/20201101145333/https://developer.apple.com/tutorials/data/documentation/apple_silicon/about_the_rosetta_translation_environment.json) |
| 2020-08 to 10 | DTK ("Universal Apps") release notes | FairPlay unavailable on the DTK, including via Rosetta 2. Workarounds tell users to enable "Open using Rosetta" for AddPrinter and Terminal. The new arm64 mandatory-signing rule does not apply to translated x86 binaries. [Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-big-sur-11_0_1-universal-apps-release-notes); [Wayback beta 5 notes](https://web.archive.org/web/20200828035411/https://developer.apple.com/tutorials/data/documentation/macos-release-notes/macos-big-sur-11-universal-apps-beta-release-notes.json) |
| 2020-11-10/12 | Newsroom (M1, Big Sur) | Intel apps "run seamlessly" with Rosetta 2. Some graphically demanding apps run better under Rosetta 2 than they did natively on older Macs with integrated graphics. [Apple newsroom](https://www.apple.com/newsroom/2020/11/macos-big-sur-is-here/) |
| 2020-11-17 | Support HT211861 (now 102527) | Rosetta is installed on demand. "In most cases, you won't notice any difference in the performance". [Wayback](https://web.archive.org/web/20201117204544/https://support.apple.com/en-us/HT211861) |
| 2021-02-18 | Apple Platform Security | JIT and AOT pipelines, Secure-Enclave-rooted signing, Data Vault cache, deterministic AOT, unsigned x86_64 allowed. [Apple support](https://support.apple.com/guide/security/rosetta-2-on-a-mac-with-apple-silicon-secebb113be1/web) |
| 2022-02-22 → 2023-04-11 | TN3117 | "Don't launch Xcode using Rosetta" to fix build errors. Xcode 14.3 adds the "Show Rosetta Destinations" menu. [Apple doc](https://developer.apple.com/documentation/technotes/tn3117-resolving-build-errors-for-apple-silicon) |
| 2022-06 | WWDC22-10002; Virtualization docs (macOS 13) | Rosetta 2 for x86-64 Linux binaries inside ARM Linux VMs. [WWDC @20:12](https://developer.apple.com/videos/play/wwdc2022/10002/?time=1212); [Wayback 2022-06-06](https://web.archive.org/web/20220606193608/https://developer.apple.com/documentation/virtualization/running_intel_binaries_in_linux_vms_with_rosetta) |
| 2023-04 | Xcode 14.3 release notes | "Xcode isn't supported under Rosetta." [Apple doc](https://developer.apple.com/documentation/xcode-release-notes/xcode-14_3-release-notes) |
| 2023-06 | WWDC23 (macOS 14) | Linux-VM Rosetta gains an AOT cache served by a daemon. The Game Porting Toolkit (GPT) arrives; its evaluation environment translates Intel instructions and Windows APIs. [WWDC23-10007 @12:00](https://developer.apple.com/videos/play/wwdc2023/10007/?time=720); [WWDC23-10123 @03:06](https://developer.apple.com/videos/play/wwdc2023/10123/?time=186) |
| 2024-06 | WWDC24 (macOS 15) | GPT 2 can evaluate Windows games that use AVX and AVX2. [WWDC24 State of the Union @54:19](https://developer.apple.com/videos/play/wwdc2024/102/?time=3259); [WWDC24-10089 @02:33](https://developer.apple.com/videos/play/wwdc2024/10089/?time=153) |
| by 2025-01-18 | Virtualization doc | *Accelerating the performance of Rosetta*: the `ACTLR.TSOEN` TSO bit, a Linux 6.10 patch, and `prctl`. [Wayback](https://web.archive.org/web/20250118101055/https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta) |
| 2025-06-09 | WWDC25 State of the Union; Apple doc | On stage: "macOS Tahoe will be the final release for Intel Macs" (Rosetta was not named). In the documentation, added on 9–11 June: Rosetta remains through macOS 27, then only a games subset. [WWDC @54:52](https://developer.apple.com/videos/play/wwdc2025/102/?time=3292); [Wayback 2025-06-11](https://web.archive.org/web/20250611040604/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json) |
| 2025-09 | macOS 26 release notes | New `nox86exec=1` boot-arg to test independence from Rosetta. [Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-26-release-notes) |
| 2025-09/10 | Apple doc | The ISA statement becomes "AVX and AVX2 translated, AVX-512 not". (Wayback links in §1, item 6.) |
| 2026 (26.4) | macOS 26.4 release notes; enterprise notes; Deployment guide | User notifications when Rosetta apps launch; MDM key `allowRosettaUsageAwareness`; "Rosetta support for apps will end after macOS 27". [Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes); [Apple support](https://support.apple.com/en-us/124963) |
| 2026-02-16 | Support 102527 | Retitled "Using Intel-based apps on a Mac with Apple silicon". Rosetta remains "through the forthcoming macOS 27". [Wayback 2026-06-11](https://web.archive.org/web/20260611164206/https://support.apple.com/en-us/102527) |
| 2026-06 | WWDC26 State of the Union; macOS 27 and Xcode 27 release notes; Virtualization doc | "The transition of macOS to Apple silicon is now complete". Apple-silicon-only binaries are allowed on the Mac App Store. Rosetta is not restored on upgrade, "Open using Rosetta" flags are reset, `game-test-tool` appears, installers default to arm64, `ARCHS_STANDARD` drops x86_64 for a macOS 27 deployment target, and Linux Intel translation is integrated into macOS. [WWDC @40:36](https://developer.apple.com/videos/play/wwdc2026/102/?time=2436); [Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes) |
| 2026-06 | Apple forums | An Apple engineer: "x86_64 macOS games should continue to work as they do on macOS 26." [Apple forums](https://developer.apple.com/forums/thread/830692) |
| 2026-09-01 | Apple dev news | "macOS 27: Final release to support Rosetta"; Intel-only apps stop running after it, except older unmaintained games. [Apple dev news](https://developer.apple.com/news/?id=w5ngl9k2) |
| 2026-09-09 | Apple dev news | Conflicting line: "macOS 26 is the final release supporting Intel Mac computers and Rosetta". [Apple dev news](https://developer.apple.com/news/?id=k1mtkt1k) |
| 2026-09-21 | Support 102527 | Adds the macOS 27 Settings list of Intel-based apps and `softwareupdate --install-rosetta`. [Apple support](https://support.apple.com/en-us/102527) |
| 2026-10-26 | macOS 27.2 enterprise notes | "Rosetta is no longer removed when upgrading to macOS 27." [Apple support](https://support.apple.com/en-us/148830) |

---

## 3. Inventory of Apple sources that discuss Rosetta

### 3.1 WWDC and other Apple videos

The author bulk-scanned the transcripts of every WWDC20–WWDC26, Tech Talk and Meet-with-Apple video listed on developer.apple.com (1,603 pages) for "Rosetta", "x86", "Intel", "AVX", "translated" and "Game Porting Toolkit". The table lists every session that discusses Rosetta or x86 translation.

Some pages have no on-page transcript: Q&A and lounge pages, the WWDC20, WWDC21 and WWDC25 keynotes, and the WWDC20 State of the Union. Three of those were read from Apple's own caption tracks instead: the WWDC20 Keynote, the WWDC20 State of the Union and the WWDC25 Keynote. The WWDC25 Keynote never mentions Intel or Rosetta. The WWDC21 Keynote was **not** checked.

| Session | Rosetta content | Key timestamps |
|---|---|---|
| WWDC20 Keynote (101) | Rosetta 2 introduced: install-time translation, on-the-fly translation for JIT/Java, pro apps and plug-ins; Maya and *Shadow of the Tomb Raider* demos | [1:39:21](https://developer.apple.com/videos/play/wwdc2020/101/?time=5961), [1:39:37](https://developer.apple.com/videos/play/wwdc2020/101/?time=5977), [1:39:43](https://developer.apple.com/videos/play/wwdc2020/101/?time=5983), [1:41:03](https://developer.apple.com/videos/play/wwdc2020/101/?time=6063) |
| WWDC20 Platforms State of the Union (102) | Most technical on-stage description: AOT, JIT, syscalls, signed machine-bound caches, emulated frameworks in-process, file-backed cache, extensions and Audio Units out of process, kexts | [0:23:35–0:29:20](https://developer.apple.com/videos/play/wwdc2020/102/?time=1415) |
| WWDC20-10686 *Explore the new system architecture of Apple silicon Macs* | Rosetta overview, install-time translation, signed per-machine translations, JIT, hardened runtime, behaviour differences, AVX, `sysctl.proc_translated` | [11:31–14:42](https://developer.apple.com/videos/play/wwdc2020/10686/?time=691) |
| WWDC20-10214 *Port your Mac app to Apple silicon* | Whole-process rule, limits, Xcode "My Mac (Rosetta)", 4 KB pages, `mach_absolute_time`, tests under Rosetta, benchmark, plug-ins, "Open using Rosetta", crash logs, memory ordering | [04:31](https://developer.apple.com/videos/play/wwdc2020/10214/?time=271), [09:26](https://developer.apple.com/videos/play/wwdc2020/10214/?time=566), [23:39](https://developer.apple.com/videos/play/wwdc2020/10214/?time=1419), [31:25](https://developer.apple.com/videos/play/wwdc2020/10214/?time=1885), [38:43](https://developer.apple.com/videos/play/wwdc2020/10214/?time=2323) |
| WWDC20-10631 *Bring your Metal app to Apple silicon Macs* | Unmodified x86 games and pro apps under Rosetta; automatic Metal "consistency features" under translation, with a performance cost | [01:01](https://developer.apple.com/videos/play/wwdc2020/10631/?time=61), [02:53](https://developer.apple.com/videos/play/wwdc2020/10631/?time=173), [32:44](https://developer.apple.com/videos/play/wwdc2020/10631/?time=1964) |
| WWDC20-10632 *Optimize Metal Performance for Apple silicon Macs* | Same translation and consistency framing | [00:57](https://developer.apple.com/videos/play/wwdc2020/10632/?time=57) |
| WWDC22-10002 *Create macOS or Linux virtual machines* | Rosetta 2 inside ARM Linux VMs; `VZLinuxRosettaDirectoryShare`; `update-binfmts` | [15:37](https://developer.apple.com/videos/play/wwdc2022/10002/?time=937), [20:12–22:00](https://developer.apple.com/videos/play/wwdc2022/10002/?time=1212) |
| WWDC22-10141 *Explore USD tools and rendering* | Practical use of `arch` to run a tool under Rosetta | [17:34](https://developer.apple.com/videos/play/wwdc2022/10141/?time=1054) |
| WWDC23-10007 *Create seamless experiences with Virtualization* | Linux Rosetta translates pages on demand; AOT cache with a runtime daemon (macOS 14) | [12:00–14:31](https://developer.apple.com/videos/play/wwdc2023/10007/?time=720) |
| WWDC23-10123 *Bring your game to Mac, Part 1* (and Keynote 101 @49:02, State of the Union 102 @27:53) | GPT evaluation environment "translates your game's Intel instructions" and Windows APIs; translation overhead | [03:06](https://developer.apple.com/videos/play/wwdc2023/10123/?time=186), [05:05](https://developer.apple.com/videos/play/wwdc2023/10123/?time=305) |
| WWDC24 State of the Union (102); WWDC24-10089 *Port advanced games to Apple platforms* | GPT 2 evaluates games that use AVX and AVX2 | [54:19](https://developer.apple.com/videos/play/wwdc2024/102/?time=3259); [02:33](https://developer.apple.com/videos/play/wwdc2024/10089/?time=153) |
| WWDC25 State of the Union (102) | "macOS Tahoe will be the final release for Intel Macs" (Rosetta not named) | [54:52](https://developer.apple.com/videos/play/wwdc2025/102/?time=3292) |
| WWDC25-247 *What's new in Xcode 26* | "Simulator runtimes no longer contain Intel support by default" | [01:04](https://developer.apple.com/videos/play/wwdc2025/247/?time=64) |
| WWDC25-209 *Level up your games*; Meet with Apple 239 and 241 | GPT 3; the evaluation environment runs the x86 Windows binary "as is" through an emulation layer | [17:21](https://developer.apple.com/videos/play/wwdc2025/209/?time=1041); [239 @10:30](https://developer.apple.com/videos/play/meet-with-apple/239/?time=630); [241 @02:35](https://developer.apple.com/videos/play/meet-with-apple/241/?time=155) |
| WWDC26 State of the Union (102) | "macOS Tahoe was the final release to support Intel Macs"; transition complete; Apple-silicon-only binaries allowed on the Mac App Store | [40:32–41:01](https://developer.apple.com/videos/play/wwdc2026/102/?time=2432) |
| WWDC26-356 *Bringing Cyberpunk 2077 to Mac*; WWDC26-357 (GPT 4) | GPT evaluation of the Windows build "in a translated environment" | [356 @04:45](https://developer.apple.com/videos/play/wwdc2026/356/?time=285); [357 @00:48](https://developer.apple.com/videos/play/wwdc2026/357/?time=48) |

Sessions the author checked that do **not** mention Rosetta by name:

- WWDC20 *iPad and iPhone apps on Apple silicon Macs* (10114)
- every WWDC21 session that has a transcript, including the WWDC21 State of the Union
- the WWDC22 State of the Union
- the WWDC23 State of the Union, which mentions only the GPT
- the WWDC25 Keynote
- WWDC25-346 *Meet Containerization*

### 3.2 developer.apple.com documentation

| Document | Rosetta-relevant content |
|---|---|
| [About the Rosetta translation environment](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment) | The canonical page: transparency, Get Info option, no mixing, what can't be translated, AVX, `sysctl.proc_translated`, lifetime box. History in §5.1. |
| [Porting your macOS apps to Apple silicon](https://developer.apple.com/documentation/apple-silicon/porting-your-macos-apps-to-apple-silicon) | In-process plug-ins must match; XPC per architecture; kexts never run under Rosetta; OpenCL CPU device not available to arm64 apps; Xcode 27 note |
| [Building a universal macOS binary](https://developer.apple.com/documentation/apple-silicon/building-a-universal-macos-binary) | Native is more efficient; debug the x86_64 slice under Rosetta; `LSRequiresNativeExecution` and `LSArchitecturePriority`; script-only apps run under Rosetta |
| [Addressing architectural differences in your macOS code](https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code) | `mach_absolute_time` differs for native vs translated; page size, cache line and `hw.optional.*` fetched dynamically; memory ordering |
| [Porting just-in-time compilers to Apple silicon](https://developer.apple.com/documentation/apple-silicon/porting-just-in-time-compilers-to-apple-silicon) | MAP_JIT and per-thread W^X on Apple silicon (native rules; does not discuss Rosetta) |
| [Porting your Metal code to Apple silicon](https://developer.apple.com/documentation/apple-silicon/porting-your-metal-code-to-apple-silicon) | Metal behavioural workarounds for translated apps linked against the macOS 10.15 SDK or earlier |
| [Porting your audio code to Apple silicon](https://developer.apple.com/documentation/apple-silicon/porting-your-audio-code-to-apple-silicon) | Universal Audio Units can be loaded in-process or out-of-process |
| [LSRequiresNativeExecution](https://developer.apple.com/documentation/bundleresources/information-property-list/lsrequiresnativeexecution), [LSArchitecturePriority](https://developer.apple.com/documentation/bundleresources/information-property-list/lsarchitecturepriority) | Info.plist launch-architecture controls |
| [NSWorkspace.OpenConfiguration.architecture](https://developer.apple.com/documentation/appkit/nsworkspace/openconfiguration/architecture), [NSRunningApplication.executableArchitecture](https://developer.apple.com/documentation/appkit/nsrunningapplication/executablearchitecture), [Bundle.executableArchitectures](https://developer.apple.com/documentation/foundation/bundle/executablearchitectures) | APIs to force, query and list architectures |
| [Examining the fields in a crash report](https://developer.apple.com/documentation/xcode/examining-the-fields-in-a-crash-report), [Interpreting the JSON format of a crash report](https://developer.apple.com/documentation/xcode/interpreting-the-json-format-of-a-crash-report) | `Code Type … (Translated)` and the JSON field `translated` |
| [TN3117](https://developer.apple.com/documentation/technotes/tn3117-resolving-build-errors-for-apple-silicon), [Downloading and installing additional Xcode components](https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components) | Rosetta run destinations; universal vs Apple-silicon simulator runtime variants |
| Virtualization: [Running Intel Binaries in Linux VMs](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms), [Accelerating the performance of Rosetta](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta), [VZLinuxRosettaDirectoryShare](https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare) and the related caching and availability types | Rosetta for Linux guests (§7.5) |
| Release notes (macOS 11, 14, 15, 26, 26.4, 26.6, 27; Xcode 12.3, 13, 13.3, 14, 14.3, 16, 26.4, 27) | §5.3 |

### 3.3 Other Apple publications

- **Apple Support**
  - [102527 *Using Intel-based apps on a Mac with Apple silicon*](https://support.apple.com/en-us/102527), formerly HT211861
  - [Platform Security: Rosetta 2](https://support.apple.com/guide/security/rosetta-2-on-a-mac-with-apple-silicon-secebb113be1/web)
  - [Platform Security: Data Protection classes](https://support.apple.com/guide/security/data-protection-classes-secb010e978a/web): per-extent keys "available to both Rosetta 2 and native apps"
  - [Deployment: device management restrictions](https://support.apple.com/guide/deployment/review-device-management-restrictions-dep739685973/web)
  - Enterprise notes for [macOS 26](https://support.apple.com/en-us/124963) and [macOS 27](https://support.apple.com/en-us/148830)
  - Logic Pro and Final Cut Pro: [102082](https://support.apple.com/en-us/102082) and [121464](https://support.apple.com/en-us/121464)
- **Apple Newsroom**
  - [2020-06-22 transition announcement](https://www.apple.com/newsroom/2020/06/apple-announces-mac-transition-to-apple-silicon/)
  - [2020-11-10 M1](https://www.apple.com/newsroom/2020/11/apple-unleashes-m1/)
  - [2020-11-12 Big Sur](https://www.apple.com/newsroom/2020/11/macos-big-sur-is-here/)
- **Apple Developer News**: [2026-09-01](https://developer.apple.com/news/?id=w5ngl9k2), [2026-09-09](https://developer.apple.com/news/?id=k1mtkt1k).
- **Apple open source and man pages** (§4.9, §6)
  - XNU (`kern_sysctl.c`, `kern_exec.c`, `mach_loader.c`, `sys/proc.h`, `cpu_x86_64_capabilities.h`, `posix_spawnattr_setarchpref_np.3`)
  - dyld (`mach-o/dyld_images.h`)
  - system_cmds (`arch.1`, `arch.c`)
  - libpthread (`pthread_jit_write_protect_np.3`)
  - `apple/device-management`, `apple/containerization`, `apple/container`, `apple/homebrew-apple`
  - LLDB (`DNB.cpp`, `TestRosetta.py`, `crashlog.py`)
  - Man pages read via the mirror: `softwareupdate(8)`, `productbuild(1)`

---

## 4. What Apple says about how Rosetta works

### 4.1 Unit of translation: the whole process

- A process is translated as a whole, including every code module it loads dynamically. "The system prevents you from mixing `arm64` code and `x86_64` code in the same process." **[Apple doc]** ([About](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment)) In the session's words, native code cannot be loaded into a translated process, "or vice versa". **[WWDC]** ([10214 @04:41–04:52](https://developer.apple.com/videos/play/wwdc2020/10214/?time=281))
- "Everything in the process is translated, including all system frameworks." **[WWDC]** ([10686 @12:58](https://developer.apple.com/videos/play/wwdc2020/10686/?time=778)) The State of the Union demo describes "an emulated version of all the macOS frameworks running alongside the emulation of the apps in the same process". **[WWDC]** ([State of the Union @0:26:24](https://developer.apple.com/videos/play/wwdc2020/102/?time=1584))
- Rosetta "fully emulates a x86_64 process, right down to the system call interface". **[WWDC]** ([10686 @12:51](https://developer.apple.com/videos/play/wwdc2020/10686/?time=771)) When a translated program makes system calls, "they're translated into native calls to the kernel". **[WWDC]** ([State of the Union @0:24:54](https://developer.apple.com/videos/play/wwdc2020/102/?time=1494))
- Rosetta "isn't running in a special container"; file-system and network access work as for any app. **[WWDC]** ([State of the Union @0:26:35](https://developer.apple.com/videos/play/wwdc2020/102/?time=1595))
- The arm64 translation is "optimized for Apple Silicon and tuned for our high-performance CPUs", and Rosetta was "written from the ground up for Apple SoCs". **[WWDC]** ([State of the Union @0:23:43, @0:24:42](https://developer.apple.com/videos/play/wwdc2020/102/?time=1423)) Apple also says the performance and compatibility were "only possible" because the Apple-silicon and software teams worked closely together. **[WWDC]** ([10686 @11:59](https://developer.apple.com/videos/play/wwdc2020/10686/?time=719)) **→ cross-ref [04-hardware-assists.md](04-hardware-assists.md).**

### 4.2 When translation happens: install time, first launch, and on the fly

| Trigger | Apple's statement | Source |
|---|---|---|
| Install from the App Store or a package installer | Rosetta "will translate the application in the background during the install". The translation work starts as soon as the app is being installed. | **[WWDC]** [State of the Union @0:24:23](https://developer.apple.com/videos/play/wwdc2020/102/?time=1463); [10686 @12:08–12:18](https://developer.apple.com/videos/play/wwdc2020/10686/?time=728) |
| Any other delivery (drag-installed apps, downloaded tools) | "All others are translated on first launch." You may see "an extra bounce or two in the dock the first time it's launched". | **[WWDC]** [State of the Union @0:24:32](https://developer.apple.com/videos/play/wwdc2020/102/?time=1472); [10686 @12:21](https://developer.apple.com/videos/play/wwdc2020/10686/?time=741) |
| General principle | "ahead-of-time compilation so that nearly all applications are translated before you even launch them" | **[WWDC]** [State of the Union @0:24:15](https://developer.apple.com/videos/play/wwdc2020/102/?time=1455) |
| Dynamically generated or loaded code | Code that a JIT generates, or that the app loads dynamically, is translated "on the fly". This covers browsers with JavaScript JITs and Java. Code not translated at install time is compiled on the fly. | **[WWDC]** [Keynote @1:39:43](https://developer.apple.com/videos/play/wwdc2020/101/?time=5983); [State of the Union @0:24:35](https://developer.apple.com/videos/play/wwdc2020/102/?time=1475); [10686 @13:03](https://developer.apple.com/videos/play/wwdc2020/10686/?time=783) |
| At launch | "When your application is launched, we load our stored translation." | **[WWDC]** [10686 @12:47](https://developer.apple.com/videos/play/wwdc2020/10686/?time=767) |
| User-visible effect | Translation takes time, so translated apps may appear to launch or run more slowly "at times". When translation finishes, the system launches the translated executable in place of the original. | **[Apple doc]** [About](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment) |
| Why AOT matters | A translation cache built at install means no glitches caused by translating new blocks of code, which matters for games with real-time audio. | **[WWDC]** [State of the Union @0:26:51](https://developer.apple.com/videos/play/wwdc2020/102/?time=1611) |
| The Keynote framing | "It translates the apps when you install them, so they can launch immediately and be instantly responsive." | **[WWDC]** [Keynote @1:39:37](https://developer.apple.com/videos/play/wwdc2020/101/?time=5977) |

### 4.3 The two pipelines (Apple Platform Security, 2021)

All of the following is **[Apple support]**, from [*Rosetta 2 on a Mac with Apple silicon*](https://support.apple.com/guide/security/rosetta-2-on-a-mac-with-apple-silicon-secebb113be1/web), published February 18, 2021 and still current.

- "There are two types of translation offered: just-in-time and ahead-of-time."
- **JIT pipeline.** An x86_64 Mach-O is identified early in the exec path. The kernel then hands control to a Rosetta *translation stub* instead of to dyld. The stub translates x86_64 pages as the image executes, entirely inside the process. The kernel still checks the code hash of each x86_64 page against the binary's code signature when the page is faulted in, and enforces the process's policy on a mismatch.
- **AOT pipeline.**
  - Binaries are read and translated "at times the system deems optimal for responsiveness". The artifact is a special Mach-O, marked as the translated product of another image.
  - A privileged user-space service signs each artifact with a **device-specific key managed by the Secure Enclave**. The key is released only to that service, which a restricted entitlement identifies. The artifact's code directory embeds the CDHash of the original x86_64 image. This is called the *supplemental signature*.
  - At exec, the kernel hands off to the Rosetta runtime instead of dyld. The runtime sends an IPC query to the *Rosetta system service* asking whether an AOT translation exists. If one does, the service returns a handle and the translation is mapped and executed. The kernel then enforces the artifact's own hashes; the original image's hashes are not involved.
  - Artifacts live in a **Data Vault** that only the Rosetta service can access. The service hands out read-only file descriptors, and its IPC surface is kept intentionally narrow.
  - If the original image's CDHash does not match the one encoded in the artifact, this is treated as an invalid code signature.
  - If another process asks the kernel for the entitlements or identity of an AOT-translated executable, it gets the original x86_64 image's identity.
- **System binaries.** macOS ships universal system binaries. The static trust cache holds three CDHashes for each Mach-O: one for the arm64 slice, one for the x86_64 slice, and one for the AOT translation of the x86_64 slice.
  - "The Rosetta AOT translation procedure is deterministic": the same input always produces identical output, on any device and at any time.
  - Apple translates every system Mach-O during the macOS build and records the resulting hash. The translated files themselves do not ship; they are "reconstituted on demand".
  - These products are not signed with the device key, because their trust is rooted in the secure boot chain.
- **Unsigned code.** Native arm64 code must carry at least an ad-hoc signature. Translated x86_64 code "is permitted to execute through Rosetta with no signature information at all", with the same limits as unsigned code on an Intel Mac.

The sessions said the same thing in plainer words. Translations "are all code-signed, tied to a single machine, securely stored, and get refreshed over OS updates". **[WWDC]** ([10686 @12:37](https://developer.apple.com/videos/play/wwdc2020/10686/?time=757)) The caches are integrated with system code signing and bound to the machine and OS version. **[WWDC]** ([State of the Union @0:24:59](https://developer.apple.com/videos/play/wwdc2020/102/?time=1499)) The translation cache is code-signature-checked before execution. **[WWDC]** ([State of the Union @0:27:49](https://developer.apple.com/videos/play/wwdc2020/102/?time=1669))

> Reconciling the two descriptions (author's reading, not an Apple statement): "install-time" and "first-launch" translation (WWDC) are the AOT pipeline. "Translate on the fly" for JIT or dynamically loaded code corresponds to translation inside the running process. The security guide also describes a JIT pipeline for whole images, but does not say when the system chooses it over AOT. **→ cross-ref [02-architecture-and-runtime.md](02-architecture-and-runtime.md), [03-translation-techniques.md](03-translation-techniques.md).**

### 4.4 Behavioural fidelity: what Rosetta emulates

| Property | Native Apple silicon | Translated process (Apple's statement) | Source |
|---|---|---|---|
| Overall | Page size, memory ordering, `mach_absolute_time` frequency and some floating-point details "all change". | "we've made sure that everything matches behavior on an Intel-based Mac" | **[WWDC]** [10686 @13:37–13:56](https://developer.apple.com/videos/play/wwdc2020/10686/?time=817) |
| Page size | 16 KB native pages; `PAGE_SIZE` is no longer a compile-time constant | "the CPU on Apple Silicon Macs will support 4 kB pages for translated processes" | **[WWDC]** [10214 @09:04–09:37](https://developer.apple.com/videos/play/wwdc2020/10214/?time=544) |
| Memory ordering | Weak ordering; races that were harmless on Intel may crash | "running under Rosetta fully supports the Intel memory ordering" | **[WWDC]** [10214 @38:16–38:52](https://developer.apple.com/videos/play/wwdc2020/10214/?time=2296); **[Apple doc]** [ArchDiff](https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code) |
| Timebase | `mach_absolute_time` ticks are not nanoseconds; a typical bug makes things run "roughly 40 times slower" | Value "is different for native and translated processes"; always apply `mach_timebase_info` | **[WWDC]** [10214 @20:55–22:35](https://developer.apple.com/videos/play/wwdc2020/10214/?time=1255); **[Apple doc]** [ArchDiff](https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code) |
| Floating point and float-to-int | arm64 saturates out-of-range float-to-int conversions; x86_64 wraps or returns the "indefinite integer" | Matches Intel (general statement only) | **[Apple doc]** [ArchDiff](https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code); **[WWDC]** [10686 @13:49](https://developer.apple.com/videos/play/wwdc2020/10686/?time=829) |
| Security model | Hardened Runtime enforced | Hardened Runtime protections are "all fully enforced on processes running in Rosetta" | **[WWDC]** [10686 @13:11](https://developer.apple.com/videos/play/wwdc2020/10686/?time=791) |
| Debugging view | — | The debugger shows Intel instructions; "They're all being transparently translated" | **[WWDC]** [10214 @05:40–05:54](https://developer.apple.com/videos/play/wwdc2020/10214/?time=340) |

**→ cross-ref [04-hardware-assists.md](04-hardware-assists.md)** for how the 4 KB pages and TSO are actually achieved. Apple's own description of the hardware TSO mode exists only for Linux guests (§7.5).

### 4.5 Graphics, ML and I/O under translation

- **Metal.** Rosetta "produces native calls to the GPUs built into Apple SoCs". CPU instructions are translated, while graphics commands are sent straight to the native GPU. **[WWDC]** ([State of the Union @0:24:05, @0:27:13](https://developer.apple.com/videos/play/wwdc2020/102/?time=1445)) Apps using Metal "directly generate the right commands for the Apple GPU". **[WWDC]** ([10686 @11:48](https://developer.apple.com/videos/play/wwdc2020/10686/?time=708))
- **Metal consistency workarounds.** For apps linked against the macOS 10.15 SDK or earlier that run under Rosetta, Metal automatically applies software workarounds that trade GPU performance for Intel-like behaviour. It forces tile loads for `MTLLoadAction.dontCare`, treats vertex positions as `invariant`, and snapshots depth data. Apple does not apply some other workarounds, because "the performance penalty is too large". **[Apple doc]** ([Metal porting](https://developer.apple.com/documentation/apple-silicon/porting-your-metal-code-to-apple-silicon)); **[WWDC]** ([10631 @02:53–03:21](https://developer.apple.com/videos/play/wwdc2020/10631/?time=173))
- **Core ML.** Translated apps that use Core ML "get to run on the Neural Engine". **[WWDC]** ([10686 @11:53](https://developer.apple.com/videos/play/wwdc2020/10686/?time=713))
- **Memory and I/O overhead.**
  - Emulation "has very little memory overhead".
  - The translation cache is "file-backed, just like the original executable".
  - File saves go through the native storage stack, and emulation "doesn't add any copies or buffering".
  - **[WWDC]** ([State of the Union @0:27:24–0:28:05](https://developer.apple.com/videos/play/wwdc2020/102/?time=1644))
- **Data Protection.** Per-extent encryption keys work for both Rosetta 2 and native apps. **[Apple support]** ([Platform Security](https://support.apple.com/guide/security/data-protection-classes-secb010e978a/web))

### 4.6 Code signing

- Starting with macOS 11 on Apple silicon, every native executable must be signed (ad-hoc is enough). "This new policy doesn't apply to translated x86 binaries running under Rosetta 2". **[Apple doc]** ([Big Sur 11.0.1 Universal Apps notes](https://developer.apple.com/documentation/macos-release-notes/macos-big-sur-11_0_1-universal-apps-release-notes)) The security guide gives the same rule (§4.3).

### 4.7 Apple's marketing claims about performance

- "Rosetta 2 is transparent to users, and the performance is amazing." **[WWDC]** ([Keynote @1:39:56](https://developer.apple.com/videos/play/wwdc2020/101/?time=5996))
- "Rosetta 2 is wickedly fast, transparent to users and completely integrated". **[WWDC]** ([State of the Union @0:28:10](https://developer.apple.com/videos/play/wwdc2020/102/?time=1690))
- Some graphically demanding apps perform "even better under Rosetta 2" than they did natively on previous Macs with integrated graphics. **[Apple newsroom]** ([2020-11-12](https://www.apple.com/newsroom/2020/11/macos-big-sur-is-here/))
- "In most cases, you won't notice any difference in the performance of an app that needs Rosetta." **[Apple support]** ([Wayback 2020-11-17](https://web.archive.org/web/20201117204544/https://support.apple.com/en-us/HT211861)). The 2026 text is similar.

### 4.8 Rosetta inside Linux VMs, in brief (full detail in the Linux doc)

- "It's the same technology we have been using on the Mac". **[WWDC]** ([WWDC22-10002 @20:54](https://developer.apple.com/videos/play/wwdc2022/10002/?time=1254))
- In Linux guests, Rosetta 2 "translates executable pages on-demand". Execution stops periodically to translate new code, and the cost is most noticeable at startup. Since macOS 14, translated libraries and executables are cached on disk and shared through a daemon that handles "dynamic linker requests". Exec-heavy work, such as compiling or installing packages, gains the most. **[WWDC]** ([WWDC23-10007 @12:21–14:31](https://developer.apple.com/videos/play/wwdc2023/10007/?time=741))

**→ cross-ref [05-rosetta-for-linux.md](05-rosetta-for-linux.md).**

### 4.9 What Apple's open source corroborates (pointers only; **→ cross-ref [02-architecture-and-runtime.md](02-architecture-and-runtime.md), [03-translation-techniques.md](03-translation-techniques.md)**)

These are citations of Apple-published code. They confirm, but do not extend, the documented model.

| Fact | Where |
|---|---|
| `sysctl.proc_translated` exists only when the kernel is built with `CONFIG_ROSETTA`. It returns 1 when `proc_is_translated()`, which tests the `P_TRANSLATED` process flag. | **[Apple OSS]** [xnu `bsd/kern/kern_sysctl.c`](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_sysctl.c), [`bsd/kern/kern_proc.c`](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_proc.c) |
| `P_TRANSLATED` = `0x00020000` in the public `<sys/proc.h>`. The PowerPC-era name `P_CLASSIC` is defined as an alias of it. It is visible through `sysctl(KERN_PROC_PID)` → `kinfo_proc.kp_proc.p_flag`. | **[Apple OSS]** [xnu `bsd/sys/proc.h`](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/proc.h) |
| At exec, the kernel sets `P_TRANSLATED` for images flagged `IMGPF_ROSETTA`. It loads an **arm64** runtime from `/usr/libexec/rosetta/runtime` instead of starting dyld ("Rosetta will parse it's load commands"), passes file descriptors for the main binary and dyld to the runtime, and creates the address space with `PMAP_CREATE_ROSETTA`. | **[Apple OSS]** [xnu `bsd/kern/kern_exec.c`](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exec.c), [`bsd/kern/mach_loader.c`](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/mach_loader.c) |
| The arm64 kernel defines an x86_64-format commpage at `0x7fffffe00000`, with x86 capability bits (SSE…AVX2, AVX-512 bits) and an `x86_64_kIsTranslated` bit. | **[Apple OSS]** [xnu `osfmk/arm/cpu_x86_64_capabilities.h`](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm/cpu_x86_64_capabilities.h) |
| The public SDK header exposes `struct dyld_aot_image_info`: x86 load address, AOT load address, size, and a 32-byte SHA-256 key. `dyld_all_image_infos` gains `aotInfoCount`, `aotInfoArray`, `aotSharedCacheBaseAddress` and `aotSharedCacheUUID` "in version 17 (macOS 10.16)". Debuggers and profilers use these to map x86 code to its translation. | **[Apple OSS]** [dyld `include/mach-o/dyld_images.h`](https://github.com/apple-oss-distributions/dyld/blob/main/include/mach-o/dyld_images.h) |
| LLDB's `debugserver` detects `P_TRANSLATED` on attach and hands the session to the "Rosetta debugserver" at `/Library/Apple/usr/libexec/oah/debugserver`. LLDB tests also look for a "Rosetta shared cache" under `~/Library/Developer/Xcode/macOS DeviceSupport`. | **[Apple OSS]** *(LLVM, largely Apple-maintained)* [`DNB.cpp`](https://github.com/llvm/llvm-project/blob/main/lldb/tools/debugserver/source/DNB.cpp), [`TestRosetta.py`](https://github.com/llvm/llvm-project/blob/main/lldb/test/API/macosx/rosetta/TestRosetta.py) |
| The `arch(1)` tool uses `posix_spawnattr_setarchpref_np`. When arm64 is requested, it clears `kern.curproc_arch_affinity`. The x86_64 build treats both x86_64 and arm64 as runnable when the commpage `kIsTranslated` bit is set. | **[Apple OSS]** [system_cmds `arch/arch.c`](https://github.com/apple-oss-distributions/system_cmds/blob/main/arch/arch.c) |

---

## 5. Limitations, as Apple documented them

### 5.1 The canonical list and how it changed (*About the Rosetta translation environment*)

The history was rebuilt from Wayback Machine captures of the page's JSON data feed.

| Period (capture dates) | "Rosetta doesn't translate…" | ISA statement | Other boxes |
|---|---|---|---|
| 2020 (first capture 2020-11-01) → 2025-06-09 | Kernel extensions; virtual-machine apps that virtualize x86_64 computer platforms | Rosetta "translates all x86_64 instructions, but it doesn't support the execution of some newer instruction sets and processor features, such as AVX, AVX2, and AVX512". Check `hw.optional.avx512f` before using such instructions. | "Important" box: no mixing of arm64 and x86_64 in one process. Rosetta "is not a substitute for creating a native version of your app." |
| 2025-06-11 → 2025-09-18 | same | same | New box: Tahoe is the last release for Intel Macs, which get 3 years of security updates. Rosetta is available for the next two major releases, "through macOS 27", then only "a subset of Rosetta functionality aimed at supporting older unmaintained gaming titles, that rely on Intel-based frameworks". |
| 2025-10-28 → 2026-04 | same | AVX and AVX2 are translated; AVX-512 execution is not supported. | same |
| 2026-07-15 → 2026-08-15 | same | same | Box shortened to "will be available through macOS 27". New paragraph: macOS 27 "directly integrates support for Intel binary translation, without needing to install Rosetta" for Intel Linux binaries in VMs and Intel Linux containers. The text now speaks of "Mac apps" and "macOS binary". |
| Current (fetched 2026-10-31) | same | same | The macOS 27 integration paragraph is **gone** from this page. It survives in the Virtualization doc. |

Sources for the table: Wayback captures [2020-11-01](https://web.archive.org/web/20201101145333/https://developer.apple.com/tutorials/data/documentation/apple_silicon/about_the_rosetta_translation_environment.json), [2025-06-09](https://web.archive.org/web/20250609074056/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json), [2025-06-11](https://web.archive.org/web/20250611040604/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json), [2025-09-18](https://web.archive.org/web/20250918164601/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json), [2025-10-28](https://web.archive.org/web/20251028174555/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json), [2026-07-15](https://web.archive.org/web/20260715042841/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json), [2026-08-15](https://web.archive.org/web/20260815045008/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json), and the [live page](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment).

Two things stand out:

- The page never contained a longer list of limitations (no x87, no 32-bit, no TSO caveats).
- Apple's on-stage list in 2020 was "kernel extensions, AVX vector instructions, or virtualization" **[WWDC]** ([10214 @04:52](https://developer.apple.com/videos/play/wwdc2020/10214/?time=292)), and AVX alone was named in 10686 ([@14:01](https://developer.apple.com/videos/play/wwdc2020/10686/?time=841)).

### 5.2 Other limitations that Apple has stated

| Limitation | Statement | Source |
|---|---|---|
| Kernel extensions | Kexts run in the kernel, "and the kernel always runs as a native process". "You cannot run kernel extensions using Rosetta translation." The State of the Union says kexts "can't run … in emulation". | **[Apple doc]** [Porting](https://developer.apple.com/documentation/apple-silicon/porting-your-macos-apps-to-apple-silicon); **[WWDC]** [State of the Union @0:29:17](https://developer.apple.com/videos/play/wwdc2020/102/?time=1757) |
| Virtualization | Rosetta cannot translate VM apps that virtualize x86-64 platforms. The Virtualization framework cannot install or boot Intel Linux distributions; it supports only Intel *apps* inside ARM Linux. | **[Apple doc]** [About](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment); [Linux VMs](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| In-process plug-ins | The plug-in's architecture must match the host process. "Native apps can only load native plug-ins and Rosetta translated apps can only load Intel-based plug-ins." | **[Apple doc]** [Porting](https://developer.apple.com/documentation/apple-silicon/porting-your-macos-apps-to-apple-silicon); **[WWDC]** [10214 @31:25](https://developer.apple.com/videos/play/wwdc2020/10214/?time=1885) |
| AVX-512 | Not supported. AVX and AVX2 were also unsupported in the documentation until autumn 2025. | §5.1 |
| Xcode itself | "Xcode isn't supported under Rosetta" (Xcode 14.3+). Don't launch Xcode under Rosetta to work around build errors. | **[Apple doc]** [Xcode 14.3 notes](https://developer.apple.com/documentation/xcode-release-notes/xcode-14_3-release-notes); [TN3117](https://developer.apple.com/documentation/technotes/tn3117-resolving-build-errors-for-apple-silicon) |
| Apple pro apps | "Don't use Rosetta to run Final Cut Pro". Logic Pro under Rosetta loses Stem Splitter, ChromaGlow and most Mastering Assistant presets; Rosetta is needed only for some ARA plug-ins. | **[Apple support]** [102082](https://support.apple.com/en-us/102082); [121464](https://support.apple.com/en-us/121464) |
| DTK hardware | The DTK had "some compatibility restrictions" (see the DTK notes). FairPlay was unavailable "via Rosetta 2". | **[WWDC]** [10686 @14:18](https://developer.apple.com/videos/play/wwdc2020/10686/?time=858); **[Apple doc]** [DTK notes](https://developer.apple.com/documentation/macos-release-notes/macos-big-sur-11_0_1-universal-apps-release-notes) |
| Metal edge cases | Some Metal behaviour differences are *not* papered over under translation, because of performance cost. | **[Apple doc]** [Metal porting](https://developer.apple.com/documentation/apple-silicon/porting-your-metal-code-to-apple-silicon) |
| Linux guests | Statically linked x86_64 binaries run as is. Dynamically linked ones need x86 shared libraries installed in the guest, in paths both the user account and Rosetta can reach. | **[Apple doc]** [Linux VMs](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |

### 5.3 Per-release record of Apple-documented Rosetta changes

| macOS | Apple-documented items |
|---|---|
| **11 Big Sur (2020)** | Rosetta 2 introduced and installed on demand. Limits: kexts, x86 VMs, AVX. Translated x86 exempt from the arm64 signing rule. `posix_spawnattr_setarchpref_np` added (man page: "appeared in macOS 10.16"). `dyld_all_image_infos` v17 AOT fields. Metal consistency mode for apps built with the 10.15 SDK. Beta notes fix "Rosetta 2 widgets" text alignment ([Wayback](https://web.archive.org/web/20201102022443/https://developer.apple.com/tutorials/data/documentation/macos-release-notes/macos-big-sur-11_0_1-beta-release-notes.json)). Xcode 12.3: Xcode's first launch without Rosetta shows a blocking prompt; workaround: launch any x86_64 process ([Apple doc](https://developer.apple.com/documentation/xcode-release-notes/xcode-12_3-release-notes)). |
| **12 Monterey (2021)** | No Rosetta item in the macOS release notes. Xcode 13 fixed Interface Builder and Asset Catalog compatibility "with Rosetta enabled" ([Apple doc](https://developer.apple.com/documentation/xcode-release-notes/xcode-13-release-notes)). Xcode 13.3 fixed bogus frames such as `0x3` when profiling Rosetta 2 apps ([Apple doc](https://developer.apple.com/documentation/xcode-release-notes/xcode-13_3-release-notes)). |
| **13 Ventura (2022)** | Rosetta for Linux VMs (`VZLinuxRosettaDirectoryShare`, `installRosetta`, `availability`). The doc says that with macOS 13, `update-binfmts` must use `preserve no`. Xcode 14 adds `simctl boot --arch` to run universal simulator runtimes as x86_64 ([Apple doc](https://developer.apple.com/documentation/xcode-release-notes/xcode-14-release-notes)). Xcode 14.3: Rosetta run destinations menu; Xcode not supported under Rosetta. |
| **14 Sonoma (2023)** | Linux Rosetta AOT caching options (`VZLinuxRosettaCachingOptions` with Unix-domain-socket and abstract-socket variants). Fix: "Intel applications might quit unexpectedly on launch under Rosetta" ([Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-14-release-notes)). GPT 1 evaluation environment. |
| **15 Sequoia (2024)** | GPT 2 with AVX/AVX2 game evaluation. Fix: "Rosetta: Intel binaries fail to run in a Virtual Machine" ([Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-15-release-notes)). The TSO kernel-patch doc for Linux guests exists by January 2025. Xcode 16 known issue in watchOS "Rosetta Simulator destinations" ([Apple doc](https://developer.apple.com/documentation/xcode-release-notes/xcode-16-release-notes)). |
| **26 Tahoe (2025)** | Last release for Intel Macs. `nox86exec=1` boot-arg ([Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-26-release-notes)). Documentation now says AVX/AVX2 are translated. **26.4**: launch-time notifications (accelerated cadence during the beta), `allowRosettaUsageAwareness` ([Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes)). **26.6**: fixed notifications that wrongly flagged a host app as Intel-only when a system plug-in loader (Color Picker, Print Dialog Extension) "loads x86 code into the host process" ([Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-26_6-release-notes)). Xcode 26.4: Swift Testing may crash under a Rosetta destination with "Xcode for Apple silicon"; workaround: use "Xcode Universal" ([Apple doc](https://developer.apple.com/documentation/xcode-release-notes/xcode-26_4-release-notes)). |
| **27 Golden Gate (2026)** | Last release with general-purpose Rosetta. Rosetta is not restored after upgrading to 27.0 (fixed in 27.2). Apps a user had set to "Open using Rosetta" now launch natively. Get Info shows a "treatment" on apps that won't run in 28. Settings › General lists Intel apps. Installer packages without `hostArchitecture` default to arm64. Intel plug-ins and loaders (VST, HAL, ARA, PDE, Color Pickers, Quick Look and Spotlight) may not be flagged. Beta-only `game-test-tool`. Linux Intel translation built in ([Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes); [Apple support](https://support.apple.com/en-us/148830)). Xcode 27 runs only on Apple silicon, and `ARCHS_STANDARD` omits x86_64 when the deployment target is 27 or later ([Apple doc](https://developer.apple.com/documentation/xcode-release-notes/xcode-27-release-notes)). |
| **28 (expected 2027)** | "All Intel-based software will no longer be compatible with macOS 28.0, excluding legacy games" ([Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes)). Support for "older, unmaintained gaming titles" and for "software running Intel binaries in Linux VMs" continues ([Apple doc](https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes)). |

---

## 6. Developer-visible APIs and behaviours for detecting or controlling translation

### 6.1 Detection

| Mechanism | Behaviour | Source |
|---|---|---|
| `sysctlbyname("sysctl.proc_translated", …)` | Returns 1 if translated, 0 if native. If the call fails with `ENOENT`, Apple's sample treats that as native (an Intel Mac, or a system without Rosetta support). | **[Apple doc]** [About](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment); **[WWDC]** [10686 @14:30](https://developer.apple.com/videos/play/wwdc2020/10686/?time=870) |
| `kinfo_proc.kp_proc.p_flag & P_TRANSLATED` (another process) | Used by LLDB's debugserver to detect translated targets. Not documented as an API; it comes from open source. | **[Apple OSS]** §4.9 |
| `NSRunningApplication.executableArchitecture` | "Indicates the executing processor architecture". Apple does not state what it returns under Rosetta. | **[Apple doc]** [link](https://developer.apple.com/documentation/appkit/nsrunningapplication/executablearchitecture) |
| `Bundle.executableArchitectures` | Lists the slices in the bundle's executable. | **[Apple doc]** [link](https://developer.apple.com/documentation/foundation/bundle/executablearchitectures) |
| Crash reports | `Code Type: … (Translated)` vs `(Native)`. The `.ips` JSON has `translated: true`. Xcode Organizer shows whether a crash ran translated. | **[Apple doc]** [fields](https://developer.apple.com/documentation/xcode/examining-the-fields-in-a-crash-report), [JSON](https://developer.apple.com/documentation/xcode/interpreting-the-json-format-of-a-crash-report); **[WWDC]** [10214 @37:15](https://developer.apple.com/videos/play/wwdc2020/10214/?time=2235) |
| Activity Monitor "Kind" column | Shows "Apple" for native processes and "Intel" for translated ones. | **[WWDC]** [10214 @02:34](https://developer.apple.com/videos/play/wwdc2020/10214/?time=154), [@05:20](https://developer.apple.com/videos/play/wwdc2020/10214/?time=320) |
| Finder Get Info "Kind" | Application (Intel), (Universal) or (Apple silicon). | **[Apple support]** [102527](https://support.apple.com/en-us/102527) |
| macOS 27 Settings › General › About › Intel-based Apps | Lists recently used and installed Intel apps, plus unused Intel software found on the system. | **[Apple support]** [102527](https://support.apple.com/en-us/102527); **[Apple doc]** [macOS 27 notes](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes) |
| Feature sysctls | Check `hw.optional.<feature>` (for example `hw.optional.avx512f`) before using optional ISA extensions. | **[Apple doc]** [About](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment), [ArchDiff](https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code) |

### 6.2 Choosing the architecture

| Mechanism | Behaviour | Source |
|---|---|---|
| Default slice choice | The system prefers the native slice (arm64 on Apple silicon, x86_64 on Intel). | **[Apple doc]** [Universal](https://developer.apple.com/documentation/apple-silicon/building-a-universal-macos-binary) |
| Finder "Open using Rosetta" | For universal apps, forces the x86_64 slice so the app can load Intel-only plug-ins. In macOS 27, apps a user had set this way launch natively, and the support article says the option appears when "the app developer chose to include this setting". | **[Apple doc]** [About](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment); **[WWDC]** [10214 @35:03](https://developer.apple.com/videos/play/wwdc2020/10214/?time=2103); **[Apple support]** [102527](https://support.apple.com/en-us/102527); **[Apple doc]** [macOS 27 notes](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes) |
| `LSRequiresNativeExecution` (Info.plist) | Forces the native slice and removes the Get Info option. For an Intel-only app linked against the macOS 11 SDK or later, it prevents the app from running on Apple silicon at all. With an older SDK, the app still runs under Rosetta. | **[Apple doc]** [key](https://developer.apple.com/documentation/bundleresources/information-property-list/lsrequiresnativeexecution), [Universal](https://developer.apple.com/documentation/apple-silicon/building-a-universal-macos-binary) |
| `LSArchitecturePriority` (Info.plist) | Ordered array of `i386`, `x86_64`, `arm64`, `arm64e`. Listing x86_64 first makes a universal app run under Rosetta. Apple recommends listing `arm64` first for apps without an executable. | **[Apple doc]** [key](https://developer.apple.com/documentation/bundleresources/information-property-list/lsarchitecturepriority) |
| Script-only apps | "the system runs script-only apps under Rosetta translation" as a precaution. | **[Apple doc]** [Universal](https://developer.apple.com/documentation/apple-silicon/building-a-universal-macos-binary) |
| `NSWorkspace.OpenConfiguration.architecture` | A `cpu_type_t`; the default `CPU_TYPE_ANY` means the app's preferred architecture. Set it to force a specific one. | **[Apple doc]** [link](https://developer.apple.com/documentation/appkit/nsworkspace/openconfiguration/architecture) |
| `posix_spawnattr_setarchpref_np` / `posix_spawnattr_setbinpref_np` | Exact cpu type and subtype preference list for `posix_spawn`. Fails with `EBADARCH` on no match, unless the list ends with `CPU_TYPE_ANY`. | **[Apple OSS]** [xnu man page](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/man/man3/posix_spawnattr_setarchpref_np.3); **[Apple man page]** [mirror](https://keith.github.io/xcode-man-pages/posix_spawnattr_setarchpref_np.3.html) |
| `arch -x86_64 <cmd>`, `ARCHPREFERENCE`, `archSettings` plists | Runs a chosen slice; supports `x86_64`, `x86_64h`, `arm64` and `arm64e`. | **[Apple OSS]** [`arch.1`](https://github.com/apple-oss-distributions/system_cmds/blob/main/arch/arch.1); **[WWDC]** [WWDC22-10141 @17:34](https://developer.apple.com/videos/play/wwdc2022/10141/?time=1054) |
| Child processes | "Once you're in 'Rosetta mode', you stay in that mode". A translated parent's `NSTask` children run translated even when universal. Fix with `posix_spawnattr_setarchpref_np` or by going through `arch`. | **[Apple forums]** Quinn, Apple DTS ([thread 701913](https://developer.apple.com/forums/thread/701913)) |
| Xcode | Run destination "My Mac (Rosetta)". `xcodebuild -destination 'arch=x86_64'` runs tests under Rosetta. Product › Destination › Destination Architectures › "Show Rosetta Destinations" (Xcode 14.3+). Simulator runtimes come in Apple-silicon and universal variants; the universal one is needed for Rosetta destinations (`-architectureVariant universal`). | **[WWDC]** [10214 @08:42](https://developer.apple.com/videos/play/wwdc2020/10214/?time=522), [@23:39](https://developer.apple.com/videos/play/wwdc2020/10214/?time=1419); **[Apple doc]** [TN3117](https://developer.apple.com/documentation/technotes/tn3117-resolving-build-errors-for-apple-silicon), [components](https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components) |
| Installer packages | On Apple silicon, Installer evaluates a distribution "under Rosetta 2 unless the arch key includes the arm64 architecture specifier", and then runs package scripts under Rosetta 2. Since Big Sur, `productbuild` adds arm64 and x86_64 by default. macOS 27 defaults packages without `hostArchitecture` to arm64. | **[Apple man page]** [`productbuild(1)` mirror](https://keith.github.io/xcode-man-pages/productbuild.1.html); **[Apple doc]** [macOS 27 notes](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes) |

### 6.3 Installing and managing Rosetta

| Mechanism | Behaviour | Source |
|---|---|---|
| On-demand prompt | Launching any Intel app prompts an install, which needs an internet connection and an admin password. "Not Now" asks again next time. Rosetta "is not an app that you open or interact with". | **[Apple support]** [102527](https://support.apple.com/en-us/102527) (2024 and 2026 versions) |
| `softwareupdate --install-rosetta [--agree-to-license]` | "Install Rosetta. Only applies to Apple silicon Macs." `--agree-to-license` accepts the licence non-interactively. | **[Apple man page]** [`softwareupdate(8)` mirror](https://keith.github.io/xcode-man-pages/softwareupdate.8.html); **[Apple support]** [102527](https://support.apple.com/en-us/102527) |
| `/System/Library/CoreServices/Rosetta2 Updater.app` | The installer app; Final Cut Pro also has Help › Install Rosetta. | **[Apple support]** [102082](https://support.apple.com/en-us/102082) |
| `VZLinuxRosettaDirectoryShare.installRosetta()` | Installs Rosetta for Linux VMs. Possible errors: network, out of disk space, user cancelled, not supported. In macOS 27, `availability` is always `.installed` and the call returns immediately. | **[Apple doc]** [Linux VMs](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms), [API](https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare/installrosetta(completionhandler:)) |
| `allowRosettaUsageAwareness` (MDM restriction, `com.apple.applicationaccess`) | macOS 26.4+; the Mac does not need to be supervised. Setting it to `false` disables the pop-up that warns Rosetta will be removed. | **[Apple support]** [Deployment](https://support.apple.com/guide/deployment/review-device-management-restrictions-dep739685973/web); **[Apple OSS]** [device-management YAML](https://github.com/apple/device-management/blob/release/mdm/profiles/com.apple.applicationaccess.yaml) |
| Boot-arg `nox86exec=1` | macOS 26+. Any process that would run through Rosetta crashes immediately and generates a crash report. | **[Apple doc]** [macOS 26 notes](https://developer.apple.com/documentation/macos-release-notes/macos-26-release-notes) |
| `sudo game-test-tool enable` | macOS 27 betas only. Enables legacy Intel game support and **disables Rosetta**; non-game processes may crash. | **[Apple doc]** [macOS 27 notes](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes) |
| Uninstall | **No documented method.** | (see §10) |

---

## 7. Topic-by-topic: what Apple tells developers

### 7.1 Plug-ins, extensions, XPC and Audio Units

- In-process plug-ins must match the host's architecture. When `dlopen` loads a wrong-architecture plug-in, it fails, and `dlerror` names the file. **[WWDC]** ([10214 @32:03–34:20](https://developer.apple.com/videos/play/wwdc2020/10214/?time=1923))
- Plug-ins that run out of process over XPC may use a different architecture than the app. Apple's pattern is two non-universal XPC services, one arm64 and one x86_64, each with a unique bundle ID. A single service can host native or translated plug-ins, "but not both at the same time". **[Apple doc]** ([Porting](https://developer.apple.com/documentation/apple-silicon/porting-your-macos-apps-to-apple-silicon); [WWDC20-10214 @34:26](https://developer.apple.com/videos/play/wwdc2020/10214/?time=2066))
- NSExtension-based plug-ins work both native and translated. **[WWDC]** ([10214 @29:02](https://developer.apple.com/videos/play/wwdc2020/10214/?time=1742))
- Because extensions run out of process, Rosetta "can even emulate extensions when they're being used with a native host app". Audio Units "run out of process under Rosetta 2", and DriverKit drivers "are in the same situation". **[WWDC]** ([State of the Union @0:28:25–0:28:56](https://developer.apple.com/videos/play/wwdc2020/102/?time=1705))
- Logic Pro and Final Cut Pro support most AUv2 and AUv3 plug-ins "whether or not the plug-in was built for use with Apple silicon", as long as Rosetta is installed. **[Apple support]** ([102082](https://support.apple.com/en-us/102082))
- Universal Audio Units can be loaded either in-process or out-of-process. **[Apple doc]** ([Audio porting](https://developer.apple.com/documentation/apple-silicon/porting-your-audio-code-to-apple-silicon))

### 7.2 JIT compilers inside translated apps

- Rosetta "can translate most Intel-based apps, including apps that contain just-in-time (JIT) compilers". **[Apple doc]** ([About](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment)) It runs "complicated apps like web browsers with embedded JIT compilers". **[WWDC]** ([10686 @11:37](https://developer.apple.com/videos/play/wwdc2020/10686/?time=697))
- Apple's JIT porting article describes only *native* arm64 rules: MAP_JIT, per-thread W^X, `pthread_jit_write_protect_np` / `pthread_jit_write_with_callback_np`, and icache invalidation. It notes that Intel Macs enforce W^X only for apps that adopt the Hardened Runtime. It says **nothing** about how a translated x86 JIT is handled. **[Apple doc]** ([JIT porting](https://developer.apple.com/documentation/apple-silicon/porting-just-in-time-compilers-to-apple-silicon))
- The `pthread_jit_write_protect_np(3)` man page says: where `pthread_jit_write_protect_supported_np()` is false, MAP_JIT regions are simultaneously writable and executable, and the toggle calls are no-ops. **[Apple OSS]** ([libpthread man page](https://github.com/apple-oss-distributions/libpthread/blob/main/man/pthread_jit_write_protect_np.3)) Apple does not document what a translated process gets from this call.
- One Apple DTS explanation exists only as a third-party copy of a support email. It says Rosetta supports apps that rely on RWX pages by toggling RW/RX "on the fly", in rough terms by catching the fault and flipping the page state. **[third-party report of Apple DTS email]** ([sljit issue #99](https://github.com/zherczeg/sljit/issues/99)) **→ cross-ref [02-architecture-and-runtime.md](02-architecture-and-runtime.md), [03-translation-techniques.md](03-translation-techniques.md).**

### 7.3 AVX, AVX2 and AVX-512

- **2020 to 2025.**
  - On stage: "Rosetta does not support the AVX vector extensions to x86", and apps "should already be checking" for support. **[WWDC]** ([10686 @14:01–14:14](https://developer.apple.com/videos/play/wwdc2020/10686/?time=841))
  - In the documentation: no AVX, AVX2 or AVX-512 (§5.1).
- **June 2024.** GPT 2 lets developers evaluate games that use AVX, through "improved compatibility with technologies like AVX2". **[WWDC]** ([WWDC24 State of the Union @54:19](https://developer.apple.com/videos/play/wwdc2024/102/?time=3259); [10089 @02:33](https://developer.apple.com/videos/play/wwdc2024/10089/?time=153))
- **GPT 2.x README.** This is Apple's "Read Me.rtf" inside the GPT disk image, available only as a community copy. On macOS 15, `ROSETTA_ADVERTISE_AVX=1` makes "the CPU instruction translation layer" publish CPUID information. The README stresses that this "does not modify the availability of the instruction set in Rosetta", only what the CPU advertises. It attributes invalid-instruction crashes to the "Rosetta 2 instruction translation layer" being unable to translate. **[Apple README via third-party copy]** ([gist](https://gist.github.com/lynkos/3999f629560219a81d4e2c083a4bf5b1))
- **Autumn 2025 to now.** Documentation: AVX and AVX2 are translated; AVX-512 is not supported (§5.1).
- **Porting advice (native).** Replace SSE, AVX and AVX-512 code with Accelerate or NEON. **[Apple doc]** ([ArchDiff](https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code); [WWDC20-10214 @25:15](https://developer.apple.com/videos/play/wwdc2020/10214/?time=1515))

### 7.4 Kernel extensions and drivers

- Kexts never run under Rosetta, and must include the native architecture (§5.2).
- The universal-binary checklist includes DriverKit extensions and kernel extensions. **[Apple doc]** ([Universal](https://developer.apple.com/documentation/apple-silicon/building-a-universal-macos-binary))
- The State of the Union puts DriverKit drivers in the same position as out-of-process plug-ins. Apple never documents explicitly that an x86_64-only dext runs translated. **[WWDC]** ([State of the Union @0:28:52](https://developer.apple.com/videos/play/wwdc2020/102/?time=1732))

### 7.5 Virtualization and Linux (summary; **→ cross-ref [05-rosetta-for-linux.md](05-rosetta-for-linux.md)**)

- **Hosting x86 VMs.** VM apps that virtualize x86-64 platforms cannot be translated (§5.2).
- **Setup.** Rosetta for Linux guests (macOS 13+) is exposed as a virtiofs directory share (`VZLinuxRosettaDirectoryShare`). The guest mounts it and registers the `rosetta` binary with `update-binfmts`, using the x86-64 ELF magic and mask. The host app cannot run or script these guest-side steps; someone must perform them inside the guest, interactively or with a script while logged in there. **[Apple doc]** ([Linux VMs](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms)); **[WWDC]** ([WWDC22-10002 @21:03](https://developer.apple.com/videos/play/wwdc2022/10002/?time=1263))
- **AOT caching (macOS 14+).** The Rosetta runtime and a Rosetta daemon talk over a Unix-domain socket or an abstract socket that the framework configures. This "can improve the performance of some X86 workloads". **[Apple doc]** ([Linux VMs](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms); [VZLinuxRosettaCachingOptions](https://developer.apple.com/documentation/virtualization/vzlinuxrosettacachingoptions))
- **Hardware TSO for Linux guests.** Apple documents that:
  - Setting `ACTLR.TSOEN` to 1 switches the CPU to the x86-64 TSO memory model; clearing it restores ARM64 ordering.
  - Apple's Linux patch context-switches the bit per thread and adds a `prctl` mode for it.
  - Without this, "programs needed to emulate TSO, degrading performance". Enabling TSO for every process slows native ARM processes that don't need it.
  - The patch applies cleanly to Linux 6.10 and is distributed as `RosettaPatch.zip`.
  - **[Apple doc]** ([Accelerating the performance of Rosetta](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta))
- **macOS 27.**
  - Linux Intel-binary translation is built into macOS. "Until macOS 26, this capability was part of Rosetta." **[Apple doc]** ([Linux VMs](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms))
  - Apple's open-source Containerization framework uses "Rosetta 2 for running linux/amd64 containers". Its `container` CLI refuses to run while it is itself translated, and checks `sysctl.proc_translated`. **[Apple OSS]** ([containerization](https://github.com/apple/containerization); [container `Application.swift`](https://github.com/apple/container/blob/main/Sources/ContainerCommands/Application.swift))

### 7.6 Debugging and profiling

- "Apple silicon supports all debugging and testing tools found on Intel-based Mac computers". **[Apple doc]** ([Porting](https://developer.apple.com/documentation/apple-silicon/porting-your-macos-apps-to-apple-silicon)) To debug the x86_64 slice of a universal binary on Apple silicon, you run it under Rosetta. **[Apple doc]** ([Universal](https://developer.apple.com/documentation/apple-silicon/building-a-universal-macos-binary))
- Translated apps can be built and run from Xcode, profiled with Instruments, and debugged with LLDB. **[WWDC]** ([10686 @13:20–13:33](https://developer.apple.com/videos/play/wwdc2020/10686/?time=800)) No special debug mode is needed, which Apple called "a real enhancement for Rosetta 2". The memory graph debugger also works. **[WWDC]** ([State of the Union @0:25:36](https://developer.apple.com/videos/play/wwdc2020/102/?time=1536))
- Three kinds of crash logs exist: x86 from Intel Macs, arm64 native, and "translated x86 crash logs". **[WWDC]** ([10214 @37:15](https://developer.apple.com/videos/play/wwdc2020/10214/?time=2235))
- Behind the scenes, LLDB hands translated processes to the Rosetta debugserver (§4.9). macOS crash `.ips` files for translated processes carry a nested `rosetta` thread-state dictionary, which LLDB's `crashlog.py` parses. **[Apple OSS]** *(LLVM)* ([crashlog.py](https://github.com/llvm/llvm-project/blob/main/lldb/examples/python/crashlog.py))

### 7.7 Performance guidance: what Apple says is slow

Apple publishes no list of slow x86 constructs. Its statements are:

1. **Translation itself takes time.** First launches without AOT, and runtime-generated or newly loaded code, cost time. **[Apple doc]** ([About](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment)); **[WWDC]** ([10686 @12:21](https://developer.apple.com/videos/play/wwdc2020/10686/?time=741); [State of the Union @0:26:56](https://developer.apple.com/videos/play/wwdc2020/102/?time=1616)) For Linux guests: periodic stops to translate new code, which caching mitigates. **[WWDC]** ([WWDC23-10007 @12:35](https://developer.apple.com/videos/play/wwdc2023/10007/?time=755))
2. **Native is faster.** "Native apps run more efficiently than translated apps because the compiler is able to optimize your code for the target architecture." **[Apple doc]** ([Universal](https://developer.apple.com/documentation/apple-silicon/building-a-universal-macos-binary)) Apple's own demo measured 21 ms native vs 29 ms translated, and advises optimizing for native execution. **[WWDC]** ([10214 @24:31–25:04](https://developer.apple.com/videos/play/wwdc2020/10214/?time=1471))
3. **Graphics consistency costs.** Metal's consistency workarounds and translation "do have some performance costs". **[WWDC]** ([10631 @03:17](https://developer.apple.com/videos/play/wwdc2020/10631/?time=197)); **[Apple doc]** ([Metal porting](https://developer.apple.com/documentation/apple-silicon/porting-your-metal-code-to-apple-silicon))
4. **Game evaluation includes overhead.** GPT baselines include "API and instruction set translation" overhead, and performance and power efficiency "may be affected". **[WWDC]** ([WWDC23-10123 @05:05–05:31](https://developer.apple.com/videos/play/wwdc2023/10123/?time=305)) "Translated games require more resources", so Apple recommends 16 GB of RAM or more. **[Apple README via third-party copy]**
5. **Software TSO is expensive** (stated for Linux guests). **[Apple doc]** ([Accelerating](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta))

### 7.8 iOS apps, Mac Catalyst and Simulator

- iPhone and iPad apps run **natively** on Apple-silicon Macs because they are built for the same architecture. **[WWDC]** ([Keynote @1:42:24](https://developer.apple.com/videos/play/wwdc2020/101/?time=6144))
- Rosetta runs x86_64 **Catalyst** apps. **[WWDC]** ([10686 @11:37](https://developer.apple.com/videos/play/wwdc2020/10686/?time=697))
- **Simulator.**
  - x86_64 simulator runtimes can run under Rosetta: `simctl boot --arch`, and Rosetta run destinations, intended for vendor libraries that lack arm64 simulator slices. **[Apple doc]** ([Xcode 14 notes](https://developer.apple.com/documentation/xcode-release-notes/xcode-14-release-notes); [TN3117](https://developer.apple.com/documentation/technotes/tn3117-resolving-build-errors-for-apple-silicon))
  - Since Xcode 26, simulator runtimes "no longer contain Intel support by default". **[WWDC]** ([WWDC25-247 @01:04](https://developer.apple.com/videos/play/wwdc2025/247/?time=64))

### 7.9 Games and the Game Porting Toolkit

- The GPT evaluation environment (2023+) runs unmodified Windows x86 games. It "translates your game's Intel instructions" plus the Windows APIs for input, audio, networking, file system and graphics. **[WWDC]** ([WWDC23-10123 @03:06](https://developer.apple.com/videos/play/wwdc2023/10123/?time=186)) The README states that it "runs under Rosetta 2". **[Apple README via third-party copy]**
- Apple's open-source Homebrew formula for GPT 1.1 requires an x86_64 environment (`depends_on arch: :x86_64`). It builds Wine with both `--enable-win64` and `--enable-win32on64`. **[Apple OSS]** ([homebrew-apple formula](https://github.com/apple/homebrew-apple/blob/main/Formula/game-porting-toolkit.rb))
- **After macOS 27.** Only "a subset of Rosetta functionality" remains, for "older unmaintained gaming titles, that rely on Intel-based frameworks" (§8). An Apple engineer said x86_64 macOS games "should continue to work as they do on macOS 26", and pointed to `game-test-tool`. He did not answer the question about Wine or CrossOver. **[Apple forums]** ([thread 830692](https://developer.apple.com/forums/thread/830692))

---

## 8. The end of Rosetta: Apple's stated roadmap

| Statement | Source |
|---|---|
| Rosetta 2 is "a transitional technology" to give developers time "at your own pace". | **[WWDC]** [State of the Union @0:25:08](https://developer.apple.com/videos/play/wwdc2020/102/?time=1508) |
| "macOS Tahoe will be the final release for Intel Macs." (On stage, June 2025; Rosetta was not named.) | **[WWDC]** [WWDC25 State of the Union @54:56](https://developer.apple.com/videos/play/wwdc2025/102/?time=3296) |
| Rosetta stays available "for the next two major macOS releases – through macOS 27 – as a general-purpose tool for Intel apps". After that, a subset for older unmaintained games. | **[Apple doc]** [Wayback 2025-06-11](https://web.archive.org/web/20250611040604/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json) |
| "Rosetta support for apps will end after macOS 27". Support continues for older unmaintained games and for software running Intel binaries in Linux VMs. | **[Apple doc]** [macOS 26.4 notes](https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes) |
| "Rosetta support for apps will remain available through the forthcoming macOS 27." | **[Apple support]** [enterprise notes, macOS 26](https://support.apple.com/en-us/124963) |
| "The transition of macOS to Apple silicon is now complete"; Apple-silicon-only binaries may ship on the Mac App Store. | **[WWDC]** [WWDC26 State of the Union @40:42](https://developer.apple.com/videos/play/wwdc2026/102/?time=2442) |
| "All Intel-based software will no longer be compatible with macOS 28.0, excluding legacy games." | **[Apple doc]** [macOS 27 notes](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes) |
| "Rosetta will continue as a general-purpose compatibility tool through macOS 27"; in 27.2, "Rosetta is no longer removed when upgrading to macOS 27." | **[Apple support]** [148830](https://support.apple.com/en-us/148830) |
| From macOS 28, Rosetta "will be available only for certain older, unmaintained games that rely on Intel-based frameworks". | **[Apple support]** [102527](https://support.apple.com/en-us/102527) |
| "macOS 27: Final release to support Rosetta". | **[Apple dev news]** [2026-09-01](https://developer.apple.com/news/?id=w5ngl9k2) |
| Legacy-game mode runs games "through the new underlying system behavior" and disables Rosetta (betas only). | **[Apple doc]** [macOS 27 notes](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes) |

---

## 9. Conflicts and inconsistencies in Apple's own statements

1. **End date.**
   - The 2026-09-09 developer news says "macOS 26 is the final release supporting Intel Mac computers and Rosetta — macOS 27 will be Apple silicon only" ([Apple dev news](https://developer.apple.com/news/?id=k1mtkt1k)).
   - The documentation, release notes, enterprise notes, the support article and the 2026-09-01 news all say Rosetta continues through macOS 27.
   - The 9 September line reads like an editing error (merging "last Intel Mac release" with "last Rosetta release"), but it is published Apple text.
2. **"Available through macOS 27" vs. macOS 27.0 behaviour.** macOS 27.0 did not restore an installed Rosetta after upgrade ([macOS 27 notes](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes)). Apple reversed this in 27.2 ([enterprise notes](https://support.apple.com/en-us/148830)). The 2026-09-01 news urged developers to make sure their apps run "when macOS 27 ships". In the author's reading, that fits this temporary removal.
3. **AVX/AVX2.**
   - The documentation said these were unsupported until autumn 2025.
   - Yet in June 2024 Apple presented AVX/AVX2 game evaluation in GPT 2 (macOS 15), and the GPT README says Rosetta on macOS 15 had the instructions available but not advertised.
   - Apple has never stated which macOS release first executed AVX/AVX2 for ordinary apps, or whether ordinary apps see them advertised.
4. **"Translates all x86_64 instructions" vs. unsupported AVX-512.** Both versions of the page say Rosetta translates "all" x86_64 instructions while listing extensions it does not support.
5. **"Open using Rosetta".**
   - 2020–2025 documentation: any universal app shows the option unless `LSRequiresNativeExecution` is set.
   - The 2026 support article: it appears when "the app developer chose to include this setting".
   - macOS 27 resets user choices to native.
   - The author found no documented developer opt-in key.
6. **Where the macOS 27 Linux-translation statement lives.** The "directly integrates support for Intel binary translation" paragraph was added to the main Rosetta page (Jul–Aug 2026) and then removed by 31 October 2026, while the Virtualization page keeps it.
7. **"Install time" vs. "times the system deems optimal".** WWDC framed AOT as happening at install or first launch. The security guide only says AOT runs "at times the system deems optimal" and also describes a separate in-process JIT pipeline for whole images. These are not contradictory, but the selection policy is unspecified.
8. **"Virtualization" as a limitation.** In 2020, "you also cannot use Rosetta for … virtualization" ([10214 @04:52](https://developer.apple.com/videos/play/wwdc2020/10214/?time=292)) meant x86 *hypervisors*. Since 2022, Rosetta is the official mechanism for running x86 Linux binaries inside ARM Linux VMs.

---

## 10. Open questions / not stated by Apple

These are things Apple has **not** said publicly, as far as the author found. Each is a lead for the internals, hardware or history documents.

1. **AOT cache details.** The physical location, file format, eviction policy, and what exactly triggers the "times the system deems optimal" in the AOT pipeline. Apple says only "Data Vault" and "special type of Mach object". **→ [02-architecture-and-runtime.md](02-architecture-and-runtime.md), [03-translation-techniques.md](03-translation-techniques.md).**
2. **JIT vs. AOT selection.** When the system uses the in-process JIT pipeline for a whole image instead of AOT, and how runtime-generated code (MAP_JIT, self-modifying code) is detected and re-translated. The DTS description of RWX toggling is not documentation.
3. **TSO on macOS.** Apple documents `ACTLR.TSOEN` only for Linux guests. For macOS apps it says only that Intel memory ordering is "fully supported". Whether macOS Rosetta uses the hardware bit, per thread, and for all translated threads, is not stated. **→ [04-hardware-assists.md](04-hardware-assists.md).**
4. **4 KB pages.** The mechanism behind the 4 KB pages that "the CPU … will support" for translated processes (in the pmap or the hardware) is not described. **→ [04-hardware-assists.md](04-hardware-assists.md), [02-architecture-and-runtime.md](02-architecture-and-runtime.md), [03-translation-techniques.md](03-translation-techniques.md).**
5. **Floating-point fidelity.** Apple claims only that "some details of floating point behavior" match Intel. It says nothing on x87 80-bit precision, denormal and flush-to-zero handling, MXCSR exceptions, or how bit-exact the results are.
6. **ISA coverage beyond AVX.** BMI1/2, FMA, F16C, AES-NI, SHA, RDRAND, TSX, CET and so on. Apple names only AVX, AVX2 and AVX-512. It also does not say which macOS release first *advertised* AVX/AVX2 to ordinary apps (CPUID, `hw.optional.avx2_0`, the commpage bits).
7. **What translated processes observe.** CPUID vendor and brand string, `machdep.cpu.*`, `hw.optional.arm64`, `uname -m`, the `arch` output, `mach_timebase_info` values, and `pthread_jit_write_protect_supported_np()`. Apple documents none of these for translated processes. The public XNU code returns the host CPU type for `sysctl.proc_native` and `sysctl.proc_cputype`, which Apple does not document.
8. **32-bit x86 code.** Apple says nothing about compatibility-mode or 32-bit code segments (LDT) under Rosetta. Its own GPT formula builds Wine's `win32on64` mode, which implies some support.
9. **Slice choice under Rosetta.** For binaries with both `x86_64h` and `x86_64` slices, which one Rosetta runs.
10. **DriverKit.** Whether x86_64-only DriverKit extensions run translated. The State of the Union hints yes; the documentation is silent.
11. **Uninstalling and re-installing.** There is no documented way to remove Rosetta. Apple also does not say what Rosetta "installation" actually consists of, beyond the updater app and `softwareupdate`.
12. **The macOS 28 "subset".** Which functionality is kept, how a "game" is recognised (third-party reports say by `LSApplicationCategoryType`), whether Wine or CrossOver-style Windows games qualify, and what the "new underlying system behavior" behind `game-test-tool` is. The Apple engineer's reply did not address Wine.
13. **Linux translation in macOS 27.** Apple says the capability "was part of Rosetta" until macOS 26 and is now integrated. It does not say whether the translator is the same engine.
14. **Performance.** Apple has published no performance model or numbers beyond demos, such as 21 ms vs 29 ms, and marketing claims.
15. **Apple Silicon CPU Optimization Guide.** It requires a developer login and an extra agreement, and was **not** checked for Rosetta content ([Apple doc](https://developer.apple.com/documentation/apple-silicon/cpu-optimization-guide)).
16. **DTK-era limits.** WWDC20 points to "DTK release notes" for Rosetta restrictions on the A12Z hardware. The archived notes (August–October 2020) mention only FairPlay; earlier June/July 2020 versions were not found in the Wayback Machine.

### Design-relevant takeaways for the reverse (ARM64 → x86-64) project

*This subsection is the author's inference from the statements above, not Apple's.*

- **Process boundary.** Apple chose whole-process translation and handles mixed-architecture needs out of process (XPC, AU hosting, extensions). It exposes one bit of truth, `sysctl.proc_translated`, to the guest.
- **Translation strategy.** It uses a hybrid of install-time or first-launch AOT, cached, signed and deterministic, plus in-process translation for dynamic code. The kernel hands control to a translator runtime instead of the guest dyld, and system calls are translated to native kernel calls.
- **Fidelity contract.** Page size, memory ordering, timebase and floating-point semantics must look like the source platform. Apple considered this important enough to add hardware help (4 KB pages; TSO bit, documented for Linux).
- **Explicit non-goals.** Kernel code, hypervisors, and some ISA extensions (AVX-512, and initially AVX/AVX2).
- **Tooling and lifecycle.** Debugger hand-off, AOT image info for tools, crash-report flags, run destinations, an on-demand installer, MDM controls, kill switches (`nox86exec`), and a published deprecation path.

---

## 11. Sources

### WWDC and Apple video (developer.apple.com)

- WWDC20 Keynote (101), Rosetta segment from about 1:38:57 (timestamps from Apple's caption track): https://developer.apple.com/videos/play/wwdc2020/101/
- WWDC20 Platforms State of the Union (102), from about 0:23:24 (caption track): https://developer.apple.com/videos/play/wwdc2020/102/
- WWDC20-10686 Explore the new system architecture of Apple silicon Macs: https://developer.apple.com/videos/play/wwdc2020/10686/
- WWDC20-10214 Port your Mac app to Apple silicon: https://developer.apple.com/videos/play/wwdc2020/10214/
- WWDC20-10631 Bring your Metal app to Apple silicon Macs: https://developer.apple.com/videos/play/wwdc2020/10631/
- WWDC20-10632 Optimize Metal Performance for Apple silicon Macs: https://developer.apple.com/videos/play/wwdc2020/10632/
- WWDC22-10002 Create macOS or Linux virtual machines: https://developer.apple.com/videos/play/wwdc2022/10002/
- WWDC22-10141 Explore USD tools and rendering: https://developer.apple.com/videos/play/wwdc2022/10141/
- WWDC23-10007 Create seamless experiences with Virtualization: https://developer.apple.com/videos/play/wwdc2023/10007/
- WWDC23-10123 Bring your game to Mac, Part 1: https://developer.apple.com/videos/play/wwdc2023/10123/
- WWDC23 Keynote (101) and Platforms State of the Union (102): https://developer.apple.com/videos/play/wwdc2023/101/, https://developer.apple.com/videos/play/wwdc2023/102/
- WWDC24 Platforms State of the Union (102): https://developer.apple.com/videos/play/wwdc2024/102/
- WWDC24-10089 Port advanced games to Apple platforms: https://developer.apple.com/videos/play/wwdc2024/10089/
- WWDC25 Platforms State of the Union (102): https://developer.apple.com/videos/play/wwdc2025/102/
- WWDC25-247 What's new in Xcode 26: https://developer.apple.com/videos/play/wwdc2025/247/
- WWDC25-209 Level up your games: https://developer.apple.com/videos/play/wwdc2025/209/
- WWDC26 Platforms State of the Union (102): https://developer.apple.com/videos/play/wwdc2026/102/
- WWDC26-356 Bringing Cyberpunk 2077 to Mac: https://developer.apple.com/videos/play/wwdc2026/356/
- WWDC26-357 Speedrun your game port with agentic coding: https://developer.apple.com/videos/play/wwdc2026/357/
- Meet with Apple 239 and 241: https://developer.apple.com/videos/play/meet-with-apple/239/, https://developer.apple.com/videos/play/meet-with-apple/241/

### Apple developer documentation

- About the Rosetta translation environment: https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment
- Porting your macOS apps to Apple silicon: https://developer.apple.com/documentation/apple-silicon/porting-your-macos-apps-to-apple-silicon
- Building a universal macOS binary: https://developer.apple.com/documentation/apple-silicon/building-a-universal-macos-binary
- Addressing architectural differences in your macOS code: https://developer.apple.com/documentation/apple-silicon/addressing-architectural-differences-in-your-macos-code
- Porting just-in-time compilers to Apple silicon: https://developer.apple.com/documentation/apple-silicon/porting-just-in-time-compilers-to-apple-silicon
- Porting your Metal code to Apple silicon: https://developer.apple.com/documentation/apple-silicon/porting-your-metal-code-to-apple-silicon
- Porting your audio code to Apple silicon: https://developer.apple.com/documentation/apple-silicon/porting-your-audio-code-to-apple-silicon
- Apple Silicon CPU Optimization Guide (landing page only): https://developer.apple.com/documentation/apple-silicon/cpu-optimization-guide
- LSRequiresNativeExecution: https://developer.apple.com/documentation/bundleresources/information-property-list/lsrequiresnativeexecution
- LSArchitecturePriority: https://developer.apple.com/documentation/bundleresources/information-property-list/lsarchitecturepriority
- NSWorkspace.OpenConfiguration.architecture: https://developer.apple.com/documentation/appkit/nsworkspace/openconfiguration/architecture
- NSRunningApplication.executableArchitecture: https://developer.apple.com/documentation/appkit/nsrunningapplication/executablearchitecture
- Bundle.executableArchitectures: https://developer.apple.com/documentation/foundation/bundle/executablearchitectures
- sysctlbyname: https://developer.apple.com/documentation/kernel/1387446-sysctlbyname
- Examining the fields in a crash report: https://developer.apple.com/documentation/xcode/examining-the-fields-in-a-crash-report
- Interpreting the JSON format of a crash report: https://developer.apple.com/documentation/xcode/interpreting-the-json-format-of-a-crash-report
- TN3117 Resolving architecture build errors on Apple silicon: https://developer.apple.com/documentation/technotes/tn3117-resolving-build-errors-for-apple-silicon
- Downloading and installing additional Xcode components: https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components
- Running Intel Binaries in Linux VMs: https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms
- Accelerating the performance of Rosetta: https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta
- VZLinuxRosettaDirectoryShare: https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare
- installRosetta(completionHandler:): https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare/installrosetta(completionhandler:)
- VZLinuxRosettaAvailability: https://developer.apple.com/documentation/virtualization/vzlinuxrosettaavailability
- VZLinuxRosettaCachingOptions: https://developer.apple.com/documentation/virtualization/vzlinuxrosettacachingoptions
- VZLinuxRosettaUnixSocketCachingOptions: https://developer.apple.com/documentation/virtualization/vzlinuxrosettaunixsocketcachingoptions
- VZLinuxRosettaAbstractSocketCachingOptions: https://developer.apple.com/documentation/virtualization/vzlinuxrosettaabstractsocketcachingoptions
- VZLinuxRosettaDirectoryShare.CachingOptions: https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare/cachingoptions-swift.enum
- Running GUI Linux in a virtual machine on a Mac: https://developer.apple.com/documentation/virtualization/running-gui-linux-in-a-virtual-machine-on-a-mac
- macOS Big Sur 11.0.1 Universal Apps (DTK) release notes: https://developer.apple.com/documentation/macos-release-notes/macos-big-sur-11_0_1-universal-apps-release-notes
- macOS release notes: 14 https://developer.apple.com/documentation/macos-release-notes/macos-14-release-notes ; 15 https://developer.apple.com/documentation/macos-release-notes/macos-15-release-notes ; 26 https://developer.apple.com/documentation/macos-release-notes/macos-26-release-notes ; 26.4 https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes ; 26.6 https://developer.apple.com/documentation/macos-release-notes/macos-26_6-release-notes ; 27 https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes
- Xcode release notes: 12.3 https://developer.apple.com/documentation/xcode-release-notes/xcode-12_3-release-notes ; 13 https://developer.apple.com/documentation/xcode-release-notes/xcode-13-release-notes ; 13.3 https://developer.apple.com/documentation/xcode-release-notes/xcode-13_3-release-notes ; 14 https://developer.apple.com/documentation/xcode-release-notes/xcode-14-release-notes ; 14.3 https://developer.apple.com/documentation/xcode-release-notes/xcode-14_3-release-notes ; 16 https://developer.apple.com/documentation/xcode-release-notes/xcode-16-release-notes ; 26.4 https://developer.apple.com/documentation/xcode-release-notes/xcode-26_4-release-notes ; 27 https://developer.apple.com/documentation/xcode-release-notes/xcode-27-release-notes
- Game Porting Toolkit page: https://developer.apple.com/games/game-porting-toolkit/

### Apple Developer News and Forums

- Upcoming changes to Rosetta support for Intel-based macOS apps (2026-09-01): https://developer.apple.com/news/?id=w5ngl9k2
- App Store submissions now open for the latest OS releases (2026-09-09): https://developer.apple.com/news/?id=k1mtkt1k
- Forum thread 701913 (DTS: child processes stay in "Rosetta mode"): https://developer.apple.com/forums/thread/701913
- Forum thread 830692 (Apple engineer on the macOS 28 games subset): https://developer.apple.com/forums/thread/830692

### Apple Support, Platform Security and Deployment

- Using Intel-based apps on a Mac with Apple silicon (102527, formerly HT211861): https://support.apple.com/en-us/102527
- Rosetta 2 on a Mac with Apple silicon (Apple Platform Security): https://support.apple.com/guide/security/rosetta-2-on-a-mac-with-apple-silicon-secebb113be1/web
- Data Protection classes (Apple Platform Security): https://support.apple.com/guide/security/data-protection-classes-secb010e978a/web
- Review device management restrictions (Apple Platform Deployment): https://support.apple.com/guide/deployment/review-device-management-restrictions-dep739685973/web
- What's new for enterprise in macOS Tahoe 26: https://support.apple.com/en-us/124963
- What's new for enterprise in macOS Golden Gate 27: https://support.apple.com/en-us/148830
- How to upgrade to macOS 27 Golden Gate: https://support.apple.com/en-us/127455
- Third-party Audio Units in Logic Pro and Final Cut Pro (102082): https://support.apple.com/en-us/102082
- Turn off Rosetta for Logic Pro (121464): https://support.apple.com/en-us/121464

### Apple Newsroom

- Apple announces Mac transition to Apple silicon (2020-06-22): https://www.apple.com/newsroom/2020/06/apple-announces-mac-transition-to-apple-silicon/
- Apple unleashes M1 (2020-11-10): https://www.apple.com/newsroom/2020/11/apple-unleashes-m1/
- Introducing the next generation of Mac (2020-11-10): https://www.apple.com/newsroom/2020/11/introducing-the-next-generation-of-mac/
- macOS Big Sur is here (2020-11-12): https://www.apple.com/newsroom/2020/11/macos-big-sur-is-here/

### Apple open source and man pages

- XNU `bsd/kern/kern_sysctl.c`: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_sysctl.c
- XNU `bsd/kern/kern_proc.c`: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_proc.c
- XNU `bsd/kern/kern_exec.c`: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exec.c
- XNU `bsd/kern/mach_loader.c`: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/mach_loader.c
- XNU `bsd/sys/proc.h`: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/proc.h
- XNU `osfmk/arm/cpu_x86_64_capabilities.h`: https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm/cpu_x86_64_capabilities.h
- XNU `posix_spawnattr_setarchpref_np.3`: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/man/man3/posix_spawnattr_setarchpref_np.3
- dyld `include/mach-o/dyld_images.h`: https://github.com/apple-oss-distributions/dyld/blob/main/include/mach-o/dyld_images.h
- system_cmds `arch/arch.1`: https://github.com/apple-oss-distributions/system_cmds/blob/main/arch/arch.1
- system_cmds `arch/arch.c`: https://github.com/apple-oss-distributions/system_cmds/blob/main/arch/arch.c
- libpthread `man/pthread_jit_write_protect_np.3`: https://github.com/apple-oss-distributions/libpthread/blob/main/man/pthread_jit_write_protect_np.3
- apple/device-management `com.apple.applicationaccess.yaml`: https://github.com/apple/device-management/blob/release/mdm/profiles/com.apple.applicationaccess.yaml
- apple/containerization: https://github.com/apple/containerization
- apple/container `Application.swift`: https://github.com/apple/container/blob/main/Sources/ContainerCommands/Application.swift
- apple/homebrew-apple `game-porting-toolkit.rb`: https://github.com/apple/homebrew-apple/blob/main/Formula/game-porting-toolkit.rb
- LLDB (LLVM, largely Apple-maintained) `DNB.cpp`: https://github.com/llvm/llvm-project/blob/main/lldb/tools/debugserver/source/DNB.cpp
- LLDB `TestRosetta.py`: https://github.com/llvm/llvm-project/blob/main/lldb/test/API/macosx/rosetta/TestRosetta.py
- LLDB `crashlog.py`: https://github.com/llvm/llvm-project/blob/main/lldb/examples/python/crashlog.py
- Man page mirror (third-party mirror of Apple man pages): `softwareupdate(8)` https://keith.github.io/xcode-man-pages/softwareupdate.8.html ; `productbuild(1)` https://keith.github.io/xcode-man-pages/productbuild.1.html ; `posix_spawnattr_setarchpref_np(3)` https://keith.github.io/xcode-man-pages/posix_spawnattr_setarchpref_np.3.html ; `pthread_jit_write_protect_np(3)` https://keith.github.io/xcode-man-pages/pthread_jit_write_protect_np.3.html

### Wayback Machine captures used for document history

- About doc JSON:
  - 2020-11-01: https://web.archive.org/web/20201101145333/https://developer.apple.com/tutorials/data/documentation/apple_silicon/about_the_rosetta_translation_environment.json
  - 2025-06-09: https://web.archive.org/web/20250609074056/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json
  - 2025-06-11: https://web.archive.org/web/20250611040604/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json
  - 2025-09-18: https://web.archive.org/web/20250918164601/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json
  - 2025-10-28: https://web.archive.org/web/20251028174555/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json
  - 2026-07-15: https://web.archive.org/web/20260715042841/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json
  - 2026-08-15: https://web.archive.org/web/20260815045008/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json
- Support HT211861:
  - 2020-11-17: https://web.archive.org/web/20201117204544/https://support.apple.com/en-us/HT211861
  - 102527, 2026-06-11: https://web.archive.org/web/20260611164206/https://support.apple.com/en-us/102527
- Accelerating the performance of Rosetta, first capture 2025-01-18: https://web.archive.org/web/20250118101055/https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta
- Running Intel Binaries in Linux VMs with Rosetta, 2022-06-06: https://web.archive.org/web/20220606193608/https://developer.apple.com/documentation/virtualization/running_intel_binaries_in_linux_vms_with_rosetta
- DTK Universal Apps beta 5 notes, 2020-08-28: https://web.archive.org/web/20200828035411/https://developer.apple.com/tutorials/data/documentation/macos-release-notes/macos-big-sur-11-universal-apps-beta-release-notes.json
- Big Sur 11.0.1 beta notes, 2020-11-02: https://web.archive.org/web/20201102022443/https://developer.apple.com/tutorials/data/documentation/macos-release-notes/macos-big-sur-11_0_1-beta-release-notes.json

### Third-party (flagged; used only as noted)

- Community copy of Apple's Game Porting Toolkit 2.x "Read Me.rtf": https://gist.github.com/lynkos/3999f629560219a81d4e2c083a4bf5b1
- sljit issue #99, quoting an Apple DTS email on RWX pages under Rosetta: https://github.com/zherczeg/sljit/issues/99
