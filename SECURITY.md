# Security Policy

## Reporting a vulnerability

Email **yash376351@gmail.com** with the repo name, a short description, and steps to reproduce. Please do not open a public issue for exploitable findings until we have had a reasonable chance to respond.

## Threat model (honest)

mcp-evals is a **developer/CI tool**. It talks to MCP servers and optional LLM endpoints you configure.

- It is **not** a sandbox for untrusted MCP servers or model output.
- Treat tool catalogs, eval fixtures, and live-server configs as trusted inputs for your environment.
- Do not pass production secrets into eval suites or commit them to cassettes/logs.
- Mock mode (`--model mock`) never calls a network model; live modes inherit whatever network and credential access your process already has.
