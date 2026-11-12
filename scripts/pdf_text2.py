"""Extract positioned text lines from the form PDF (Type3 subset fonts + ToUnicode)."""
import re, zlib, json, collections

SRC = r"C:\Users\k_981\Desktop\本专科生国家助学金申请表（2025版）.pdf"
OUT = r"D:\DSH Workspace\work\pdf_text_out.txt"
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
            d = zlib.decompressobj()
            body = d.decompress(body)
            body += d.flush()
        except Exception as e:
            return None
    return body


def parse_tounicode(body):
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


page = objs[2].decode("latin1")
contents = re.findall(r"/Contents\s+(\d+)\s+\d+\s+R", page)
fonts = dict((m.group(1), int(m.group(2))) for m in re.finditer(r"/(F\d+)\s+(\d+)\s+\d+\s+R", page))
font_cmaps, font_widths = {}, {}
for name, num in fonts.items():
    raw = objs.get(num, b"")
    tu = re.search(rb"/ToUnicode\s+(\d+)\s+\d+\s+R", raw)
    if tu:
        b = obj_stream(int(tu.group(1)))
        if b:
            font_cmaps[name] = parse_tounicode(b)
    wm = re.search(rb"/Widths\s*\[([^\]]*)\]", raw, re.S)
    if wm:
        font_widths[name] = [float(x) for x in wm.group(1).split()]
    # FontMatrix scale
cbody = b"\n".join(filter(None, [obj_stream(int(c)) for c in contents]))

# --- interpret content stream ---
num_re = r"[-+]?[\d.]+"
_pat = (
    r"/(F\d+)\s+(%s)\s+Tf" % num_re
    + (r"|(%s)\s+(%s)\s+(%s)\s+(%s)\s+(%s)\s+(%s)\s+Tm" % ((num_re,) * 6))
    + (r"|(%s)\s+(%s)\s+(TD|Td)" % ((num_re,) * 2))
    + (r"|(%s)\s+TL" % num_re)
    + r"|\[((?:[^\[\]\\]|\\.)*)\]\s*TJ"
    + r"|\(((?:[^()\\]|\\.)*)\)\s*Tj"
    + r"|(<[0-9A-Fa-f\s]*>)\s*Tj"
    + r"|(BT|ET)"
)
tokens = re.findall(_pat, cbody.decode("latin1"), re.S)

tm = [1.0, 0, 0, 1.0, 0, 0]
tlm = list(tm)
cur = None
size = 0.0
leading = 0.0
runs = []


def mmul(a, b):
    return [a[0]*b[0]+a[1]*b[2], a[0]*b[1]+a[1]*b[3],
            a[2]*b[0]+a[3]*b[2], a[2]*b[1]+a[3]*b[3],
            a[4]*b[0]+a[5]*b[2]+b[4], a[4]*b[1]+a[5]*b[3]+b[5]]


def decode_hex_codes(h):
    h = h.strip()
    if h.startswith("<"):
        h = h[1:]
    if h.endswith(">"):
        h = h[:-1]
    h = re.sub(r"\s+", "", h)
    if len(h) % 2:
        h += "0"
    return [int(h[i:i+2], 16) for i in range(0, len(h), 2)]


def decode_lit(s):
    out = []
    i = 0
    esc = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "(": "(", ")": ")", "\\": "\\"}
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i+1]
            if n in esc:
                out.append(ord(esc[n]))
                i += 2
                continue
            if n.isdigit():
                j = i + 1
                oct_digits = ""
                while j < len(s) and s[j].isdigit() and len(oct_digits) < 3:
                    oct_digits += s[j]
                    j += 1
                out.append(int(oct_digits, 8) & 0xFF)
                i = j
                continue
            i += 2
            continue
        out.append(ord(c))
        i += 1
    return out


for t in tokens:
    (fname, fsize, a, b, c, d, e, f, td1, td2, tdop, tl, arr, lit, hexs, bt) = t
    if fname:
        cur, size = fname, float(fsize)
    elif a:
        tm = [float(x) for x in (a, b, c, d, e, f)]
        tlm = list(tm)
    elif tdop:
        dx, dy = float(td1), float(td2)
        if tdop == "TD":
            leading = -dy
        tlm = mmul([1, 0, 0, 1, dx, dy], tlm)
        tm = list(tlm)
    elif tl:
        leading = float(tl)
    elif arr:
        # TJ array: strings + numbers (kerning); emit text per string
        codes = []
        for part in re.finditer(r"\(((?:[^()\\]|\\.)*)\)|<([0-9A-Fa-f\s]*)>|([-+]?[\d.]+)", arr, re.S):
            if part.group(1) is not None:
                codes += decode_lit(part.group(1))
            elif part.group(2):
                codes += decode_hex_codes(part.group(2))
            else:
                codes.append(None)  # kerning marker
        runs.append((tm[4], tm[5], size, cur, codes))
    elif lit:
        runs.append((tm[4], tm[5], size, cur, decode_lit(lit)))
    elif hexs:
        runs.append((tm[4], tm[5], size, cur, decode_hex_codes(hexs)))

lines = []
for x, y, sz, fnt, codes in runs:
    cm = font_cmaps.get(fnt, {})
    widths = font_widths.get(fnt, [])
    text = ""
    for cde in codes:
        if cde is None:
            continue
        text += cm.get(cde, "")
    if text.strip():
        lines.append((round(-y, 1), round(x, 1), round(sz, 1), fnt, text))

lines.sort(key=lambda r: (-r[0], r[1]))
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(f"runs={len(runs)} lines={len(lines)}\n")
    prev_y = None
    buf = []
    for y, x, sz, fnt, text in lines:
        if prev_y is None or abs(y - prev_y) > 3:
            if buf:
                fh.write(f"y={prev_y:8.1f} | " + "  ".join(buf) + "\n")
            buf = []
            prev_y = y
        buf.append(f"[x={x:.0f} sz={sz:.1f} {fnt}]{text}")
    if buf:
        fh.write(f"y={prev_y:8.1f} | " + "  ".join(buf) + "\n")
print("done", len(lines))
