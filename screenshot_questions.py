import subprocess
import tempfile
import os
import importlib
import make_templates

before_text = r"""\documentclass[11pt,preview,border=0.5in]{standalone}
\usepackage{cs170}
\def\title{Homework 1}
\def\duedate{Friday 9/6/204, at 10:00 pm (grace period until 11:59pm)}

\fancyhf{} % clear all header and footer fields
\renewcommand*\headrulewidth{0pt}

\begin{document}
"""
after_text = r"""
\end{document}"""

def latex_to_images(assignment, src_dir, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    os.makedirs(os.path.join(output_folder, f"hw{assignment:02d}"), exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        with open('cs170.sty', 'r') as f:
            with open(os.path.join(temp_dir, 'cs170.sty'), 'w') as f2:
                f2.write(f.read())

        make_templates.generate(assignment, src_dir, temp_dir)
        questions = make_templates.parse_questions(os.path.join(temp_dir, f'hw{assignment:02d}.tex'))[2:]
        print(f"Found {len(questions)} questions")

        for i, q in enumerate(questions, start=2):
            latex_file = os.path.join(temp_dir, f'q{i}.tex')
            with open(latex_file, 'w') as f:
                f.write(before_text + r"\setcounter{section}{" + str(i-1) + '}\n' + q + after_text)

            print(f"Converting question {i} to image")
            # Run pdflatex and save the output in the temporary directory
            subprocess.run(['pdflatex', '-interaction=batchmode', '-file-line-error', '-output-directory', temp_dir, latex_file])

            pdf_file = os.path.join(temp_dir, os.path.basename(latex_file).replace('.tex', '.pdf'))

            subprocess.run(['convert', '-density', '150', '-quality', '100', '-flatten', pdf_file, os.path.join(output_folder, f"hw{assignment:02d}", f'hw{assignment:02d}-img{i:02d}.png')])

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert Latex file to images"
    )
    parser.add_argument(
        "assignment", help="Number for the assignment", type=int
    )
    parser.add_argument(
        "src_dir",
        help="Directory where the tex source files are located",
    )
    parser.add_argument(
        "output_folder",
        help="Path to the output folder"
    )

    args = parser.parse_args()
    latex_to_images(args.assignment, args.src_dir, args.output_folder)