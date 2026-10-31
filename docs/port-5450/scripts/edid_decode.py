"""Decode the fields of an EDID 1.4 base block that matter for a laptop panel."""
import sys


def mfg(b):
    v = (b[8] << 8) | b[9]
    return ''.join(chr(((v >> s) & 31) + 64) for s in (10, 5, 0))


def dtd(d):
    clk = (d[0] | d[1] << 8) * 10
    if not clk:
        return None
    ha, hb = d[2] | (d[4] & 0xF0) << 4, d[3] | (d[4] & 0x0F) << 8
    va, vb = d[5] | (d[7] & 0xF0) << 4, d[6] | (d[7] & 0x0F) << 8
    hso, hsw = d[8] | (d[11] & 0xC0) << 2, d[9] | (d[11] & 0x30) << 4
    vso, vsw = d[10] >> 4 | (d[11] & 0x0C) << 2, d[10] & 0x0F | (d[11] & 0x03) << 4
    wmm, hmm = d[12] | (d[14] & 0xF0) << 4, d[13] | (d[14] & 0x0F) << 8
    refresh = clk * 1000 / ((ha + hb) * (va + vb))
    return {
        'pixel_clock_khz': clk, 'h_active': ha, 'h_blank': hb, 'v_active': va, 'v_blank': vb,
        'h_sync_offset': hso, 'h_sync_width': hsw, 'v_sync_offset': vso, 'v_sync_width': vsw,
        'h_total': ha + hb, 'v_total': va + vb, 'refresh_hz': round(refresh, 3),
        'size_mm': (wmm, hmm), 'flags': hex(d[17]),
    }


def descriptor(d):
    tag = d[3]
    text = bytes(d[5:18]).split(b'\n')[0].decode('ascii', 'backslashreplace').rstrip()
    names = {0xFC: 'name', 0xFE: 'text', 0xFF: 'serial', 0xFD: 'range'}
    return names.get(tag, hex(tag)), (text if tag in (0xFC, 0xFE, 0xFF) else bytes(d).hex())


def decode(path):
    b = open(path, 'rb').read()
    base = b[:128]
    out = {
        'file': path, 'length': len(b), 'manufacturer': mfg(base),
        'product': hex(base[10] | base[11] << 8), 'serial_u32': hex(int.from_bytes(base[12:16], 'little')),
        'week_year': (base[16], 1990 + base[17]), 'version': f'{base[18]}.{base[19]}',
        'input': hex(base[20]), 'size_cm': (base[21], base[22]), 'extensions': base[126],
        'checksum_ok': sum(base) % 256 == 0,
    }
    for i, off in enumerate((54, 72, 90, 108)):
        d = base[off:off + 18]
        if d[0] | d[1]:
            out[f'dtd{i}'] = dtd(d)
        else:
            k, v = descriptor(d)
            out[f'desc{i}_{k}'] = v
    if len(b) > 128:
        ext = b[128:256]
        out['ext_tag'] = hex(ext[0])
        out['ext_checksum_ok'] = sum(ext) % 256 == 0
    return out


if __name__ == '__main__':
    for p in sys.argv[1:]:
        for k, v in decode(p).items():
            print(f'{k:16s} {v}')
        print()
