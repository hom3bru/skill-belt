# Reproduce

Hypothesis work starts only once a reproduction exists. A reproduction is one command you have actually run that:

- goes through the code path the user reported and checks the user's symptom (the wrong value, the exact error), so it fails on this bug and would pass without it;
- gives a stable answer, or a measured failure rate for an intermittent bug ([flaky](flaky.md));
- finishes in seconds without a person in the loop.

"It ran and nothing crashed" is not a reproduction. A failure close to the reported one but not the same is another bug: record it as a surprise and keep looking for the reported one.

## Ways to get one, cheapest first

1. The failing test, run on its own with full output.
2. A focused test or an inline call at the narrowest point that reaches the bug (outside the project in diagnose mode).
3. The user's own command or request, with a fixed input, compared against the expected output.
4. A captured input (payload, file, event log) replayed through the code path.
5. A small harness around the suspect unit with its neighbours stubbed.
6. A loop over many generated inputs, for output that is only sometimes wrong.
7. The same input through two versions or two configurations, outputs compared.

## Tighten, then shrink

- Faster: run one test, skip setup that does not matter.
- Sharper: assert the specific symptom, not "no exception".
- Stable: fix the clock, time zone, random seed, locale, file order and network.

Then remove inputs, steps and settings one at a time, rerunning after each removal, and keep only what the failure needs. A small reproduction leaves fewer suspects and becomes the regression test.

## It does not fail for you

Treat the gap between the user's environment and yours as the first lead, not as doubt about the report. List the differences before guessing: operating system, time zone and locale, tool and dependency versions, environment variables, configuration actually loaded, data and state left by earlier runs, terminal against pipe, execution order, machine load. Ask for the single artifact that would settle it, such as the exact command, a log or the input.

When the report is a missing file or folder, name the first missing folder on its path, the nearest parent that exists and any similar names there before searching wider. The usual causes are a removed worktree and a path resolved from the wrong working directory.

## No reproduction possible

Stop. Report what you tried and why each attempt failed, then ask for access to an environment where it fails, a captured artifact, or permission for temporary logging. Anything said about the cause without a reproduction is a guess, and the report labels it so.
