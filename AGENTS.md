# AGENTS.md — rust-node-exporter

Prometheus metrics exporter (single Rust binary) exposing custom desktop metrics:
NZXT Kraken AIO (hidapi), lm_sensors via FFI to system `libsensors`, hddtemp,
nvidia-smi, /proc/{meminfo,netdev,stat}, and radeontop GPU stats. Personal
single-user project; the code assumes THIS machine (see Pitfalls).

## Layout

- `src/main.rs` — CLI (clap derive), TCP listener, per-request metric assembly.
  No HTTP framework: HTTP responses are hand-built strings.
- `src/helpers/` — one module per exporter, each exposing a `get_*_metrics() -> String`
  (Prometheus text format) and, for long-running collectors (`lm_sensors`,
  `amd_radeontop`), an `init()` called once at startup.
- `build.rs` + `wrapper.h` — bindgen FFI bindings to system `libsensors`;
  links `libsensors` at build time.
- `PKGBUILD`, `rust-node-exporter.service`, `99-kraken.rules` — Arch packaging,
  systemd unit (KillSignal=SIGINT, required for the ctrlc graceful shutdown),
  udev symlink `/dev/kraken` for the NZXT device.

## Commands

- Build: `cargo build --release`
- Check without linking side effects: `cargo check`
- Lint: `cargo clippy` (project history shows clippy warnings being fixed deliberately)
- Format: `cargo fmt --check` / `cargo fmt`
- Tests: none exist in the repo; `cargo test` runs but the suite is empty.
- Run locally: `./target/debug/rust-node-exporter [-p PORT] [-x exporter ...]`
  (exporters: hddtemp, lm_sensors, proc_meminfo, proc_netdev, proc_stat, nvidia,
  nzxt_aio, amd_radeontop; an unspecified set defaults to the list in
  `main.rs`, which excludes nvidia and nzxt_aio. Default port 7878,
  binds 127.0.0.1 only).
- Package: `makepkg -f` (Arch; runs `cargo build --release` and installs the
  binary, systemd unit, and udev rule).

## Conventions (observed)

- Add a new exporter as `src/helpers/<name>.rs` + `pub mod` in
  `src/helpers/mod.rs`, a variant in the `Exporter` enum in `main.rs`
  (snake_case clap naming), a guarded `contains` block in `handle_connection`,
  and optionally an `init()` call in `main`.
- Error handling is `expect`/`panic` on hard environment failures; no custom
  error types. Collectors keep state in `lazy_static!` `Mutex<Option<...>>`
  (see `amd_radeontop.rs`).
- Parsing is regex-based (`regex` crate) with patterns in `lazy_static!`
  statics; radeontop output is deserialized with serde/quick-xml where
  applicable.
- Commits: short imperative summaries, no conventional-commit prefixes
  (e.g. "Fix graceful shutdown of the service").
- Version is bumped in BOTH `Cargo.toml` and `PKGBUILD` (`pkgver`) together.

## Pitfalls

- Builds require the C library and headers for `libsensors` (lm_sensors
  package, `sensors-sensors.h`) — bindgen/link will fail without them.
- `hddtemp.rs` and `lm_sensors.rs` regexes/labels are hardcoded to this
  machine's exact disk models and sensor output; don't "generalize" them
  unless asked.
- The nzxt_aio exporter needs `/dev/kraken` (udev rule) and the hidraw device;
  it is only opened during request handling by design.
- amd_radeontop spawns `radeontop` (must be installed; 15s sample interval) —
  first scrape returns empty until it has data.
- Graceful shutdown depends on the ctrlc handler poking the listener with a
  dummy TCP connect; the systemd unit's KillSignal=SIGINT must be preserved.
- Prometheus requires the `Content-Type: text/plain; version=0.0.4` header the
  hand-rolled response provides; don't drop it (broke on Prometheus v3 once).
