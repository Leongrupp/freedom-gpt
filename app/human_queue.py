"""Presentation of human-authored inputs, using native controls and local admission receipts."""


def human_input(row, known=()):
    # Controls are issued by the native owner only after checking human provenance.
    # Never classify from message text: a human may paste a process notice as a question.
    return (row.get('admission_id') in known or
            bool(set(row.get('controls') or ()) & {'steer', 'replace'}))


def visible_queue(rows, known=()):
    return [row for row in rows if human_input(row, known)]
