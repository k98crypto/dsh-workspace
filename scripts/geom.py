"""Geometry + CharProc inspection for the aid-application form."""
import re, zlib, json, collections

SRC = r"C:\Users\k_981\Desktop\本专科生国家助学金申请表（2025版）.pdf"
OUT = r"D:\DSH Workspace\work\geometry.txt"
data = open(SRC, "rb").read()
objs = {}
for m in re.finditer(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b", data):
    start = m.end(); end = data.find(b"endobj", start)
    objs[int(m.group(1))] = data[start:end]


def obj_stream(num):
    raw = objs.get(num, b"")
    m = re.search(rb"stream\r?\n", raw)
    if not m:
        return None
    body = raw[m.end():raw.find(b"endstream", m.end())]
    if b"FlateDecode" in raw[:m.start()]:
        try:
            d = zlib.decompressobj(); body = d.decompress(body) + d.flush()
        except Exception:
            return None
    return body


cbody = obj_stream(83).decode("latin1")
out = []
out.append(f"content len {len(cbody)}")
# q/Q balance
depth = 0; mind = 0
for m in re.finditer(r"(?<![A-Za-z])(q|Q)(?![A-Za-z])", cbody):
    depth += 1 if m.group(1) == "q" else -1
    mind = min(mind, depth)
out.append(f"q/Q final depth={depth} min={mind}")
out.append(f"ends with: {cbody[-120:]!r}")
out.append(f"starts with: {cbody[:80]!r}")

# path ops: collect 're' rectangles and line paths that are stroked
rects = []
lines = []
for m in re.finditer(r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+re\b([^A-Za-z]*)", cbody):
    x, y, w, h = (float(m.group(i)) for i in range(1, 5))
    rects.append((x, y, w, h, m.group(5).strip()[:20]))
out.append(f"--- 're' ops: {len(rects)} ---")
for r in rects:
    out.append("RE " + str(r))

# stroke/fill ops context: count
out.append("op counts: " + str(collections.Counter(re.findall(r"(?<![A-Za-z])(re|f|F|f\*|S|s|B|W\*|n|m|l|c|v|y|h)(?![A-Za-z])", cbody))))

# show unique operators sequence length
out.append("--- first 60 path-ish ops ---")
ops = re.findall(r"(?m)^([-\d.\s]+(?:re|m|l|c|h)|[fF*SsBbNn]|q|Q|W\*|BT|ET|Tj|Tf|Tm|Td|TD|TL|gs|rg|RG|cm)$", cbody)
out.append("ops found: " + str(len(ops)))

# CharProc sample
for n in (468, 469, 470, 472):
    raw = objs.get(n, b"")
    s = obj_stream(n)
    out.append(f"===== CharProc obj {n} raw={raw[:120]!r} =====")
    if s:
        out.append(s[:500].decode("latin1"))

# page dict extras
out.append("===== page 2 raw (first 200) =====")
out.append(objs[2][:200].decode("latin1"))
page = objs[2].decode("latin1")
for key in ("/Rotate", "/MediaBox", "/CropBox", "/Matrix", "/Annots"):
    mm = re.search(re.escape(key) + r"[^\n/]*", page)
    out.append(f"{key}: {mm.group(0) if mm else 'ABSENT'}")

# xref type
out.append("===== tail 400 =====")
out.append(data[-400:].decode("latin1"))
out.append("xref keyword count: " + str(len(re.findall(rb"\sxref\s", data))))
out.append("startxref pos: " + str(data.rfind(b"startxref")))

open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("written", OUT)
