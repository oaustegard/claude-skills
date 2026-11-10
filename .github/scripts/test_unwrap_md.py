from unwrap_md import unwrap


def test_joins_paragraph_and_list_continuations():
    src = "One line\nwrapped.\n\n- item\n  continued\n- next\n"
    assert unwrap(src) == "One line wrapped.\n\n- item continued\n- next\n"


def test_leaves_code_tables_and_headings():
    src = "# Title\nText\n\n```sh\na\nb\n```\n\n| a |\n|---|\n| b |\n"
    assert unwrap(src) == src


def test_wrapped_number_stays_in_paragraph():
    src = "fails entries 53 to\n56. A flagged shape\n\n1. one\n2. two\n"
    assert unwrap(src) == "fails entries 53 to 56. A flagged shape\n\n1. one\n2. two\n"
