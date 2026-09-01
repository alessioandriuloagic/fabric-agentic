"""Build the static onboarding page without network access or third-party dependencies."""

import argparse
import json
import shutil
from pathlib import Path

from fabric_agentic.bootstrap import render_instance_profile
from fabric_agentic.instance_profile import profile_schema


ASSET_DIRECTORY = Path(__file__).resolve().parents[1] / "onboarding"
ASSET_NAMES = ("index.html", "styles.css", "app.js")


def build(output_directory: Path) -> tuple[Path, ...]:
    output_directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in ASSET_NAMES:
        target = output_directory / name
        shutil.copyfile(ASSET_DIRECTORY / name, target)
        written.append(target)

    schema_path = output_directory / "instance-profile-v1.0.json"
    schema_path.write_text(
        json.dumps(profile_schema(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    written.append(schema_path)

    starter_path = output_directory / "starter-instance.json"
    starter_path.write_text(
        render_instance_profile("cliente_demo", "Cliente Demo"),
        encoding="utf-8",
        newline="\n",
    )
    written.append(starter_path)
    return tuple(written)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    for path in build(args.output):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())