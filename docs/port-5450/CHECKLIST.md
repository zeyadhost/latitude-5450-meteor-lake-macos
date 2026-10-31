# Latitude 5450 port checklist

Everything in VedCloud's fork that is tied to the Latitude 5350 and must change, be replaced
or be checked for the Latitude 5450. Organised by priority: **BLOCK** (code that refuses to
run), **REPLACE** (wrong hardware, must change), **CHECK** (may work, needs verification),
**DOCS** (text references, no runtime effect).

> **Hardware inventory source:** `acpi/device-paths.txt` and the Windows PnP dump from this
> session. A Linux live-USB report is still needed for firmware versions and display wiring.

## Progress

| Item | Status | Details |
|---|---|---|
| R6 Panel EDID | **Done.** 5450 header written; the original and 5450 tests compile and pass | [panel-edid.md](panel-edid.md) |
| B8 / R7 CPU table (APIC) | **Done.** Generated from this laptop's firmware; byte-identical to the 5350's table. The Delete rule must change to `TableLength 0` | [apic.md](apic.md) |
| R1 Audio | **Shortlist ready:** test layouts 69, 68, 11, 3, 54 in that order | [audio-alc236.md](audio-alc236.md) |

---

## BLOCK — code that checks for the 5350 and refuses the 5450

These stop the port dead. Fix them first.

| # | What | 5350 value | 5450 value | Files (non-backup) | Action |
|---|------|-----------|-----------|---------------------|--------|
| B1 | **GPU subsystem ID gate** in the Tahoe runtime check | `0x0cb6` | `0x0cb2` | `tahoe-port/Sources/Runtime/Sources/tahoe-runtime-check.m:32-33` | Change `0x0cb6` → `0x0cb2` (or accept both) |
| B2 | **GPU subsystem ID gate** in the VGAFB framebuffer | `0x0cb6` | `0x0cb2` | `tahoe-port/Sources/Tahoe-bridge/NMXVGAFB/nmxvgafb.cpp:649` | Change `!= 0x0cb6` → accept `0x0cb2` |
| B3 | **GPU subsystem ID** in LatitudePanelClaim | `0x0cb6` | `0x0cb2` | `desktop-sources/LatitudePanelClaim.cpp:44` | Change `sd!=0x0cb6` |
| B4 | **GPU subsystem ID** in LatitudeMTLFB Info.plist | `0x0cb61028` | `0x0cb21028` | `desktop-build/LatitudeMTLFB.kext/Contents/Info.plist:32` | Change IOPCISubDevId |
| B5 | **GPU subsystem ID** in touchpad I2C power check | `0x0cb6` | `0x0cb2` | `touchpad-sources/latitude_i2c_power.h:6`, `touchpad-sources/test-power.py:9`, `touchpad-sources/build.py:9` | Change subsystem check |
| B6 | **GPU subsystem ID** in touchpad candidate plist | `0x0cb61028` | `0x0cb21028` | `touchpad-candidate/.../Info.plist:38` | Change |
| B7 | **DSDT.aml** — the 5350's patched firmware DSDT | 557,441 bytes, Dell 5350 | Must be dumped from the 5450 | Every `config.plist` lists `DSDT.aml` in ACPI→Add; 14+ copies across `port-artifacts/`, `latitude-desktop/`, `touchpad-candidate/` | Replace with our own DSDT (already dumped: `acpi/raw/DSDT.aml`, 557,912 bytes) |
| B8 | **APIC-Latitude5350.aml** — custom MADT with P-core-first UIDs | 604 bytes, 5350 CPU topology | Must match 5450's APIC table | All config.plist files reference it in ACPI→Add; ACPI→Delete drops the original APIC by `TableLength=604` | Build a new one from our `acpi/raw/APIC.aml` (856 bytes — **different size**, so the Delete rule's TableLength must also change) |

---

## REPLACE — wrong hardware, must swap the driver or config

| # | What | 5350 | 5450 | Files | Action |
|---|------|------|------|-------|--------|
| R1 | **Audio codec** | Realtek ALC295, layout-id 33, device-id spoof `0x51CA` | Realtek **ALC236** | `README.md`, config.plist `DeviceProperties` at `PciRoot(0x0)/Pci(0x1F,0x3)`, `desktop-sources/test-audio-plan.py`, `tahoe-port/Sources/Builders/prepare-audio.py`, `tahoe-port/Sources/Runtime/Sources/combine-audio-graphics.py` (6+ files), `research/nightshift-and-audio-0.3.16.md` | Find correct AppleALC layout-id for ALC236 on Dell (likely layout 11, 15 or 36 — needs testing). Change `alc-layout-id`, `layout-id` and `device-id` in DeviceProperties. SimpleHDA config for Tahoe also needs ALC236 support. |
| R2 | **Wi-Fi card and driver** | Intel CNVi `8086:7E40` (Meteor Lake built-in), custom AirportItlwm with MTL PCI match, `iwlwifi-ma-b0-gf-a0-83.ucode`, fragmented PNVM loader | Intel AC 8260 `8086:24F3` (separate PCIe card) | `tahoe-port/Sources/Network/` (itlwm driver with `0x7e40` matches), all 3 AirportItlwm Info.plists, `wireless-sources/` (6+ files with `0x7e40`), config.plist DeviceProperties at `PciRoot(0x0)/Pci(0x14,0x3)` | **Much simpler:** use the standard community AirportItlwm/itlwm — AC 8260 is well-supported with no custom patches. Remove the `PciRoot(0x0)/Pci(0x14,0x3)` DeviceProperties entry (it has MTL-specific trial flags). The Wi-Fi PCI path changes: 5350 is `0x14,0x3` (CNVi), 5450 is `RP10.PXSX` at `0x6,0x0` → `0x0,0x0`. |
| R3 | **Bluetooth** | Intel `8087:0033` (CNVi companion) | Intel `8087:0A2B` (AC 8260 companion) | `desktop-sources/publish-peripherals.py:23`, `desktop-sources/prepare-peripherals.py:55`, `tahoe-port/Sources/Native-Bluetooth-source/NativeLEHandshake.hpp:1`, `latitude-desktop/BUILD-MANIFEST.json:1465`, 4 VALIDATION.json files | Use the standard IntelBluetoothFirmware — `0A2B` is supported out of the box. Remove or update any hardcoded USB ID checks. |
| R4 | **Touchpad** | ELAN `04F3:328E` on I2C3 (`_SB.PC00.I2C3.TPD0`) | Cirque `VEN_0488` on I2C3 (`_SB.PC00.I2C3.TPD0`) | `desktop-sources/test-hid-readguard.py:33` (`wProductID=0x328e`), `gpio-sources/HID-before-irq-required.cpp:602`, `tablet-sources/` (5+ files), `tahoe-port/Sources/Touchpad-experimental/` (3+ files), `touchpad-sources/` (all files), `latitude-desktop/BUILD-MANIFEST.json:1040,1469` | Same I2C bus and ACPI device (`TPD0`), different HID product. Change every `0x328e`/`ELAN04F3` check. The SSDT-LAT-TPD0 fix for `_DSM`/`_CRS` (XDSM/XCRS rename) **should still apply** since our DSDT has the same `HIDG` scoping bug. But: (a) verify the Cirque's HID descriptor, (b) the `LatitudeI2CMeteorLake` kext's I2C timing may need changes, (c) VoodooI2CHID needs to recognise the Cirque. |
| R5 | **Touchscreen** | Wacom (3 SSDTs: SSDT-WACOM-DIRECT/GPIO/RES) on I2C0 (`_SB.PC00.I2C0.TPL0`) | ELAN `ELAN900C` on I2C0 (`_SB.PC00.I2C0.TPL0`) | All config.plist ACPI→Add entries, `latitude-desktop/BUILD-MANIFEST.json:623-625`, 15+ VALIDATION.json files | Remove the 3 SSDT-WACOM-*.aml from ACPI→Add. The ELAN touchscreen should work with VoodooI2CHID without custom SSDTs (it's a standard I2C-HID device). DeviceProperties at `PciRoot(0x0)/Pci(0x15,0x0)` has Wacom-specific entries (`LatitudeWacomResourceFallback`, `wacom-polling-wifi-init-test2`) — remove them. Keep `force-polling` if GPIO interrupts don't work on the ELAN. |
| R6 | **Panel EDID** | BOE 13.3" 1920×1080, pixel clock 147,750 kHz | AUO `243D` (B140HAK) 14" 1920×1080, pixel clock 141,000 kHz | `desktop-sources/latitude_panel_edid.h:4` (hardcoded BOE EDID bytes), `MyIntelGPU/ports/latitude5350/hardware-profile.json:30` | **Done:** `desktop-sources/latitude_panel_edid_5450.h` (see [panel-edid.md](panel-edid.md)). The framebuffer takes timing from the GPU's pipe registers; the EDID only gives macOS the panel's size and identity. |
| R7 | **Custom APIC table** | `APIC-Latitude5350.aml`, 604 bytes | Same 14 CPUs and APIC IDs; the 5450 firmware uses x2APIC entries (856 bytes) | See B8 above | **Done:** `docs/port-5450/acpi/APIC-Latitude5450.aml`, byte-identical to the 5350's table. Set the ACPI→Delete rule to `TableLength 0` (see [apic.md](apic.md)). |
| R8 | **USB map** | `UTBMap.kext` (no executable, just a plist mapping 5350's ports) | 5450's USB ports differ | `touchpad-candidate/`, config.plist Kernel→Add | Generate a new USB map with USBToolBox on the 5450. The tool runs from Windows. |
| R9 | **Keyboard ACPI ID** | `DLLK0CB6` (in the 5350's DSDT, PS2 keyboard) | `DLLK0CB2` (in our DSDT) | VoodooPS2Controller matches by ACPI, should handle any DLLK* | **Check only** — VoodooPS2 should match generically. Verify the Copilot key scancode is the same. |

---

## CHECK — may work as-is, needs verification on the 5450

| # | What | Notes | Files |
|---|------|-------|-------|
| C1 | **CPUID spoof** (Comet Lake-S `0xA5`) | Same CPU, should be identical | config.plist Kernel→Emulate |
| C2 | **SMBIOS** (`MacBookPro16,2`) | Works for Meteor Lake on 5350; should work for 5450 | config.plist PlatformInfo (generate new serials) |
| C3 | **GPU driver** (NMXGPU 1.0.15 + NMXAccel) | Same GPU chip `8086:7D45`. Matches by primary PCI ID, not subsystem. **Should work** after fixing B1–B6. | `latitude-runtime/`, `latitude-desktop/` |
| C4 | **Boot args** | Most are generic. `itlwm_mtl_internal_aux=1` is for the MTL Wi-Fi — remove it for AC 8260. | config.plist NVRAM→Add boot-args |
| C5 | **SIP / AMFI settings** | Same requirements | `csr-active-config = 0x0A43`, same boot-args |
| C6 | **Standard SSDTs** (EC, GPI0, PNLF, PLUG-ALT, XOSI, USBX, SBUS, MCHC, ALS0, RTCAWAC) | All reference ACPI paths that exist in our DSDT (verified by `scripts/ssdt_paths.py`) | config.plist ACPI→Add |
| C7 | **SSDT-LAT-BRT** (brightness keys) | Hooks `_Q66` EC event and `BRT6`. Verify these methods exist in our DSDT and do the same thing. | `desktop-sources/SSDT-LAT-BRT.dsl` |
| C8 | **SSDT-LAT-TPD0** (touchpad _DSM fix) | Same ACPI path `_SB.PC00.I2C3.TPD0`, same `HIDG` bug. The fix should apply, but the HID descriptor handle (`TPDH`) must return the Cirque's values, not the ELAN's. | `touchpad-sources/SSDT-LAT-TPD0.dsl` |
| C9 | **DMAR drop** | Comment says "Core Ultra hangs at kernel hand-off with it". Same SoC, same issue expected. | config.plist ACPI→Delete |
| C10 | **Kernel quirks** | All are for Meteor Lake / Comet Lake CPUID spoof. Should be the same. | config.plist Kernel→Quirks |
| C11 | **LatitudeHotkeys** | Dell-specific Fn key handler. May need different scancodes for the 5450's keyboard layout. | `hotkey-build/LatitudeHotkeys.kext` |
| C12 | **Ethernet** (not in 5350 config) | 5450 has Intel I219-LM `8086:550A` at `_SB.PC00.GLAN`. Needs `IntelMausi.kext` added to Kernel→Add. | Not present — must add |
| C13 | **NVMe** | 5350 uses NVMeFix. 5450 has Samsung PM9C1a — should work, but verify VMD is off in BIOS. | config.plist Kernel→Add `NVMeFix.kext` |
| C14 | **SSDT-LAT-TABLET** (tablet mode) | The 5450 is NOT a 2-in-1, so this SSDT is irrelevant. Remove it if present. | `tablet-sources/SSDT-LAT-TABLET.dsl` |

---

## DOCS — text and metadata references, no runtime effect but should be updated

| # | What | Count (non-backup) | Action |
|---|------|--------------------|--------|
| D1 | `Dell Latitude 5350` model name in README, AGENTS.md, ROADMAP.md, PORT-STATUS.md, BUILD-MANIFEST.json, research/ | ~15 files | Update or add "5450" alongside |
| D2 | `BOE` panel manufacturer in README, ROADMAP, desktop-sources | ~6 files | Note AUO panel |
| D3 | `ALC295` in README, research notes | ~11 files | Note ALC236 |
| D4 | `/Users/ved/` developer paths in build logs, PORT-STATUS, publish scripts | ~80 files | Not runtime-breaking but confusing; clean up over time |
| D5 | `/Volumes/SEQOUIA/iGPU-Port/` USB volume paths in all publish/install scripts | ~100+ files | These scripts won't run on your machine anyway; update if you write new ones |
| D6 | `8087:0033` Bluetooth USB ID in VALIDATION.json, BUILD-MANIFEST | ~8 files | Update metadata |
| D7 | `ELAN04F3:328E` touchpad in BUILD-MANIFEST, README | ~20 files | Update metadata |
| D8 | Hardware profile JSON | 1 file | Create `MyIntelGPU/ports/latitude5450/hardware-profile.json` from our inventory |

---

## What we still need (from a Linux live-USB boot)

| Data | Why | How to collect |
|------|-----|----------------|
| `i915` dmesg output | Confirms GuC/DMC/HuC/GSC firmware versions, GPU stepping, display pipe wiring, eDP link parameters | `dmesg \| grep -i i915 > i915-dmesg.txt` |
| `lspci -nnvvv` | Full PCI topology with subsystem IDs and BAR sizes | `lspci -nnvvv > lspci.txt` |
| Panel EDID via `i915` | The EDID bytes the GPU reads from the panel over eDP AUX, more complete than Windows | `cat /sys/class/drm/card*-eDP-1/edid > edid.bin` |
| VBT (Video BIOS Table) | Panel timing, backlight type, connector configuration | `cat /sys/kernel/debug/dri/0/i915_vbt > vbt.bin` |
| `i915_capabilities` | Stolen memory, GuC features, GGTT/PPGTT sizes | `cat /sys/kernel/debug/dri/0/i915_capabilities` |
| `i915_display_info` | Active pipes, connectors, encoder assignments | `cat /sys/kernel/debug/dri/0/i915_display_info` |
| I2C/HID device info for touchpad and touchscreen | HID descriptors, I2C addresses, interrupt pins | `cat /sys/bus/i2c/devices/*/name; dmesg \| grep -i 'i2c\|hid\|elan\|cirque'` |
| Full ACPI dump from Linux | Sometimes more complete than Windows, and matches what the hackintosh community expects | `sudo cat /sys/firmware/acpi/tables/DSDT > DSDT.aml` etc. |

---

## Summary: minimum changes for a first boot attempt

1. **Replace** `DSDT.aml` with our own (B7)
2. **Replace** `APIC-Latitude5350.aml` and update the Delete rule's TableLength (B8/R7)
3. **Change** the six `0x0cb6` subsystem checks to accept `0x0cb2` (B1–B6)
4. **Change** audio to ALC236 with the right layout-id (R1)
5. **Swap** AirportItlwm to the standard AC 8260 build, remove MTL Wi-Fi DeviceProperties (R2)
6. **Remove** the 3 SSDT-WACOM-*.aml and their Wacom DeviceProperties (R5)
7. **Replace** the panel EDID in `latitude_panel_edid.h` (R6)
8. **Generate** a new USB map with USBToolBox (R8)
9. **Add** IntelMausi.kext for Ethernet (C12)
10. **Remove** `itlwm_mtl_internal_aux=1` from boot-args (C4)
11. **Generate** new SMBIOS serials (C2)
12. **Remove** SSDT-LAT-TABLET if present (C14)

The touchpad (R4) can wait — it's broken on the 5350 too. Get the desktop working first.
