# 06 — History and timeline of Rosetta

Scope: Apple's earlier instruction-set transitions (the 68K emulator, Rosetta 1), Rosetta 2 from its
2020 announcement to the plans Apple has published for macOS 28, and other translators for
context. Research cut-off: 31 October 2026, when macOS 27.2 "Golden Gate" is current. Every
version number and date below was checked against an Apple page (release notes, security-release
lists, newsroom) where one exists; dates that rest only on secondary sources are marked.

Related documents in this folder: `02-architecture-and-runtime.md` (how the macOS runtime works),
`04-hardware-assists.md` (CPU features), `05-rosetta-for-linux.md` (the Linux VM feature in
detail).

Provenance labels: **[Apple]** = Apple documentation, release notes, WWDC sessions, press
releases, or public posts by identifiable Apple engineers (marked as such); **[press]** =
journalism and established independent technical blogs (Wikipedia is marked separately as
"secondary"); **[RE: author]** = reverse engineering or hands-on testing by the named author;
**[project docs]** = third-party project documentation, source or issue threads;
**[Inferred]** = my own conclusion from the cited material; **[forum]** = community forum posts,
used only as corroboration. Numbers in square brackets link to the Sources list.

---

## 1. Precedent: the 68K emulator on PowerPC Macs (1994–1995)

- **Launch.** The first Power Macintosh models (6100, 7100, 8100) were introduced on 14 March 1994
  **[press]** [[2]](https://tidbits.com/1994/03/14/the-power-macintosh-picture/), shipping with
  System 7.1.2 **[secondary: Wikipedia]** [[8]](https://en.wikipedia.org/wiki/System_7).
- **Design.** Apple's *Inside Macintosh: PowerPC System Software* describes two cooperating parts:
  the **68LC040 Emulator**, which converts 680x0 instructions into PowerPC instructions and keeps an
  emulated 680x0 register state, and the **Mixed Mode Manager**, which switches between emulated
  and native code whenever either calls the other. This let 68K applications, drivers and even
  unported parts of the OS run unchanged alongside native code **[Apple]**
  [[1]](https://developer.apple.com/library/archive/documentation/mac/pdf/PPC_System_Software/Intro_to_PowerPC.pdf).
- **Origin.** Gary Davidian began the emulator in 1990, first on a Motorola 88000 prototype, before
  the 1991 Apple–IBM–Motorola PowerPC alliance moved it to PowerPC **[press]**
  [[3]](https://computerhistory.org/blog/transplanting-the-macs-central-processor-gary-davidian-and-his-68000-emulator/).
- **Performance at launch.** *Microprocessor Report* estimated about ten PowerPC instructions per
  emulated 680x0 instruction, and 15–35% of native speed for typical emulated applications, helped
  by Apple porting the most-used Toolbox routines to native code **[press]**
  [[4]](http://ardent-tool.com/CPU/docs/MPR/19940328/080401.pdf).
- **Dynamic recompilation (1995).** Apple Technote PT 39, written by Eric Traut in February 1995,
  describes a "dynamic recompiling emulator" for the next Power Macs: it translates 68K code into
  PowerPC code held in a translation cache instead of decoding every instruction each time
  **[Apple]** [[5]](https://preterhuman.net/macstuff/technotes/pt/pt_39.html). It shipped with the
  PCI-based Power Macs and needed their ROMs **[press]**
  [[6]](https://tidbits.com/1996/07/08/fishing-for-chips-part-2/); the first of these, the Power
  Macintosh 9500, came with System 7.5.2 on 19 June 1995 **[secondary: Wikipedia]**
  [[8]](https://en.wikipedia.org/wiki/System_7). Traut's related Apple patent has a priority date
  of 8 November 1995 **[project docs: patent]** [[7]](https://patents.google.com/patent/US5790825A/en).

**[Inferred]** Two ideas from 1994–95 return in Rosetta 2: a translation cache to avoid repeating
work, and native implementations of OS services so that only application code is translated.

---

## 2. Rosetta (PowerPC → x86, 2005–2011)

### 2.1 Announcement and first release

- **6 June 2005, WWDC.** Apple announced Intel-based Macs for 2006 and a $999 Developer Transition
  Kit **[Apple]** [[9]](https://www.apple.com/newsroom/2005/06/06Apple-to-Use-Intel-Microprocessors-Beginning-in-2006/).
  Steve Jobs demonstrated Rosetta running unmodified PowerPC builds of Microsoft Office and
  Photoshop **[press]** [[10]](https://appleinsider.com/articles/05/06/06/apple_confirms_switch_to_intel).
- **10 January 2006.** The first Intel iMac shipped with Mac OS X 10.4.4 Tiger, which Apple said
  "includes an innovative software translation technology called Rosetta" **[Apple]**
  [[15]](https://www.apple.com/newsroom/2006/01/10Apple-Unveils-New-iMac-with-Intel-Core-Duo-Processor/).
  Apple's product page promised: "You'll never see it, you'll never configure it, you'll never have
  to think about it." **[Apple]** [[16]](https://web.archive.org/web/20060113055505/http://www.apple.com/rosetta/)
  The same page listed Apple's own pro apps (Final Cut Pro, Logic Pro, Aperture and others) as
  *not* supported under Rosetta.

### 2.2 QuickTransit and Transitive

- On 8 June 2005 CNET reported that the start-up Transitive supplied the engine inside Rosetta;
  its CEO, Bob Wiederhold, said "We've had a long-term relationship with them" **[press]**
  [[11]](https://web.archive.org/web/20160301203848/http://www.cnet.com/news/the-brains-behind-apples-rosetta-transitive/).
  The same article quoted an analyst's scepticism that binary translation "basically doesn't
  work".
- Transitive's product was **QuickTransit**, a dynamic translator that works on blocks of code and
  keeps translations in memory for reuse **[press]**
  [[12]](https://spectrum.ieee.org/how-old-apps-will-run-on-new-macs). QuickTransit grew out of
  the University of Manchester's "Dynamite" research **[secondary: Wikipedia]**
  [[24]](https://en.wikipedia.org/wiki/QuickTransit). CNET named SGI as Transitive's first
  customer **[press]**
  [[11]](https://web.archive.org/web/20160301203848/http://www.cnet.com/news/the-brains-behind-apples-rosetta-transitive/);
  SGI used it to run MIPS/IRIX binaries on Itanium/Linux systems **[secondary: Wikipedia]**
  [[24]](https://en.wikipedia.org/wiki/QuickTransit).
- **IBM.** On 18–19 November 2008 IBM announced it would acquire Transitive (Los Gatos, California,
  with R&D in Manchester) and use the technology to move x86 Linux workloads onto its Power
  servers, where it already shipped as part of IBM's PowerVM software **[press]**
  [[21]](https://arstechnica.com/information-technology/2008/11/ibm-to-buy-transitive/),
  [[22]](https://www.theregister.com/2008/11/19/ibm_buys_transitive),
  [[23]](https://www.infoworld.com/article/2317779/ibm-s-virtualization-plans-include-transitive.html).

### 2.3 What Rosetta 1 could and could not do

Apple's *Universal Binary Programming Guidelines* (second edition) give the shipped scope
**[Apple]** [[13]](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/universal_binary/universal_binary_exec_a/universal_binary_exec_a.html):

- It targeted Mac OS X applications (CFM or Mach-O) that run on a **G3 or G4** processor.
- It did not run: pre-Mac OS X software or the Classic environment; applications that require a
  **G5**; kernel extensions or apps that depend on PowerPC-only ones; PowerPC screen savers and
  preference panes; Java applications with JNI libraries.
- It did not support precise exceptions (handlers that rely on exact register state).
- It ran in the same thread as the application, translating blocks as they were reached and caching
  translations for reuse; a process ran either entirely native or entirely translated.

The June 2005 developer documentation was narrower: Macworld reported then that Rosetta would not
support G4-specific features or AltiVec (PowerPC's vector unit) **[press]**
[[14]](https://www.macworld.com/article/175923/intelfaq.html). **[Inferred]** Support for G4 code
was added between the June 2005 preview and the shipping documentation.

### 2.4 Optional, then removed

- **Mac OS X 10.6 Snow Leopard (28 August 2009).** Rosetta was no longer installed by default; it
  was a custom install option or was offered when a PowerPC app was first opened **[press]**
  [[17]](https://www.engadget.com/2009-08-27-getting-ready-for-snow-leopard-think-about-your-applications.html),
  [[18]](https://www.macworld.com/article/150693/snow_leopard_which_apps_wont_run.html).
- **Mac OS X 10.7 Lion.** Developer previews in February 2011 had no Rosetta **[press]**
  [[19]](https://appleinsider.com/articles/11/02/26/mac_os_x_lion_drops_front_row_java_runtime_rosetta);
  Lion shipped on 20 July 2011 **[Apple]**
  [[20]](https://www.apple.com/newsroom/2011/07/20Mac-OS-X-Lion-Available-Today-From-the-Mac-App-Store/).
  Rosetta was therefore present in Mac OS X 10.4, 10.5 and 10.6, about five years in total
  **[press]** [[51]](https://arstechnica.com/gadgets/2025/06/apple-details-the-end-of-intel-mac-support-and-a-phaseout-for-rosetta-2/).

---

## 3. Rosetta 2, release by release

Apple does not publish version numbers for Rosetta 2 itself; changes are tied to macOS releases
and to Apple's documentation **[Inferred]**. Dates of macOS releases below come from Apple's
security-release lists [[28]](https://support.apple.com/en-us/120989),
[[29]](https://support.apple.com/en-us/121012), [[30]](https://support.apple.com/en-us/100100).

### 3.1 Announcement and macOS 11 Big Sur (2020)

- **22 June 2020, WWDC20.** Apple announced the move to Apple silicon. Its press release says
  "the translation technology of Rosetta 2" lets users run Mac apps not yet updated, including
  ones with plug-ins, and introduced a Developer Transition Kit built on the A12Z chip **[Apple]**
  [[25]](https://www.apple.com/newsroom/2020/06/apple-announces-mac-transition-to-apple-silicon/).
- **10–17 November 2020.** Apple introduced the first M1 Macs on 10 November **[Apple]**
  [[26]](https://www.apple.com/newsroom/2020/11/introducing-the-next-generation-of-mac/), released
  macOS Big Sur 11.0.1 on 12 November, and listed a separate 11.0.1 build for the M1 models on
  17 November **[Apple]** [[27]](https://www.apple.com/newsroom/2020/11/macos-big-sur-is-here/),
  [[28]](https://support.apple.com/en-us/120989).
- Rosetta 2 is not preinstalled: macOS offers to install it the first time an Intel app opens, or
  an administrator runs `softwareupdate --install-rosetta` **[Apple]**
  [[61]](https://support.apple.com/en-us/102527), **[press]**
  [[84]](https://derflounder.wordpress.com/2020/11/17/installing-rosetta-2-on-apple-silicon-macs/).
- Apple's statement of limits, quoted by developers in July 2020 and unchanged in the January 2024
  archive: no kernel extensions, no virtual-machine apps that virtualise x86-64 computers, and no
  AVX, AVX2 or AVX-512 **[Apple]**
  [[32]](https://web.archive.org/web/20240119013640/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json),
  **[forum]** [[91]](https://developer.apple.com/forums/thread/653902).
  Big Sur's new rule that all arm64 code must be signed did not apply to translated x86 binaries
  **[Apple]** [[33]](https://developer.apple.com/documentation/macos-release-notes/macos-big-sur-11_0_1-universal-apps-release-notes).
  How the runtime works (ahead-of-time translation at first launch, JIT for generated code, the
  `oahd` service) is covered in `02-architecture-and-runtime.md`.

### 3.2 macOS 13 Ventura (2022): Rosetta for Linux VMs

- **6 June 2022, WWDC22.** Apple announced that the Virtualization framework could give ARM64
  Linux guests access to Rosetta, "the same technology we have been using on the Mac", and
  published its guide the same day **[Apple]**
  [[34]](https://developer.apple.com/videos/play/wwdc2022/10002/),
  [[35]](https://web.archive.org/web/20220606194510/https://developer.apple.com/tutorials/data/documentation/virtualization/running_intel_binaries_in_linux_vms_with_rosetta.json).
- **24 October 2022.** Ventura shipped; `VZLinuxRosettaDirectoryShare` is marked macOS 13.0+
  **[Apple]** [[36]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare),
  [[29]](https://support.apple.com/en-us/121012). Ventura's Rosetta package gained a `RosettaLinux`
  folder **[press]** [[37]](https://eclecticlight.co/2022/12/10/explainer-rosetta-2/). Details are
  in `05-rosetta-for-linux.md`.

### 3.3 macOS 14 Sonoma (2023): Linux caching and the Game Porting Toolkit

- **5 June 2023, WWDC23.** Apple announced ahead-of-time translation caching for Linux guests,
  served by a new daemon in the VM **[Apple]**
  [[38]](https://developer.apple.com/videos/play/wwdc2023/10007/), and the **Game Porting
  Toolkit** (GPTK). Its evaluation environment translates a Windows game's Intel instructions
  and Windows API calls so developers can test unmodified Windows builds on a Mac **[Apple]**
  [[39]](https://developer.apple.com/videos/play/wwdc2023/10123/). The toolkit's instructions say
  the environment "runs under Rosetta 2", inside an x86-64 Homebrew installation of a custom Wine
  build **[Apple, README copy]** [[40]](https://gist.github.com/lynkos/3999f629560219a81d4e2c083a4bf5b1).
- **26 September 2023.** Sonoma shipped; the Linux caching APIs are marked macOS 14.0+ **[Apple]**
  [[41]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettacachingoptions),
  [[29]](https://support.apple.com/en-us/121012).
- **7 March 2024, macOS 14.4.** According to an Apple engineer's Linux kernel patch posting, this
  is the first host version that lets a Linux guest change the CPU's TSO bit **[Apple engineer,
  LKML via LWN]** [[42]](https://lwn.net/Articles/969480/), [[30]](https://support.apple.com/en-us/100100).
  Apple's own release notes do not mention it.
- **April 2024.** Two patch series for TSO control in Linux appeared a day apart, one from Apple
  (Zayd Qumsieh) for Linux VMs and one from Asahi Linux (Hector Martin); arm64 maintainers objected
  **[press]** [[43]](https://lwn.net/Articles/970907/). Neither is in mainline Linux as of
  October 2026 (see `05-rosetta-for-linux.md`, section 6).

### 3.4 macOS 15 Sequoia (2024): AVX and AVX2

- **10 June 2024, WWDC24.** Apple announced Game Porting Toolkit 2; its session says Windows games
  that use AVX instructions can now be evaluated **[Apple]**
  [[44]](https://developer.apple.com/videos/play/wwdc2024/10089/). Press coverage tied this to AVX2
  support in Sequoia's Rosetta **[press]**
  [[45]](https://www.macg.co/macos/2024/06/rosetta-2-va-etre-plus-efficace-avec-macos-sequoia-et-cest-important-pour-les-jeux-144245).
- **16 September 2024.** Sequoia shipped **[Apple]** [[30]](https://support.apple.com/en-us/100100).
  Its release notes list a fix for Intel binaries failing to run in VMs on Apple silicon
  **[Apple]** [[47]](https://developer.apple.com/documentation/macos-release-notes/macos-15-release-notes).
- **How AVX was exposed.** The GPTK documentation describes `ROSETTA_ADVERTISE_AVX`: on Sequoia,
  setting it to 1 makes the translation layer report AVX support in `cpuid` inside the evaluation
  environment; it does not change what Rosetta can execute **[Apple, README copy]**
  [[40]](https://gist.github.com/lynkos/3999f629560219a81d4e2c083a4bf5b1). CodeWeavers'
  CrossOver tips tell users to set the variable for games that require AVX **[project docs]**
  [[46]](https://www.codeweavers.com/compatibility/crossover/tips/death-stranding/enabling-avx-support-for-death-stranding).
  A December 2024 report found an AVX2 build still failing with an illegal-instruction error on
  macOS 15.1.1; the maintainers attributed it to BMI1 instructions that the build also uses
  **[project docs]** [[48]](https://github.com/official-stockfish/Stockfish/issues/5707).
- **Documentation lag.** On 30 January 2025 an Apple engineer wrote that Sequoia's Rosetta supports
  AVX and AVX2 but not AVX-512, and that the documentation team had been asked to update the page
  **[Apple engineer, Swift Forums]** [[49]](https://forums.swift.org/t/minimum-supported-development-environment/77565/14).
  Archived copies show the page still listing AVX/AVX2 as unsupported on 18 September 2025 and the
  new wording ("including ones from the AVX and AVX2 instruction set") by 28 October 2025 **[Apple]**
  [[32]](https://web.archive.org/web/20250918164601/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json),
  [[31]](https://web.archive.org/web/20251028174555/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json).
- **Linux kernel patch (late 2024).** Apple published "Accelerating the performance of Rosetta" and
  a downloadable TSO patch for Linux 6.10 guests **[Apple]**
  [[50]](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta).
- **2025 regression.** With Linux 6.13 and later guest kernels, Rosetta on macOS 15.x hosts failed;
  Podman switched Rosetta off by default in August 2025 and reported the problem fixed in the
  macOS Tahoe betas **[project docs]**
  [[52]](https://blog.podman.io/2025/08/podman-5-6-released-rosetta-status-update/),
  [[53]](https://github.com/lima-vm/lima/issues/3592).

### 3.5 WWDC25 and macOS 26 Tahoe (2025): the end is announced

- **9 June 2025, WWDC25.** Apple said macOS Tahoe would be the last release for Intel Macs, and
  that Rosetta would stay a general-purpose tool through macOS 27; after that Apple will keep "a
  subset of Rosetta functionality aimed at supporting older unmaintained gaming titles, that rely
  on Intel-based frameworks" **[Apple]**
  [[54]](https://web.archive.org/web/20250611040604/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json),
  **[press]** [[55]](https://www.macrumors.com/2025/06/10/apple-to-phase-out-rosetta-2/),
  [[51]](https://arstechnica.com/gadgets/2025/06/apple-details-the-end-of-intel-mac-support-and-a-phaseout-for-rosetta-2/).
  The statement first appeared in Apple's developer documentation between 9 and 11 June 2025
  (archived copies); press reports place it in the Platforms State of the Union **[press]**
  [[56]](https://www.macrumors.com/2026/06/10/macos-golden-gate-last-to-support-intel-apps/).
- **Same day.** Apple released its open-source Containerization framework and `container` tool,
  which use Rosetta to run `linux/amd64` containers **[project docs]**
  [[57]](https://github.com/apple/containerization), [[58]](https://github.com/apple/container/releases).
- **15 September 2025.** Tahoe shipped **[Apple]** [[30]](https://support.apple.com/en-us/100100).
  Its release notes add a test switch: with the boot argument `nox86exec=1`, any process that would
  run through Rosetta crashes at launch and leaves a crash report, so developers can find hidden
  Intel dependencies **[Apple]** [[59]](https://developer.apple.com/documentation/macos-release-notes/macos-26-release-notes).
- **24 March 2026, macOS 26.4.** Users are now notified when they launch apps that use Rosetta;
  organisations can control this with the device-management key `allowRosettaUsageAwareness`.
  Apple restated that Rosetta for apps ends after macOS 27 and that support continues for older
  unmaintained games and for Intel binaries in Linux VMs **[Apple]**
  [[60]](https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes),
  [[30]](https://support.apple.com/en-us/100100). Press reports describe the alerts in 26.4 and
  26.5 **[press]** [[56]](https://www.macrumors.com/2026/06/10/macos-golden-gate-last-to-support-intel-apps/).

### 3.6 WWDC26 and macOS 27 Golden Gate (2026): the last general-purpose release

- **8 June 2026, WWDC26.** Apple previewed macOS 27, named Golden Gate **[Apple]**
  [[62]](https://www.apple.com/newsroom/2026/06/apple-unveils-next-generation-of-apple-intelligence-siri-ai-and-more/),
  [[63]](https://developer.apple.com/videos/play/wwdc2026/101/). Related changes:
  - **Linux translation built in.** Apple's Virtualization guide says macOS 27 integrates Intel
    binary translation for Linux guests, with no Rosetta install; `availability` always reports
    `.installed` **[Apple]** [[64]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).
  - **Legacy-game test mode.** A beta-only command, `sudo game-test-tool enable`, runs legacy Intel
    games "through the new underlying system behavior"; enabling it disables Rosetta, and other
    processes may crash **[Apple]** [[65]](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes).
    A tester found that the macOS 27 beta's Intel-app warnings skip apps whose `Info.plist`
    declares the games category (`LSApplicationCategoryType`) **[RE: ngyikp]**
    [[66]](https://ngyikp.com/legacy-intel-apps-games-rosetta-on-macos-27-golden-gate/).
  - **Game Porting Toolkit 4.** Its evaluation environment adds Metal 4 support **[Apple]**
    [[67]](https://developer.apple.com/games/game-porting-toolkit/).
- **1 September 2026.** Apple's developer news called macOS 27 the "final release to support
  Rosetta" for Intel-only apps, while older unmaintained games keep support **[Apple]**
  [[68]](https://developer.apple.com/news/?id=w5ngl9k2).
- **14 September 2026, macOS 27.0.** Golden Gate shipped, for Apple silicon Macs only **[Apple]**
  [[69]](https://www.apple.com/newsroom/2026/09/major-updates-for-apples-software-platforms-are-now-available/),
  [[30]](https://support.apple.com/en-us/100100). Rosetta-related changes in its notes **[Apple]**
  [[65]](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes),
  [[70]](https://support.apple.com/en-us/148830):
  - an existing Rosetta installation is not restored after upgrading to 27.0;
  - apps that a user had set to "Open using Rosetta" now launch natively;
  - Settings → General lists Intel-based apps that will not work in macOS 28, and Get Info shows a
    warning for them;
  - installer packages that name no host architecture now default to arm64.
- **26 October 2026, macOS 27.2.** Apple's enterprise notes say Rosetta is no longer removed when
  upgrading to macOS 27 **[Apple]** [[70]](https://support.apple.com/en-us/148830),
  [[30]](https://support.apple.com/en-us/100100), **[press]**
  [[71]](https://www.macrumors.com/2026/10/27/macos-27-2-stops-removing-rosetta/).

### 3.7 After macOS 27

Apple's support article (updated 21 September 2026) says Rosetta is available on Apple silicon Macs
running macOS 27 or earlier, and that from macOS 28 its functionality will be available only for
certain older, unmaintained games that rely on Intel-based frameworks **[Apple]**
[[61]](https://support.apple.com/en-us/102527). Separately, Apple's macOS 26.4 notes say Intel
binaries in Linux VMs remain supported **[Apple]**
[[60]](https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes).
Apple has not said which games qualify or how the reduced translator will differ (see Open
questions).

---

## 4. Related translators, for context

Each of these is a separate product with its own design; the notes only show where Rosetta sits
among them.

- **Microsoft, Windows on Arm.**
  - Windows 10 on ARM launched in late 2017 with emulation of 32-bit x86 apps only; x64 emulation
    reached Insiders in build 21277 on 10 December 2020 and became generally available in
    Windows 11 **[project docs: Microsoft]**
    [[72]](https://blogs.windows.com/windows-insider/2020/12/10/introducing-x64-emulation-in-preview-for-windows-10-on-arm-pcs-to-the-windows-insider-program/).
  - **Prism** is the emulator in Windows 11 24H2 (2024). It JIT-compiles blocks of x86 code into
    Arm64 and a service caches the results per module; system binaries are "Arm64X" files that load
    into both x64 and Arm64 processes **[project docs: Microsoft]**
    [[73]](https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-x86-emulation),
    [[74]](https://devblogs.microsoft.com/directx/step-forward-for-gaming-on-arm-devices-2024/).
  - Prism added AVX, AVX2, BMI, FMA and F16C for x64 apps in Insider build 27744 (6 November 2024)
    and rolled this out to all Windows 11 24H2+ Arm devices in late 2025 **[project docs:
    Microsoft]** [[75]](https://blogs.windows.com/windows-insider/2024/11/06/announcing-windows-11-insider-preview-build-27744-canary-channel/),
    [[76]](https://techcommunity.microsoft.com/blog/windowsosplatform/windows-on-arm-runs-more-apps-and-games-with-new-prism-update/4475631).
  - Microsoft describes Prism's handling of memory ordering in terms of the memory barriers it
    inserts: per-app settings trade speed for safety by adding more barriers, or force single-core
    execution so no barriers are needed **[project docs: Microsoft]**
    [[77]](https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-program-compat-troubleshooter).
    **[Inferred]** This is the main architectural contrast with Rosetta, which can rely on Apple
    silicon's TSO mode (see `04-hardware-assists.md`).
- **Intel Houdini and Intel Bridge Technology.** Houdini is Intel's proprietary ARM-to-x86
  translator that let ARM-only Android native code run on Intel-based Android devices around
  2012–2013 **[press]** [[78]](https://commonsware.com/blog/2013/11/21/libhoudini-what-it-means-for-developers.html).
  A 2021 analysis found it to be an interpreter rather than a JIT, hooked into Android's
  NativeBridge for libraries and `binfmt_misc` for executables **[RE: Brian Hong, NCC Group]**
  [[79]](https://media.defcon.org/DEF%20CON%2029/DEF%20CON%2029%20presentations/Brian%20Hong%20-%20Sleight%20of%20ARM%20-%20%20Demystifying%20Intel%20Houdini.pdf).
  Intel's later Intel Bridge Technology (2021), described as a "runtime post-compiler", was used by
  Microsoft's Windows Subsystem for Android so ARM-only apps could run on Intel and AMD PCs
  **[project docs: Intel, Microsoft]**
  [[80]](https://www.intc.com/news-events/press-releases/detail/1479/intel-core-processors-and-intel-bridge-technology-unleash),
  [[81]](https://blogs.windows.com/windows-insider/2021/10/20/introducing-android-apps-on-windows-11-to-windows-insiders/).
- **FEX-Emu.** An open-source user-mode x86 and x86-64 emulator for Arm64 Linux. Its first commit
  was on 28 November 2018 and Valve has funded it from the start **[project docs]**
  [[82]](https://fex-emu.com/FEXiversary/). It forwards OpenGL/Vulkan calls to host libraries, has
  a code cache, and lets users skip "costly memory model emulation" per app **[project docs]**
  [[83]](https://github.com/FEX-Emu/FEX). Valve uses it in SteamOS on the Arm-based Steam Frame
  **[press]** [[85]](https://arstechnica.com/gaming/2026/09/not-just-proton-getting-to-know-valves-new-steamos-compatibility-layers/).
- **Box86 / Box64.** User-space x86 (Box86, repository created January 2019) and x86-64 (Box64,
  December 2020) emulators for Linux on Arm, with Box64 also targeting RISC-V and LoongArch. Their
  "twist" is calling native system libraries (libc, libm, SDL, OpenGL) instead of emulating them,
  plus a dynamic recompiler **[project docs]** [[86]](https://github.com/ptitSeb/box64),
  [[87]](https://github.com/ptitSeb/box86).
- **QEMU user mode.** QEMU's first preview release was in 2003 **[secondary: Wikipedia]**
  [[88]](https://en.wikipedia.org/wiki/QEMU). Its user-mode emulator runs a Linux process built for
  one CPU on another, translating system calls; the 2005 USENIX paper measured QEMU 0.4.2's user
  mode at about 4x slower than native on integer code **[project docs]**
  [[89]](https://www.usenix.org/legacy/publications/library/proceedings/usenix05/tech/freenix/full_papers/bellard/bellard.pdf).
  QEMU's documentation warns that host/guest memory-model differences can break software that
  assumes a particular model **[project docs]** [[90]](https://www.qemu.org/docs/master/user/main.html).
  Rosetta for Linux uses the same `binfmt_misc` registration pattern as QEMU (see
  `05-rosetta-for-linux.md`, section 4.2).

**[Inferred]** Common ground: all of these (QEMU in its user mode) handle user-mode code only and
keep the host kernel native, and most cache translated code (Houdini, per the 2021 analysis,
interprets instead). Rosetta 2 differs mainly in being tied to one host CPU family whose
designer added translation aids in hardware (`04-hardware-assists.md`), and in being scheduled for
withdrawal by its vendor once the transition it served is complete, as Rosetta 1 was.

---

## 5. Timeline

| Date | Mac OS / macOS version | Change | Source |
|---|---|---|---|
| 14 Mar 1994 | System 7.1.2 | First Power Macs ship with the 68LC040 emulator and Mixed Mode Manager | **[Apple]** [[1]](https://developer.apple.com/library/archive/documentation/mac/pdf/PPC_System_Software/Intro_to_PowerPC.pdf); **[press]** [[2]](https://tidbits.com/1994/03/14/the-power-macintosh-picture/); [[8]](https://en.wikipedia.org/wiki/System_7) |
| Feb 1995 | — (pre-release) | Technote PT 39 describes the dynamic recompiling emulator | **[Apple]** [[5]](https://preterhuman.net/macstuff/technotes/pt/pt_39.html) |
| 19 Jun 1995 | System 7.5.2 (Power Mac 9500) | First PCI Power Macs, which carry the DR emulator | **[press]** [[6]](https://tidbits.com/1996/07/08/fishing-for-chips-part-2/); [[8]](https://en.wikipedia.org/wiki/System_7) |
| Sep–Oct 2004 | — | QuickTransit reaches market (SGI) | **[press]** [[12]](https://spectrum.ieee.org/how-old-apps-will-run-on-new-macs); [[24]](https://en.wikipedia.org/wiki/QuickTransit) |
| 6 Jun 2005 | Mac OS X 10.4 (Intel preview) | Intel transition announced; Rosetta demonstrated; Developer Transition Kit | **[Apple]** [[9]](https://www.apple.com/newsroom/2005/06/06Apple-to-Use-Intel-Microprocessors-Beginning-in-2006/); **[press]** [[10]](https://appleinsider.com/articles/05/06/06/apple_confirms_switch_to_intel) |
| 8 Jun 2005 | — | Transitive reported as the supplier of Rosetta's engine | **[press]** [[11]](https://web.archive.org/web/20160301203848/http://www.cnet.com/news/the-brains-behind-apples-rosetta-transitive/) |
| 10 Jan 2006 | Mac OS X 10.4.4 | First Intel Macs ship with Rosetta | **[Apple]** [[15]](https://www.apple.com/newsroom/2006/01/10Apple-Unveils-New-iMac-with-Intel-Core-Duo-Processor/) |
| 18–19 Nov 2008 | — | IBM announces plan to acquire Transitive | **[press]** [[21]](https://arstechnica.com/information-technology/2008/11/ibm-to-buy-transitive/), [[22]](https://www.theregister.com/2008/11/19/ibm_buys_transitive) |
| 28 Aug 2009 | Mac OS X 10.6 | Rosetta becomes an optional, on-demand install | **[press]** [[17]](https://www.engadget.com/2009-08-27-getting-ready-for-snow-leopard-think-about-your-applications.html), [[18]](https://www.macworld.com/article/150693/snow_leopard_which_apps_wont_run.html) |
| 26 Feb 2011 | 10.7 developer preview | Lion previews drop Rosetta | **[press]** [[19]](https://appleinsider.com/articles/11/02/26/mac_os_x_lion_drops_front_row_java_runtime_rosetta) |
| 20 Jul 2011 | Mac OS X 10.7 | Lion ships without Rosetta | **[Apple]** [[20]](https://www.apple.com/newsroom/2011/07/20Mac-OS-X-Lion-Available-Today-From-the-Mac-App-Store/) |
| 22 Jun 2020 | macOS 11 beta | Apple silicon transition and Rosetta 2 announced; A12Z Developer Transition Kit | **[Apple]** [[25]](https://www.apple.com/newsroom/2020/06/apple-announces-mac-transition-to-apple-silicon/) |
| 12 Nov 2020 | macOS 11.0.1 | Big Sur released | **[Apple]** [[27]](https://www.apple.com/newsroom/2020/11/macos-big-sur-is-here/), [[28]](https://support.apple.com/en-us/120989) |
| 17 Nov 2020 | macOS 11.0.1 (M1 build) | Separate 11.0.1 build for the first M1 Macs; Rosetta 2 installs on demand | **[Apple]** [[28]](https://support.apple.com/en-us/120989), [[61]](https://support.apple.com/en-us/102527) |
| 6 Jun 2022 | macOS 13 beta | Rosetta for Linux VMs announced; Apple guide published | **[Apple]** [[34]](https://developer.apple.com/videos/play/wwdc2022/10002/), [[35]](https://web.archive.org/web/20220606194510/https://developer.apple.com/tutorials/data/documentation/virtualization/running_intel_binaries_in_linux_vms_with_rosetta.json) |
| 24 Oct 2022 | macOS 13.0 | Ventura ships `VZLinuxRosettaDirectoryShare` | **[Apple]** [[36]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare), [[29]](https://support.apple.com/en-us/121012) |
| 5 Jun 2023 | macOS 14 beta | Linux AOT caching announced; Game Porting Toolkit 1 (runs under Rosetta 2) | **[Apple]** [[38]](https://developer.apple.com/videos/play/wwdc2023/10007/), [[39]](https://developer.apple.com/videos/play/wwdc2023/10123/) |
| 26 Sep 2023 | macOS 14.0 | Sonoma ships the Linux caching APIs | **[Apple]** [[41]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettacachingoptions), [[29]](https://support.apple.com/en-us/121012) |
| 7 Mar 2024 | macOS 14.4 | Linux guests can toggle the TSO bit (per Apple engineer, Apr 2024) | **[Apple engineer]** [[42]](https://lwn.net/Articles/969480/); **[Apple]** [[30]](https://support.apple.com/en-us/100100) |
| 10 Jun 2024 | macOS 15 beta | Game Porting Toolkit 2 can evaluate games that use AVX | **[Apple]** [[44]](https://developer.apple.com/videos/play/wwdc2024/10089/) |
| 16 Sep 2024 | macOS 15.0 | Sequoia: Rosetta executes AVX/AVX2 (not AVX-512); `ROSETTA_ADVERTISE_AVX` for GPTK; VM fix | **[Apple]** [[49]](https://forums.swift.org/t/minimum-supported-development-environment/77565/14), [[40]](https://gist.github.com/lynkos/3999f629560219a81d4e2c083a4bf5b1), [[47]](https://developer.apple.com/documentation/macos-release-notes/macos-15-release-notes) |
| Late Oct–7 Nov 2024 (inferred) | Host macOS 14.4+, guest Linux 6.10 | Apple publishes the Rosetta TSO kernel patch and article | **[Apple]** [[50]](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta) |
| 9 Jun 2025 | macOS 26 beta | Phase-out announced: general Rosetta through macOS 27, then a games subset; Apple open-sources `container` (uses Rosetta) | **[Apple]** [[54]](https://web.archive.org/web/20250611040604/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json); **[press]** [[55]](https://www.macrumors.com/2025/06/10/apple-to-phase-out-rosetta-2/); **[project docs]** [[58]](https://github.com/apple/container/releases) |
| May–Aug 2025 | macOS 15.5 → 26 betas | Linux 6.13+ guests break under Rosetta; fixed in Tahoe betas per Podman | **[project docs]** [[53]](https://github.com/lima-vm/lima/issues/3592), [[52]](https://blog.podman.io/2025/08/podman-5-6-released-rosetta-status-update/) |
| 15 Sep 2025 | macOS 26.0 | Tahoe ships (last Intel-Mac release); `nox86exec=1` test boot argument | **[Apple]** [[59]](https://developer.apple.com/documentation/macos-release-notes/macos-26-release-notes), [[30]](https://support.apple.com/en-us/100100) |
| Sep–Oct 2025 | — (documentation) | Apple's Rosetta page updated to say AVX/AVX2 are translated | **[Apple]** [[31]](https://web.archive.org/web/20251028174555/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json) |
| 24 Mar 2026 | macOS 26.4 | Launch notifications for Rosetta apps; `allowRosettaUsageAwareness`; games and Linux VMs to remain supported | **[Apple]** [[60]](https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes) |
| 8 Jun 2026 | macOS 27 beta | Golden Gate previewed; Linux translation built in; `game-test-tool` (beta only); GPTK 4 | **[Apple]** [[62]](https://www.apple.com/newsroom/2026/06/apple-unveils-next-generation-of-apple-intelligence-siri-ai-and-more/), [[64]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms), [[65]](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes) |
| 1 Sep 2026 | macOS 27 | Developer notice: final release to support Rosetta for Intel-only apps | **[Apple]** [[68]](https://developer.apple.com/news/?id=w5ngl9k2) |
| 14 Sep 2026 | macOS 27.0 | Golden Gate ships (Apple silicon only); Rosetta not restored on upgrade; Intel-app list and warnings | **[Apple]** [[65]](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes), [[70]](https://support.apple.com/en-us/148830), [[30]](https://support.apple.com/en-us/100100) |
| 26 Oct 2026 | macOS 27.2 | Upgrading to macOS 27 no longer removes Rosetta | **[Apple]** [[70]](https://support.apple.com/en-us/148830), [[30]](https://support.apple.com/en-us/100100) |
| 2027 (planned) | macOS 28 | Rosetta limited to certain older unmaintained games using Intel-based frameworks | **[Apple]** [[61]](https://support.apple.com/en-us/102527) |

---

## 6. Open questions

1. **Transitive's history.** Ars Technica (2008) says Transitive was founded in the 1990s and that
   Apple was QuickTransit's first licensee [[21]](https://arstechnica.com/information-technology/2008/11/ibm-to-buy-transitive/);
   IEEE Spectrum (2005) calls it a five-year-old Manchester firm, and CNET (2005) names SGI as the
   first customer [[12]](https://spectrum.ieee.org/how-old-apps-will-run-on-new-macs),
   [[11]](https://web.archive.org/web/20160301203848/http://www.cnet.com/news/the-brains-behind-apples-rosetta-transitive/).
   Wikipedia gives June 2009 for completion of the IBM acquisition [[24]](https://en.wikipedia.org/wiki/QuickTransit);
   I could not confirm the closing date from IBM.
2. **When QuickTransit first shipped**: September 2004 (IEEE Spectrum) or October 2004 (Wikipedia).
3. **When G4/AltiVec support entered Rosetta 1**: the June 2005 documents excluded it, the shipping
   guidelines included it; the exact build is not documented here.
4. **When AVX/AVX2 first executed under Rosetta 2**: press and an Apple engineer point to macOS 15,
   but Apple's own page was not updated until autumn 2025, and the AVX status for *Linux* guests is
   undocumented (see `05-rosetta-for-linux.md`).
5. **macOS 14.4 and TSO in guests** rests on one Apple engineer's mailing-list post; Apple's release
   notes do not mention it.
6. **What survives in macOS 28.** Apple has not said which games qualify ("older unmaintained
   gaming titles that rely on Intel-based frameworks"), whether the remaining translator is still
   called Rosetta, or how the "new underlying system behavior" behind `game-test-tool` works.
7. **Why macOS 27.0 removed Rosetta on upgrade and 27.2 stopped doing so.** Apple gives no reason
   [[70]](https://support.apple.com/en-us/148830).
8. **Where the WWDC25 statement was first made.** Press attributes it to the Platforms State of the
   Union; I verified it only in Apple's documentation.

---

## Sources

Accessed 31 October 2026 unless noted.

1. [Apple] *Inside Macintosh: PowerPC System Software*, "Introduction to PowerPC" (1994). https://developer.apple.com/library/archive/documentation/mac/pdf/PPC_System_Software/Intro_to_PowerPC.pdf
2. [press] TidBITS, "The Power Macintosh Picture" (14 Mar 1994). https://tidbits.com/1994/03/14/the-power-macintosh-picture/
3. [press] Hansen Hsu, Computer History Museum, "Transplanting the Mac's Central Processor: Gary Davidian and His 68000 Emulator" (29 Jun 2020). https://computerhistory.org/blog/transplanting-the-macs-central-processor-gary-davidian-and-his-68000-emulator/
4. [press] Linley Gwennap, "RISC Reaches Mainstream with Power Macs", *Microprocessor Report* (28 Mar 1994). http://ardent-tool.com/CPU/docs/MPR/19940328/080401.pdf
5. [Apple] Technote PT 39, "The DR Emulator", Eric Traut (Feb 1995), mirror. https://preterhuman.net/macstuff/technotes/pt/pt_39.html
6. [press] TidBITS, "Fishing For Chips: Part 2" (8 Jul 1996). https://tidbits.com/1996/07/08/fishing-for-chips-part-2/
7. [project docs: patent] US 5,790,825, Eric P. Traut, Apple Computer (priority 8 Nov 1995). https://patents.google.com/patent/US5790825A/en
8. [secondary: Wikipedia] System 7 (release table). https://en.wikipedia.org/wiki/System_7
9. [Apple] "Apple to Use Intel Microprocessors Beginning in 2006" (6 Jun 2005). https://www.apple.com/newsroom/2005/06/06Apple-to-Use-Intel-Microprocessors-Beginning-in-2006/
10. [press] AppleInsider, "Apple confirms switch to Intel" (6 Jun 2005). https://appleinsider.com/articles/05/06/06/apple_confirms_switch_to_intel
11. [press] Stephen Shankland, CNET, "The brains behind Apple's Rosetta: Transitive" (8 Jun 2005), archived. https://web.archive.org/web/20160301203848/http://www.cnet.com/news/the-brains-behind-apples-rosetta-transitive/
12. [press] IEEE Spectrum, "How Old Apps Will Run on New Macs" (June 2005). https://spectrum.ieee.org/how-old-apps-will-run-on-new-macs
13. [Apple] *Universal Binary Programming Guidelines, Second Edition*, Appendix "Rosetta". https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/universal_binary/universal_binary_exec_a/universal_binary_exec_a.html
14. [press] Jason Snell, Macworld, "Apple and Intel: What you need to know" (8 Jun 2005). https://www.macworld.com/article/175923/intelfaq.html
15. [Apple] "Apple Unveils New iMac with Intel Core Duo Processor" (10 Jan 2006). https://www.apple.com/newsroom/2006/01/10Apple-Unveils-New-iMac-with-Intel-Core-Duo-Processor/
16. [Apple] apple.com/rosetta, archived 13 Jan 2006. https://web.archive.org/web/20060113055505/http://www.apple.com/rosetta/
17. [press] Engadget (TUAW), "Getting ready for Snow Leopard: Think about your applications" (27 Aug 2009). https://www.engadget.com/2009-08-27-getting-ready-for-snow-leopard-think-about-your-applications.html
18. [press] Macworld, "Snow Leopard: Which Apps Won't Run?" (30 Aug 2009). https://www.macworld.com/article/150693/snow_leopard_which_apps_wont_run.html
19. [press] AppleInsider, "Inside Mac OS X 10.7 Lion: Missing Front Row, Rosetta and Java runtime" (26 Feb 2011). https://appleinsider.com/articles/11/02/26/mac_os_x_lion_drops_front_row_java_runtime_rosetta
20. [Apple] "Mac OS X Lion Available Today From the Mac App Store" (20 Jul 2011). https://www.apple.com/newsroom/2011/07/20Mac-OS-X-Lion-Available-Today-From-the-Mac-App-Store/
21. [press] Ryan Paul, Ars Technica, "IBM to buy Transitive" (20 Nov 2008). https://arstechnica.com/information-technology/2008/11/ibm-to-buy-transitive/
22. [press] Chris Mellor, The Register, "IBM gets into server transit business" (19 Nov 2008). https://www.theregister.com/2008/11/19/ibm_buys_transitive
23. [press] InfoWorld, "IBM's virtualization plans include Transitive" (19 Nov 2008). https://www.infoworld.com/article/2317779/ibm-s-virtualization-plans-include-transitive.html
24. [secondary: Wikipedia] QuickTransit (formerly "Transitive Corporation"). https://en.wikipedia.org/wiki/QuickTransit
25. [Apple] "Apple announces Mac transition to Apple silicon" (22 Jun 2020). https://www.apple.com/newsroom/2020/06/apple-announces-mac-transition-to-apple-silicon/
26. [Apple] "Introducing the next generation of Mac" (10 Nov 2020). https://www.apple.com/newsroom/2020/11/introducing-the-next-generation-of-mac/
27. [Apple] "macOS Big Sur is here" (12 Nov 2020). https://www.apple.com/newsroom/2020/11/macos-big-sur-is-here/
28. [Apple] Apple security releases, 2020 to 2021. https://support.apple.com/en-us/120989
29. [Apple] Apple security releases, 2022 to 2023. https://support.apple.com/en-us/121012
30. [Apple] Apple security releases (2024 onward). https://support.apple.com/en-us/100100
31. [Apple] "About the Rosetta translation environment", archived 28 Oct 2025 (JSON). https://web.archive.org/web/20251028174555/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json (live page: https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment)
32. [Apple] Same page, archived 19 Jan 2024 and 18 Sep 2025 (JSON). https://web.archive.org/web/20240119013640/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json and https://web.archive.org/web/20250918164601/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json
33. [Apple] macOS Big Sur 11.0.1 Universal Apps Release Notes. https://developer.apple.com/documentation/macos-release-notes/macos-big-sur-11_0_1-universal-apps-release-notes
34. [Apple] WWDC22 session 10002, "Create macOS or Linux virtual machines". https://developer.apple.com/videos/play/wwdc2022/10002/
35. [Apple] "Running Intel Binaries in Linux VMs with Rosetta", archived 6 Jun 2022 (JSON). https://web.archive.org/web/20220606194510/https://developer.apple.com/tutorials/data/documentation/virtualization/running_intel_binaries_in_linux_vms_with_rosetta.json
36. [Apple] VZLinuxRosettaDirectoryShare. https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare
37. [press] Howard Oakley, "Explainer: Rosetta 2" (10 Dec 2022). https://eclecticlight.co/2022/12/10/explainer-rosetta-2/
38. [Apple] WWDC23 session 10007, "Create seamless experiences with Virtualization". https://developer.apple.com/videos/play/wwdc2023/10007/
39. [Apple] WWDC23 session 10123, "Bring your game to Mac, Part 1: Make a game plan". https://developer.apple.com/videos/play/wwdc2023/10123/
40. [Apple, README copy] Copy of Apple's Game Porting Toolkit 2.1 README (environment variables, "runs under Rosetta 2"). https://gist.github.com/lynkos/3999f629560219a81d4e2c083a4bf5b1
41. [Apple] VZLinuxRosettaCachingOptions. https://developer.apple.com/documentation/virtualization/vzlinuxrosettacachingoptions
42. [Apple engineer, LKML] Zayd Qumsieh, "tso: aarch64: Expose TSO for virtualized linux on Apple Silicon" (10 Apr 2024), via LWN. https://lwn.net/Articles/969480/
43. [press] Jonathan Corbet, LWN, "Support for the TSO memory model on Arm CPUs" (26 Apr 2024). https://lwn.net/Articles/970907/
44. [Apple] WWDC24 session 10089, "Port advanced games to Apple platforms". https://developer.apple.com/videos/play/wwdc2024/10089/
45. [press] MacGeneration, "Rosetta 2 va être plus efficace avec macOS Sequoia…" (11 Jun 2024). https://www.macg.co/macos/2024/06/rosetta-2-va-etre-plus-efficace-avec-macos-sequoia-et-cest-important-pour-les-jeux-144245
46. [project docs] CodeWeavers, "Enabling AVX Support for Death Stranding". https://www.codeweavers.com/compatibility/crossover/tips/death-stranding/enabling-avx-support-for-death-stranding
47. [Apple] macOS Sequoia 15 Release Notes. https://developer.apple.com/documentation/macos-release-notes/macos-15-release-notes
48. [project docs] Stockfish issue #5707, AVX2 binary under Rosetta on macOS 15 (Dec 2024). https://github.com/official-stockfish/Stockfish/issues/5707
49. [Apple engineer, Swift Forums] Post by @grynspan (30 Jan 2025). https://forums.swift.org/t/minimum-supported-development-environment/77565/14
50. [Apple] "Accelerating the performance of Rosetta" (with RosettaPatch.zip). https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta
51. [press] Andrew Cunningham, Ars Technica, "Apple details the end of Intel Mac support and a phaseout for Rosetta 2" (9 Jun 2025). https://arstechnica.com/gadgets/2025/06/apple-details-the-end-of-intel-mac-support-and-a-phaseout-for-rosetta-2/
52. [project docs] Podman blog, "Podman 5.6 Released: Rosetta Status Update" (18 Aug 2025). https://blog.podman.io/2025/08/podman-5-6-released-rosetta-status-update/
53. [project docs] Lima issue #3592 (May–Jun 2025). https://github.com/lima-vm/lima/issues/3592
54. [Apple] "About the Rosetta translation environment", archived 11 Jun 2025 (JSON). https://web.archive.org/web/20250611040604/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json
55. [press] Joe Rossignol, MacRumors, "Apple to Phase Out Rosetta 2 Starting With macOS 28 as Intel Era Ends" (10 Jun 2025). https://www.macrumors.com/2025/06/10/apple-to-phase-out-rosetta-2/
56. [press] Hartley Charlton, MacRumors, "macOS 27 Golden Gate Is the Last to Support Intel Apps via Rosetta 2" (10 Jun 2026). https://www.macrumors.com/2026/06/10/macos-golden-gate-last-to-support-intel-apps/
57. [project docs] apple/containerization (README: Rosetta 2 for linux/amd64). https://github.com/apple/containerization
58. [project docs] apple/container releases (0.1.0, 9 Jun 2025). https://github.com/apple/container/releases
59. [Apple] macOS Tahoe 26 Release Notes (Rosetta: `nox86exec=1`). https://developer.apple.com/documentation/macos-release-notes/macos-26-release-notes
60. [Apple] macOS Tahoe 26.4 Release Notes (Rosetta deprecations). https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes
61. [Apple] "Using Intel-based apps on a Mac with Apple silicon" (updated 21 Sep 2026). https://support.apple.com/en-us/102527
62. [Apple] WWDC26 press release (8 Jun 2026). https://www.apple.com/newsroom/2026/06/apple-unveils-next-generation-of-apple-intelligence-siri-ai-and-more/
63. [Apple] WWDC26 Keynote (macOS Golden Gate naming). https://developer.apple.com/videos/play/wwdc2026/101/
64. [Apple] "Running Intel Binaries in Linux VMs" (macOS 27 wording). https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms
65. [Apple] macOS 27 Golden Gate Release Notes (Rosetta, Gaming, EcosystemUI, Deprecation sections). https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes
66. [RE: ngyikp] "Legacy Intel games on macOS 27 Golden Gate" (8 Jun 2026). https://ngyikp.com/legacy-intel-apps-games-rosetta-on-macos-27-golden-gate/
67. [Apple] Game Porting Toolkit page (GPTK 4). https://developer.apple.com/games/game-porting-toolkit/
68. [Apple] Developer news, "Upcoming changes to Rosetta support for Intel-based macOS apps" (1 Sep 2026). https://developer.apple.com/news/?id=w5ngl9k2
69. [Apple] "Major updates for Apple's software platforms are now available" (14 Sep 2026). https://www.apple.com/newsroom/2026/09/major-updates-for-apples-software-platforms-are-now-available/
70. [Apple] "What's new for enterprise in macOS Golden Gate 27" (27.0 and 27.2 sections, published 26 Oct 2026). https://support.apple.com/en-us/148830
71. [press] MacRumors, "macOS 27.2 Stops Upgrades From Removing Rosetta" (27 Oct 2026). https://www.macrumors.com/2026/10/27/macos-27-2-stops-removing-rosetta/
72. [project docs: Microsoft] Windows Insider Blog, "Introducing x64 emulation in preview for Windows 10 on ARM PCs" (10 Dec 2020, updated Nov 2021). https://blogs.windows.com/windows-insider/2020/12/10/introducing-x64-emulation-in-preview-for-windows-10-on-arm-pcs-to-the-windows-insider-program/
73. [project docs: Microsoft] Microsoft Learn, "How emulation works on Arm". https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-x86-emulation
74. [project docs: Microsoft] DirectX Developer Blog, "A Step Forward for Gaming on Arm Devices" (Jun 2024). https://devblogs.microsoft.com/directx/step-forward-for-gaming-on-arm-devices-2024/
75. [project docs: Microsoft] Windows Insider Blog, Build 27744 (6 Nov 2024). https://blogs.windows.com/windows-insider/2024/11/06/announcing-windows-11-insider-preview-build-27744-canary-channel/
76. [project docs: Microsoft] Tech Community, "Windows on Arm runs more apps and games with new Prism update" (Dec 2025). https://techcommunity.microsoft.com/blog/windowsosplatform/windows-on-arm-runs-more-apps-and-games-with-new-prism-update/4475631
77. [project docs: Microsoft] Microsoft Learn, "Adjust Emulation Settings on Arm". https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-program-compat-troubleshooter
78. [press] CommonsWare, "libhoudini: What It Means for Developers" (21 Nov 2013). https://commonsware.com/blog/2013/11/21/libhoudini-what-it-means-for-developers.html
79. [RE: Brian Hong, NCC Group] "Sleight of ARM: Demystifying Intel Houdini", DEF CON 29 (2021). https://media.defcon.org/DEF%20CON%2029/DEF%20CON%2029%20presentations/Brian%20Hong%20-%20Sleight%20of%20ARM%20-%20%20Demystifying%20Intel%20Houdini.pdf
80. [project docs: Intel] "Intel Core Processors and Intel Bridge Technology Unleash Windows 11 Experience" (24 Jun 2021). https://www.intc.com/news-events/press-releases/detail/1479/intel-core-processors-and-intel-bridge-technology-unleash
81. [project docs: Microsoft] Windows Insider Blog, "Introducing Android Apps on Windows 11 to Windows Insiders" (20 Oct 2021). https://blogs.windows.com/windows-insider/2021/10/20/introducing-android-apps-on-windows-11-to-windows-insiders/
82. [project docs] FEX-Emu, "FEX seven year anniversary!" (28 Nov 2025). https://fex-emu.com/FEXiversary/
83. [project docs] FEX-Emu/FEX README. https://github.com/FEX-Emu/FEX
84. [press] Rich Trouton, Der Flounder, "Installing Rosetta 2 on Apple Silicon Macs" (17 Nov 2020). https://derflounder.wordpress.com/2020/11/17/installing-rosetta-2-on-apple-silicon-macs/
85. [press] Kyle Orland, Ars Technica, "Not just Proton: Getting to know Valve's new SteamOS compatibility layers" (16 Sep 2026). https://arstechnica.com/gaming/2026/09/not-just-proton-getting-to-know-valves-new-steamos-compatibility-layers/
86. [project docs] ptitSeb/box64 README (repository created 1 Dec 2020). https://github.com/ptitSeb/box64
87. [project docs] ptitSeb/box86 (repository created 9 Jan 2019). https://github.com/ptitSeb/box86
88. [secondary: Wikipedia] QEMU. https://en.wikipedia.org/wiki/QEMU
89. [project docs] Fabrice Bellard, "QEMU, a Fast and Portable Dynamic Translator", USENIX ATC 2005. https://www.usenix.org/legacy/publications/library/proceedings/usenix05/tech/freenix/full_papers/bellard/bellard.pdf
90. [project docs] QEMU documentation, "QEMU User space emulator". https://www.qemu.org/docs/master/user/main.html
91. [forum] Apple Developer Forums thread 653902, quoting Apple's 2020 Rosetta limits text. https://developer.apple.com/forums/thread/653902
