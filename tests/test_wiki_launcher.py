import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_wiki_launcher_uses_project_and_home_paths_and_forwards_options(tmp_path):
    project = tmp_path / "project with spaces"
    project.mkdir()
    launcher = project / "start-wiki"
    shutil.copy2(ROOT / "start-wiki", launcher)
    python = project / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" "$@"\nexit 17\n')
    python.chmod(0o755)
    home = tmp_path / "home with spaces"

    result = subprocess.run(
        [str(launcher), "--host", "127.0.0.1"],
        cwd=tmp_path,
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 17
    assert result.stdout.splitlines() == [
        str(project),
        "-m", "ki_knowledge.doc_viewer",
        "--workspace", str(home / "dev_wiki"),
        "--domain", "Dokumentation", str(project / "doc"), str(home / "dev_wiki_rel"),
        "--host", "127.0.0.1",
    ]
