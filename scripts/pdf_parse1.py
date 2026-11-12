"""Minimal PDF 1.4 parser: objects, page tree, content streams, ToUnicode CMaps."""
import re, zlib, sys, json

SRC = r"C:\Users\k_981\Desktop\本专科生国家助学金申请表（2025版）.pdf"
data = open(SRC, "rb").read()


def parse_objects(data):
    objs = {}
    for m in re.finditer(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b", data):
        num = int(m.group(1))
        start = m.end()
        end = data.find(b"endobj", start)
        if end < 0:
            continue
        objs[num] = data[start:end]
    return objs


objs = parse_objects(data)
print("objects:", len(objs), "max:", max(objs))


def deref(tok):
    m = re.match(rb"\s*(\d+)\s+\d+\s+R", tok)
    return int(m.group(1)) if m else None


def resolve(num):
    return objs.get(num, b"")


def get_stream(num):
    raw = objs.get(num, b"")
    m = re.search(rb"stream\r?\n", raw)
    if not m:
        return None, raw
    start = m.end()
    end = raw.find(b"endstream", start)
    body = raw[start:end]
    if b"/FlateDecode" in raw[:m.start()] or b"FlateDecode" in raw[:m.start()]:
        try:
            body = zlib.decompress(body)
        except Exception:
            try:
                body = zlib.decompressobj().decompress(body)
            except Exception:
                return None, raw
    return body, raw


# ---- find Root -> Pages -> Page tree
root = deref(re.search(rb"/Root\s+(\d+\s+\d+\s+R)", data[-400:]).group(1)) if re.search(rb"/Root\s+(\d+\s+\d+\s+R)", data[-400:]) else None
print("Root obj:", root)
root_raw = resolve(root)
print("Root raw:", root_raw[:600])

pages_num = deref(re.search(rb"/Pages\s+(\d+\s+\d+\s+R)", root_raw).group(1))
print("Pages obj:", pages_num)
pages_raw = resolve(pages_num)
print("Pages raw:", pages_raw[:400])


def walk(node_num, depth=0, acc=None):
    if acc is None:
        acc = []
    raw = resolve(node_num)
    if b"/Type" in raw and re.search(rb"/Type\s*/Page\b", raw):
        acc.append(node_num)
        return acc
    for m in re.finditer(rb"(\d+)\s+\d+\s+R", raw):
        n = int(m.group(1))
        if n == node_num or n in acc:
            continue
        sub = resolve(n)
        if b"/Page" in sub:
            if re.search(rb"/Type\s*/Page\b", sub):
                acc.append(n)
            elif re.search(rb"/Type\s*/Pages\b", sub):
                walk(n, depth + 1, acc)
    return acc


page_nums = walk(pages_num)
print("pages:", page_nums)
for p in page_nums:
    raw = resolve(p)
    print(f"--- Page {p} ---")
    print(raw[:800])
