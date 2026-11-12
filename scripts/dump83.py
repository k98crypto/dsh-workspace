import re, zlib
data = open(r"D:\DSH Workspace\work\src_form.pdf","rb").read()
objs={}
for m in re.finditer(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b", data):
    s=m.end(); objs[int(m.group(1))]=data[s:data.find(b"endobj",s)]
raw=objs[83]; m=re.search(rb"stream\r?\n",raw)
body=raw[m.end():raw.find(b"endstream",m.end())]
d=zlib.decompressobj(); body=d.decompress(body)+d.flush()
open(r"D:\DSH Workspace\work\content83.txt","wb").write(body)
print(len(body))
