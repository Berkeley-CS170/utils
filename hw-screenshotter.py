import subprocess
from pdf2image import convert_from_path
from PIL import Image
import tempfile
import os
import importlib
templater = importlib.import_module('make-templates')
# \usepackage[margin=1.2in,paperheight=""" + str(ht) + r"""in]{{geometry}}"

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

def crop_whitespace(image):
    gray_image = image.convert("L")
    bbox = gray_image.getbbox()
    if bbox:
        return image.crop(bbox)
    return image

def pdf_to_images(pdf_file, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    images = convert_from_path(pdf_file)
    for i, image in enumerate(images):
        cropped_image = crop_whitespace(image)
        image_path = os.path.join(output_folder, f'page_{i + 1}.jpg')
        cropped_image.save(image_path, 'jpg')

def latex_to_images(assignment, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    os.makedirs(os.path.join(output_folder, f"hw{assignment:02d}"), exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        with open('cs170.sty', 'r') as f:
            with open(os.path.join(temp_dir, 'cs170.sty'), 'w') as f2:
                f2.write(f.read())

        templater.generate(assignment, temp_dir)
        questions = parse_questions(os.path.join(temp_dir, f'hw{assignment:02d}.tex'))

        for i, q in enumerate(questions, start=2):
            latex_file = os.path.join(temp_dir, f'q{i}.tex')
            with open(latex_file, 'w') as f:
                f.write(before_text + r"\setcounter{section}{" + str(i-1) + '}\n' + q + after_text)

            # Run pdflatex and save the output in the temporary directory
            subprocess.run(['pdflatex', '-output-directory', temp_dir, latex_file])

            pdf_file = os.path.join(temp_dir, os.path.basename(latex_file).replace('.tex', '.pdf'))

            # pdf_to_images(pdf_file, output_folder)
            # subprocess.run(['cp', pdf_file, output_folder])
            subprocess.run(['convert', '-density', '150', '-quality', '100', '-flatten', pdf_file, os.path.join(output_folder, f"hw{assignment:02d}", f'hw{assignment:02d}-img{i:02d}.png')])

def parse_questions(tex_file):
    questions = []
    with open(tex_file, 'r') as f:
        question = ''
        for line in f:
            if line.lstrip().startswith(r'\question'):
                if question:
                    questions.append(question)
                question = line
            else:
                question += line
        questions.append(question)
    return questions[2:]

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert Latex file to images"
    )
    parser.add_argument(
        "assignment", help="Number for the assignment", type=int
    )
    parser.add_argument(
        "output_folder",
        help="Path to the output folder"
    )

    args = parser.parse_args()
    latex_to_images(args.assignment, args.output_folder)