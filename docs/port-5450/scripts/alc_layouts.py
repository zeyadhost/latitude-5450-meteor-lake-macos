"""Decode AppleALC ConfigData verbs for one codec into a per-pin table."""
import plistlib
import sys

DEVICES = ['Line Out', 'Speaker', 'HP Out', 'CD', 'SPDIF Out', 'Digital Out', 'Modem Line', 'Modem Handset',
           'Line In', 'AUX', 'Mic In', 'Telephony', 'SPDIF In', 'Digital In', 'Reserved', 'Other']
CONNECT = ['Jack', 'None', 'Fixed', 'Both']


def pins(config):
    regs, other = {}, 0
    for i in range(0, len(config) - 3, 4):
        verb = int.from_bytes(config[i:i + 4], 'big')
        nid, vid, payload = (verb >> 20) & 0xFF, (verb >> 8) & 0xFFF, verb & 0xFF
        if 0x71C <= vid <= 0x71F:
            regs.setdefault(nid, [0, 0, 0, 0])[vid - 0x71C] = payload
        else:
            other += 1
    out = {}
    for nid, b in sorted(regs.items()):
        cfg = b[0] | b[1] << 8 | b[2] << 16 | b[3] << 24
        out[nid] = {
            'connect': CONNECT[cfg >> 30], 'device': DEVICES[(cfg >> 20) & 0xF],
            'assoc_seq': f'{(cfg >> 4) & 0xF}/{cfg & 0xF}', 'raw': f'{cfg:08X}',
        }
    return out, other


def main(kext_plist, codec_id, layouts):
    p = plistlib.load(open(kext_plist, 'rb'))
    ents = p['IOKitPersonalities']['as.vit9696.AppleALC']['HDAConfigDefault']
    for e in sorted((e for e in ents if e.get('CodecID') == codec_id), key=lambda e: e['LayoutID']):
        if layouts and e['LayoutID'] not in layouts:
            continue
        table, other = pins(e.get('ConfigData', b''))
        used = {n: v for n, v in table.items() if v['connect'] != 'None'}
        print(f"layout {e['LayoutID']} — {e.get('Codec')} — {other} non-pin verbs")
        for nid, v in used.items():
            print(f"   NID 0x{nid:02X}  {v['connect']:5s} {v['device']:9s} assoc/seq {v['assoc_seq']:5s} {v['raw']}")
        off = [f'0x{n:02X}' for n, v in table.items() if v['connect'] == 'None']
        print(f"   disabled: {', '.join(off) or '-'}")


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2], 16), {int(x) for x in sys.argv[3:]})
