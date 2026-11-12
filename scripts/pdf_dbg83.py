import re, zlib
SRC = r"C:\Users\k_981\Desktop\本专科生国家助学金申请表（2025版）.pdf"
data = open(SRC, "rb").read()
objs = {}
for m in re.finditer(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b", data):
    start = m.end()
    end = data.find(b"endobj", start)
    objs[int(m.group(1))] = data[start:end]

for n in (81, 82, 83):
    raw = objs.get(n, b"<missing>")
    print(f"===== obj {n} len={len(raw)} =====")
    print(raw[:300])
    print("...tail:", raw[-120:])
