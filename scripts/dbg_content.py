import re, zlib
SRC = r"C:\Users\k_981\Desktop\本专科生国家助学金申请表（2025版）.pdf"
data = open(SRC, "rb").read()
objs = {}
for m in re.finditer(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b", data):
    start = m.end(); end = data.find(b"endobj", start)
    objs[int(m.group(1))] = data[start:end]
raw = objs[83]
m = re.search(rb"stream\r?\n", raw)
body = raw[m.end():raw.find(b"endstream", m.end())]
d = zlib.decompressobj(); out = d.decompress(body) + d.flush()
print("inflated len", len(out))
open(r"D:\DSH Workspace\work\content83.txt", "wb").write(out)
print(out[:1200].decode("latin1"))
print("......")
print(out[-800:].decode("latin1"))
