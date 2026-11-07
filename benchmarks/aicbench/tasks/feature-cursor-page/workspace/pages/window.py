def window(items, page_number, size):
    if type(page_number) is not int or type(size) is not int or page_number < 1 or size < 1:
        raise ValueError("page")
    start = (page_number - 1) * size
    return list(items[start:start + size])
