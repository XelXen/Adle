# adle-core

The local Python service behind Adle. It owns document ingestion, the curriculum graph, the learner
model, adaptive policy, and AI/TTS orchestration. It is started and supervised by the Electron main
process and is never exposed beyond the loopback interface.

See the repository root `AGENTS.md` and `services/core/AGENTS.md` for rules and commands.
