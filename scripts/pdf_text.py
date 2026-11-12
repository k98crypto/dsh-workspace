"""Extract positioned text from the 国家助学金 form PDF using its Type3 fonts + ToUnicode CMaps."""
import re, zlib, json, collections

SRC = r"C:\Users\k_981\Desktop\本专科生国家助学金申请表（2025版）.pdf"
data = open(SRC, "rb").read()
objs = {}
for m in re.finditer(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b", data):
    start = m.end()
    end = data.find(b"endobj", start)
    objs[int(m.group(1))] = data[start:end]


def obj_stream(num):
    raw = objs.get(num, b"")
    m = re.search(rb"stream\r?\n", raw)
    if not m:
        return None
    start = m.end()
    end = raw.find(b"endstream", start)
    body = raw[start:end]
    head = raw[:m.start()]
    if b"FlateDecode" in head:
        try:
            body = zlib.decompress(body)
        except Exception:
            return None
    return body


def parse_tounicode(body):
    """Return dict code(int) -> str"""
    txt = body.decode("latin1", "replace")
    cmap = {}
    for blk in re.findall(r"beginbfchar(.*?)endbfchar", txt, re.S):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            u = "".join(chr(int(dst[i:i+4], 16)) for i in range(0, len(dst), 4))
            cmap[int(src, 16)] = u
    for blk in re.findall(r"beginbfrange(.*?)endbfrange", txt, re.S):
        for lo, hi, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            lo_i, hi_i, d0 = int(lo, 16), int(hi, 16), int(dst, 16)
            for k in range(lo_i, hi_i + 1):
                cmap[k] = chr(d0 + (k - lo_i))
    return cmap


# page 2 resources: font name -> obj
page_raw = objs[2]
page = page_raw.decode("latin1")
media = re.search(r"/MediaBox\s*\[([^\]]*)\]", page)
print("MediaBox:", media.group(1) if media else None)
contents = re.findall(r"/Contents\s+(\d+)\s+\d+\s+R", page)
print("Contents:", contents)
fonts = dict((m.group(1), int(m.group(2))) for m in re.finditer(r"/(F\d+)\s+(\d+)\s+\d+\s+R", page))
print("fonts:", len(fonts))

font_cmaps = {}
for name, num in fonts.items():
    raw = objs.get(num, b"")
    tu = re.search(rb"/ToUnicode\s+(\d+)\s+\d+\s+R", raw)
    if tu:
        body = obj_stream(int(tu.group(1)))
        if body:
            font_cmaps[name] = parse_tounicode(body)
    # widths
print("cmaps:", len(font_cmaps))
for n in list(font_cmaps)[:3]:
    print(n, list(font_cmaps[n].items())[:12])

# content stream: concatenate
cbody = b"\n".join(filter(None, [obj_stream(c) for c in contents]))
print("content bytes:", len(cbody))
open(r"D:\DSH Workspace\work\content.txt", "wb").write(cbody)

# tokenise text ops
items = []
def hexstr_to_codes(h):
    h = re.sub(r"\s+", "", h)
    if len(h) % 2:
        h += "0"
    return [int(h[i:i+2], 16) for i in range(0, len(h), 2)]


tm = [1, 0, 0, 1, 0, 0]
tlm = list(tm)
cur_font = None
cur_size = 0
leading = 0
stack = []


def mat_mul(a, b):
    return [
        a[0]*b[0] + a[1]*b[2],
        a[0]*b[1] + a[1]*b[3],
        a[2]*b[0] + a[3]*b[2],
        a[2]*b[1] + a[3]*b[3],
        a[4]*b[0] + a[5]*b[2] + b[4],
        a[4]*b[1] + a[5]*b[3] + b[5],
    ]


tok_re = re.compile(rb"/([A-Za-z0-9]+)\s+[\d.]+\s+Tf|\[(.*?)\]\s*TJ|\((.*?)\)\s*Tj|(<[0-9A-Fa-f\s]*>)\s*Tj|([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+Tm|([\d.eE+-]+)\s+([\d.eE+-]+)\s+Td|([\d.eE+-]+)\s+([\d.eE+-]+)\s+TD|([\d.eE+-]+)\s+TL|BT|ET|q|Q", re.S)
for m in tok_re.finditer(cbody):
    if m.group(1):
        cur_font = m.group(1).decode()
    elif m.group(2) is not None:
        pass
    elif m.group(5):
        tm = [float(m.group(i)) for i in range(5, 11)]
        tlm = list(tm)
    elif m.group(11) is not None:
        tlm = mat_mul([1, 0, 0, 1, float(m.group(11)), float(m.group(12))], tlm)
        tm = list(tlm)
    elif m.group(13) is not None:
        leading = -float(m.group(14))
        tlm = mat_mul([1, 0, 0, 1, float(m.group(13)), float(m.group(14))], tlm)
        tm = list(tlm)
    elif m.group(15) is not None:
        leading = float(m.group(15))

# simpler robust pass: iterate showing operators sequentially through the raw stream
print("--- sample content ---")
print(cbody[:1500].decode("latin1"))
