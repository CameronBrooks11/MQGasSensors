#!/usr/bin/env python3
"""Download the datasheets listed in datasheets/manifest.toml.

    scripts/datasheets.py fetch    get every datasheet, first good mirror wins
    scripts/datasheets.py verify   test every mirror of every datasheet

The PDFs are copyrighted and are not stored in the repository. Each manifest
entry names the exact file by size and SHA-256 and lists mirrors in the order
to try them. A download is accepted only if its bytes match; anything else
(an error page served with status 200, a truncated copy, another edition of the
same sheet) is discarded and the next mirror is tried.

Standard library only.
"""
import argparse
import hashlib
import os
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "mqgassensors-datasheets/1.0"
KINDS = ("wayback", "swh", "live", "github")
MAX_BYTES = 50 * 1024 * 1024


class ManifestError(ValueError):
    pass


def load_manifest(path):
    with open(path, "rb") as f:
        entries = tomllib.load(f).get("datasheet", [])
    if not entries:
        raise ManifestError(f"{path}: no [[datasheet]] entries")
    seen = set()
    for e in entries:
        ident = e.get("id", "<no id>")
        for key in ("id", "sensor", "maker", "edition", "bytes", "sha256", "mirrors"):
            if key not in e:
                raise ManifestError(f"{ident}: missing '{key}'")
        if ident in seen:
            raise ManifestError(f"{ident}: duplicate id")
        seen.add(ident)
        sha = e["sha256"]
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ManifestError(f"{ident}: sha256 is not 64 lowercase hex digits")
        if not isinstance(e["bytes"], int) or e["bytes"] <= 0:
            raise ManifestError(f"{ident}: bytes must be a positive integer")
        if not e["mirrors"]:
            raise ManifestError(f"{ident}: no mirrors")
        kinds = []
        for m in e["mirrors"]:
            if m.get("kind") not in KINDS or not m.get("url"):
                raise ManifestError(f"{ident}: each mirror needs a url and a kind in {KINDS}")
            kinds.append(m["kind"])
        if "github" in kinds[:-1]:
            raise ManifestError(f"{ident}: a github mirror is the last resort and must come last")
    return entries


def matches(entry, data):
    return len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"]


def describe(entry, data):
    """Say how a rejected download differs from the expected file."""
    if data[:5] != b"%PDF-":
        return f"not a PDF ({len(data)} bytes)"
    if len(data) != entry["bytes"]:
        return f"a PDF of {len(data)} bytes, expected {entry['bytes']}"
    return "a PDF of the right size with different content"


def try_mirror(entry, url, retries, backoff, timeout):
    """Return (data, None) when the mirror serves the exact file, else (None, reason)."""
    reason = "not attempted"
    for attempt in range(1, retries + 1):
        retryable = True
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read(MAX_BYTES + 1)
            if matches(entry, data):
                return data, None
            reason = describe(entry, data)
        except urllib.error.HTTPError as err:
            reason = f"HTTP {err.code}"
            # A client error will not change on a second try; 429 might.
            retryable = err.code >= 500 or err.code == 429
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as err:
            reason = f"unreachable ({getattr(err, 'reason', err)})"
        if not retryable or attempt == retries:
            break
        time.sleep(backoff * attempt)
    return None, reason


def file_matches(entry, path):
    try:
        return matches(entry, path.read_bytes())
    except OSError:
        return False


def fetch(entries, dest, retries, backoff, timeout, out=sys.stdout):
    dest.mkdir(parents=True, exist_ok=True)
    failed = 0
    for e in entries:
        target = dest / f"{e['id']}.pdf"
        if file_matches(e, target):
            print(f"ok       {e['id']}  already present", file=out)
            continue
        for n, m in enumerate(e["mirrors"], 1):
            data, reason = try_mirror(e, m["url"], retries, backoff, timeout)
            if data is None:
                print(f"  miss   {e['id']}  mirror {n}/{len(e['mirrors'])} {m['kind']}: {reason}", file=out)
                continue
            tmp = target.with_suffix(".part")
            tmp.write_bytes(data)
            os.replace(tmp, target)
            print(f"ok       {e['id']}  mirror {n}/{len(e['mirrors'])} {m['kind']}", file=out)
            break
        else:
            failed += 1
            note = "  (the file on disk does not match)" if target.exists() else ""
            print(f"FAILED   {e['id']}  no mirror served the expected file{note}", file=out)
    print(f"{len(entries) - failed} of {len(entries)} datasheets present and verified in {dest}", file=out)
    return 1 if failed else 0


def verify(entries, retries, backoff, timeout, out=sys.stdout):
    dead = degraded = 0
    for e in entries:
        good = 0
        for n, m in enumerate(e["mirrors"], 1):
            data, reason = try_mirror(e, m["url"], retries, backoff, timeout)
            if data is None:
                print(f"BAD      {e['id']}  mirror {n} {m['kind']}: {reason}  {m['url']}", file=out)
            else:
                good += 1
                print(f"ok       {e['id']}  mirror {n} {m['kind']}", file=out)
        if good == 0:
            dead += 1
            print(f"DEAD     {e['id']}  no working mirror", file=out)
        elif good < len(e["mirrors"]):
            degraded += 1
    print(f"{len(entries)} datasheets: {dead} with no working mirror, {degraded} with a failing mirror", file=out)
    return 1 if dead else 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=("fetch", "verify"))
    p.add_argument("--manifest", type=Path, default=ROOT / "datasheets" / "manifest.toml")
    p.add_argument("--dest", type=Path, default=ROOT / "datasheets" / "files")
    p.add_argument("--only", action="append", metavar="ID", help="limit to this datasheet id (repeatable)")
    p.add_argument("--retries", type=int, default=4, help="attempts per mirror (default 4)")
    p.add_argument("--backoff", type=float, default=5.0, help="seconds to wait, times the attempt number (default 5)")
    p.add_argument("--timeout", type=float, default=60.0, help="seconds per request (default 60)")
    args = p.parse_args(argv)

    try:
        entries = load_manifest(args.manifest)
    except (ManifestError, tomllib.TOMLDecodeError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    if args.only:
        unknown = set(args.only) - {e["id"] for e in entries}
        if unknown:
            print(f"error: no such datasheet id: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        entries = [e for e in entries if e["id"] in args.only]

    if args.command == "fetch":
        return fetch(entries, args.dest, args.retries, args.backoff, args.timeout)
    return verify(entries, args.retries, args.backoff, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
