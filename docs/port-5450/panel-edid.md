# Panel EDID: Latitude 5450 (AUO) vs Latitude 5350 (BOE)

Checklist item **R6**. The 5350's framebuffer code embeds that laptop's panel EDID in
`desktop-sources/latitude_panel_edid.h`. This fork adds a drop-in replacement for the 5450's panel.

## Files

| File | What |
|---|---|
| `desktop-sources/latitude_panel_edid_5450.h` | Same symbols as `latitude_panel_edid.h` (`latitudePanelEDID`, `latitudeEDIDGeometry`), with the 5450's AUO EDID |
| `desktop-sources/test-panel-edid-5450.cpp` | The upstream test adapted to the AUO panel: checksum, native mode, 309×174 mm, 14-inch diagonal, rejection of malformed data |
| `docs/port-5450/panel/AUO-B140HAK-243D.edid.bin` | The raw 128-byte EDID |

Both the original test and the 5450 test compile and pass on a host compiler (MinGW g++, `-std=c++17`).

## How it was captured

From the Windows display registry cache
(`HKLM\SYSTEM\CurrentControlSet\Enum\DISPLAY\AUO243D\...\Device Parameters\EDID`) on 2026-10-31.
Windows holds two copies: a 128-byte one, and a 256-byte one whose second block is all zeros (padding,
not a real extension block). The base blocks are byte-identical.

A Linux capture of `/sys/class/drm/card*-eDP-1/edid` should give the same 128 bytes, which would be a
second confirmation.

## Comparison

| Field | 5350 (BOE) | 5450 (AUO) |
|---|---|---|
| Manufacturer / product | BOE `0x0BAE` | AUO `0x243D` |
| Panel model (text descriptor) | `NV13N49` | `B140HAK` |
| Manufactured | week 38, 2022 | 2018 (week not set) |
| Serial field | 0 | 0 |
| EDID version / input | 1.4, digital (`0xA5`) | 1.4, digital (`0xA5`) |
| Extension blocks | 0 | 0 |
| Physical size (DTD) | 294 × 165 mm (13.3") | **309 × 174 mm (14.0")** |
| Native mode | 1920 × 1080 | 1920 × 1080 |
| Pixel clock (60 Hz mode) | 147,750 kHz | **141,000 kHz** |
| Total h × v | 2160 × 1140 | **2104 × 1116** |
| H sync offset / width | 48 / 32 | **16 / 16** |
| V sync offset / width | 3 / 6 | 3 / **14** |
| Refresh (60 Hz mode) | 60.002 Hz | 60.049 Hz |
| Second timing (low refresh) | 118,200 kHz → 48.0 Hz | 112,800 kHz → 48.0 Hz |
| Vendor-specific descriptor (tag `0x00`) | present | present (different bytes) |

Both panels offer a 48 Hz low-refresh mode, which is useful later for power saving.

## What the EDID is used for

In `nmxvgafb.cpp` (`tahoe-port/Sources/Tahoe-bridge/NMXVGAFB/` and the identical copy in
`NullMoth/kexts/NMXVGAFB/`), the driver:

- reads the **real timing from the GPU's pipe registers** (`htotal`, `vtotal`, sync positions), not from
  the EDID;
- uses the embedded EDID only to report the panel's **physical size** to macOS
  (`imageWidth`/`imageHeight`) and to publish an EDID for display identification.

So a wrong EDID gives macOS the wrong size and panel identity (and with them DPI, scaled-mode choices
and display overrides), but it does not change the scanout timing.

## Using it in a 5450 build

Replace the header before building the framebuffer:

```bash
cp desktop-sources/latitude_panel_edid_5450.h desktop-sources/latitude_panel_edid.h
```

One cosmetic string also names the 5350's capture: the `LatitudePanelEDIDSource` registry property in
`nmxvgafb.cpp` (`"Dell Linux capture 20261012 eDP-1"`). It has no functional effect.

**Note:** Dell ships more than one panel in the same model. This EDID matches this laptop's AUO panel;
another 5450 may have a different panel and needs its own capture.
