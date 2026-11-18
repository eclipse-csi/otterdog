# AI Coding Agents

The repository contains instructions for AI coding agents. There is one source for them, so that several tools can
use the same text.

## Layout

```text
AGENTS.md                              # instructions shared by all agents
CLAUDE.md                              # Claude Code adapter, only imports AGENTS.md with "@AGENTS.md"
.agents/skills/<skill-name>/SKILL.md   # skills, the only copy of their content
.claude/skills/<skill-name>            # relative symlinks to ../../.agents/skills/<skill-name>
```

- [`AGENTS.md`](https://github.com/eclipse-csi/otterdog/blob/main/AGENTS.md) starts with the rules that are never
  negotiable, then describes the project, its conventions, the commands, how to choose the checks for a change, the
  adversarial review required before a pull request, the git rules for sessions that share a checkout, and the
  precautions for commands that read or change real GitHub organizations. It summarises this documentation: when a
  technical description diverges from it, update `AGENTS.md`; when the documentation contradicts one of its rules
  (safety, git, contribution), report the gap instead of weakening the rule.
- A skill is a procedure for one kind of task, written in the open
  [Agent Skills](https://agentskills.io) format: a folder with a `SKILL.md` file that starts with a YAML frontmatter
  holding `name` and `description`. `AGENTS.md` lists the available skills and when to use each one.

Edit only `AGENTS.md` and the files in `.agents/skills/`. `CLAUDE.md` and `.claude/skills/` are adapters and hold no
instructions of their own.

## Portable format, tool-dependent discovery

The format is portable: `AGENTS.md` and `SKILL.md` are plain Markdown, and any agent can follow them once it reads
them. Whether a tool finds them **on its own** depends on the tool and its version:

- Some tools read `AGENTS.md` and `.agents/skills/` automatically; others do not, or use their own file names or
  folders. Check the documentation of your tool.
- Claude Code is set up by this repository: it reads `CLAUDE.md`, which imports `AGENTS.md`, and discovers the skills
  through the symlinks in `.claude/skills/`. It may pick a skill from its description, or you can invoke it as
  `/<skill-name>`.
- With a tool that discovers neither file, tell the agent to read `AGENTS.md`, and point it to the `SKILL.md` that
  fits the task, e.g. "follow `.agents/skills/github-config-property/SKILL.md`".

The symlinks need a checkout that supports them. On Windows, enable symlinks in git (`core.symlinks`) and in the
system; otherwise git checks each link out as a small text file that contains its target path.

## Adding a skill

1. Check that the task needs its own procedure. General rules belong in `AGENTS.md`; a skill holds the steps for one
   recurring kind of change, with references to the files involved.
2. Create `.agents/skills/<skill-name>/SKILL.md`. The name uses lowercase letters, digits and hyphens, and is
   identical in the folder name and the `name` field:

    ```markdown
    ---
    name: <skill-name>
    description: What the skill does and when to use it, in one or two sentences with the words a request would use.
    ---

    # Title

    ## When to use
    ## Procedure (steps with paths of the files of the repository)
    ## Checks (refer to the rules of AGENTS.md instead of copying them)
    ```

3. Keep it short and specific to otterdog. Refer to `AGENTS.md` for the shared conventions, commands and safety rules
   instead of repeating them. Use only the standard fields `name` and `description`, and no features specific to one
   tool, such as Claude-only frontmatter keys, tool names, or variables like `${CLAUDE_*}`.
4. Add the symlink for Claude Code, and check that it resolves:

    ```shell
    ln -s ../../.agents/skills/<skill-name> .claude/skills/<skill-name>
    test -f .claude/skills/<skill-name>/SKILL.md && readlink .claude/skills/<skill-name>
    ```

5. Add the skill to the table of the "Skills" section of `AGENTS.md`.
6. Run `poetry run prek run --files <new files>`. A skill is documentation for agents, so it needs no tests, but its
   paths and commands must exist in the repository.

To change a skill, edit its `SKILL.md` in `.agents/skills/`. The symlink follows automatically. To remove a skill,
delete its folder, its symlink, and its row in `AGENTS.md`.
