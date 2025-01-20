class Link:
    def __init__(self, text, href):
        self.text = text
        self.href = href

class H2:
    def __init__(self, text):
        self.text = text

EXAM_MEGATHREAD_TEMPLATE = lambda exam: [
    f"Please find past {exam} threads here.",
    "When posting questions, please do us a favor and post which question you are asking for help with. Also ask your question in the format (q2bii) to help staff and other students filter for posts.",
    H2("Alternate Solutions Policy"),
    "When checking the validity of an alternate solution, please check other threads first, then write a well defined proof of correctness demonstrating why you believe your alternate works. All other threads will not be considered due to staff bandwidth, and we cannot guarantee that we will be able to respond to alternative approaches. We encourage students to discuss alternate solutions together, since it helps understand both the intended reasoning and variations.",
]
SINGLE_EXAM_TEMPLATE = lambda sem, exam: [
    f"Please ask questions about the {sem} {exam} here.",
    "When posting questions, please do us a favor and post which question you are asking for help with. Also ask your question in the format (q2bii) to help staff and other students filter for posts.",
    H2("Alternate Solutions Policy:"),
    "When checking the validity of an alternate solution, please check other threads first, then write a well defined proof of correctness demonstrating why you believe your alternate works. All other threads will not be considered due to staff bandwidth, and we cannot guarantee that we will be able to respond to alternative approaches. We encourage students to discuss alternate solutions together, since it helps understand both the intended reasoning and variations.",
]

HW_TEMPLATE = lambda num, duedate: [
    "Hi all,",
    [
        f"Homework {num} has been posted to the ",
        Link(
            "course website",
            f"https://cs170.org/assets/pdf/hw{num}.pdf",
        ),
        f". It is due on Friday ({duedate}) at 10:00pm, with a grace period until 11:59pm.",
    ],
    "Any general questions about the homework should be posted in this thread, and questions about specific problems should be posted under the individual threads:",
]

DIS_TEMPLATE = lambda num: [
    [
        f"You can find the discussion {num} worksheet on the ",
        Link("course website", f"https://cs170.org/assets/pdf/dis{num:02d}.pdf"),
        ". Please post any questions you have about it in the thread below!",
    ],
]

LEC_TEMPLATE = lambda lecs: [
    [
        f"Good afternoon everyone! Post any questions you have about this week's lectures ({lecs}) below.",
    ],
]