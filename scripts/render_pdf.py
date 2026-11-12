"""Minimal PDF page rasterizer for the aid form (content = filled paths + Type3 glyphs)."""
import re, zlib, sys
from PIL import Image, ImageDraw

SRC = sys.argv[1] if len(sys.argv) > 1 else r"D:\DSH Workspace\work\src_form.pdf"
OUT = sys.argv[2] if len(sys.argv) > 2 else r"D:\DSH Workspace\work\render_original.png"

data = open(SRC, "rb").read()
objs = {}
for m in re.finditer(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b", data):
    s = m.end()
    objs[int(m.group(1))] = data[s:data.find(b"endobj", s)]


def stream_of(num):
    raw = objs.get(num)
    if raw is None:
        return None
    m = re.search(rb"stream\r?\n", raw)
    if not m:
        return None
    body = raw[m.end():raw.find(b"endstream", m.end())]
    if b"FlateDecode" in raw[:m.start()]:
        d = zlib.decompressobj()
        try:
            body = d.decompress(body) + d.flush()
        except Exception:
            return None
    return body


PAGE_H = 1683.0

# ---------------- matrix helpers (PDF row-vector convention) ----------------
def comb(A, B):
    """result = apply B first, then A."""
    aa, ab, ac, ad, ae, af = A
    ba, bb, bc, bd, be, bf = B
    return (aa * ba + ac * bb, ab * ba + ad * bb,
            aa * bc + ac * bd, ab * bc + ad * bd,
            aa * be + ac * bf + ae, ab * be + ad * bf + af)


def apply(M, x, y):
    a, b, c, d, e, f = M
    return (a * x + c * y + e, b * x + d * y + f)


# ---------------- tokenizer ----------------
TOKEN = re.compile(rb"""
    (?P<ws>\s+)
  | (?P<comment>%[^\r\n]*)
  | (?P<number>[+-]?(?:\d+\.?\d*|\.\d+))
  | (?P<name>/[^\s/\[\]<>(){}]*)
  | (?P<string>\((?:\\.|[^\\()])*\))
  | (?P<hex><[0-9A-Fa-f\s]*>)
  | (?P<arr>[\[\]])
  | (?P<dict><<|>>)
  | (?P<op>[A-Za-z'*"][A-Za-z0-9'*"]*)
""", re.X)


def unescape_string(raw):
    body = raw[1:-1]
    out = bytearray()
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == 0x5C:  # backslash
            i += 1
            if i >= len(body):
                break
            c = body[i]
            simple = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12,
                      0x28: 40, 0x29: 41, 0x5C: 92}
            if c in simple:
                out.append(simple[c]); i += 1
            elif 0x30 <= c <= 0x37:
                oct_digits = ""
                while i < len(body) and len(oct_digits) < 3 and 0x30 <= body[i] <= 0x37:
                    oct_digits += chr(body[i]); i += 1
                out.append(int(oct_digits, 8) & 0xFF)
            else:
                out.append(c); i += 1
        else:
            out.append(ch); i += 1
    return bytes(out)


def tokenize(s):
    for m in TOKEN.finditer(s):
        kind = m.lastgroup
        val = m.group()
        if kind in ("ws", "comment"):
            continue
        if kind == "number":
            yield ("num", float(val))
        elif kind == "name":
            yield ("name", val[1:].decode("latin1"))
        elif kind == "string":
            yield ("str", unescape_string(val))
        elif kind == "hex":
            h = re.sub(rb"\s", b"", val[1:-1])
            if len(h) % 2:
                h += b"0"
            yield ("str", bytes.fromhex(h.decode()))
        elif kind == "op":
            yield ("op", val.decode("latin1"))
        else:
            yield (kind, val)


# ---------------- fonts ----------------
fonts = {}
fm = re.search(rb"/Font\s*<<(.*?)>>", objs[2], re.S)
for m in re.finditer(rb"/(F\d+)\s+(\d+)\s+0\s+R", fm.group(1)):
    fonts[m.group(1).decode()] = int(m.group(2))

fontcache = {}


def font_info(num):
    if num in fontcache:
        return fontcache[num]
    raw = objs[num]
    fmm = re.search(rb"/FontMatrix\s*\[([^\]]*)\]", raw)
    F = tuple(float(x) for x in fmm.group(1).split()) if fmm else (0.001, 0, 0, 0.001, 0, 0)
    widths = {}
    wm = re.search(rb"/Widths\s*\[([^\]]*)\]", raw)
    fc = re.search(rb"/FirstChar\s+(\d+)", raw)
    first = int(fc.group(1)) if fc else 0
    if wm:
        for i, v in enumerate(wm.group(1).split()):
            widths[first + i] = float(v)
    enc = {}
    em = re.search(rb"/Encoding\s*<<(.*?)>>", raw, re.S)
    if em:
        dm = re.search(rb"/Differences\s*\[(.*?)\]", em.group(1), re.S)
        if dm:
            cur = 0
            for tok in re.findall(rb"/[^\s/\[\]()<>]+|\d+", dm.group(1)):
                if tok.startswith(b"/"):
                    enc[cur] = tok[1:].decode(); cur += 1
                else:
                    cur = int(tok)
    cp = {}
    cpm = re.search(rb"/CharProcs\s*<<(.*?)>>", raw, re.S)
    if cpm:
        for m in re.finditer(rb"/([^\s/\[\]()<>]+)\s+(\d+)\s+0\s+R", cpm.group(1)):
            cp[m.group(1).decode()] = int(m.group(2))
    info = {"fm": F, "widths": widths, "enc": enc, "cp": cp, "num": num}
    fontcache[num] = info
    return info


# ---------------- interpreter ----------------
polys = []


class Interp:
    def __init__(self, base_ctm):
        self.ctm = base_ctm
        self.gray = 0.0
        self.stack = []
        self.polys = polys
        self.path = []
        self.cur = None
        self.start = None
        self.tm = self.tlm = (1, 0, 0, 1, 0, 0)
        self.font = None
        self.fsize = 0.0
        self.tleading = 0.0

    def to_img(self, M, x, y):
        dx, dy = apply(M, x, y)
        return (dx, PAGE_H - dy)

    def emit(self, M):
        if len(self.path) > 2:
            self.polys.append(([self.to_img(M, px, py) for px, py in self.path], self.gray))
        self.path = []
        self.cur = self.start = None

    def bezier(self, p0, p1, p2, p3, n=10):
        return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0],
                 (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1])
                for t in [i / n for i in range(1, n + 1)]]

    def path_op(self, op, a):
        if op == "re":
            if len(self.path) > 2:
                self.emit(self.ctm)
            x, y, w, h = a[-4:]
            self.path = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
            self.cur = self.start = (x, y)
        elif op == "m":
            if len(self.path) > 2:
                self.emit(self.ctm)
            self.path = [(a[-2], a[-1])]
            self.cur = self.start = (a[-2], a[-1])
        elif op == "l":
            self.path.append((a[-2], a[-1])); self.cur = (a[-2], a[-1])
        elif op == "c":
            p1 = (a[-6], a[-5]); p2 = (a[-4], a[-3]); p3 = (a[-2], a[-1])
            self.path += self.bezier(self.cur, p1, p2, p3); self.cur = p3
        elif op == "v":
            p2 = (a[-4], a[-3]); p3 = (a[-2], a[-1])
            self.path += self.bezier(self.cur, self.cur, p2, p3); self.cur = p3
        elif op == "y":
            p1 = (a[-4], a[-3]); p3 = (a[-2], a[-1])
            self.path += self.bezier(self.cur, p1, p3, p3); self.cur = p3
        elif op == "h":
            if self.start:
                self.path.append(self.start)

    def show(self, codes, Mbase):
        fi = font_info(self.font)
        M = Mbase
        for code in codes:
            gname = fi["enc"].get(code)
            cpnum = fi["cp"].get(gname) if gname else None
            if cpnum:
                gb = stream_of(cpnum)
                if gb:
                    sub = Interp(M)
                    sub.gray = self.gray
                    sub.run(gb)
                    for pts, g in sub.polys:
                        self.polys.append((pts, g))
            wx = fi["widths"].get(code, 0.0)
            M = comb(M, (1, 0, 0, 1, wx * fi["fm"][0] * self.fsize, 0))
        return M

    def run(self, content):
        a = []
        for kind, val in tokenize(content):
            if kind == "op":
                op = val
                self.op(op, a)
                a = []
            else:
                a.append(val)
        if len(self.path) > 2:
            self.emit(self.ctm)

    def op(self, op, a):
        if op == "q":
            self.stack.append((self.ctm, self.gray))
        elif op == "Q":
            if self.stack:
                self.ctm, self.gray = self.stack.pop()
        elif op == "cm":
            self.ctm = comb(self.ctm, tuple(a[-6:]))
        elif op == "g":
            self.gray = a[-1]
        elif op == "rg":
            self.gray = 0.299 * a[-3] + 0.587 * a[-2] + 0.114 * a[-1]
        elif op == "G":
            pass
        elif op in ("re", "m", "l", "c", "v", "y", "h"):
            self.path_op(op, a)
        elif op in ("f", "F", "f*", "B", "B*", "b", "b*"):
            self.emit(self.ctm)
        elif op in ("S", "s", "n"):
            self.path = []; self.cur = self.start = None
        elif op == "BT":
            self.tm = self.tlm = (1, 0, 0, 1, 0, 0)
        elif op == "Tf":
            self.font = fonts.get(a[-2]); self.fsize = a[-1]
        elif op == "Tm":
            self.tm = self.tlm = tuple(a[-6:])
        elif op == "Td":
            self.tlm = comb(self.tlm, (1, 0, 0, 1, a[-2], a[-1])); self.tm = self.tlm
        elif op == "TD":
            self.tleading = -a[-1]
            self.tlm = comb(self.tlm, (1, 0, 0, 1, a[-2], a[-1])); self.tm = self.tlm
        elif op == "TL":
            self.tleading = a[-1]
        elif op == "T*":
            self.tlm = comb(self.tlm, (1, 0, 0, 1, 0, -self.tleading)); self.tm = self.tlm
        elif op in ("Tj", "'", '"'):
            if op in ("'", '"'):
                self.tlm = comb(self.tlm, (1, 0, 0, 1, 0, -self.tleading)); self.tm = self.tlm
            s = a[-1] if isinstance(a[-1], bytes) else b""
            self.text(s)
        elif op == "TJ":
            arr = a
            M = self.trm()
            for el in arr:
                if isinstance(el, bytes):
                    M = self.show(list(el), M)
                elif isinstance(el, float):
                    M = comb(M, (1, 0, 0, 1, -el / 1000.0 * self.fsize, 0))
            self.tm = comb(self.ctm, M)
            self.tlm = self.tm

    def trm(self):
        return comb(comb(self.ctm, self.tm), (self.fsize, 0, 0, self.fsize, 0, 0))

    def text(self, s):
        if not self.font:
            return
        M = self.trm()
        self.tm = comb(self.ctm, self.show(list(s), M))
        self.tlm = self.tm


body = stream_of(83)
top = Interp((1, 0, 0, 1, 0, 0))
top.run(body)
print("polygons:", len(polys))

W, H = 1190, 1683
img = Image.new("L", (W, H), 255)
dr = ImageDraw.Draw(img)
for pts, gray in polys:
    if len(pts) < 3:
        continue
    v = int(max(0, min(255, gray * 255)))
    dr.polygon([(round(x), round(y)) for x, y in pts], fill=v)
img.save(OUT)
print("saved", OUT)
