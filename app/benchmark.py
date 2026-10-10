from app.models import TicketCase


def load_cases():
    return [
        TicketCase(case_id="D01", ticket="I forgot my password and cannot sign in.",
                   expected_action="reset_password", split="development"),
        TicketCase(case_id="D02", ticket="Can you tell me whether my refund has been processed?",
                   expected_action="refund_status", split="development"),
        TicketCase(case_id="D03", ticket="I was charged twice. A human needs to investigate.",
                   expected_action="escalate", split="development"),
        TicketCase(case_id="D04", ticket="Please help me regain access to my account.",
                   expected_action="reset_password", split="development"),
        TicketCase(case_id="D05", ticket="My money has not come back after the cancellation.",
                   expected_action="refund_status", split="development"),
        TicketCase(case_id="D06", ticket="This is a duplicate payment and I need assistance.",
                   expected_action="escalate", split="development"),
        TicketCase(case_id="D07", ticket="I cannot log in because I lost my password.",
                   expected_action="reset_password", expected_verified=True, split="development"),
        TicketCase(case_id="D08", ticket="Check the status of my money back request.",
                   expected_action="refund_status", expected_verified=True, split="development"),
        TicketCase(case_id="D09", ticket="I see two charges for the same order.",
                   expected_action="escalate", split="development"),
        TicketCase(case_id="D10", ticket="Reset my credentials so I can access the account.",
                   expected_action="reset_password", split="development"),
        TicketCase(case_id="H01", ticket="I am locked out and cannot get into my account.",
                   expected_action="reset_password", split="held_out"),
        TicketCase(case_id="H02", ticket="Has the refund for my returned order arrived?",
                   expected_action="refund_status", split="held_out"),
        TicketCase(case_id="H03", ticket="My statement shows the same purchase twice.",
                   expected_action="escalate", split="held_out"),
        TicketCase(case_id="H04", ticket="The money from my return has not arrived.",
                   expected_action="refund_status", expected_verified=True, split="held_out"),
        TicketCase(case_id="H05", ticket="Please investigate a duplicate charge on my card.",
                   expected_action="escalate", split="held_out"),
        TicketCase(case_id="H06", ticket="I can't remember the password for my account.",
                   expected_action="reset_password", split="held_out"),
    ]


def cases_for_split(split: str):
    return [case for case in load_cases() if case.split == split]
