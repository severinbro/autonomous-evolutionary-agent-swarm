# Oracle generators

Scripts that produced the hidden-check case files in `benchmarks/oracles/` from reference implementations.

| Case file | Generator | Reference | How to run |
| :--- | :--- | :--- | :--- |
| `t9_semver_cases.json` | `t9_semver_gen.js` | npm `semver` 7.8.5 | `npm install semver@7.8.5 && node t9_semver_gen.js > ../t9_semver_cases.json` |
| `t10_cron_cases.json` | `t10_cron_gen.py` | `croniter` 6.2.4 | `pip install --target lib croniter==6.2.4 && PYTHONPATH=lib python3 t10_cron_gen.py > ../t10_cron_cases.json` |
| `t11_gitignore_cases.json` | `t11_gitignore_gen.py` | git 2.53.0 | `python3 t11_gitignore_gen.py > ../t11_gitignore_cases.json` (git prints `.gitignore` as unparsed; expected) |
| `t12_commonmark_spec_0.31.2.json` | — | CommonMark spec 0.31.2 | `curl -sSfL https://spec.commonmark.org/0.31.2/spec.json -o ../t12_commonmark_spec_0.31.2.json` |

The cron generator leaves out `*/n` day-of-month or day-of-week fields combined with a restricted other day field, and reversed ranges: there `croniter` departs from crontab(5) (or accepts input crontab(5) rejects), so it is not a valid oracle for those cases.
