# Quickstart

```bash
sudo dnf install curl jq python3 socat bubblewrap passt nftables util-linux xdg-utils tar xz nodejs npm
git clone <this repo> ~/dev/github/localllma-setup && cd ~/dev/github/localllma-setup
./setup.sh                       # add --download-models without GGUF backups
systemctl --user start llama-cpp.service
~/.local/bin/llama-webui         # WebUI on http://127.0.0.1:8080
cd ~/dev/github/my-project && pi # coding on Cyber-Tiel
```

- `research` for chat/research, `coding-cyber-tiel-35b` for coding (Pi default),
  `creative-writing`/`human-writing` for prose in the WebUI.
- In the WebUI: pick the profile at the bottom, MCP entries under **MCP
  Servers** (websearch, context7, github, skills read-only), approve each
  tool call with **Allow once**.
- `./setup.sh doctor` when anything is odd.
- The installed German walkthroughs live in `~/.config/llama.cpp/QUICKSTART.md`
  (managed copy of `docs/QUICKSTART.md`).
