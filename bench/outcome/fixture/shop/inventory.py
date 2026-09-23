"""Stock movements."""


def reserve(stock, sku, quantity):
    stock[sku] = stock[sku] - quantity
    return stock[sku]


def release(stock, sku, quantity):
    stock[sku] = stock.get(sku, 0) + quantity
    return stock[sku]
