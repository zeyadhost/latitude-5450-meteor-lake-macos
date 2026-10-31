# Audio: ALC236 layout shortlist for the Latitude 5450

Checklist item **R1**. The 5350 config uses AppleALC with the ALC295 codec, `layout-id 33`. The 5450
has a different codec, so it needs a different layout.

## Hardware

| | Latitude 5350 | Latitude 5450 |
|---|---|---|
| HDA controller | Intel `8086:7E28` (Meteor Lake-P) | Intel `8086:7E28`, the same |
| Codec | Realtek ALC295 | Realtek **ALC236** (`10EC:0236`), subsystem `1028:0CB2`, rev `0x1000` |
| AppleALC layout | 33 | to be tested: see shortlist |

The controller is identical, so the 5350's controller setting carries over unchanged:
`device-id = 0x51CA` at `PciRoot(0x0)/Pci(0x1F,0x3)`. Only the layout changes.

## Layouts AppleALC 1.9.8 offers for the ALC236

This is the AppleALC build shipped in the fork (`latitude-desktop/Audio/AppleALC.kext`). It has 17
ALC236 layouts. Only five are plausible for a Dell business laptop; the rest come from Lenovo and HP
machines.

| Layout | Origin | Built-in mic | Speaker | Headphone | Jack second pin (`0x19`) |
|---|---|---|---|---|---|
| **69** | Dell Ice Lake laptops (Vorshim, for Lorys89) | `0x12` fixed | `0x14` fixed | `0x21` jack | **Mic In** |
| **68** | Dell Vostro 5401 (Lorys89) | `0x12` fixed | `0x14` fixed | `0x21` jack | Line In |
| **11** | Generic (Jake Lo), the common ALC236 default | `0x12` fixed | `0x14` fixed | `0x21` jack | Line In |
| **3** | Generic (Mirone) | `0x12` fixed | `0x14` fixed | `0x21` jack | Line In |
| **54** | Dell Inspiron 5488 (Daggeryu) | `0x12` fixed | `0x14` fixed | `0x21` jack | not used |

Values are decoded from each layout's pin configuration with `docs/port-5450/scripts/alc_layouts.py`.
All five use the standard ALC236 pins: `0x14` speaker, `0x21` headphone, `0x12` built-in mic.

### Test order

1. **69:** a Dell layout that treats the jack's second pin as a microphone, which is what a Dell
   combo headset jack needs.
2. **68:** a Dell layout from the same period.
3. **11:** the usual default for ALC236.
4. **3:** a minimal generic layout.
5. **54:** last resort; it has no headset mic.

Remaining layouts: 12–19, 23, 36 and 99 (Lenovo), 55 (HP).

## Config change

```
DeviceProperties → Add → PciRoot(0x0)/Pci(0x1F,0x3)
  layout-id      (data, 4 bytes, little-endian)   69 → 45000000
  alc-layout-id  (data, 4 bytes, little-endian)   69 → 45000000
  device-id      (data)                           CA510000   (unchanged from the 5350)
```

Hex for the other candidates: 68 → `44000000`, 11 → `0B000000`, 3 → `03000000`, 54 → `36000000`.

Faster for trying layouts: leave the property out and use the boot argument `alcid=69`, then
`alcid=68` and so on. Put the winner into DeviceProperties afterwards.

## What to check for each layout

- Internal speakers play.
- Headphones play, and the speakers mute when they are plugged in.
- A headset microphone records.
- The built-in microphone records.
- Sound still works after sleep, once sleep works.

## Not known yet

- **Built-in microphone.** Whether the 5450's built-in mics reach the Realtek codec at all is not
  confirmed. If they don't, no layout will make them work.
- **The actual pin wiring.** A Linux live-USB boot can print the codec's real pin configuration
  (`/proc/asound/card*/codec#*`), which would pick the right layout directly instead of by trial.
  This belongs in the Linux hardware report.
- **Tahoe.** The 5350 uses SimpleHDA instead of AppleALC on Tahoe. Whether SimpleHDA handles the
  ALC236 is not checked here.
