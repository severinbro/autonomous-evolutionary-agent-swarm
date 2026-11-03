import json, os, subprocess, sys, tempfile
FILES = ["README.md", "a.log", "important.log", "debug/app.log", "logs/x.log", "logs/keep.txt", "logs/sub/y.log",
         "build/out.o", "build/keep/me.txt", "src/build/gen.py", "src/main.py", "src/main.pyc",
         "src/util/__pycache__/m.pyc", "doc/a.txt", "doc/sub/b.txt", "doc/a.pdf", "tmp/cache/z.bin",
         "a/b/c/d.txt", "a/x/b/c/e.txt", "a/b/foo.txt", "#hash.txt", "!bang.txt", "x[1].txt",
         "data1.csv", "data2.csv", "dataA.csv", ".env", "config/.env", "node_modules/pkg/index.js",
         "frontend/node_modules/x.js", "notes.txt", "deep/er/notes.txt"]
SCENARIOS = [
    ["*.log", "!important.log"],
    ["logs/", "!logs/keep.txt"],
    ["logs/*", "!logs/keep.txt"],
    ["/build", "doc/*.txt"],
    ["build/"],
    ["**/foo.txt", "a/**/c", "tmp/**"],
    ["*.py[co]", "__pycache__/"],
    ["data[0-9].csv", "\\#hash.txt", "\\!bang.txt", "x\\[1\\].txt"],
    ["# comment", "", ".env", "#hash.txt"],
    ["node_modules", "!frontend/node_modules/x.js"],
    ["*", "!*/", "!*.txt"],
    ["a.log   ", "doc/**/*.txt"],
    ["?.log", "debug/*.log", "/notes.txt"],
    ["src/*", "!src/main.py", "!src/build/"],
    ["/*.log", "**/sub", "deep/**/notes.txt"],
]
env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
out = {"git_version": subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip(),
       "files": FILES, "scenarios": []}
for lines in SCENARIOS:
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q"], cwd=d, env=env, check=True)
        for f in FILES:
            p = os.path.join(d, f); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write("x")
        open(os.path.join(d, ".gitignore"), "w").write("\n".join(lines) + "\n")
        res = subprocess.run(["git", "-c", "core.excludesFile=/dev/null", "ls-files", "--others", "--ignored",
                              "--exclude-standard"], cwd=d, env=env, capture_output=True, text=True, check=True)
        ignored = sorted(l for l in res.stdout.splitlines() if l)
        # git quotes unusual names; keep only names we know, and make sure none were lost to quoting
        unknown = [l for l in ignored if l not in FILES]
        if unknown:
            print("unparsed git output:", unknown, file=sys.stderr)
        out["scenarios"].append({"gitignore": lines, "ignored": [l for l in ignored if l in FILES]})
json.dump(out, sys.stdout, indent=0)
