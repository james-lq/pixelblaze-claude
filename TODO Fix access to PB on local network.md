# TODO: Fix Access to PixelBlaze on Local Network

## Problem

The MCP server (and terminal tools like `curl`, `nc`, `ping`) cannot connect to the
PixelBlaze at `192.168.3.210`, even though Chrome can reach it successfully at
`http://192.168.3.210/`.

Symptoms:
- `curl` and `nc` fail immediately with `No route to host`
- `ping` fails with `sendto: No route to host`
- ARP resolves correctly (`b4:8a:0a:6c:05:ac` via `en0`)
- Routing table has a valid entry for `192.168.3.0/24` via `en0`
- Internet connectivity works fine from the terminal
- Other LAN hosts (e.g. router at `192.168.3.1`) are reachable

## Root Cause (Most Likely)

**macOS Local Network privacy permission** — since macOS Ventura, each app must be
granted permission to access local network devices. Chrome has been granted it;
Terminal, VS Code, and Python have not (or were denied at some point).

The network is a TP-Link Omada managed by org IT — possible that Omada client
isolation or VLAN rules also play a role, but the per-app permission is the first
thing to check.

## Fix

1. Open **System Settings → Privacy & Security → Local Network**
2. Enable access for:
   - **Terminal** (or iTerm2, whichever terminal app is in use)
   - **Visual Studio Code**
   - **Python** (may appear as `python3` or the `uv`-managed venv binary)
3. Retry `nc -zv -G 3 192.168.3.210 81` to confirm connectivity is restored
4. Re-run `pixelblaze_list_patterns` via the MCP tool

## Hypotheses Evaluated and Ruled Out

- **Wrong IP in `.env`** — confirmed `192.168.3.210` is correct and matches what Chrome uses
- **Offline mode flag** — `.pixelblaze_offline` file not present; `PIXELBLAZE_OFFLINE` env var not set
- **Little Snitch / LuLu / Radio Silence** — no per-app outbound firewall installed
- **Active VPN** — 6 `utun` interfaces present but all are standard macOS system tunnels; `scutil --nc list` showed no active VPN connections
- **pf firewall rules** — `/etc/pf.conf` is stock macOS default with no custom rules
- **System/network extensions** — `systemextensionsctl list` returned nothing relevant
- **Network segmentation / VLAN** — possible given the Omada managed network, but not confirmed; router at `192.168.3.1` is reachable from terminal so the subnet itself isn't fully blocked

## Other Notes

- The `.env` file correctly has `PIXELBLAZE_HOST=192.168.3.210`
- The initial MCP failure (`Cannot read properties of undefined (reading 'invoke')`)
  was a separate VS Code race condition bug: the extension host restarted at 23:59:29,
  and the first tool call was made just ~7 seconds later before the MCP client object
  was fully initialized. This resolves itself on retry.
