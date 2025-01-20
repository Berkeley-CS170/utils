"""
This example script will NOT work if you run it directly; it is meant to be used as a reference
in case you'd like to implement something similar.

This script is used for CS70 at UC Berkeley to automatically post
homework, discussion, and note threads. All of these threads are tracked in a locked index post,
which is continually updated by this script as well.

Homework templates are also posted with each homework, by uploading a zip file to Overleaf
and prompting the user to finalize the new Overleaf project.
This Overleaf view link is included in a separate post for students.

Usage:
    post_threads.py hw <num>
    post_threads.py dis <num> [--summer]
    post_threads.py note <num>
    post_threads.py init-index

Requirements:
    config file with:
        course_id: id of course to target
        index_thread_num: id of index thread for homeworks/discussions
    environment variables:
        ED_API_KEY: ed api key
"""

import json
import os
import datetime
from dataclasses import dataclass
from typing import Optional, Union
import re
from ruamel.yaml import YAML
from bs4 import BeautifulSoup, Tag

from edapi import EdAPI
from edapi.constants import ThreadType
from edapi.utils import new_document, parse_content
from PIL import Image
import ed_templates

OVERLEAF_UPLOAD_URL = "https://www.overleaf.com/docs?snip_uri="
ANSI_BLUE = lambda text: f"\u001b[34m{text}\u001b[0m"


@dataclass
class Config:
    """Configuration for posting Ed threads."""

    course_id: int
    index_thread_num: Optional[int]
    overleaf_url: Optional[str]
    lectures_path: Optional[str]

    def copy(self) -> "Config":
        """Make a copy of the current configuration."""
        return Config(course_id=self.course_id, index_thread_num=self.index_thread_num)

    @staticmethod
    def from_json(obj: dict, id_field: str) -> "Config":
        """Convert a JSON object (dict) into a Config dataclass."""
        assert id_field in obj, "config JSON must contain 'course_id' value"

        index_thread_num = obj.get("index_thread_num", None)
        if index_thread_num is not None:
            index_thread_num = int(index_thread_num)

        overleaf_url = obj.get("overleaf_link", None)
        lectures_path = obj.get("lectures_path", None)

        return Config(
            course_id=int(obj[id_field]),
            index_thread_num=index_thread_num,
            overleaf_url=overleaf_url,
            lectures_path=lectures_path,
        )

    def as_json(self) -> dict:
        """Convert this dataclass into a dict to write to a JSON file."""
        return {
            "course_id": self.course_id,
            "index_thread_num": self.index_thread_num,
            "overleaf_url": self.overleaf_url,
        }


# ========== File path helpers ==========

HOMEWORK_IMAGE_EXTENSION = ".png"


def get_hw_folder(hw_num: str):
    """Compute the base path for homework files."""
    return f"./hw-screenshots/hw{hw_num}/"


def get_hw_template_zip(hw_num: str):
    """Compute the path to the homework template zip file."""
    return f"../rendered/hw{hw_num}/raw/hw{hw_num}-template.zip"


# ========== Ed post helpers ==========

def parse_template(template: list[Union[str, ed_templates.Link, ed_templates.H2]]) -> tuple[BeautifulSoup, Tag]:
    """
    Parse a template into a BeautifulSoup document.
    """
    post_soup, document = new_document()
    for par in template:
        paragraph = post_soup.new_tag("paragraph")
        if isinstance(par, list):
            for item in par:
                if isinstance(item, str):
                    paragraph.append(item)
                elif isinstance(item, ed_templates.Link):
                    link_tag = post_soup.new_tag("link", href=item.href)
                    link_tag.string = item.text
                    paragraph.append(link_tag)
            document.append(paragraph)
        elif isinstance(par, ed_templates.H2):
            if paragraph.string:
                document.append(paragraph)
            h2_tag = post_soup.new_tag("heading", level=2)
            h2_tag.string = par.text
            document.append(h2_tag)
        else:
            paragraph.string = par
            document.append(paragraph)
    return post_soup, document

def post_exam(ed: EdAPI, config: Config, exam_name: str):
    """
    Post past midterm/final exam question threads.
    """
    exam_names_long = dict(
        mt1="Midterm 1",
        mt2="Midterm 2",
        final="Final",
    )
    assert exam_name in exam_names_long, f"Invalid exam name: {exam_name}"
    exam_name_fmt = exam_names_long[exam_name]

    summary = []

    yaml = YAML()
    with open(f"./{exam_name}.yml", "r") as f:
        exam_data = yaml.load(f)
    
    for entry in reversed(exam_data):
        sem = entry["sem"]
        # create post body
        template = ed_templates.SINGLE_EXAM_TEMPLATE(sem, exam_name_fmt)
        post_soup, document = parse_template(template)

        links_paragraph = post_soup.new_tag("paragraph")
        links_paragraph.string = "Links: "
        field_to_text = {
            "exam_link": "Blank",
            "sol_link": "Solutions",
            "video_link": "Video Walkthrough",
            "common_mistakes": "Common Mistakes Doc",
        }
        has_field = False
        for field, text in field_to_text.items():
            link = entry.get(field, None)
            if link is not None:
                if has_field:
                    links_paragraph.append(", ")
                link_tag = post_soup.new_tag("link", href=link)
                link_tag.string = text
                links_paragraph.append(link_tag)
                has_field = True
        document.append(links_paragraph)

        clarifications_hdr = post_soup.new_tag("heading", level=2)
        clarifications_hdr.string = "Clarifications/Notes/Errata"

        clarifications_paragraph = post_soup.new_tag("list")
        for bullet in (entry.get("clarifications", "") or "").split("\n"):
            if not bullet:
                continue
            bullet_tag = post_soup.new_tag("list-item")
            bullet_tag.string = bullet
            clarifications_paragraph.append(bullet_tag)
        if clarifications_paragraph.contents:
            document.append(clarifications_hdr)
            document.append(clarifications_paragraph)

        result = ed.post_thread(
            config.course_id,
            {
                "type": ThreadType.POST,
                "title": f"{sem} {exam_name_fmt} Thread",
                "category": "Exam",
                "subcategory": exam_name_fmt,
                "subsubcategory": "",
                "content": str(document),
                "is_pinned": False,
                "is_private": False,
                "is_anonymous": False,
                "is_megathread": True,
                "anonymous_comments": True,
            },
        )
        print(
            f"[{sem} {exam_name}] Posted thread for {exam_name_fmt}: #{result['number']}" 
        )
        summary.append(f"{sem} {exam_name_fmt} (#{result['number']})")

    template = ed_templates.EXAM_MEGATHREAD_TEMPLATE(exam_name_fmt)
    post_soup, document = parse_template(template)

    question_list = post_soup.new_tag("list")
    question_list.attrs["style"] = "bullet"
    for question_content in reversed(summary):
        question_item = post_soup.new_tag("list-item")
        question_paragraph = post_soup.new_tag("paragraph")
        question_paragraph.append(question_content)
        question_item.append(question_paragraph)
        question_list.append(question_item)
    document.append(question_list)

    template_result = ed.post_thread(
        config.course_id,
        {
            "type": ThreadType.POST,
            "title": f"Past {exam_name_fmt} Megathread",
            "category": "Exam",
            "subcategory": exam_name_fmt,
            "subsubcategory": "",
            "content": str(document),
            "is_pinned": True,
            "is_private": False,
            "is_anonymous": False,
            "is_megathread": True,
            "anonymous_comments": True,
        },
    )
    print(f"Posted megathread for {exam_name_fmt}: #{template_result['number']}")
    summary.append(f"{exam_name_fmt} Megathread (#{template_result['number']})")


def post_hw(ed: EdAPI, config: Config, hw_num: str):
    """
    Post homework question threads and update the homework/discussion index.
    """
    assert config.index_thread_num is not None, "Index thread number must be provided."

    summary = []
    hw_num_fmt = f"{int(hw_num):02d}"
    base_path = get_hw_folder(hw_num)
    # retrieve all images from the rendered directory
    hw_imgs = [
        f
        for f in os.listdir(base_path)
        if os.path.isfile(os.path.join(base_path, f))
        and f.endswith(HOMEWORK_IMAGE_EXTENSION)
    ]
    # sort images by problem number (names are of the format "hwXX-imgXX.png")
    hw_imgs.sort(key=lambda x: int(x.split(".")[0].split("-")[1][3:]), reverse=True)
    num_imgs = len(hw_imgs)

    for hw_idx, hw_img in enumerate(hw_imgs, 1):
        with open(base_path + hw_img, "rb") as f:
            curr_img = f.read()

        # upload image to ed
        img_url = ed.upload_file(hw_img, curr_img, "image/png")
        print(f"[{hw_idx}/{num_imgs}] Uploaded {hw_img}: {img_url}")

        # get image dimensions for display
        img = Image.open(base_path + hw_img)
        img_width, img_height = img.size

        # hw_img has format hw<hw #>-img<problem #>.png
        problem_num = hw_img.split(".")[0][-1]

        # create post body
        problem_soup, document = new_document()
        problem_figure = problem_soup.new_tag("figure")
        problem_image = problem_soup.new_tag(
            "image", src=img_url, width=img_width, height=img_height
        )
        problem_figure.append(problem_image)
        document.append(problem_figure)

        result = ed.post_thread(
            config.course_id,
            {
                "type": ThreadType.POST,
                "title": f"Homework {hw_num_fmt} Question {problem_num} Thread",
                "category": "Homework",
                "subcategory": f"HW{hw_num_fmt}",
                "subsubcategory": "",
                "content": str(document),
                "is_pinned": False,
                "is_private": False,
                "is_anonymous": False,
                "is_megathread": True,
                "anonymous_comments": True,
            },
        )
        print(
            f"[{hw_idx}/{num_imgs}] Posted thread for HW{hw_num_fmt} Q{problem_num}:"
            f" #{result['number']}"
        )
        summary.append(f"Question {problem_num} (#{result['number']})")

    summary.reverse()

    # LaTeX Template
    # with open(get_hw_template_zip(hw_num), "rb") as f:
    #     template_zip = f.read()
    # template_url = ed.upload_file(
    #     f"hw{hw_num}-template.zip", template_zip, "multipart/form-data"
    # )

    # template_creation_url = OVERLEAF_UPLOAD_URL + template_url
    # print(f"\nGo to:\n\t{ANSI_BLUE(template_creation_url)}")

    # Release post
    # student_link = input("Enter shareable Overleaf link: ")
    student_link = config.overleaf_url
    print("Shareable Overleaf link:", student_link)

    # create post body
    next_friday = (datetime.datetime.now() + datetime.timedelta(
        days=(4 - datetime.datetime.now().weekday()) % 7
    )).strftime(r"%m/%d")
    
    template = ed_templates.HW_TEMPLATE(hw_num_fmt, next_friday)
    post_soup, document = parse_template(template)

    question_list = post_soup.new_tag("list")
    question_list.attrs["style"] = "bullet"
    for question_content in summary:
        question_item = post_soup.new_tag("list-item")
        question_paragraph = post_soup.new_tag("paragraph")
        question_paragraph.append(question_content)
        question_item.append(question_paragraph)
        question_list.append(question_item)
    document.append(question_list)


    link_paragraph = post_soup.new_tag("paragraph")
    link_paragraph.string = "LaTeX Template link: "
    link_link = post_soup.new_tag("link", href=student_link)
    link_link.string = student_link
    link_paragraph.append(link_link)
    document.append(link_paragraph)

    # zip_paragraph = post_soup.new_tag("paragraph")
    # zip_paragraph.string = "Source files:"
    # document.append(zip_paragraph)
    # zip_link = post_soup.new_tag(
    #     "file", url=template_url, filename=f"hw{hw_num}-template.zip"
    # )
    # zip_paragraph.append(zip_link)
    # document.append(zip_link)

    template_result = ed.post_thread(
        config.course_id,
        {
            "type": ThreadType.POST,
            "title": f"HW {hw_num_fmt} Released",
            "category": "Homework",
            "subcategory": f"HW{hw_num_fmt}",
            "subsubcategory": "",
            "content": str(document),
            "is_pinned": True,
            "is_private": False,
            "is_anonymous": False,
            "is_megathread": True,
            "anonymous_comments": True,
        },
    )
    print(f"Posted template for HW{hw_num_fmt}: #{template_result['number']}")
    print(f"https://edstem.org/us/courses/{template_result['course_id']}/discussion/{template_result['id']}")
    summary.append(f"LaTeX Template (#{template_result['number']})")

    # Update summary
    course_id = config.course_id
    hw_dis_post_num = config.index_thread_num
    hw_dis_post = ed.get_course_thread(course_id, hw_dis_post_num)
    hw_dis_post_id = hw_dis_post["id"]

    last_content = hw_dis_post["content"]
    soup, document = parse_content(last_content)
    hw_list = document.find(string=lambda s: s.startswith("Homework Thread")).parent.parent.find("list")

    hw_item = soup.new_tag("list-item")
    hw_item_paragraph = soup.new_tag("paragraph")
    hw_item_paragraph.string = (
        f"Homework {str(int(hw_num_fmt))}: #{template_result['number']}"
    )
    hw_item.append(hw_item_paragraph)
    hw_list.append(hw_item)

    ed.edit_thread(hw_dis_post_id, {"content": str(document)})
    print("Updated Index Thread")

    # unpin old threads
    for row in hw_list.find_all("list-item"):
        res = re.search(r"#\d+", row.text)
        if res is not None:
            old_thread_num = int(res.group()[1:])
            if old_thread_num == template_result["number"]:
                continue
            old_thread = ed.get_course_thread(config.course_id, old_thread_num)
            if old_thread and old_thread.get("is_pinned", False):
                old_thread_id = old_thread["id"]
                ed.edit_thread(old_thread_id, {"is_pinned": False})
                print(f"Unpinned old HW thread: #{old_thread_num}")


def post_dis(ed: EdAPI, config: Config, dis_num: str, is_summer: bool):
    """
    Post discussion thread and update the homework/discussion index.
    """
    assert config.index_thread_num is not None, "Index thread number must be provided."

    dis_num_fmt = int(dis_num)

    # create post body
    template = ed_templates.DIS_TEMPLATE(dis_num_fmt)
    discussion_soup, document = parse_template(template)

    # post thread
    dis_post_result = ed.post_thread(
        config.course_id,
        {
            "type": ThreadType.POST,
            "title": f"Discussion {dis_num_fmt} Thread",
            "category": "Discussion",
            "subcategory": "",
            "subsubcategory": "",
            "content": str(document),
            "is_pinned": True,
            "is_private": False,
            "is_anonymous": False,
            "is_megathread": True,
            "anonymous_comments": True,
        },
    )
    print(f"Posted discussion {dis_num_fmt}: #{dis_post_result['number']}")

    # update summary
    hw_dis_post_num = config.index_thread_num
    hw_dis_post = ed.get_course_thread(config.course_id, hw_dis_post_num)
    hw_dis_post_id = hw_dis_post["id"]

    last_content = hw_dis_post["content"]
    soup, document = parse_content(last_content)
    dis_list = document.find(string="Discussion Threads:", recursive=True).parent.parent.find("list")

    dis_item = soup.new_tag("list-item")
    dis_item_paragraph = soup.new_tag("paragraph")
    dis_item_paragraph.string = (
        f"Discussion {dis_num_fmt}: #{dis_post_result['number']}"
    )
    dis_item.append(dis_item_paragraph)
    dis_list.append(dis_item)

    ed.edit_thread(hw_dis_post_id, {"content": str(document)})
    print("Updated Index Thread")

    # unpin old threads
    for row in dis_list.find_all("list-item"):
        res = re.search(r"#\d+", row.text)
        if res is not None:
            old_thread_num = int(res.group()[1:])
            if old_thread_num == dis_post_result["number"]:
                continue
            old_thread = ed.get_course_thread(config.course_id, old_thread_num)
            if old_thread and old_thread.get("is_pinned", False):
                old_thread_id = old_thread["id"]
                ed.edit_thread(old_thread_id, {"is_pinned": False})
                print(f"Unpinned old discussion thread: #{old_thread_num}")

def post_lec(ed: EdAPI, config: Config, week_num: str):
    """
    Post discussion thread and update the homework/discussion index.
    """
    assert config.index_thread_num is not None, "Index thread number must be provided."

    week_num_fmt = int(week_num)

    # create post body
    # read weeks.yml and get the lec topics for this week
    lecs_path = config.lectures_path

    topics = []
    yaml = YAML()
    with open(lecs_path, "r") as f:
        lecs = yaml.load(f)

    for lec in lecs:
        if int(lec["week"]) == week_num_fmt:
            # skip malformed lectures, holidays, and midterms
            if "title" not in lec:
                continue
            if "holiday" in lec:
                continue
            title = lec["title"]
            if "midterm" in title.lower():
                continue
            if "no lecture" in title.lower():
                continue
            topics.append(title)

    topics_fmt = ", ".join(topics)

    template = ed_templates.LEC_TEMPLATE(topics_fmt)
    lec_soup, document = parse_template(template)

    # post thread
    lec_post_result = ed.post_thread(
        config.course_id,
        {
            "type": ThreadType.POST,
            "title": f"Week {week_num_fmt} Lecture Thread",
            "category": "Lecture",
            "subcategory": "",
            "subsubcategory": "",
            "content": str(document),
            "is_pinned": True,
            "is_private": False,
            "is_anonymous": False,
            "is_megathread": True,
            "anonymous_comments": True,
        },
    )
    print(f"Posted week {week_num_fmt} lec thread: #{lec_post_result['number']}")

    # update summary
    hw_dis_post_num = config.index_thread_num
    hw_dis_post = ed.get_course_thread(config.course_id, hw_dis_post_num)
    hw_dis_post_id = hw_dis_post["id"]

    last_content = hw_dis_post["content"]
    soup, document = parse_content(last_content)
    lec_list = document.find(string="Weekly Lecture Threads:", recursive=True).parent.parent.find("list")

    lec_item = soup.new_tag("list-item")
    lec_item_paragraph = soup.new_tag("paragraph")
    lec_item_paragraph.string = (
        f"Week {week_num} ({topics_fmt}): #{lec_post_result['number']}"
    )
    lec_item.append(lec_item_paragraph)
    lec_list.append(lec_item)

    ed.edit_thread(hw_dis_post_id, {"content": str(document)})
    print("Updated Index Thread")

    # unpin old threads
    for row in lec_list.find_all("list-item"):
        res = re.search(r"#\d+", row.text)
        if res is not None:
            old_thread_num = int(res.group()[1:])
            if old_thread_num == lec_post_result["number"]:
                continue
            old_thread = ed.get_course_thread(config.course_id, old_thread_num)
            if old_thread and old_thread.get("is_pinned", False):
                old_thread_id = old_thread["id"]
                ed.edit_thread(old_thread_id, {"is_pinned": False})
                print(f"Unpinned old lecture thread: #{old_thread_num}")


def post_note(ed: EdAPI, config: Config, note_num: str):
    """
    Post note thread and update the homework/discussion index.
    """
    assert config.index_thread_num is not None, "Index thread number must be provided."

    # create post body
    note_soup, document = new_document()
    note_link_paragraph = note_soup.new_tag("paragraph")
    note_link_paragraph.string = f"Note {note_num}: "

    link_text = f"https://www.eecs70.org/assets/pdf/notes/n{note_num}.pdf"
    note_link = note_soup.new_tag("link", href=link_text)
    note_link.string = link_text

    note_link_paragraph.append(note_link)
    document.append(note_link_paragraph)

    # second paragraph
    note_paragraph = note_soup.new_tag("paragraph")
    note_paragraph.string = (
        f"Please ask any questions you have about note {note_num} here."
    )
    document.append(note_paragraph)

    # post thread
    note_post_result = ed.post_thread(
        config.course_id,
        {
            "type": ThreadType.POST,
            "title": f"Note {note_num} Thread",
            "category": "Notes",
            "subcategory": "",
            "subsubcategory": "",
            "content": str(document),
            "is_pinned": False,
            "is_private": False,
            "is_anonymous": False,
            "is_megathread": True,
            "anonymous_comments": True,
        },
    )
    print(f"Posted note {note_num} thread: #{note_post_result['number']}")

    # update summary
    hw_dis_post_num = config.index_thread_num
    hw_dis_post = ed.get_course_thread(config.course_id, hw_dis_post_num)
    hw_dis_post_id = hw_dis_post["id"]

    last_content = hw_dis_post["content"]
    soup, document = parse_content(last_content)
    # hw list is first, dis list is second, note list is third
    note_list = document.find_all("list", recursive=False)[2]

    note_item = soup.new_tag("list-item")
    note_item_paragraph = soup.new_tag("paragraph")
    note_item_paragraph.string = f"Note {note_num} (#{note_post_result['number']})"
    note_item.append(note_item_paragraph)
    note_list.append(note_item)

    ed.edit_thread(hw_dis_post_id, {"content": str(document)})
    print("Updated Index Thread")


def init_index(ed: EdAPI, config: Config):
    """Initialize the index post, updating the config file with the post number."""
    course_id = config.course_id

    index_soup, document = new_document()

    # Homework section
    homework_title = index_soup.new_tag("heading", level=2)
    homework_title.string = "Homeworks"
    homework_list = index_soup.new_tag("list", style="bullet")
    document.extend([homework_title, homework_list])

    # Discussion section
    discussion_title = index_soup.new_tag("heading", level=2)
    discussion_title.string = "Discussions"
    discussion_list = index_soup.new_tag("list", style="bullet")
    document.extend([discussion_title, discussion_list])

    # Note section
    note_title = index_soup.new_tag("heading", level=2)
    note_title.string = "Notes"
    note_list = index_soup.new_tag("list", style="bullet")
    document.extend([note_title, note_list])

    # create and lock the index thread
    index_thread = ed.post_thread(
        course_id,
        {
            "type": ThreadType.POST,
            "title": "Homework/Discussion/Note Thread",
            "category": "Logistics",
            "subcategory": "",
            "subsubcategory": "",
            "content": str(document),
            "is_pinned": True,
            "is_private": False,
            "is_anonymous": False,
            "is_megathread": True,
            "anonymous_comments": True,
        },
    )
    ed.lock_thread(index_thread["id"])

    index_thread_num = index_thread["number"]
    print(f"Created index thread: #{index_thread_num}")

    # update config json file
    new_config = Config(course_id=config.course_id, index_thread_num=index_thread_num)

    with open("./config.json", "w", encoding="utf-8") as config_file:
        json.dump(new_config.as_json(), config_file, indent=2)
        config_file.write("\n")  # add newline at end of file

    print("Updated config file")


def main(args):
    """
    Main method, delegating to other functions to post threads.
    """

    # read configuration
    with open("./config.json", "r", encoding="utf-8") as config_file:
        config_json = json.load(config_file)
        config = Config.from_json(config_json, args.id_field)

    ed = EdAPI()
    ed.login()

    if args.type == "hw":
        post_hw(ed, config, args.num)
    elif args.type == "dis":
        post_dis(ed, config, args.num, args.summer)
    elif args.type == "note":
        post_note(ed, config, args.num)
    elif args.type == "lec":
        post_lec(ed, config, args.num)
    elif args.type == "exam":
        post_exam(ed, config, args.exam)
    elif args.type == "init-index":
        init_index(ed, config)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--id_field",
        help="If multiple courses, specify which course forum to post to",
        default="draft_course_id",
    )
    subparsers = parser.add_subparsers(dest="type")
    subparsers.required = True

    hw_parser = subparsers.add_parser("hw")
    dis_parser = subparsers.add_parser("dis")
    exam_parser = subparsers.add_parser("exam")
    lec_parser = subparsers.add_parser("lec")
    note_parser = subparsers.add_parser("note")
    init_parser = subparsers.add_parser("init-index")

    # add "num" argument to hw/dis/note parsers
    for p in (hw_parser, dis_parser, note_parser, lec_parser):
        p.add_argument("num", help="HW/discussion/note/week number")

    exam_parser.add_argument("exam", help="Exam name (mt1, mt2, final)")

    # optional summer flag for discussions
    dis_parser.add_argument(
        "--summer",
        action="store_true",
        help="Flag for summer discussions; creates 4 discussion threads instead of 2",
    )

    arguments = parser.parse_args()
    main(arguments)
