# CPU table (MADT/APIC): Latitude 5450

Checklist items **B8** and **R7**. The 5350 config replaces the firmware's MADT (the ACPI table that
lists the CPUs and interrupt controllers) with `APIC-Latitude5350.aml`.

## Result

**The table the 5450 needs is byte-identical to VedCloud's `APIC-Latitude5350.aml`.** Converting
this laptop's own firmware MADT with the 5350 recipe reproduces their file exactly (604 bytes,
SHA-256 `1322249ac822e12592a6f347e8847c26ec4b971da62862222074691edce003bb`, the same hash as all 21
copies in `backups/`).

What does **not** carry over is the config's Delete rule. See *Config changes* below.

## Files (`docs/port-5450/acpi/`)

| File | Size | What |
|---|---|---|
| `APIC-Latitude5450.aml` | 604 B | **Use this.** The 5350 layout, generated from this laptop's firmware table |
| `APIC-Latitude5450.dsl` | — | Decompiled source for review (iasl 20260408) |
| `APIC-5450-firmware.aml` / `.dsl` | 856 B | This laptop's original firmware MADT (Windows dump, BIOS 1.24.0) |
| `APIC-Latitude5450-specnmi.aml` / `.dsl` | 466 B | Experimental alternative: one ACPI-spec "all processors" NMI entry instead of 24 per-CPU entries. Untested; keep for later |

Scripts in `docs/port-5450/scripts/`: `madt_dump.py` lists a MADT's entries; `madt_convert.py`
converts it (`--nmi 5350` gives the shipped table, `--nmi all` the experimental one).

Recompiling `APIC-Latitude5450.dsl` with iasl produces the same table except for iasl's own creator
stamp in the header (`INTL`, 20260408) and the checksum. The shipped `.aml` keeps the original header.

## What the firmware has and what the 5350 table changes

Both laptops list the same 14 CPUs (Core Ultra 5 135U) in the same order with the same APIC IDs,
followed by 34 disabled placeholders:

| Table position | APIC IDs | Core type | Firmware UIDs (5450) | 5350-layout UIDs |
|---|---|---|---|---|
| 0–3 | 16, 17, 24, 25 | P-cores (2 cores × 2 threads) | 8–11 | **0–3** |
| 4–11 | 0, 2, 4, 6, 8, 10, 12, 14 | E-cores | 0–7 | 4–11 |
| 12–13 | 64, 66 | LP E-cores (low-power island) | 12–13 | 12–13 |
| 14–47 | none (placeholders) | disabled | 14–47 | 14–47 |

The 5350 layout makes three changes:

1. **Legacy entries.** The 5450 firmware describes CPUs with **Local x2APIC** entries (16 bytes each,
   ACPI type 9). The 5350 table uses **legacy Local APIC** entries (8 bytes, type 0). All APIC IDs here are
   below 255, so they fit.
2. **P-core-first UIDs.** Each CPU's processor UID becomes its table position, so the first P-core
   thread gets UID 0. APIC IDs stay unchanged ("original APIC IDs preserved", in VedCloud's words).
3. **NMI entries.** The firmware has one x2APIC NMI entry for all processors (LINT1, level-triggered,
   flags `0xD`). The 5350 table has 24 legacy NMI entries for UIDs 1–24 (LINT1, edge-triggered,
   flags `0x5`).

### Why the 5350 needed fewer changes

The 5350 config's Delete rule removes a firmware MADT of **604 bytes**, the size of a legacy-entry
table. So the 5350's firmware already used legacy entries, and VedCloud only renumbered the UIDs.
The 5450 firmware (BIOS 1.24.0, as dumped from Windows) uses x2APIC entries (856 bytes).

**Unconfirmed:** a BIOS setting may control this. Intel firmware often switches to x2APIC entries when
VT-d/Kernel DMA Protection is on. Check this when you go through the BIOS settings, and dump the MADT
again after any change.

Whether macOS would boot with the firmware's x2APIC table unchanged has not been tested. The 5350
layout is the one that has booted on this platform.

## Config changes for the 5450

| Section | 5350 config | 5450 config |
|---|---|---|
| ACPI → Add | `APIC-Latitude5350.aml` | `APIC-Latitude5450.aml` (same bytes; renamed so the config says what it is) |
| ACPI → Delete | `TableSignature APIC`, `OemTableId "Dell Inc"`, `TableLength 604`, `All true` | Same, but **`TableLength 0`** |

**Why `TableLength 0`:** this laptop's firmware MADT is 856 bytes, so the 5350's rule (604 bytes)
never matches. The firmware table would stay, and macOS would get two MADTs. A rule of `856` would
work today, but would silently stop working if a BIOS setting switched the firmware back to legacy
entries (604 bytes). With `0`, the rule removes any `APIC` table whose OEM table ID is `Dell Inc`.
OpenCore applies Delete to the firmware's tables before Add, so the injected table isn't affected.
