# Introduction

This is a minimal, self-contained example built for a DEF CON workshop to illustrate how a real-world infostealer discovers and exfiltrates sensitive data. Nothing here is obfuscated, packed, or intended for actual deployment.

This example scans the filesystem with simple pattern matching to locate credentials, emails, passwords, and env files; the same categories of data real infostealers target. By default it scans the working directory and its subdirectories, plus a few well-known locations like `~/.ssh` and `~/.config`, where private keys and other secrets tend to live.

## How it works

The example has three pieces:

- **`population_script/`** — seeds a test directory with fake credentials, `.env` files, SSH-style keys, and other bait data, so there's something to find.
- **`agent/`** — the actual stealer. Walks the filesystem, matches candidate files against a set of regexes, and streams anything it finds to the server in real time.
- **`server/`** — a small web dashboard (`localhost:8080`) that receives findings from the agent and displays them as they come in.

## Running the example

### 1. Populate test data

Generates sample files for the agent to find. Only run this in a disposable test environment — it writes fake secrets to your home directory.

```sh
cd population_script
./populate_data.sh
```

### 2. Start the dashboard

```sh
# from the project root
./server/server
```

Open [http://localhost:8080](http://localhost:8080) to watch findings come in.

Flags:

| Flag    | Default | Description                      |
| ------- | ------- | -------------------------------- |
| `-addr` | `:8080` | Address the dashboard listens on |

### 3. Run the agent

```sh
./agent/agent -server http://localhost:8080
```

As it walks the filesystem, each match is streamed to the dashboard.

Flags:

| Flag      | Default           | Description                                              |
| --------- | ----------------- | -------------------------------------------------------- |
| `-server` | _(required)_      | URL of the findings server, e.g. `http://localhost:8080` |
| `-root`   | current directory | Directory to scan instead of the cwd                     |
