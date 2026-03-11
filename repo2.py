#!/usr/bin/env python3

import subprocess, sys, os, re

OUTPUT_FILE = "project.txt"
SPECFILE_OUTPUT = "specfile.txt"
SPECFOL_OUTPUT = "specfol.txt"

EXCLUDE_PATHS = re.compile(
    r"(__pycache__|migrations|tests|static|media|venv|env)"
)

EXCLUDE_FILES = re.compile(
    r"(admin|apps|asgi|wsgi|settings|manage|__init__)\.py$"
)

ALLOWED_EXT = (".py", ".html")

DJANGO_NOISE = re.compile(
    r"(verbose_name|help_text|permissions|ordering|indexes|__str__|Meta:)"
)


def git_ls_files():
    try:
        return subprocess.check_output(
            ["git", "ls-files"], text=True
        ).splitlines()
    except subprocess.CalledProcessError:
        sys.exit("❌ Not a git repository")


def relevant(path):
    if EXCLUDE_PATHS.search(path): return False
    if EXCLUDE_FILES.search(path): return False
    return path.endswith(ALLOWED_EXT)


def dynamic_html(path):
    try:
        c = open(path, encoding="utf-8", errors="ignore").read()
        return "{{" in c or "{%" in c
    except:
        return False


def compress_py(code):
    out, skip = [], False
    for l in code.splitlines():
        s = l.strip()

        if not s or s.startswith("#"):
            continue

        if s.startswith(('"""', "'''")):
            skip = not skip
            continue

        if skip or DJANGO_NOISE.search(s):
            continue

        if s.startswith("from django.contrib"):
            continue

        l = re.sub(r"#.*", "", l)
        out.append(re.sub(r"\s+", " ", l.strip()))

    return "\n".join(out)


def compress_html(code):
    out = []
    for l in code.splitlines():
        s = l.strip()
        if not s or s.startswith("<!--"):
            continue
        if "{{" in s or "{%" in s:
            out.append(re.sub(r"\s+", " ", s))
    return "\n".join(out)


def compress(code, ext):
    if ext == ".py":
        return compress_py(code)
    if ext == ".html":
        return compress_html(code)
    return ""


def write(files, target, append=False):
    mode = "a" if append else "w"
    with open(target, mode, encoding="utf-8") as out:
        for f in files:
            if not os.path.exists(f): continue

            ext = os.path.splitext(f)[1]
            raw = open(f, encoding="utf-8", errors="ignore").read()
            cmp = compress(raw, ext)

            if cmp.strip():
                out.write(f"\n=== {f} ===\n{cmp}\n")

    print(f"✅ Written → {target}")


def opt_django(files):
    selected = [
        f for f in files
        if relevant(f) and (not f.endswith(".html") or dynamic_html(f))
    ]
    write(selected, OUTPUT_FILE)


def opt_files(files):
    for i, f in enumerate(files):
        print(f"{i}: {f}")
    idx = input("Files: ").split(",")
    write([files[int(i)] for i in idx if i.isdigit()], SPECFILE_OUTPUT)


def opt_folders(files):
    folders = sorted({f.split("/")[0] for f in files if "/" in f})
    for i, f in enumerate(folders):
        print(f"{i}: {f}")
    idx = input("Folders: ").split(",")

    chosen = [folders[int(i)] for i in idx if i.isdigit()]
    selected = [
        f for f in files
        if any(f.startswith(c + "/") for c in chosen) and relevant(f)
    ]
    write(selected, SPECFOL_OUTPUT, append=True)


def menu():
    files = git_ls_files()
    while True:
        print("""
1) Core Django logic (ultra-compressed)
2) Select specific files
3) Select folders
4) Exit
""")
        c = input("> ").strip()
        if c == "1": opt_django(files)
        elif c == "2": opt_files(files)
        elif c == "3": opt_folders(files)
        elif c == "4": break


if __name__ == "__main__":
    menu()