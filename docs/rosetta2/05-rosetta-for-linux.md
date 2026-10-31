# 05 — Rosetta for Linux virtual machines

Scope: how Apple offers its x86-64 translator to **ARM64 Linux guests** running under Apple's
Virtualization framework on Apple silicon Macs, what Apple documents about it, which Mac tools
use it in the supported way, and the licence position. Research cut-off: 31 October 2026
(macOS 27.2 "Golden Gate" is current).

This document covers only Apple's supported configuration: an ARM64 Linux guest started by the
Virtualization framework on an Apple silicon Mac. It does not cover other environments or any way
around Rosetta's hardware or licence checks.

Related documents in this folder:

- `02-architecture-and-runtime.md`: the macOS-side runtime (`oahd`, AOT files, the JIT path).
- `04-hardware-assists.md`: the CPU features Rosetta relies on, including the Apple silicon
  total-store-ordering mode.
- `06-history-and-timeline.md`: dates and version history, including the Linux feature.

Provenance labels: **[Apple]** = Apple documentation, release notes, WWDC sessions, press
releases, Apple-published source, or public posts by identifiable Apple engineers (marked as
such); **[press]** = journalism and established independent technical blogs; **[RE: author]** =
reverse engineering by the named author;
**[project docs]** = documentation, source code, release notes or issue threads of third-party
projects; **[Inferred]** = my own conclusion from the cited material; **[forum]** = unverified
community forum posts, used only to flag open questions. Numbers in square brackets are links to
the Sources list at the end.

---

## 1. At a glance

| Item | What is documented | Label |
|---|---|---|
| Host | Mac with Apple silicon, macOS 13 Ventura or later | **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| Guest | An ARM64 Linux distribution. Installing or booting *Intel* Linux distributions is not supported | **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| What gets translated | x86-64 Linux user-space programs (ELF executables and their libraries) | **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| How it reaches the guest | A special directory share (`VZLinuxRosettaDirectoryShare`) exported over virtiofs | **[Apple]** [[2]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare) |
| How Linux uses it | The guest registers the `rosetta` binary with the kernel's `binfmt_misc` handler | **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| Translation cache | Ahead-of-time (AOT) caching options, macOS 14 Sonoma or later, served by a daemon in the guest | **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms), [[12]](https://developer.apple.com/videos/play/wwdc2023/10007/) |
| Installation | macOS 13–26: Rosetta must be installed on the host (one-time, needs user consent). macOS 27: built into macOS, no install | **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| Memory ordering | Enabling the share affects the whole VM's memory model; an optional Apple kernel patch allows per-thread control | **[Apple]** [[9]](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta), **[project docs]** [[47]](https://github.com/lima-vm/lima/issues/1269) |
| Future | Apple says support for Intel binaries in Linux VMs continues after general Rosetta support for Mac apps ends | **[Apple]** [[16]](https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes) |

---

## 2. Terms used

- **Virtualization framework**: Apple's high-level macOS API for building virtual machines
  (VMs). It is separate from the lower-level Hypervisor framework **[Apple]**
  [[11]](https://developer.apple.com/videos/play/wwdc2022/10002/).
- **virtiofs**: a shared-file-system protocol for VMs. The host exports a directory under a
  *tag* (a short name), and the guest mounts it with `mount -t virtiofs <tag> <dir>`
  **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).
- **ELF**: the executable file format used by Linux. Its header records the CPU architecture
  (field `e_machine`, value 62 for x86-64) **[project docs]**
  [[24]](https://man7.org/linux/man-pages/man5/elf.5.html).
- **binfmt_misc**: a Linux kernel feature that runs a chosen "interpreter" program whenever
  someone executes a file whose first bytes match a registered pattern **[project docs]**
  [[23]](https://docs.kernel.org/admin-guide/binfmt-misc.html). Rosetta for Linux uses it the
  same way QEMU's user-mode emulator does.
- **JIT / AOT translation**: just-in-time translation converts x86-64 code while the program
  runs; ahead-of-time translation converts it before it runs and can store the result in a cache
  for reuse.
- **TSO (total store ordering)**: the x86 memory-ordering model. ARM64 normally uses a weaker
  model, so a translator must either add ordering instructions or switch the CPU into a TSO mode.
  The hardware side is covered in `04-hardware-assists.md`.
- **Abstract socket**: a Linux-only kind of UNIX-domain socket whose address is a name in a
  kernel namespace, not a file on disk.
- **Multiarch / multilib**: distribution features for installing x86-64 libraries alongside
  ARM64 ones.

---

## 3. Host side: the Virtualization framework API

### 3.1 API summary

All names below are from Apple's reference documentation; availability is as Apple lists it.

| API (Swift / Objective-C) | Purpose | Availability | Source |
|---|---|---|---|
| `class VZLinuxRosettaDirectoryShare` (subclass of `VZDirectoryShare`) | The directory share that exposes Rosetta to the guest | macOS 13.0+ | **[Apple]** [[2]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare) |
| `VZLinuxRosettaDirectoryShare.availability` (class property) | Reports whether Rosetta is usable on this host | macOS 13.0+ | **[Apple]** [[2]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare) |
| `enum VZLinuxRosettaAvailability`: `.notSupported`, `.notInstalled`, `.installed` | Possible availability states | macOS 13.0+ | **[Apple]** [[3]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettaavailability) |
| `installRosetta(completionHandler:)` / `installRosetta() async throws` (Obj-C `installRosettaWithCompletionHandler:`) | Starts the one-time host installation | macOS 13.0+ | **[Apple]** [[4]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare/installrosetta(completionhandler:)) |
| `init() throws` (Obj-C `initWithError:`) | Creates the share; fails if Rosetta is not installed | macOS 13.0+ | **[Apple]** [[2]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare) |
| `cachingOptions` / `setCachingOptions(_:)` (Obj-C property `options`) | Turns on AOT caching and selects the socket type | macOS 14.0+ | **[Apple]** [[2]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare) |
| `enum VZLinuxRosettaDirectoryShare.CachingOptions`: `.unixSocket(_:)`, `.abstractSocket(_:)`, `defaultUnixSocket`, `maximumPathLength`, `maximumNameLength` | Swift caching option values | macOS 14.0+ | **[Apple]** [[5]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare/cachingoptions-swift.enum) |
| `VZLinuxRosettaCachingOptions` (abstract base class) | Obj-C base class; "don't instantiate directly" | macOS 14.0+ | **[Apple]** [[6]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettacachingoptions) |
| `VZLinuxRosettaUnixSocketCachingOptions` (`init`, `initWithPath:error:`, `path`, `maximumPathLength`) | Cache channel over a UNIX-domain socket file | macOS 14.0+ | **[Apple]** [[7]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettaunixsocketcachingoptions) |
| `VZLinuxRosettaAbstractSocketCachingOptions` (`initWithName:error:`, `name`, `maximumNameLength`) | Cache channel over an abstract socket | macOS 14.0+ | **[Apple]** [[8]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettaabstractsocketcachingoptions) |

### 3.2 Checking and installing

Apple's guide tells apps to read `availability` before doing anything else **[Apple]**
[[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms):

- `.notSupported`: the hardware or software cannot run Rosetta (for example an Intel Mac).
- `.notInstalled`: ask the user for permission, then call `installRosetta`.
- `.installed`: ready.

On macOS 26 and earlier, installation is a one-time, per-computer step that needs a person to
authorise it. If Rosetta is already installed for Mac apps, the framework simply activates it;
otherwise it downloads the installer. Apps must handle `networkError`, `outOfDiskSpace`,
`userCancelled` and `notSupported` errors **[Apple]**
[[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).

**macOS 27 change.** Apple's current guide says that until macOS 26 this capability "was part of
Rosetta", and that macOS 27 integrates Intel binary translation directly. On macOS 27,
`availability` always returns `.installed` and `installRosetta` returns immediately **[Apple]**
[[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).
The guide was renamed from "Running Intel Binaries in Linux VMs with Rosetta" (2022 wording, which
said "the Virtualization framework supports Rosetta") to "Running Intel Binaries in Linux VMs"
**[Apple]** [[22]](https://web.archive.org/web/20220606194510/https://developer.apple.com/tutorials/data/documentation/virtualization/running_intel_binaries_in_linux_vms_with_rosetta.json),
[[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).

### 3.3 Attaching the share

The share is attached like any other virtiofs device: create a
`VZVirtioFileSystemDeviceConfiguration` with a tag (validated with `validateTag(_:)`), set its
`share` to a `VZLinuxRosettaDirectoryShare`, and add it to the configuration's
`directorySharingDevices` **[Apple]**
[[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).
WWDC22's sample used the tag `RosettaShare` **[Apple]**
[[11]](https://developer.apple.com/videos/play/wwdc2022/10002/):

```swift
let rosettaDirectoryShare = try! VZLinuxRosettaDirectoryShare()
let directorySharingDevice = VZVirtioFileSystemDeviceConfiguration(tag: "RosettaShare")
directorySharingDevice.share = rosettaDirectoryShare
configuration.directorySharingDevices = [directorySharingDevice]
```

Tags used by real tools: `rosetta` (UTM, Apple's Containerization), `vz-rosetta` (Lima), or a
user-chosen tag (Tart) **[project docs]**
[[36]](https://github.com/utmapp/UTM/blob/main/Configuration/UTMAppleConfigurationVirtualization.swift),
[[28]](https://github.com/apple/containerization/blob/main/Sources/Containerization/VZVirtualMachineInstance.swift),
[[27]](https://github.com/lima-vm/lima/blob/master/pkg/driver/vz/rosetta_directory_share_arm64.go),
[[38]](https://github.com/cirruslabs/tart/blob/main/Sources/tart/Commands/Run.swift).

### 3.4 AOT caching options (macOS 14+)

At WWDC23 Apple explained the motivation. Rosetta translates executable pages on demand, so
startup is quick, but every new process that uses the same libraries pays the translation cost
again. In macOS 14 Sonoma the Virtualization framework added a guest-side "runtime daemon" that
keeps a translation cache; dynamic-linker requests are forwarded to it, and the Rosetta runtime
fetches pre-translated code from it **[Apple]**
[[12]](https://developer.apple.com/videos/play/wwdc2023/10007/). Apple says the biggest gains are
on exec-heavy work such as compiling or installing packages **[Apple]**
[[12]](https://developer.apple.com/videos/play/wwdc2023/10007/).

Two channels connect the runtime and the daemon **[Apple]**
[[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms):

1. **UNIX-domain socket file**: the framework shares a file representing the socket, which the
   guest exposes at the configured path through a symlink or bind-mount. The guest must create the
   directory at that path, and the path length is limited by `maximumPathLength` **[Apple]**
   [[7]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettaunixsocketcachingoptions).
2. **Abstract socket**: the framework defines a shared name instead of a file; the length limit
   comes from Linux's `sockaddr_un` **[Apple]**
   [[8]](https://developer.apple.com/documentation/virtualization/vzlinuxrosettaabstractsocketcachingoptions).

Apple's sample code sets the option on the share before attaching it, for example
`try rosettaDirectoryShare.setCachingOptions(.abstractSocket("abstractSocketName"))`, and treats a
failure as "proceed without caching" **[Apple]**
[[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).
UTM simply calls `setCachingOptions(.defaultUnixSocket)` on macOS 14 and later **[project docs]**
[[36]](https://github.com/utmapp/UTM/blob/main/Configuration/UTMAppleConfigurationVirtualization.swift).

---

## 4. Guest side: mounting the share and registering the translator

### 4.1 Apple's procedure

Apple stresses that these steps run *inside* the guest: the host app cannot execute or script
them, so a person (or a script they run while logged in to the guest) must perform them
**[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).
In practice, tools that control their own guest image (Docker Desktop, Lima, Apple's container
tool) do this in their guest init code; see section 7.

1. Install `update-binfmts` (Debian's `binfmt-support` package) if needed; it requires `sudo`.
2. Create a mount point and mount the tag: `sudo mount -t virtiofs <TAG> <dir>`.
3. Check that the directory contains `rosetta`.
4. Register it as the x86-64 ELF handler **[Apple]**
   [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms):

```sh
sudo /usr/sbin/update-binfmts --install rosetta /tmp/mountpoint/rosetta \
  --magic "\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00" \
  --mask  "\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff" \
  --credentials yes --preserve yes --fix-binary yes
```

Apple's note: on macOS 13 hosts, `--preserve` must be `no` **[Apple]**
[[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).
The WWDC22 version of the command used `--preserve no` throughout **[Apple]**
[[11]](https://developer.apple.com/videos/play/wwdc2022/10002/). UTM's documentation repeats the
macOS 13 caveat and suggests an `/etc/fstab` line (`rosetta /media/rosetta virtiofs ro,nofail 0 0`)
so the share mounts at boot **[project docs]** [[35]](https://docs.getutm.app/advanced/rosetta/).

### 4.2 What the magic and mask match

Apple says the `magic` describes the first 20 bytes of an x86-64 ELF header and that the kernel
masks those bytes with `mask` before comparing **[Apple]**
[[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).
Decoded against the ELF layout **[Inferred]** from
[[24]](https://man7.org/linux/man-pages/man5/elf.5.html):

| Bytes | Field | Required value |
|---|---|---|
| 0–3 | ELF signature | `\x7f E L F` |
| 4 | Class | 64-bit |
| 5–6 | Data encoding, version | low bit ignored (little-endian, version 1 accepted) |
| 7 | OS ABI | ignored (mask `00`) |
| 8–15 | ABI version, padding | zero |
| 16–17 | Type | 2 or 3 (executable or position-independent executable / shared object) |
| 18–19 | Machine | 62, i.e. x86-64 |

This pattern is byte-for-byte the one QEMU's `qemu-binfmt-conf.sh` uses for x86-64
**[project docs]** [[69]](https://github.com/qemu/qemu/blob/master/scripts/qemu-binfmt-conf.sh),
so Rosetta and `qemu-user-static` compete for the same files. The kernel matches the most recently
added entry first **[project docs]** [[23]](https://docs.kernel.org/admin-guide/binfmt-misc.html),
and Lima writes a `binfmt.d` file so Rosetta wins even when QEMU's handlers are installed
**[project docs]** [[26]](https://github.com/lima-vm/lima/blob/master/pkg/driver/vz/boot.Linux/05-rosetta-volume.sh).

### 4.3 What the flags do

From the kernel's `binfmt_misc` documentation **[project docs]**
[[23]](https://docs.kernel.org/admin-guide/binfmt-misc.html):

| `update-binfmts` option | Kernel flag | Effect |
|---|---|---|
| `--preserve yes` | `P` | Keeps the program's original `argv[0]` by inserting an extra argument; the interpreter must expect this layout (hence Apple's "use `no` on macOS 13") |
| `--credentials yes` | `C` (implies `O`) | Computes credentials from the binary, not the interpreter, so set-user-ID binaries behave as expected; the kernel docs warn this needs care |
| (implied by `C`) | `O` | Passes an open file descriptor for the binary in the auxiliary vector |
| `--fix-binary yes` | `F` | Opens the interpreter once, at registration, so it keeps working inside containers and chroots that do not have the share mounted |

Tools that register directly instead of via `update-binfmts` choose similar flags: Lima uses
`OCF`, Apple's Containerization uses `CF` **[project docs]**
[[26]](https://github.com/lima-vm/lima/blob/master/pkg/driver/vz/boot.Linux/05-rosetta-volume.sh),
[[28]](https://github.com/apple/containerization/blob/main/Sources/ContainerizationOS/Linux/Binfmt.swift).
The `F` flag is why one registration in the VM serves every container started later
**[Inferred]**.

### 4.4 Libraries

Statically linked x86-64 programs run without further setup. Dynamically linked ones need the
x86-64 shared libraries installed in the guest, in paths both the user and Rosetta can read
**[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).
OrbStack's documentation gives the typical symptom and fix: an error that Rosetta failed to open
`/lib64/ld-linux-x86-64.so` means multiarch libraries are missing; Debian-family guests can add
`amd64` as a foreign architecture **[project docs]** [[33]](https://docs.orbstack.dev/machines).
Inside a container, the x86-64 image supplies its own libraries, which is why container use needs
no multiarch setup **[Inferred]**.

### 4.5 Running the caching daemon in the guest

Apple's WWDC23 session says you must launch the daemon in the guest but does not print the
command **[Apple]** [[12]](https://developer.apple.com/videos/play/wwdc2023/10007/). Lima's
guest script is a complete public example **[project docs]**
[[26]](https://github.com/lima-vm/lima/blob/master/pkg/driver/vz/boot.Linux/05-rosetta-volume.sh),
[[27]](https://github.com/lima-vm/lima/blob/master/pkg/driver/vz/rosetta_directory_share_arm64.go):

- Host: on macOS 14+, Lima sets `VZLinuxRosettaUnixSocketCachingOptions` with path
  `/run/rosettad/rosetta.sock`.
- Guest: if the share contains an executable `rosettad`, Lima starts it as a service with
  `rosettad daemon /var/cache/rosettad`.
- The daemon creates its socket at `/var/cache/rosettad/uds/rosetta.sock`; Lima makes it
  world-writable and symlinks it to the path the host configured.
- For containers, Lima publishes a Container Device Interface (CDI) entry,
  `lima-vm.io/rosetta=cached`, that bind-mounts the socket into a container; cache files appear
  as `*.aotcache` under `/var/cache/rosettad` **[project docs]**
  [[25]](https://lima-vm.io/docs/config/multi-arch/).

---

## 5. How this relates to the macOS Rosetta

**What Apple says.** At WWDC22 Apple called it "the same technology we have been using on the
Mac" **[Apple]** [[11]](https://developer.apple.com/videos/play/wwdc2022/10002/), and at WWDC23
"the same technology used on macOS" **[Apple]**
[[12]](https://developer.apple.com/videos/play/wwdc2023/10007/). Apple has not published how much
code is shared.

**How it is delivered.**

- On macOS 13–26 the Linux translator ships inside the host's on-demand Rosetta package. Howard
  Oakley noted in 2022 that Ventura added a `RosettaLinux` folder under
  `/Library/Apple/usr/libexec/oah` **[press]**
  [[56]](https://eclecticlight.co/2022/12/10/explainer-rosetta-2/); a 2026 analysis lists
  `RosettaLinux/rosetta` and `RosettaLinux/rosettad` there **[RE: Inoki]**
  [[57]](https://blog.inoki.cc/2026/02/28/Apple-Rosetta-Linux-VM-Secret-en/).
- On macOS 27 Apple says Intel binary translation for Linux is integrated into macOS and needs
  no Rosetta install **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).
  For a while (snapshots from July to September 2026) Apple's general Rosetta page said this
  integration covers both Linux VMs and Intel Linux containers **[Apple]**
  [[14]](https://web.archive.org/web/20260815045008/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json),
  [[15]](https://github.com/apple/container/discussions/1679); that sentence is absent from the
  live page on 31 October 2026 **[Apple]**
  [[13]](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment).

**Where it runs.** The translator never runs in macOS for Linux programs. The host only exports
files (and, with caching, a socket); `rosetta` and `rosettad` are ARM64 Linux programs executed by
the guest kernel **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms),
[[12]](https://developer.apple.com/videos/play/wwdc2023/10007/).

**Comparison with the macOS path** (macOS details are in `02-architecture-and-runtime.md`):

| Aspect | Mac apps (macOS) | Linux guests | Label |
|---|---|---|---|
| Who starts the translator | The XNU kernel launches Rosetta for x86-64-only Mach-O programs | The Linux kernel's `binfmt_misc` handler starts `rosetta` | **[Apple]** [[13]](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment), [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| AOT cache manager | `oahd` and its helper on macOS | `rosettad` in the guest, macOS 14+ only | **[RE: FFRI]** [[64]](https://ffri.github.io/ProjectChampollion/part1/), **[Apple]** [[12]](https://developer.apple.com/videos/play/wwdc2023/10007/) |
| Ventura behaviour | AOT plus JIT since Big Sur | No caching until Sonoma, so effectively on-demand translation only | **[Inferred]** from [[12]](https://developer.apple.com/videos/play/wwdc2023/10007/) |
| System calls | x86-64 macOS calls mapped onto XNU | x86-64 Linux calls mapped onto the ARM64 Linux kernel | **[RE: Inoki]** [[57]](https://blog.inoki.cc/2026/02/28/Apple-Rosetta-Linux-VM-Secret-en/) |
| CPU identity shown to programs | `sysctl`/CPUID values (see 02) | A synthetic `/proc/cpuinfo` with vendor `VirtualApple`; `uname -m` reports `x86_64` for translated processes | **[RE: Inoki]** [[57]](https://blog.inoki.cc/2026/02/28/Apple-Rosetta-Linux-VM-Secret-en/) |

**[Inferred]** The Linux product looks like the same translation core packaged with Linux-specific
front ends (ELF loading, Linux system calls, `/proc` emulation, the `rosettad` cache protocol).
Apple's own wording supports "same technology", but there is no public statement about shared code.

---

## 6. Memory ordering inside a VM

x86-64 programs assume TSO ordering; Apple silicon can switch a CPU thread into a TSO mode, which
saves the translator from adding ordering instructions to ordinary loads and stores. The hardware
details (the `ACTLR_EL1` bit, performance-core restrictions, measured costs) are in
`04-hardware-assists.md`. This section covers only what changes inside a Linux VM.

### 6.1 Default behaviour: the whole VM is affected

- In January 2023 a Lima developer posted what he described as Apple's official response to a
  performance report: the
  behaviour is expected, the Apple silicon features Rosetta needs affect how the VM executes
  memory operations, and the guidance is "to only use Rosetta support as needed" **[project docs,
  relaying Apple]** [[47]](https://github.com/lima-vm/lima/issues/1269).
- In November 2023 a Docker engineer reported Apple's feedback that creating the Rosetta share
  changes the memory model of the whole VM even when Rosetta is not used; the effect is usually
  small but large for some instructions (an ARM `LD4` loop ran about 20 times slower) **[project
  docs, relaying Apple]** [[48]](https://github.com/docker/for-mac/issues/6733).
- OrbStack's settings page says enabling Rosetta can slightly slow every program in its VM,
  including native ARM code **[project docs]** [[34]](https://docs.orbstack.dev/settings).
- Apple's own article puts it this way: without per-process control, "the system opts all
  processes into this memory mode", which slows native ARM processes **[Apple]**
  [[9]](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta).

### 6.2 Guest-controlled TSO (macOS 14.4+ hosts) and Apple's kernel patch

- In April 2024 an Apple engineer, Zayd Qumsieh, posted a three-patch series to the Linux kernel
  mailing list adding TSO control for *virtualised* Linux on Apple silicon. The cover letter says
  the host must run macOS Sonoma 14.4 or later, because earlier versions do not let the guest
  change the TSO bit **[Apple engineer, LKML via LWN]** [[52]](https://lwn.net/Articles/969480/).
- Apple later published **"Accelerating the performance of Rosetta"** with a downloadable patch,
  *Rosetta Enhancement Patch* (`RosettaPatch.zip`, containing `RosettaPatch.diff` and
  `LICENSE.txt`). Apple says it applies cleanly to Linux 6.10 **[Apple]**
  [[9]](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta),
  [[10]](https://developer.apple.com/download/files/RosettaPatch.zip). The patch files are dated
  October 2024 inside the archive, and public discussion of the article dates from 7 November 2024
  **[Inferred]** from [[10]](https://developer.apple.com/download/files/RosettaPatch.zip),
  [[66]](https://news.ycombinator.com/item?id=42074592).
- What the patch does, per Apple's article and the diff itself **[Apple]**
  [[9]](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta),
  [[10]](https://developer.apple.com/download/files/RosettaPatch.zip):
  - adds `CONFIG_ARM64_TSO` ("ARM64 Apple Silicon TSO support", default on);
  - treats TSO as available only if the CPU implementer is Apple and bit 9 of `AIDR_EL1` is set;
  - reads and writes `ACTLR_EL1` bit 1 (`TSOEN`) and saves/restores it on every thread switch;
  - clears TSO when a new program is executed;
  - adds `prctl(PR_SET_MEM_MODEL, PR_SET_MEM_MODEL_TSO)` so a translator can enable TSO only for
    its own threads. Apple's article tells apps to call this on each thread that needs it.
- Constant values differ between versions: Apple's published patch defines `PR_SET_MEM_MODEL` as
  `0x4d4d444c` (ASCII "MMDL"), whereas the April 2024 mailing-list version used `71`. Software
  must match the kernel it targets **[Inferred]** from [[10]](https://developer.apple.com/download/files/RosettaPatch.zip),
  [[52]](https://lwn.net/Articles/969480/).

### 6.3 Upstream status

- A day after Apple's series, Hector Martin (Asahi Linux) posted a competing series for a generic
  `PR_SET_MEM_MODEL`/`PR_GET_MEM_MODEL` interface **[project docs]**
  [[53]](https://lwn.net/Articles/969484/). Arm64 maintainers objected that a user-visible TSO
  switch would fragment Linux user space **[press]** [[54]](https://lwn.net/Articles/970907/).
- As of 31 October 2026, mainline Linux's `include/uapi/linux/prctl.h` contains no memory-model
  prctl, so the feature needs Apple's out-of-tree patch **[project docs]**
  [[55]](https://github.com/torvalds/linux/blob/master/include/uapi/linux/prctl.h).

---

## 7. Mac tools that use it in Apple's supported way

All of these attach `VZLinuxRosettaDirectoryShare` to a Virtualization-framework VM. None ship
Rosetta itself; they ask macOS to install it or use the copy macOS provides **[project docs]**
(sources in the table). Howard Oakley notes that virtualisers which do not use the Virtualization
framework are unlikely to offer Rosetta in guests **[press]**
[[56]](https://eclecticlight.co/2022/12/10/explainer-rosetta-2/).

| Tool | How Rosetta is enabled | AOT caching | Notes from its documentation | Sources |
|---|---|---|---|---|
| **Apple `container` / Containerization** | Automatic when an `amd64` image runs on an arm64 Mac; `--rosetta` flag; the builder VM uses Rosetta by default | No caching options set in the public source (Oct 2026) | Guest init (`vminitd`) mounts tag `rosetta` at `/run/rosetta` and registers `/run/rosetta/rosetta` with flags `CF`; installs Rosetta if `availability` is `.notInstalled`; `container` supports macOS 26 | **[project docs]** [[28]](https://github.com/apple/containerization/blob/main/Sources/Containerization/Vminitd%2BRosetta.swift), [[29]](https://github.com/apple/container) |
| **Docker Desktop** | Settings → General → "Use Rosetta for x86_64/amd64 emulation on Apple Silicon"; requires the Apple Virtualization framework VMM | Not documented | Beta in 4.16 (12 Jan 2023); auto-install of Rosetta in 4.17; GA in 4.25 (26 Oct 2023) for macOS 13+; enforceable by admins from 4.29 | **[project docs]** [[30]](https://docs.docker.com/desktop/settings-and-maintenance/settings/), [[31]](https://docs.docker.com/desktop/release-notes/) |
| **OrbStack** | Setting `rosetta` (OrbStack recommends leaving it on); `docker --platform linux/amd64`; `orb create --arch amd64` for x86 machines | Not documented | Says Rosetta is over 2x faster than its fallback; macOS 12 and older use the fallback; warns of a slight slowdown for native code; debuggers cannot attach directly to translated processes | **[project docs]** [[32]](https://docs.orbstack.dev/docker/), [[33]](https://docs.orbstack.dev/machines), [[34]](https://docs.orbstack.dev/settings) |
| **UTM** | "Enable Rosetta (x86_64 Emulation)" for Apple Virtualization Linux VMs; share tag `rosetta` | Yes, `defaultUnixSocket` on macOS 14+ (UTM 4.4.0, Aug 2023) | Support added in UTM 4.0.0 (Aug 2022) for macOS 13; guest steps follow Apple's | **[project docs]** [[35]](https://docs.getutm.app/advanced/rosetta/), [[36]](https://github.com/utmapp/UTM/blob/main/Configuration/UTMAppleConfigurationVirtualization.swift), [[37]](https://github.com/utmapp/UTM/releases/tag/v4.4.0) |
| **Lima** (and **Colima**, which builds on it) | `limactl start --vm-type=vz --rosetta` (Lima ≥ 0.14, macOS ≥ 13); Colima: `colima start --vm-type=vz --vz-rosetta` (v0.5.3+) | Yes: `--device=lima-vm.io/rosetta=cached` (Lima ≥ 2.0, macOS ≥ 14) | Calls Rosetta "much faster" than QEMU user-mode emulation; installs Rosetta via the API if missing | **[project docs]** [[25]](https://lima-vm.io/docs/config/multi-arch/), [[26]](https://github.com/lima-vm/lima/blob/master/pkg/driver/vz/boot.Linux/05-rosetta-volume.sh), [[39]](https://github.com/abiosoft/colima) |
| **Tart** | `tart run --rosetta=<tag>` | No | Requires macOS 13 with Rosetta installed; user must do Apple's guest steps | **[project docs]** [[38]](https://github.com/cirruslabs/tart/blob/main/Sources/tart/Commands/Run.swift) |
| **Podman** (`podman machine`, `applehv` provider) | `rosetta` key in `containers.conf` | Not documented | Added in 5.1.0 (May 2024), on by default; disabled by default in 5.6 (Aug 2025) because Rosetta failed with Linux 6.13+ kernels; Podman 6 defaults to off | **[project docs]** [[40]](https://github.com/containers/podman/releases/tag/v5.1.0), [[41]](https://blog.podman.io/2025/06/podman-and-apple-rosetta/), [[42]](https://blog.podman.io/2025/08/podman-5-6-released-rosetta-status-update/), [[44]](https://github.com/podman-container-tools/container-libs/commit/dbc9788e37c234b74b47ab1d849a48130e03100d) |
| **Parallels Desktop** | Pro/Business editions, from Parallels Desktop 19; in version 27 the checkbox is gone and `prlctl set <vm> --rosetta-linux on` is used | Not documented | Parallels Tools registers the handler; lists Snap packages, cross-architecture dependencies and incomplete RHEL-family support as limitations | **[project docs]** [[45]](https://kb.parallels.com/en/129871), [[46]](https://kb.parallels.com/en/131226), [[70]](https://docs.parallels.com/landing/parallels-desktop-developers-guide/software-development-specific-functions-of-parallels-desktop/using-rosetta-to-run-x86-64-linux-software-on-apple-silicon-macs) |

---

## 8. Performance: what Apple says, and what others report

What Apple documents (all qualitative; Apple publishes no benchmark numbers for Linux guests):

- WWDC22: "it's fast", same technology as on the Mac **[Apple]**
  [[11]](https://developer.apple.com/videos/play/wwdc2022/10002/).
- WWDC23: caching removes re-translation overhead, most visible in exec-heavy workloads **[Apple]**
  [[12]](https://developer.apple.com/videos/play/wwdc2023/10007/).
- The TSO kernel patch raises Rosetta performance and avoids slowing native processes **[Apple]**
  [[9]](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta).
- Enable Rosetta only when needed **[project docs, relaying Apple]**
  [[47]](https://github.com/lima-vm/lima/issues/1269).

What third parties report (anecdotal; methodology varies):

- OrbStack: "over 2x faster" than its non-Rosetta fallback **[project docs]**
  [[32]](https://docs.orbstack.dev/docker/).
- Lima: "much faster" than QEMU user-mode emulation **[project docs]**
  [[25]](https://lima-vm.io/docs/config/multi-arch/).
- A Lima user on an M1 running macOS 15.5 measured native ARM Geekbench 6 in the VM at roughly
  1201/4919 (single/multi) with Rosetta enabled and 2177/6869 with it disabled **[project docs]**
  [[50]](https://github.com/lima-vm/lima/issues/3726). This is one user's measurement, not a
  controlled study.

---

## 9. Limits and known issues

| Limit or issue | Detail | Label / source |
|---|---|---|
| User space only | Intel Linux kernels and distributions cannot be booted; only x86-64 programs inside an ARM64 distribution | **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| Guest setup is the guest's job | The host app cannot script the mount/registration | **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| Libraries | Dynamically linked programs need x86-64 libraries in the guest | **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| macOS 13 flag | `--preserve` must be `no` on macOS 13 hosts | **[Apple]** [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| Vector instructions | Apple's general page says Rosetta translates AVX/AVX2 but not AVX-512; Apple says nothing Linux-specific (see Open questions) | **[Apple]** [[13]](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment) |
| Debugging | `gdb`/`lldb` cannot attach directly to translated processes; OrbStack suggests QEMU's gdb stub instead | **[project docs]** [[33]](https://docs.orbstack.dev/machines) |
| Self-modifying code via double mapping | .NET found Rosetta in x64 containers does not notice when an already-executed code page is modified through a second mapping, and disables its W^X double mapping there | **[project docs]** [[51]](https://github.com/dotnet/runtime/pull/102509) |
| Newer guest kernels (2025) | With Linux 6.13 and later on macOS 15.x hosts, translated programs failed with "unhandled auxillary vector type 29"; Podman and Lima users report it fixed in macOS 26 | **[project docs]** [[49]](https://github.com/lima-vm/lima/issues/3592), [[42]](https://blog.podman.io/2025/08/podman-5-6-released-rosetta-status-update/) |
| macOS 15 beta regression (2024) | Intel binaries failed in VMs on early Sequoia betas; Apple lists the fix in the macOS 15 release notes | **[Apple]** [[18]](https://developer.apple.com/documentation/macos-release-notes/macos-15-release-notes), **[project docs]** [[67]](https://github.com/docker/for-mac/issues/7322) |
| Start-up ordering | Docker Desktop 4.67 (Mar 2026) fixed intermittent `exec format error` caused by a race between `binfmt` registration and the virtiofs device appearing | **[project docs]** [[31]](https://docs.docker.com/desktop/release-notes/) |
| Whole-VM slowdown | See section 6.1 | **[project docs, relaying Apple]** [[47]](https://github.com/lima-vm/lima/issues/1269), [[48]](https://github.com/docker/for-mac/issues/6733) |
| CPU identity | Programs see a synthetic "VirtualApple" CPU in `/proc/cpuinfo`, not the real Apple core | **[RE: Inoki]** [[57]](https://blog.inoki.cc/2026/02/28/Apple-Rosetta-Linux-VM-Secret-en/) |

---

## 10. Apple's licence terms

Stated as found; where a statement is my reading rather than Apple's words, it is marked.

1. **Supported environment.** Apple documents the feature for ARM64 Linux guests of the
   Virtualization framework on Apple silicon Macs running macOS 13 or later **[Apple]**
   [[1]](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms).
2. **No Rosetta-specific licence.** A text search of the English macOS software licence
   agreements for Big Sur, Monterey, Ventura, Sonoma, Sequoia, Tahoe and Golden Gate, the Apple
   Developer Program License Agreement and the Xcode licence found no mention of "Rosetta" or
   "Linux" **[Apple]** [[58]](https://www.apple.com/legal/sla/docs/macOSGoldenGate.pdf),
   [[59]](https://www.apple.com/legal/sla/), [[63]](https://developer.apple.com/support/downloads/terms/apple-developer-program/Apple-Developer-Program-License-Agreement-English.pdf).
   A developer question on Apple's Developer Forums asking which licence covers Rosetta shows no
   answer from Apple **[forum]** [[62]](https://developer.apple.com/forums/thread/691387).
3. **What the install prompt says.** macOS's Rosetta install dialog says use is subject to "the
   original licence agreement that accompanied the software being updated" and links to Apple's
   list of licences **[Apple, quoted in a user forum]**
   [[60]](https://forum.lightburnsoftware.com/t/is-rosetta-stone-required-to-run-lightburn-on-a-macbook-m1/126820).
   `softwareupdate --install-rosetta` asks the user to agree to "the software license agreement"
   and points to the same list **[Apple, quoted]**
   [[61]](https://www.alansiu.net/2020/12/02/installing-rosetta-2-on-m1-apple-silicon-macs/).
4. **The macOS licence's general terms.** The macOS licence covers Apple-provided updates and
   feature enhancements as part of the "Apple Software"; grants use on a single Apple-branded
   computer; does not permit installing, using or running the Apple Software on non-Apple-branded
   computers; and forbids redistributing, sublicensing or reverse-engineering it **[Apple]**
   [[58]](https://www.apple.com/legal/sla/docs/macOSGoldenGate.pdf) (sections 1A, 1B, 2A, 2J, 2N).
   **[Inferred]** Because the Linux translator arrives with Rosetta through Software Update (and is
   part of macOS itself from macOS 27), these general terms are the ones that apply to it; Apple
   has not said so explicitly for Linux.
5. **The kernel patch is open source.** Apple says the TSO patches are open source and may be
   added to kernels or distributions you ship **[Apple]**
   [[9]](https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta).
   `LICENSE.txt` in `RosettaPatch.zip` is an MIT-style permission notice (© 2024 Apple); the
   source headers carry Apple's permissive sample-code licence, and one new header is tagged
   `GPL-2.0-only` **[Apple]** [[10]](https://developer.apple.com/download/files/RosettaPatch.zip).
6. **Tools do not redistribute Rosetta.** The tools in section 7 attach the host's share and ask
   macOS to install Rosetta when needed **[project docs]**
   [[27]](https://github.com/lima-vm/lima/blob/master/pkg/driver/vz/rosetta_directory_share_arm64.go),
   [[28]](https://github.com/apple/containerization/blob/main/Sources/Containerization/VZVirtualMachineInstance.swift).

---

## 11. Open questions

1. **AVX in Linux guests.** Apple's general page says Rosetta translates AVX/AVX2 (wording added
   between September and October 2025), but says nothing Linux-specific. A November 2024 forum
   user reported AVX2 not working in Linux VMs on macOS 15 **[forum]**
   [[66]](https://news.ycombinator.com/item?id=42074592), while a 2026 analysis found the Linux
   runtime's synthetic `/proc/cpuinfo` lists `avx` and `avx2` [[57]](https://blog.inoki.cc/2026/02/28/Apple-Rosetta-Linux-VM-Secret-en/).
   Which macOS version first shipped AVX for Linux guests is unconfirmed.
2. **Default memory model without the patch.** Apple's relayed statements (2023) and its 2024
   article both describe a VM-wide effect. A forum comment claims that from macOS 15 the VM is no
   longer kept in TSO and that Rosetta falls back to non-TSO code if the guest kernel lacks the
   patch **[forum]** [[65]](https://news.ycombinator.com/item?id=42188900). I found no Apple
   statement either way; a July 2025 user measurement on macOS 15.5 still showed native code
   slowing when Rosetta was enabled [[50]](https://github.com/lima-vm/lima/issues/3726). Related
   but not conclusive: Apple's lower-level Hypervisor framework gained `HV_SYS_REG_ACTLR_EL1` in
   macOS 15.0, letting a VM monitor set a guest's `ACTLR_EL1` **[Apple]**
   [[71]](https://developer.apple.com/documentation/hypervisor/hv_sys_reg_actlr_el1) (see also
   `04-hardware-assists.md`).
3. **Exact publication date** of "Accelerating the performance of Rosetta". Evidence brackets it
   between late October 2024 (patch file dates) and 7 November 2024 (first public discussion).
4. **Why the macOS 27 "Linux VMs and containers" sentence disappeared** from Apple's general
   Rosetta page between mid-September and 31 October 2026, while the Virtualization guide still
   carries the macOS 27 statement.
5. **Long-term Linux support.** Apple's macOS 26.4 notes promise continued support for Intel
   binaries in Linux VMs after Rosetta for Mac apps ends [[16]](https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes),
   but a Parallels support article says Rosetta for Linux VMs will stop once Rosetta is removed
   from macOS [[46]](https://kb.parallels.com/en/131226). These conflict; Apple's statement is
   the primary source.
6. **Docker Desktop default.** Docker's 4.25 notes say Rosetta is on by default on macOS 14.1+,
   while the current settings page lists the default as "Disabled" [[31]](https://docs.docker.com/desktop/release-notes/),
   [[30]](https://docs.docker.com/desktop/settings-and-maintenance/settings/).
7. **Shared code with macOS Rosetta.** Apple says "same technology"; the degree of code sharing is
   not public.

---

## Sources

Accessed 31 October 2026 unless noted. Apple developer pages were read through Apple's public
documentation JSON endpoints (`developer.apple.com/tutorials/data/documentation/...`).

1. [Apple] Running Intel Binaries in Linux VMs. https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms
2. [Apple] VZLinuxRosettaDirectoryShare. https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare
3. [Apple] VZLinuxRosettaAvailability. https://developer.apple.com/documentation/virtualization/vzlinuxrosettaavailability
4. [Apple] installRosetta(completionHandler:). https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare/installrosetta(completionhandler:)
5. [Apple] VZLinuxRosettaDirectoryShare.CachingOptions. https://developer.apple.com/documentation/virtualization/vzlinuxrosettadirectoryshare/cachingoptions-swift.enum
6. [Apple] VZLinuxRosettaCachingOptions. https://developer.apple.com/documentation/virtualization/vzlinuxrosettacachingoptions
7. [Apple] VZLinuxRosettaUnixSocketCachingOptions (and initWithPath:error:). https://developer.apple.com/documentation/virtualization/vzlinuxrosettaunixsocketcachingoptions
8. [Apple] VZLinuxRosettaAbstractSocketCachingOptions (and initWithName:error:). https://developer.apple.com/documentation/virtualization/vzlinuxrosettaabstractsocketcachingoptions
9. [Apple] Accelerating the performance of Rosetta. https://developer.apple.com/documentation/virtualization/accelerating-the-performance-of-rosetta
10. [Apple] Rosetta Enhancement Patch (RosettaPatch.zip: RosettaPatch.diff, LICENSE.txt). https://developer.apple.com/download/files/RosettaPatch.zip
11. [Apple] WWDC22 session 10002, "Create macOS or Linux virtual machines". https://developer.apple.com/videos/play/wwdc2022/10002/
12. [Apple] WWDC23 session 10007, "Create seamless experiences with Virtualization". https://developer.apple.com/videos/play/wwdc2023/10007/
13. [Apple] About the Rosetta translation environment (live page). https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment
14. [Apple] Same page, Wayback Machine snapshot of 15 Aug 2026 (JSON). https://web.archive.org/web/20260815045008/https://developer.apple.com/tutorials/data/documentation/apple-silicon/about-the-rosetta-translation-environment.json
15. [project docs] apple/container Discussion #1679, "What happen after rosetta2?" (June 2026). https://github.com/apple/container/discussions/1679
16. [Apple] macOS Tahoe 26.4 Release Notes (Rosetta section). https://developer.apple.com/documentation/macos-release-notes/macos-26_4-release-notes
17. [Apple] macOS 27 Golden Gate Release Notes. https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes
18. [Apple] macOS Sequoia 15 Release Notes (Virtualization section). https://developer.apple.com/documentation/macos-release-notes/macos-15-release-notes
19. [Apple] macOS Tahoe 26 Release Notes. https://developer.apple.com/documentation/macos-release-notes/macos-26-release-notes
20. [Apple] What's new for enterprise in macOS Golden Gate 27. https://support.apple.com/en-us/148830
21. [Apple] Using Intel-based apps on a Mac with Apple silicon. https://support.apple.com/en-us/102527
22. [Apple] Original 2022 article "Running Intel Binaries in Linux VMs with Rosetta", Wayback snapshot of 6 Jun 2022 (JSON). https://web.archive.org/web/20220606194510/https://developer.apple.com/tutorials/data/documentation/virtualization/running_intel_binaries_in_linux_vms_with_rosetta.json
23. [project docs] Linux kernel documentation, binfmt_misc. https://docs.kernel.org/admin-guide/binfmt-misc.html
24. [project docs] elf(5) manual page. https://man7.org/linux/man-pages/man5/elf.5.html
25. [project docs] Lima, "Intel-on-ARM and ARM-on-Intel". https://lima-vm.io/docs/config/multi-arch/
26. [project docs] Lima source, `pkg/driver/vz/boot.Linux/05-rosetta-volume.sh`. https://github.com/lima-vm/lima/blob/master/pkg/driver/vz/boot.Linux/05-rosetta-volume.sh
27. [project docs] Lima source, `pkg/driver/vz/rosetta_directory_share_arm64.go`. https://github.com/lima-vm/lima/blob/master/pkg/driver/vz/rosetta_directory_share_arm64.go
28. [project docs] apple/containerization: README, `Sources/Containerization/Vminitd+Rosetta.swift`, `Sources/Containerization/VZVirtualMachineInstance.swift`, `Sources/ContainerizationOS/Linux/Binfmt.swift`. https://github.com/apple/containerization
29. [project docs] apple/container: README (macOS 26 support), `docs/multiplatform-images.md`, `docs/command-reference.md`, `docs/container-system-config.md`. https://github.com/apple/container
30. [project docs] Docker, "Change your Docker Desktop settings". https://docs.docker.com/desktop/settings-and-maintenance/settings/
31. [project docs] Docker Desktop release notes (4.16, 4.17, 4.25, 4.29, 4.67). https://docs.docker.com/desktop/release-notes/
32. [project docs] OrbStack, Docker containers. https://docs.orbstack.dev/docker/
33. [project docs] OrbStack, Linux machines. https://docs.orbstack.dev/machines
34. [project docs] OrbStack, Settings. https://docs.orbstack.dev/settings
35. [project docs] UTM documentation, Rosetta. https://docs.getutm.app/advanced/rosetta/
36. [project docs] UTM source, `Configuration/UTMAppleConfigurationVirtualization.swift`. https://github.com/utmapp/UTM/blob/main/Configuration/UTMAppleConfigurationVirtualization.swift
37. [project docs] UTM releases v4.0.0 (5 Aug 2022) and v4.4.0 (25 Aug 2023). https://github.com/utmapp/UTM/releases/tag/v4.0.0 and https://github.com/utmapp/UTM/releases/tag/v4.4.0
38. [project docs] Tart source, `Sources/tart/Commands/Run.swift`. https://github.com/cirruslabs/tart/blob/main/Sources/tart/Commands/Run.swift
39. [project docs] Colima README. https://github.com/abiosoft/colima
40. [project docs] Podman v5.1.0 release notes (29 May 2024). https://github.com/containers/podman/releases/tag/v5.1.0
41. [project docs] Podman blog, "Podman and Apple Rosetta" (9 Jun 2025). https://blog.podman.io/2025/06/podman-and-apple-rosetta/
42. [project docs] Podman blog, "Podman 5.6 Released: Rosetta Status Update" (18 Aug 2025). https://blog.podman.io/2025/08/podman-5-6-released-rosetta-status-update/
43. [project docs] podman-machine-os issue #212, "Re-enable Rosetta" (Jan 2026). https://github.com/containers/podman-machine-os/issues/212
44. [project docs] container-libs commit "turn rosetta off by default" (Apr 2026). https://github.com/podman-container-tools/container-libs/commit/dbc9788e37c234b74b47ab1d849a48130e03100d
45. [project docs] Parallels KB 129871, Rosetta in Linux VMs. https://kb.parallels.com/en/129871
46. [project docs] Parallels KB 131226, prlctl in Parallels Desktop 27. https://kb.parallels.com/en/131226
47. [project docs] Lima issue #1269 (Apple response relayed, 10 Jan 2023). https://github.com/lima-vm/lima/issues/1269
48. [project docs] docker/for-mac issue #6733 (Apple feedback relayed, 18 Nov 2023). https://github.com/docker/for-mac/issues/6733
49. [project docs] Lima issue #3592, "unhandled auxillary vector type 29". https://github.com/lima-vm/lima/issues/3592
50. [project docs] Lima issue #3726, Geekbench with and without Rosetta. https://github.com/lima-vm/lima/issues/3726
51. [project docs] dotnet/runtime PR #102509, "Disable W^X in Rosetta emulated x64 containers on macOS". https://github.com/dotnet/runtime/pull/102509
52. [Apple engineer, LKML] Zayd Qumsieh, "tso: aarch64: Expose TSO for virtualized linux on Apple Silicon" (10 Apr 2024), via LWN. https://lwn.net/Articles/969480/
53. [project docs] Hector Martin, "arm64: Support the TSO memory model" (11 Apr 2024), via LWN. https://lwn.net/Articles/969484/
54. [press] Jonathan Corbet, "Support for the TSO memory model on Arm CPUs", LWN (26 Apr 2024). https://lwn.net/Articles/970907/
55. [project docs] Linux mainline `include/uapi/linux/prctl.h` (checked 31 Oct 2026). https://github.com/torvalds/linux/blob/master/include/uapi/linux/prctl.h
56. [press] Howard Oakley, "Explainer: Rosetta 2", The Eclectic Light Company (10 Dec 2022). https://eclecticlight.co/2022/12/10/explainer-rosetta-2/
57. [RE: Inoki] "Things You Might Want to Know About Apple's Rosetta 2 for Linux VMs" (28 Feb 2026). https://blog.inoki.cc/2026/02/28/Apple-Rosetta-Linux-VM-Secret-en/
58. [Apple] macOS software licence agreements (Golden Gate; also Tahoe, Sequoia, Sonoma, Ventura, Monterey, Big Sur PDFs under the same path). https://www.apple.com/legal/sla/docs/macOSGoldenGate.pdf
59. [Apple] Software License Agreements index. https://www.apple.com/legal/sla/
60. [Apple, quoted] Rosetta install dialog text, quoted in LightBurn forum (Jan 2024). https://forum.lightburnsoftware.com/t/is-rosetta-stone-required-to-run-lightburn-on-a-macbook-m1/126820
61. [Apple, quoted] `softwareupdate --install-rosetta` output, quoted by Alan Siu (Dec 2020). https://www.alansiu.net/2020/12/02/installing-rosetta-2-on-m1-apple-silicon-macs/
62. [forum] "Is Rosetta 2 usage covered by a particular license agreement?" https://developer.apple.com/forums/thread/691387
63. [Apple] Apple Developer Program License Agreement (PDF). https://developer.apple.com/support/downloads/terms/apple-developer-program/Apple-Developer-Program-License-Agreement-English.pdf
64. [RE: FFRI] Project Champollion part 1 (oahd and AOT files on macOS). https://ffri.github.io/ProjectChampollion/part1/
65. [forum] Hacker News item 42188900 (Nov 2024). https://news.ycombinator.com/item?id=42188900
66. [forum] Hacker News item 42074592, "Accelerating the Performance of Rosetta in Linux VMs on Apple Silicon" (7 Nov 2024). https://news.ycombinator.com/item?id=42074592
67. [project docs] docker/for-mac issue #7322, Rosetta on macOS Sequoia betas (Jun 2024). https://github.com/docker/for-mac/issues/7322
68. [project docs] Podman Desktop, "Native Apple Rosetta translation layer". https://podman-desktop.io/docs/podman/rosetta
69. [project docs] QEMU source, `scripts/qemu-binfmt-conf.sh`. https://github.com/qemu/qemu/blob/master/scripts/qemu-binfmt-conf.sh
70. [project docs] Parallels Desktop Developer's Guide, "Using Rosetta to Run x86-64 Linux Software on Apple Silicon Macs". https://docs.parallels.com/landing/parallels-desktop-developers-guide/software-development-specific-functions-of-parallels-desktop/using-rosetta-to-run-x86-64-linux-software-on-apple-silicon-macs
71. [Apple] Hypervisor framework, `HV_SYS_REG_ACTLR_EL1` (macOS 15.0+). https://developer.apple.com/documentation/hypervisor/hv_sys_reg_actlr_el1
