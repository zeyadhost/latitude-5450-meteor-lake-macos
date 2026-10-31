"""List the subtables of an ACPI MADT (APIC) table: CPU entries with UID, APIC ID and flags."""
import struct
import sys
from collections import Counter

NAMES = {0: 'LocalAPIC', 1: 'IOAPIC', 2: 'IntSrcOverride', 3: 'NMISource', 4: 'LocalAPIC-NMI',
         5: 'LAPIC-AddrOverride', 9: 'Localx2APIC', 10: 'x2APIC-NMI'}


def parse(path):
    b = open(path, 'rb').read()
    sig, length, rev, csum, oem, oemtab, oemrev = struct.unpack_from('<4sIBB6s8sI', b, 0)
    hdr = {'signature': sig.decode(), 'length': length, 'file_len': len(b), 'revision': rev,
           'checksum_ok': sum(b) % 256 == 0, 'oem': oem.decode().strip(), 'oem_table': oemtab.decode().strip(),
           'oem_rev': oemrev, 'lapic_addr': hex(struct.unpack_from('<I', b, 36)[0]),
           'flags': hex(struct.unpack_from('<I', b, 40)[0])}
    subs, off = [], 44
    while off < length:
        t, l = b[off], b[off + 1]
        e = {'type': NAMES.get(t, f'type{t}'), 'len': l}
        if t == 0:
            e.update(uid=b[off + 2], apic=b[off + 3], flags=struct.unpack_from('<I', b, off + 4)[0])
        elif t == 9:
            apic, flags, uid = struct.unpack_from('<III', b, off + 4)
            e.update(uid=uid, apic=apic, flags=flags)
        elif t == 4:
            e.update(uid=b[off + 2], flags=struct.unpack_from('<H', b, off + 3)[0], lint=b[off + 5])
        elif t == 10:
            e.update(flags=struct.unpack_from('<H', b, off + 2)[0], uid=struct.unpack_from('<I', b, off + 4)[0],
                     lint=b[off + 8])
        elif t == 1:
            e.update(id=b[off + 2], addr=hex(struct.unpack_from('<I', b, off + 4)[0]),
                     gsi=struct.unpack_from('<I', b, off + 8)[0])
        elif t == 2:
            e.update(bus=b[off + 2], src=b[off + 3], gsi=struct.unpack_from('<I', b, off + 4)[0],
                     flags=struct.unpack_from('<H', b, off + 8)[0])
        subs.append(e)
        off += l
    return hdr, subs


def show(path):
    hdr, subs = parse(path)
    print(f'=== {path}')
    print('   ', hdr)
    print('    subtable counts:', dict(Counter(s['type'] for s in subs)))
    for i, s in enumerate(subs):
        if s['type'] in ('LocalAPIC', 'Localx2APIC'):
            en = 'enabled' if s['flags'] & 1 else ('online-capable' if s['flags'] & 2 else 'DISABLED')
            print(f"    [{i:2d}] {s['type']:11s} uid={s['uid']:3d} apic_id={s['apic']:#05x} ({s['apic']:3d}) {en}")
        else:
            extra = {k: v for k, v in s.items() if k not in ('type', 'len')}
            print(f"    [{i:2d}] {s['type']:11s} {extra}")


if __name__ == '__main__':
    for p in sys.argv[1:]:
        show(p)
