"""Convert a MADT with Local x2APIC entries into the layout VedCloud's Latitude 5350 table uses.

The 5350 table (APIC-Latitude5350.aml) has:
  * legacy Local APIC entries (type 0), one per x2APIC entry, in the firmware's order;
  * processor UIDs renumbered by table position (0, 1, 2 ...), so the first P-core gets UID 0
    ("P-core-first CPU UIDs; original APIC IDs preserved");
  * disabled placeholders with APIC ID 0xFF;
  * the firmware's I/O APIC and interrupt source overrides unchanged.

NMI entries:
  --nmi all     one Local APIC NMI for all processors (UID 0xFF), converted from the
                firmware's single x2APIC NMI (UID 0xFFFFFFFF). The ACPI-spec conversion.
  --nmi 5350    24 Local APIC NMIs for UIDs 1..24 on LINT1, as in the 5350 table.
"""
import argparse
import struct


def parse_subtables(b):
    length = struct.unpack_from('<I', b, 4)[0]
    off, subs = 44, []
    while off < length:
        t, l = b[off], b[off + 1]
        subs.append((t, b[off:off + l]))
        off += l
    return subs


def convert(src, nmi_mode):
    header = bytearray(src[:44])
    body = bytearray()
    x2 = [s for t, s in parse_subtables(src) if t == 9]
    nmis = [s for t, s in parse_subtables(src) if t == 10]
    for uid, s in enumerate(x2):
        apic_id, flags, _ = struct.unpack_from('<III', s, 4)
        if apic_id > 0xFE and apic_id != 0xFFFFFFFF:
            raise SystemExit(f'APIC ID {apic_id:#x} does not fit a legacy Local APIC entry')
        body += struct.pack('<BBBBI', 0, 8, uid, 0xFF if apic_id == 0xFFFFFFFF else apic_id, flags)
    for t, s in parse_subtables(src):
        if t not in (9, 10):
            body += s
    if nmi_mode == 'all':
        for s in nmis:
            flags, uid = struct.unpack_from('<HI', s, 2)
            lint = s[8]
            body += struct.pack('<BBBHB', 4, 6, 0xFF if uid == 0xFFFFFFFF else uid, flags, lint)
    else:
        for uid in range(1, 25):
            body += struct.pack('<BBBHB', 4, 6, uid, 0x0005, 1)
    out = header + body
    struct.pack_into('<I', out, 4, len(out))
    out[9] = 0
    out[9] = (-sum(out)) & 0xFF
    return bytes(out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--nmi', choices=('all', '5350'), default='all')
    a = ap.parse_args()
    out = convert(open(a.src, 'rb').read(), a.nmi)
    open(a.dst, 'wb').write(out)
    print(f'{a.dst}: {len(out)} bytes, checksum ok: {sum(out) % 256 == 0}')
