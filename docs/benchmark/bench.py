#!/usr/bin/env python3
"""Benchmark rust-node-exporter vs prometheus/node_exporter on this machine.

Apples-to-apples scenario: only the collectors both exporters implement.
Context scenario: node_exporter as-shipped (all defaults) vs rust as-shipped.
"""
import json, os, signal, statistics, subprocess, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RUST_BIN = "/home/tim/git/rust-node-exporter/target/release/rust-node-exporter"
NODE_BIN = os.path.join(HERE, "node_exporter-1.13.1.linux-amd64", "node_exporter")
RESULTS = os.path.join(HERE, "results.json")


def cpu_seconds(pid):
    with open(f"/proc/{pid}/stat") as f:
        parts = f.read().split()
    utime, stime = int(parts[13]), int(parts[14])
    return (utime + stime) / os.sysconf("SC_CLK_TCK")


def rss_kb(pid, field):
    for line in open(f"/proc/{pid}/status"):
        if line.startswith(field):
            return int(line.split()[1])
    return 0


def scrape(url, timeout=30):
    start = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        body = resp.read()
    ms = (time.perf_counter() - start) * 1000
    return ms, len(body), body.decode("utf-8", "replace")


def run_case(name, cmd, port):
    out = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}/metrics"
    # startup: time from spawn to first successful scrape
    t0 = time.perf_counter()
    startup_ms = None
    first_body = ""
    for _ in range(600):
        try:
            ms, nb, body = scrape(url)
            startup_ms = (time.perf_counter() - t0) * 1000
            first_body = body
            break
        except Exception:
            time.sleep(0.05)
    assert startup_ms is not None, f"{name} never became ready"

    # warmup
    for _ in range(20):
        scrape(url)

    peak_kb = rss_kb(out.pid, "VmHWM")
    rss0 = rss_kb(out.pid, "VmRSS")

    # 100 sequential scrapes: latency + cpu per scrape
    cpu0 = cpu_seconds(out.pid)
    latencies, bodies = [], []
    for _ in range(100):
        ms, nb, body = scrape(url)
        latencies.append(ms)
        bodies.append(nb)
    cpu1 = cpu_seconds(out.pid)

    result = {
        "name": name,
        "startup_ms": round(startup_ms, 1),
        "rss_after_warmup_kb": rss0,
        "peak_rss_kb": peak_kb,
        "cpu_ms_per_scrape": round((cpu1 - cpu0) * 1000 / 100, 3),
        "latency_mean_ms": round(statistics.mean(latencies), 2),
        "latency_p95_ms": round(statistics.quantiles(latencies, n=20)[18], 2),
        "latency_max_ms": round(max(latencies), 2),
        "body_bytes": statistics.mode(bodies),
        "metric_lines": sum(1 for l in first_body.splitlines() if l and not l.startswith("#")),
    }
    out.send_signal(signal.SIGINT)
    try:
        out.wait(timeout=10)
    except subprocess.TimeoutExpired:
        out.kill()
    return result


def main():
    results = {}
    common_rust = ["-x", "lm_sensors", "-x", "proc_meminfo", "-x", "proc_netdev", "-x", "proc_stat"]
    common_node = [
        "--collector.disable-defaults", "--collector.meminfo",
        "--collector.netdev", "--collector.stat", "--collector.hwmon",
    ]
    rust_defaults = common_rust + ["-x", "hddtemp", "-x", "amd_radeontop"]  # as-shipped minus GPU/AIO special hw
    results["rust_common"] = run_case(
        "rust-node-exporter (common collectors)", [RUST_BIN, "-p", "17871"] + common_rust, 17871)
    results["node_common"] = run_case(
        "node_exporter 1.13.1 (common collectors)", [NODE_BIN, "--web.listen-address=127.0.0.1:17872"] + common_node, 17872)
    results["node_defaults"] = run_case(
        "node_exporter 1.13.1 (all defaults)", [NODE_BIN, "--web.listen-address=127.0.0.1:17873"], 17873)

    results["binary_sizes"] = {
        "rust-node-exporter": os.path.getsize(RUST_BIN),
        "node_exporter": os.path.getsize(NODE_BIN),
    }
    results["versions"] = {
        "rust-node-exporter": "0.2.5 (rustc 1.100.0, lto release)",
        "node_exporter": "1.13.1 (go1.27.4)",
    }
    with open(RESULTS, "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
