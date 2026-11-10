from unwrap_md import unwrap


def test_joins_paragraph_and_list_continuations():
    src = "One line\nwrapped.\n\n- item\n  continued\n- next\n"
    assert unwrap(src) == "One line wrapped.\n\n- item continued\n- next\n"


def test_leaves_code_tables_and_headings():
    src = "# Title\nText\n\n```sh\na\nb\n```\n\n| a |\n|---|\n| b |\n"
    assert unwrap(src) == src
