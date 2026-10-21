# Freedom GPT — your local AI agent

**Model + tools + project memory.** Describe an outcome; the agent works with available tools and presents the result. Free and open source, with no subscription for local inference.

## Version 1.5.0

Version 1.5.0 adds the capabilities below. Previous releases remain available. Use Check for updates when you choose to upgrade.

| Capability | What it does |
|---|---|
| Goals | Outcome, acceptance criteria and constraints. Continue after a turn, pause, inspect history and reactivate. A step counter does not impose a twenty-turn limit. |
| Queue and steering | Edit, reorder or remove future prompts. Send an urgent correction to the current task. |
| Memory | History and project records on disk, retrieved after compression, restart or a model switch. Context remains finite and recall can be imperfect. |
| Branches | Start a separate task from a chat and its files, with an empty queue of its own. |
| Skills | Save reusable instructions and examples. Skills do not retrain model weights. |
| Browser | Website preview beside the chat, snapshots and visual checks with a compatible vision model. External sites require internet. |
| Applications and Blender | Use available CLI tools, scripts and integrations. Blender and specialist tools are separate installations; installing an app does not guarantee control over every GUI action. |
| Files and media | Collapsed file list, preview, editing supported text files and recoverable removal. Images and video appear inline. |
| Models | Hardware suggestions, library, resumable downloads and compatible GGUF import without an account. Engine architecture and quantization support still apply. |
| GitHub | Optional PAT or explicit use of an existing GitHub CLI sign-in. Reading; repositories, branches, commits, draft PRs and issues with write opt-in and suitable token permissions. |
| Hugging Face | Optional Read token for models your account can access. Gated models require separate approval and terms acceptance. Open downloads need no sign-in. |
| API providers | Optional supported providers with internet and your own key. Free quotas can change; a free consumer chatbot does not imply a free API. |
| Rewards | Achievements, XP, levels and local Freedom game points for confirmed results. No cryptocurrency, cash balance or promised exchange. |
| Updates | Start with Check for updates. Signatures and SHA256 are verified; installation waits for idle work and preserves user data. |

## Start simply

1. Install for your OS. Mac remains an unsigned preview requiring real-device validation.
2. Check the PC, select a compatible model and complete download verification.
3. Choose a project folder and verify a small tool-using task.
4. For longer work, define a goal and clear acceptance checks.
5. Review results and keep Git history and backups.

Example: “Create a local website in this project. Start with a plan, implement and test it, then show the page in preview. Stop before publishing externally.”

## An agent development workflow

Chat, terminal, files, queue, steering, branches and visual preview are familiar development-agent workflows. Freedom GPT adds a choice of compatible models and local computation. Comparative quality against Codex or another product has not been benchmarked. A small local model can make more mistakes than a strong cloud model. Speed depends on hardware, the model and context; 100+ tokens/s is not guaranteed.

Public packages do not include the author's entire personal toolkit. External actions need internet, appropriate permissions and user responsibility.

[Website](https://aionpc.ru) · [Releases](https://github.com/Leongrupp/freedom-gpt/releases) · [Support @AI1rus](https://t.me/AI1rus) · [Русский](AGENT.ru.md)
