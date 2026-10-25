"""Build levels.csv (word,system,level) from HSK repo JSON + YCT text lists.

Each row is the word's FIRST (lowest) level within its system, so a level
holds only the words introduced at that level. Usage:
    python3 -I build_levels.py <hsk_repo_dir> <yct_dir> <out_csv>
"""
import csv
import json
import re
import sys
from collections import defaultdict

hsk_repo, yct_dir, out_csv = sys.argv[1:4]

CJK = re.compile(r"[一-鿿]")
PAREN = re.compile(r"[\(（][^\)）]*[\)）]")


def clean(token):
    """Return a list of clean Chinese-only words from one raw token."""
    token = PAREN.sub("", token)
    parts = re.split(r"[…/|、,，]", token)
    return ["".join(CJK.findall(p)) for p in parts if CJK.search(p)]


rows = defaultdict(dict)  # system -> word -> lowest level
oddities = []

# ---- HSK (three standards) -------------------------------------------------
schemes = {"old": ("HSK2.0", 6), "new": ("HSK3.0", 7), "newest": ("HSK3.0-2026", 7)}
for scheme, (system, top) in schemes.items():
    for level in range(1, top + 1):
        path = f"{hsk_repo}/wordlists/exclusive/{scheme}/{level}.min.json"
        for entry in json.load(open(path, encoding="utf-8")):
            raw = entry["s"]
            words = clean(raw)
            if len(words) != 1 or words[0] != raw:
                oddities.append((system, level, raw, words))
            for w in words:
                rows[system].setdefault(w, level)

# ---- YCT (cumulative lists -> exclusive levels) -----------------------------
raw_counts = {}
levels_sets = {}
for level in range(1, 5):
    tokens = open(f"{yct_dir}/yct{level}.txt", encoding="utf-8").read().split()
    raw_counts[level] = len(tokens)
    words = []
    for t in tokens:
        words.extend(clean(t))
    levels_sets[level] = set(words)
    for w in words:
        rows["YCT"].setdefault(w, level)

# ---- write CSV ---------------------------------------------------------------
with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["word", "system", "level"])
    for system in ["YCT", "HSK2.0", "HSK3.0", "HSK3.0-2026"]:
        for word, level in sorted(rows[system].items(), key=lambda kv: (kv[1], kv[0])):
            wr.writerow([word, system, level])

# ---- report --------------------------------------------------------------------
print("== rows per system/level (new at that level)")
for system in ["YCT", "HSK2.0", "HSK3.0", "HSK3.0-2026"]:
    c = defaultdict(int)
    for lv in rows[system].values():
        c[lv] += 1
    cum = 0
    out = []
    for lv in sorted(c):
        cum += c[lv]
        out.append(f"L{lv}: +{c[lv]} (cum {cum})")
    print(system, "|", "  ".join(out))

print("\n== YCT raw tokens per level:", raw_counts)
print("== YCT unique words per level (cumulative lists):",
      {k: len(v) for k, v in levels_sets.items()})
for a, b in [(1, 2), (2, 3), (3, 4)]:
    missing = sorted(levels_sets[a] - levels_sets[b])
    print(f"== in YCT{a} but not in YCT{b}:", missing)

print(f"\n== HSK cleaning oddities: {len(oddities)}")
for o in oddities[:40]:
    print(o)
