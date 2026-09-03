# Workspace shared Memory

The maintained Surveying runtime exposes Memory Proxy at:

```text
https://memory-api.repomind.cn/codex/default
```

The maintained profiles are selected with:

```bash
codex --profile surveying-memory
codex --profile platform-memory
```

Each profile uses the OpenAI Responses wire API and disables response storage so
each turn passes through Memory Proxy. Workspace routing is:

- Team: `Surveying` (`team-u0rh0npaq8`)
- Agent: `Codex Builder` (`agt-u0rh13l4lx`)
- Chat Memory: `chat_memory-team-u0rh0npaq8-agt-u0rh13l4lx`
- Team: `Platform` (`team-1aeow35t36`)
- Agent: `Codex Builder` (`agt-1aep2gte7s`)
- Chat Memory: `chat_memory-team-1aeow35t36-agt-1aep2gte7s`
- Task: Plane WP/Issue identifier, or `no-task` when no Plane item exists
- Memory instance: `default`

Credentials remain in `~/.config/surveying/team-knowledge-memory.json`, owned by
the current user with mode `0600`. The provider auth command is:

```text
~/.codex/skills/memory-governance/scripts/memory_token.py
```

Do not run the token helper interactively because its stdout is intentionally
the bearer token consumed by Codex. A missing, symlinked, wrong-owner, or
wrong-mode credential file fails closed.

The approved context policy is authoritative. Team Memory contains a reviewed
pointer to that policy; it does not mirror the complete document. The runtime
injector allowlist is Chat Memory plus Skill. Wiki and CodeGraph stay disabled.

Every host receives a separately issued and revocable user-key. Never clone the
Debian credential for Ubuntu. The maintained infra provisioner may create a new
destination key, place it in a mode-0600 transfer file, deliver it once over
authenticated Tailnet SSH, verify it at the destination, and remove the transfer
copy. Both hosts may then select either workspace profile without sharing keys.
