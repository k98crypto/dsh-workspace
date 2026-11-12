import re, zlib, sys, collections

SRC = r"C:\Users\k_981\Desktop\本专科生国家助学金申请表（2025版）.pdf"
data = open(SRC, "rb").read()
print("size", len(data))
print("header", data[:16])
print("tail", data[-64:])

# top-level object keys present in raw bytes
keys = collections.Counter(m.group(1).decode("latin1") for m in re.finditer(rb"/([A-Za-z][A-Za-z0-9]*)", data))
print("--- top raw keys ---")
for k, v in keys.most_common(60):
    print(f"{k}: {v}")

print("--- obj count ---", len(re.findall(rb"\d+\s+\d+\s+obj", data)))
print("--- stream count ---", data.count(b"stream"))
print("--- Filter kinds ---", collections.Counter(m.group(0).decode("latin1") for m in re.finditer(rb"/Filter\s*/?\w+", data)))
print("--- Subtype list ---", collections.Counter(m.group(1).decode("latin1") for m in re.finditer(rb"/Subtype\s*/(\w+)", data)))

# try to inflate every stream and look for interesting tokens
inflated_ok = 0
tokens = collections.Counter()
texts = []
for m in re.finditer(rb"stream\r?\n", data):
    start = m.end()
    end = data.find(b"endstream", start)
    if end < 0:
        continue
    raw = data[start:end]
    try:
        out = zlib.decompress(raw)
    except Exception:
        try:
            out = zlib.decompressobj().decompress(raw)
        except Exception:
            continue
    inflated_ok += 1
    for t in re.findall(rb"/(AcroForm|Widget|Annot|Field|FT|T\b|Tx|Btn|Ch|DA|DR|Font|Type0|Type1|TrueType|Image|XObject|Page|Contents|ObjStm)", out):
        tokens[t.decode()] += 1
        pass
    try:
        s = out.decode("latin1")
    except Exception:
        continue
    if re.search(r"/(AcroForm|Widget|Field|Annot)", s):
        texts.append(s)
print("--- inflated streams ---", inflated_ok)
print("--- interesting tokens in streams ---", tokens.most_common(30))

for i, s in enumerate(texts[:5]):
    print(f"===== stream text {i} (len {len(s)}) =====")
    print(s[:3000])
