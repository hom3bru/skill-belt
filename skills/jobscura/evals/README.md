# Behavioural evals

These cases test how an agent *behaves* with Jobscura installed: whether the right workflow
triggers, and whether the integrity rules hold under pressure (hidden canaries, employer AI-use
bans, invented metrics, authority inflation, scams, deadline arithmetic, false action claims and
invented interview stories). The deterministic unit suites cannot measure this.

They use the `claude plugin eval` layout: one folder per case with `prompt.md` (frontmatter and the
user's message) and `graders/*.md`. Run from the Jobscura directory (it costs model usage):

```sh
claude plugin eval . --runs 1 --case "triggers-*"
claude plugin eval . --json eval-results.json --threshold 0.8
```

Results are written under `evals/results/`, which is ignored and never packaged. All people,
employers and figures in the prompts are fictional.
