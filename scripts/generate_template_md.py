#!/usr/bin/env python3

import argparse
import yaml
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import xml.etree.ElementTree as ET

import subprocess

def get_remote_branches(repo_dir: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin"],
            cwd=repo_dir,
            capture_output=True, text=True, check=True
        )
        lines = result.stdout.splitlines()
        return [line.split("refs/heads/")[1] for line in lines if "refs/heads/" in line]
    except Exception as e:
        print(f"[WARN] Could not retrieve branch list: {e}")
        return []

def extract_package_metadata(package_dir: Path):
    pkg_xml = package_dir / "package.xml"
    description, license = None, None
    maintainers = []
    if pkg_xml.exists():
        try:
            tree = ET.parse(pkg_xml)
            root = tree.getroot()
            # Extract description
            desc_el = root.find("description")
            description = desc_el.text.strip() if desc_el is not None else None
            # Extract license
            lic_el = root.find("license")
            license = lic_el.text.strip() if lic_el is not None else None
            # Extract all maintainers
            for maint_el in root.findall("maintainer"):
                name = maint_el.text.strip()
                email = maint_el.attrib.get("email", "")
                obfuscated_email = email.replace("@", " [at] ").replace(".", " [dot] ") if email else ""
                maintainers.append({"name": name, "email": email, "obfuscated_email": obfuscated_email})
        except Exception as e:
            print(f"[WARN] Failed to parse package.xml: {e}")
    return description, license, maintainers

def extract_dependencies(package_dir: Path, dep_files: list[str] = ["dependencies.repos", "dependencies.rosinstall"]) -> list[dict]:
    for dep_file in dep_files:
        path = package_dir / dep_file
        if path.exists():
            try:
                with path.open("r") as f:
                    data = yaml.safe_load(f)
                repos = data.get("repositories", {})
                return [
                    {
                        "name": name,
                        "url": info.get("url", ""),
                        "version": info.get("version", "")
                    }
                    for name, info in repos.items()
                    if isinstance(info, dict)
                ]
            except Exception as e:
                print(f"[WARN] Failed to parse {dep_file}: {e}")
    return []

def parse_args():
    parser = argparse.ArgumentParser(
        description="Render a Jinja2 template for Home.md with launch docs."
    )
    parser.add_argument(
        "--template-dir",
        type=Path,
        required=True,
        help="Directory containing the Jinja2 template.",
    )
    parser.add_argument(
        "--template-name",
        type=str,
        required=True,
        help="Name of the Jinja2 template file (e.g. Home.template.md).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the rendered file (e.g. wiki/Home.md).",
    )
    parser.add_argument(
        "--launch-docs-dir",
        type=Path,
        help="Base directory containing per-package .md launch doc files.",
    )
    parser.add_argument(
        "--cli-command-docs-dir",
        type=Path,
        help="Base directory containing per-cli-command .md doc files.",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        help="Name of the ROS workspace to use.",
    )
    parser.add_argument(
        "--package-name",
        type=str,
        help="Name of the package to filter launch docs for.",
    )
    parser.add_argument(
        "--github-user",
        type=str,
        default="csun-arcs",
        help="Name of the GitHub user for forming GitHub URLs in templates.",
    )
    parser.add_argument(
        "--docs-workflow-filename",
        type=str,
        default="generate-docs.yml",
        help="Name of the Github Actions workflow filename used for generating documentation.",
    )
    parser.add_argument(
        "--tests-workflow-filename",
        type=str,
        default="run-tests.yml",
        help="Name of the Github Actions workflow filename used for running tests.",
    )
    parser.add_argument(
        "-pdf",
        "--package-dependency-files",
        nargs="*",
        default=["dependencies.repos", "dependencies.rosinstall"],
        help=(
            "Dependency file names to search for within packages."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="If set, renders the output to stdout instead of writing to a file.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    env = Environment(
        loader=FileSystemLoader(str(args.template_dir)),
        trim_blocks=True,
        lstrip_blocks=True)
    template = env.get_template(args.template_name)

    if args.launch_docs_dir and args.package_name:
        package_doc_dir = args.launch_docs_dir / args.package_name
        if not package_doc_dir.exists():
            print(f"[WARN] Launch doc directory not found: {package_doc_dir}")
            launch_docs = []
        else:
            launch_docs = [
                {
                    "name": md.name,
                    "title": md.name.removesuffix(".launch.md").replace("_", " ").title(),
                }
                for md in sorted(package_doc_dir.glob("*.md"))
            ]

        if not launch_docs:
            print(f"[WARN] No launch docs found for package: {args.package_name}")
        else:
            print(
                f"[INFO] Found {len(launch_docs)} launch docs for package: {args.package_name}"
            )
    else:
        launch_docs = []

    if args.cli_command_docs_dir:
        if not args.cli_command_docs_dir.exists():
            print(f"[WARN] CLI command docs directory not found: {args.cli_command_docs_dir}")
            cli_command_docs = []
        else:
            cli_command_docs = [
                {
                    "name": md.name,
                    "title": md.name.removesuffix(".md").replace("_", " ").title(),
                }
                for md in sorted(args.cli_command_docs_dir.glob("*.md"))
            ]

        if not cli_command_docs:
            print(f"[WARN] No CLI command docs found.")
        else:
            print(
                f"[INFO] Found {len(cli_command_docs)} CLI command docs."
            )
    else:
        cli_command_docs = []

    if args.workspace and args.package_name:
        package_dir = Path(args.workspace) / "src" / args.package_name
        description, license, maintainers = extract_package_metadata(package_dir)
        available_branches = get_remote_branches(package_dir)
        dependencies = extract_dependencies(package_dir, dep_files=args.package_dependency_files)
    else:
        package_dir = None
        description, license, maintainers = None, None, None
        available_branches = None
        dependencies = None

    context = {
        "repo_name": args.package_name,
        "github_user": args.github_user,
        "branches": available_branches,
        "launch_docs": launch_docs,
        "cli_command_docs": cli_command_docs,
        "description": description,
        "license": license,
        "maintainers": maintainers,
        "dependencies": dependencies,
        "docs_workflow_filename": args.docs_workflow_filename,
        "tests_workflow_filename": args.tests_workflow_filename,
    }

    rendered = template.render(**context)

    if args.dry_run:
        print("[INFO] Dry run enabled - rendered output below:")
        print("=" * 40)
        print(rendered)
        print("=" * 40)
    else:
        args.output.write_text(rendered)
        print(f"[INFO] Rendered template written to: {args.output}")


if __name__ == "__main__":
    main()
