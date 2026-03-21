# Understanding the BSL Assignment — A Complete Mental Model

## The Big Picture (What's Going On?)

Imagine you're a **game designer** building an escape room. But instead of a human player, an **AI agent** will try to escape. Your job is to:

1. Build the room (the broken environment)
2. Write the clue sheet (the instructions)
3. Have a working answer key (the solution)
4. Set up cameras to check if the player escaped (the tests)

The room should be **hard but not impossible** — the AI should solve it sometimes (>0%) but not always (<70%).

---

## The Key Players

### 1. Terminal Bench 2.0 — "The Question Bank"

**What it is:** A collection of ~92 challenges (like an exam paper) used by major AI labs to test how good AI agents are at real-world terminal/coding tasks.

**Analogy:** Think of it like a standardized test (SAT/JEE) but for AI agents. Just like JEE has Physics, Chemistry, Math sections — Terminal Bench has categories like DevOps, Security, ML, Data Engineering, etc.

**Examples of existing tasks:**
| Task | What the AI must do |
|------|-------------------|
| `nginx-request-logging` | Fix a broken Nginx config to enable proper logging |
| `fix-code-vulnerability` | Find and patch security bugs in code |
| `multi-source-data-merger` | Merge data from JSON, CSV, Parquet files with conflict resolution |
| `build-cython-ext` | Fix dependency issues to compile a Cython extension |

**Your assignment = Create ONE new question for this "exam paper"**

---

### 2. Harbor — "The Exam Hall Infrastructure"

**What it is:** A CLI tool that runs and manages these AI challenges. Think of it as the infrastructure/platform that:
- Sets up isolated Docker containers (the "exam room")
- Places the AI agent inside
- Gives it the instructions
- Runs the tests after the AI is done
- Reports the score

**Analogy:** Harbor is like the exam hall + invigilator + answer-checking system all in one.

**How Harbor works step by step:**

```
You create a task folder
        |
        v
harbor run -p "./your_task" -a oracle
        |
        v
Harbor reads your task.toml, instruction.md, environment/, solution/, tests/
        |
        v
Harbor builds a Docker container from environment/Dockerfile
        |
        v
Harbor copies your environment files into /app/ inside the container
        |
        v
[If oracle]: Runs your solve.sh to verify your setup works
[If terminus-2]: Drops the AI agent into the container with instruction.md
        |
        v
Harbor runs tests/ against the result
        |
        v
Reports: PASS or FAIL
```

**Two modes you'll use:**

| Command | What it does | When to use |
|---------|-------------|-------------|
| `harbor run -a oracle` | Runs YOUR solution (solve.sh) and checks if tests pass | First — to verify your task is valid |
| `harbor run -a terminus-2` | Drops an AI agent into the container to try solving it | Second — to check difficulty level |

---

### 3. Terminus-2 — "The AI Test-Taker"

**What it is:** An AI agent that gets dropped into the Docker container and tries to solve your challenge. It can:
- Read files
- Run bash commands
- Install packages
- Write/edit code
- Basically do anything a developer could do in a terminal

**What it sees:**
- The `instruction.md` (your task description)
- Everything in the `environment/` folder (mounted at `/app/`)

**What it does NOT see:**
- Your `solution/` folder
- Your `tests/` folder (these are kept hidden and only run AFTER the agent is done)

---

### 4. Groq + Kimi K2 — "The AI's Brain"

**What it is:** The AI agent (terminus-2) needs a language model to think. You'll use:
- **Groq** = The API provider (like a cloud service that hosts the model)
- **Kimi K2** (`moonshotai/kimi-k2-instruct-0905`) = The specific LLM model the agent uses

**Analogy:** Terminus-2 is the body (it can type commands, read files). Kimi K2 is the brain (it decides WHAT to type). Groq is the server that runs the brain.

---

## Your Task Folder Structure — What Each Piece Does

```
your_task_name/
├── task.toml              # Config: metadata, Python version, timeouts
├── instruction.md         # What the AI reads: "Here's what's broken, fix it"
├── environment/           # The "broken room"
│   ├── Dockerfile         # Sets up the container (OS, packages, etc.)
│   ├── app.py             # Your broken code/setup
│   ├── config.yaml        # Any config files needed
│   └── ...                # Whatever files make up the challenge
├── solution/              # YOUR answer key (AI never sees this)
│   └── solve.sh           # Script that fixes everything
└── tests/                 # The checker (AI never sees this either)
    ├── test.sh            # Don't touch this (Harbor's built-in runner)
    └── test_outputs.py    # YOUR pytest tests that verify the fix worked
```

### How they connect:

```
instruction.md tells the AI:  "The app at /app/ is broken. Fix it."
                                        |
                                        v
environment/ IS the broken app:   The Dockerfile builds it,
                                  files are copied to /app/ in container
                                        |
                                        v
The AI (or your solve.sh) works on /app/ to fix things
                                        |
                                        v
tests/test_outputs.py checks:    "Did the fix actually work?"
                                  (e.g., does the API return 200?)
                                  (e.g., does the output file exist and have correct data?)
```

---

## The Flow End-to-End

```
Step 1: You design a hard DevOps/SWE problem
            |
Step 2: You build it using Harbor's structure
            |
Step 3: harbor run -a oracle  →  Does YOUR solution pass?
            |                      If no → fix your task
            |                      If yes → continue
Step 4: harbor run -a terminus-2 --model groq/kimi-k2 -k 10
            |
            → AI tries 10 times
            → You get a score like 3/10 (30% pass rate)
            → Is it between 0% and 70%?
                If yes → PERFECT difficulty!
                If no → Adjust (make easier or harder)
            |
Step 5: Zip it up, email it, done!
```

---

## What Makes a Task "Hard" (The Sweet Spot)

The AI should NOT be able to solve it by just:
- Reading a file (`cat some_file`)
- Running an obvious command (`pip install X`)
- Following a simple error message

The AI SHOULD need to:
- **Reason about multiple connected problems** (e.g., Service A fails because Service B's config is wrong, which depends on Service C's port)
- **Analyze logs and trace errors** across multiple files
- **Understand domain concepts** (e.g., how Nginx proxying works, how DB migrations interact)
- **Make non-obvious connections** (e.g., a race condition, a circular dependency, a subtle version conflict)

**Target: 0% < pass rate < 70% across 10 runs with Kimi K2**

---

## Key Rules to Remember

1. **No cheating possible** — The answer must NOT be findable by just reading files in `environment/`
2. **Tests stay hidden** — Never copy `tests/` into the Docker image
3. **Pin versions** — Always use exact versions in Dockerfile (`pip install flask==2.3.0`, not `pip install flask`)
4. **Files go in /app/** — Everything in the container lives under `/app/`
5. **instruction.md = goal, not steps** — Say "Fix the broken API" not "Change line 42 in config.yaml"
6. **Functional tests** — Your tests should check if things actually WORK (API responds, data is correct), not just if files exist
