"""Formatting for the daily report."""


def percent(part, whole):
    return "%.1f%%" % (100.0 * part / whole)


def money(amount):
    return "$%0.2f" % amount
