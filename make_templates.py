import os
import re
import subprocess


def read_tex(fname):
    out_tex = ""
    ignorelist = ["%"]  # ignore lines starting with these
    ignore = 0  # flag for solution block

    with open(fname, "r") as f:
        for line in f.readlines():
            # remove solutions and IGNORE blocks
            if line.lstrip().startswith(
                r"\begin{solution}"
            ) or line.lstrip().startswith(r"% BEGIN IGNORE"):
                ignore += 1
                continue
            if line.lstrip().startswith(r"\end{solution}") or line.lstrip().startswith(
                r"% END IGNORE"
            ):
                ignore -= 1
                continue
            if ignore:
                continue

            # ignore lines starting with certain strings
            if any(line.lstrip().startswith(s) for s in ignorelist):
                continue

            # substitute inputs with exact text
            if line.lstrip().startswith(r"\input"):
                input_file = line.split("{")[1].split("}")[0]
                if not input_file.rstrip().endswith(".tex"):
                    input_file += ".tex"
                contents = read_tex(input_file)
                out_tex += contents
            else:
                out_tex += line

    return out_tex


def generate(assignment, out_dir, overwrite=False):
    if not os.path.isdir(out_dir):
        raise ValueError(f"{out_dir} is not a directory")

    out_fname = f"hw{assignment:02d}.tex"

    if not overwrite and os.path.exists(os.path.join(out_dir, out_fname)):
        raise ValueError(f"Template already exists in {out_dir}")

    template = read_tex(f"hw{assignment:02d}.tex")

    # reign in the whitespace
    template = re.sub(r"(\n\s*){3,}", "\n\n", template)

    # make sure sufficient space between questions
    template = re.sub(
        r"[\n\s]*(\\newpage\n)?[\n\s]*(\\question)", r"\n\n\n\g<1>\g<2>", template
    )

    # reformat without making insane backup files
    subprocess.run(
        [
            "latexindent",
            "-s",
            os.path.join(out_dir, out_fname),
            "-o",
            os.path.join(out_dir, out_fname),
        ]
    )

    with open(os.path.join(out_dir, out_fname), "w") as f:
        f.write(template)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate student-facing Latex template from HW source repo"
    )
    parser.add_argument("assignment", help="Number for the assignment", type=int)
    parser.add_argument(
        "out_dir",
        help="Directory to write the template to",
    )
    parser.add_argument(
        "--overwrite",
        help="Overwrite existing template",
        action="store_true",
    )

    args = parser.parse_args()
    generate(args.assignment, args.out_dir, args.overwrite)
