"""Daily iptv-org/epg guide for the iptv-org worldwide playlist (stdlib only)."""
import argparse
import collections
import datetime as dt
import gzip
import html
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import urllib.request
import xml.etree.ElementTree as ET


def download(url):
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read().decode("utf-8")


def plan():
    upstream = Path("upstream")
    playlist = download("https://iptv-org.github.io/iptv/index.m3u")
    ids = set(re.findall(r'tvg-id="([^"]+)"', playlist))
    if not ids:
        raise RuntimeError("Worldwide playlist contains no channel IDs")
    healthy = set(re.findall(r'<tr><td><a href="sites/([^"]+)">[^\n]*?🟢',
                             (upstream / "SITES.md").read_text()))
    candidates = collections.defaultdict(dict)
    for path in sorted((upstream / "sites").glob("*/*.channels.xml")):
        if path.parent.name not in healthy:
            continue
        for channel in ET.parse(path).getroot():
            channel_id = channel.get("xmltv_id")
            if channel_id in ids and channel.get("site_id"):
                candidates[path.parent.name].setdefault(channel_id, channel)
    # Prefer sources covering many channels; keep two distinct sources per ID.
    # This provides a fallback without scraping every duplicate provider.
    selected = collections.Counter()
    batches = []
    for site in sorted(candidates, key=lambda s: (-len(candidates[s]), s)):
        channels = [c for i, c in candidates[site].items() if selected[i] < 2]
        for channel in channels:
            selected[channel.get("xmltv_id")] += 1
        # Keep cached multi-channel downloads together by their source file tag.
        groups = collections.defaultdict(list)
        for channel in channels:
            tag = channel.get("site_id", "").split("#")[0] if site in {
                "i.mjh.nz", "epgshare01.online"} else ""
            groups[tag].append(channel)
        for group in groups.values():
            for start in range(0, len(group), 80):
                batches.append((site, group[start:start + 80]))
    if not batches:
        raise RuntimeError("No matching EPG channels found")
    directory = Path("plan")
    directory.mkdir(exist_ok=True)
    shards = [[] for _ in range(16)]
    sizes = [0] * len(shards)
    for index, (site, channels) in enumerate(sorted(batches, key=lambda b: -len(b[1]))):
        filename = f"{index:04d}.channels.xml"
        root = ET.Element("channels")
        root.extend(channels)
        ET.ElementTree(root).write(directory / filename, encoding="utf-8", xml_declaration=True)
        shard = min(range(len(shards)), key=lambda s: sizes[s])
        shards[shard].append({"file": filename, "site": site})
        sizes[shard] += len(channels)
    (directory / "shards.json").write_text(json.dumps(shards))
    (directory / "coverage.json").write_text(json.dumps({
        "playlist_ids": sorted(ids), "mapped_ids": sorted(selected),
        "upstream": subprocess.check_output(
            ["git", "-C", "upstream", "rev-parse", "HEAD"], text=True).strip()
    }))
    print(f"{len(ids)} playlist IDs, {len(selected)} mapped IDs, {len(batches)} batches")


def run(shard):
    output = Path("results")
    output.mkdir(exist_ok=True)
    batches = json.loads(Path("plan/shards.json").read_text())[shard]
    for batch in batches:
        name = batch["file"].split(".")[0]
        command = ["npm", "run", "grab", "--", "--channels", "../plan/" + batch["file"],
                   "--output", "../results/" + name + ".xml", "--days", "2",
                   "--timeout", "15000", "--maxConnections", "2"]
        print(f"Fetching {batch['site']} ({name})", flush=True)
        with (output / (name + ".log")).open("w") as log:
            process = subprocess.Popen(command, cwd="upstream", stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                print("Batch timed out; continuing with other sources", flush=True)
        print(f"Exit status: {process.returncode}", flush=True)


def elements(path):
    context = ET.iterparse(path, events=("start", "end"))
    _, root = next(context)
    for event, element in context:
        if event == "end" and element.tag in {"channel", "programme"}:
            yield element
            root.clear()


def publish():
    coverage = json.loads(Path("plan/coverage.json").read_text())
    wanted = set(coverage["playlist_ids"])
    now = dt.datetime.now(dt.timezone.utc)
    def current(element):
        try:
            return dt.datetime.strptime(element.get("stop", ""), "%Y%m%d%H%M%S %z") >= now
        except ValueError:
            return False
    valid = []
    owners = {}
    # Use a single successful provider per channel, avoiding duplicate schedules.
    for path in sorted(Path("results").glob("*.xml")):
        try:
            channels = set()
            for element in elements(path):
                if element.tag == "programme" and current(element):
                    if element.get("channel") in wanted:
                        channels.add(element.get("channel"))
            valid.append(path)
            for channel_id in channels:
                owners.setdefault(channel_id, path)
        except (ET.ParseError, OSError):
            print(f"Skipping incomplete output: {path}")
    if not owners:
        raise RuntimeError("No current programmes; previous published guide is preserved")
    public = Path("public")
    public.mkdir(exist_ok=True)
    total = 0
    # Write XMLTV channels first, followed by programmes. Memory remains bounded.
    with (public / "guide.xml").open("wb") as out:
        out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="iptv-org/epg">\n')
        written = set()
        for path in valid:
            for element in elements(path):
                channel_id = element.get("id")
                if element.tag == "channel" and owners.get(channel_id) == path and channel_id not in written:
                    out.write(ET.tostring(element, encoding="utf-8"))
                    written.add(channel_id)
        for path in valid:
            for element in elements(path):
                if element.tag == "programme" and owners.get(element.get("channel")) == path:
                    if current(element):
                        out.write(ET.tostring(element, encoding="utf-8"))
                        total += 1
        out.write(b"\n</tv>\n")
    with (public / "guide.xml").open("rb") as src, gzip.open(public / "guide.xml.gz", "wb") as dst:
        import shutil
        shutil.copyfileobj(src, dst)
    report = {"updated_utc": now.isoformat(), "playlist_channels": len(wanted),
              "mapped_channels": len(coverage["mapped_ids"]), "guide_channels": len(owners),
              "programmes": total, "upstream": coverage["upstream"],
              "missing_channels": sorted(wanted - owners.keys())}
    (public / "status.json").write_text(json.dumps(report, indent=2))
    # Include the original worldwide playlist with an absolute EPG reference.
    playlist = download("https://iptv-org.github.io/iptv/index.m3u")
    base = os.environ.get("PAGES_URL", "").rstrip("/")
    playlist = re.sub(r"^#EXTM3U[^\n]*", f'#EXTM3U x-tvg-url="{base}/guide.xml.gz"', playlist, count=1)
    (public / "world.m3u").write_text(playlist)
    (public / ".nojekyll").touch()
    (public / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>World EPG</title>'
        '<style>body{font:18px system-ui;max-width:760px;margin:60px auto;padding:24px;line-height:1.7}</style>'
        '<h1>World EPG · iptv-org/epg</h1>'
        f'<p>Updated (UTC): {html.escape(now.isoformat())}</p>'
        f'<p>{len(owners)} channels with current programmes · {total} programmes</p>'
        '<p><a href="guide.xml.gz">Compressed EPG</a> · <a href="guide.xml">XML EPG</a>'
        ' · <a href="world.m3u">Worldwide playlist</a> · <a href="status.json">Coverage report</a></p>'
        '<p>Not all playlist channels have matching EPG data. Source availability varies.</p>'
    )
    print(json.dumps({k: v for k, v in report.items() if k != "missing_channels"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["plan", "run", "publish"])
    parser.add_argument("--shard", type=int, default=0)
    args = parser.parse_args()
    if args.command == "run":
        run(args.shard)
    else:
        globals()[args.command]()
