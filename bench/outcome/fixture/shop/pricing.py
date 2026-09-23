"""Order pricing. Deliberately carries small, real defects for the outcome pilot."""

TAX = 0.07


def line_total(unit_price, quantity):
    return unit_price * quantity


def order_total(lines, discount=0.0):
    total = sum(line_total(u, q) for u, q in lines)
    return total * (1 - discount) * (1 + TAX)


def apply_promo(total, code, table):
    return total - table[code]
