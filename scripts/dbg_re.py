import re
s = open(r"D:\DSH Workspace\work\content83.txt", "r", encoding="latin1").read()
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
print(_pat)
toks = re.findall(_pat, s, re.S)
print("tokens:", len(toks))
print("groups:", len(toks[0]) if toks else None)
for t in toks[:6]:
    print(t)
print("--- Tj count raw:", len(re.findall(r"Tj", s)), "TJ:", len(re.findall(r"TJ", s)), "Tf:", len(re.findall(r"Tf", s)))
