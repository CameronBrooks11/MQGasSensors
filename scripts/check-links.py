#!/usr/bin/env python3
"""Fail if a Markdown file links to a path in this repository that does not exist.

Checks relative links and images in every tracked .md file. Links to other
sites are not followed: this runs in the pull request gate, which must not
depend on the network.

    scripts/check-links.py            check tracked files
    scripts/check-links.py --urls     only list the external URLs, one per line
"""
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
# [text](target) and ![alt](target), and reference definitions "[name]: target".
INLINE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REFERENCE = re.compile(r"^\[[^\]]+\]:\s*<?(\S+?)>?\s*$", re.MULTILINE)
FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)


def targets(text):
    text = FENCE.sub("", text)
    return INLINE.findall(text) + REFERENCE.findall(text)


def main(argv):
    files = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.split("\n")
    files = [ROOT / f for f in files if f]
    broken, urls, local = [], set(), 0
    for md in files:
        for target in targets(md.read_text(errors="replace")):
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                if target.startswith(("http://", "https://")):
                    urls.add(target)
                continue
            path = unquote(target.split("#", 1)[0])
            if not path:
                continue  # a link to a heading in the same file
            local += 1
            if not (md.parent / path).exists():
                broken.append(f"{md.relative_to(ROOT)}: {target}")
    if "--urls" in argv:
        print("\n".join(sorted(urls)))
        return 0
    if broken:
        print("error: these Markdown links point at paths that do not exist:", file=sys.stderr)
        print("\n".join(f"  {b}" for b in broken), file=sys.stderr)
        return 1
    print(f"links: {local} local links in {len(files)} Markdown files all resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
