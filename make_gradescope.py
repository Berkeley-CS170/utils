from gradescopeapi.classes.connection import GSConnection
from datetime import datetime

import json
import re
import subprocess
import tempfile
import os
import importlib

import make_templates

PREFIX = "https://www.gradescope.com/"

def get_due_date(template):
    pattern = r"\\def\\duedate{(\w+)?,?\s*(\d{1,2}\/\d{1,2}\/\d{,4}).*?(\d{1,2}:\d{2})\s*?([ap]m).*}"
    match = re.search(pattern, template)
    if match:
        date_str = match.group(1) + " " + match.group(2) + " " + match.group(3) + " " + match.group(4)
        dt = datetime.strptime(date_str, "%A %m/%d/%Y %I:%M %p")
        return dt


def post_gradescope_written(connection, course_id, assignment, pdf_dir, due_date_str, late_due_date_str, has_coding):
    assignment_name = f"Homework {assignment}" + (" (Coding Portion)" if has_coding else "")
    template_fname = os.path.join(pdf_dir, f"hw{assignment:02d}.pdf")
    
    # release today, always hardcode time to midnight for consistency
    release_date_str = datetime.now().strftime("%Y-%m-%dT00:00") 

    data = {
        "assignment[type]": "PDFAssignment",
        "assignment[title]": assignment_name,
        "assignment[submissions_anonymized]": 0,
        "assignment[student_submission]": True, 
        "assignment[release_date_string]": release_date_str,
        "assignment[due_date_string]": due_date_str,
        "assignment[allow_late_submissions]": 1, 
        "assignment[enforce_time_limit]": 0,
        "assignment[hard_due_date_string]": late_due_date_str,
        "assignment[group_submission]": 0,
        "assignment[submission_type]": "image",
        "assignment[when_to_create_rubric]": "while_grading",
        "assignment[template_visible_to_students]": 0,
    }
    files = {
        'template_pdf': (f'hw{assignment}.pdf', open(template_fname, 'rb'), 'application/pdf')
    }
    response = connection.session.post(PREFIX + f"/courses/{course_id}/assignments/", data=data, files=files)
    if response.ok:
        print("Created written: " + response.url)
        if not response.url.endswith("/edit"):
            print("Warning: Does the assignment already exist?")
    else:
        raise Exception(response.status_code, response.reason)

def get_assignment_id(connection, course_id, assignment_name):
    print("Querying existing assignments")
    assignments = connection.account.get_assignments(course_id)
    for a in assignments:
        if a.name == assignment_name:
            return a.assignment_id

def add_questions_to_outline(connection, course_id, assignment, has_coding, questions):
    assignment_name = f"Homework {assignment}" + (" (Coding Portion)" if has_coding else "")
    assignment_id = get_assignment_id(connection, course_id, assignment_name)

    # Need json.dumps to get correct handling of null fields
    data = json.dumps({
        "assignment": {                     # Needs to be here or API freaks out
            "identification_regions": None  # Subfields only used for exams
        },
        "question_data": [{"title": q, "weight": 1} for q in questions]
    })
    # Need to force JSON, requests automatic resolution gives the wrong type
    headers = {"Content-Type": "application/json"}

    response = connection.session.patch(PREFIX + f"/courses/{course_id}/assignments/{assignment_id}/outline/", data=data, headers=headers)
    if response.ok:
        print(f"Added {len(questions)} questions to the outline")
        print("IMPORTANT: Make sure to manually configure point values and add rubrics")
    else:
        raise Exception(response.status_code, response.reason)


def post_gradescope_coding(connection, course_id, assignment, due_date_str, late_due_date_str):
    assignment_name = f"Homework {assignment} (Coding Portion)"
    # release today, always hardcode time to midnight for consistency
    release_date_str = datetime.now().strftime("%Y-%m-%dT00:00") 

    # All adjustable params, tweak as needed
    form_data = { 
        "assignment[type]": "ProgrammingAssignment",
        "assignment[title]": assignment_name,
        "assignment[submissions_anonymized]": 0,
        "assignment[total_points]": 10,
        "assignment[manual_grading]": 0,
        "assignment[student_submission]": True, 
        "assignment[release_date_string]": release_date_str,
        "assignment[due_date_string]": due_date_str,
        "assignment[allow_late_submissions]": 1,
        "assignment[hard_due_date_string]": late_due_date_str,
        "assignment[group_submission]": 0,
        "assignment[leaderboard_enabled]": 0
    }
    response = connection.session.post(PREFIX + f"/courses/{course_id}/assignments/", data=form_data)
    if response.ok:
        print("Created coding: " + response.url)
        print("IMPORTANT: You need to manually configure point values and upload the auto-grader zip")
    else:
        raise Exception(response.status_code, response.reason)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create Gradescope Assignments"
    )
    parser.add_argument(
        "assignment", help="Number for the assignment", type=int
    )
    parser.add_argument(
        "config_path", help="Path to .json file containing Gradescope credentials"
    )
    parser.add_argument(
        "pdf_dir", help="Directory containing PDFs of the assignment"
    )
    args = parser.parse_args()
    config_path = args.config_path
    assignment = args.assignment
    pdf_dir = args.pdf_dir

    config = json.load(open(config_path))
    GS_COURSE_ID = config['gradescope_id']
    GS_UNAME = config['gradescope_uname']
    GS_PASSWORD = config['gradescope_password']

    template = make_templates.read_tex(pdf_dir, f"hw{assignment:02d}.tex")
    due_date_str = get_due_date(template).strftime("%Y-%m-%dT%H:%M")
    late_due_date = re.sub(r"T\d{2}:\d{2}", "T23:59", due_date_str)
    question_titles = re.findall(r"\\question{([^}]*)}", template)

    has_coding = False
    for title in reversed(question_titles):
        if "coding" in title.lower():
            has_coding = True
            question_titles.remove(title)

    connection = GSConnection()
    connection.login(GS_UNAME, GS_PASSWORD)

    post_gradescope_written(connection, GS_COURSE_ID, assignment, pdf_dir, due_date_str, late_due_date, has_coding)
    add_questions_to_outline(connection, GS_COURSE_ID, assignment, has_coding, question_titles)
    if has_coding:
        post_gradescope_coding(connection, GS_COURSE_ID, assignment, due_date_str, late_due_date)