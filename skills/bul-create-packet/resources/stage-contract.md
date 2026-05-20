# Bottom-Up LENS Create Stage Contract

The create workflow uses these exact stages in order:

1. `context-intake`
2. `candidate-selection`
3. `local-sufficiency`
4. `scope-boundary`
5. `preview`
6. `confirmation`
7. `write`
8. `receipt`

At `context-intake`, the workflow displays explicit/module context, `packet_output_path`, `reports_output_path`, and runtime write scope before any mutation-capable stage. It blocks instead of inferring from branch name, open editor, or cwd/current working directory.

At `confirmation`, interactive writes require the exact token `CREATE PACKET`. Headless writes require `--confirm`.
