"""Narrow original-grounding guards shared by generated document and Wiki claims."""

import re


class QuantityPropertyError(ValueError):
    pass


def check_volume_properties(text, originals):
    """Reject explicit capacity/stored-amount swaps for numeric litre values.

    This narrow guard complements entailment; it does not establish subjects or
    classify all units. Unknown wording still needs semantic review.
    """

    def properties(value):
        found = {}
        previous_quantity_end = 0
        for quantity in re.finditer(
            r"(\d+(?:[.,]\d+)*)\s*(?:litres?|liters?|리터|L)(?![A-Za-z])", value, re.I
        ):
            # A property before one quantity cannot label a later, independently
            # phrased quantity. Unknown phrasing still needs semantic verification.
            prefix = re.split(r"[.!?。\n]", value[previous_quantity_end : quantity.start()])[-1][
                -100:
            ]
            tail = value[quantity.end() :]
            # An explicit noun after the unit labels this value too: "92리터의
            # 용량을 저장" is still a capacity claim, despite its later verb.
            postfix_capacity = re.match(
                r"[ \t]*(?:(?:의|인|짜리|는|가)[ \t]*)?(?:저장[ \t]*)?용량"
                r"|[ \t]*(?:of[ \t]+)?(?:storage[ \t]+)?capacity(?![A-Za-z0-9])",
                tail,
                re.I,
            )
            postfix_stored = re.match(
                r"[ \t]*(?:(?:의|를|가|는)[ \t]*)?(?:저장량|보관량|저장|보관)"
                r"|[ \t]*(?:currently[ \t]+)?stored(?![A-Za-z0-9])",
                tail,
                re.I,
            )
            postfix = postfix_capacity or postfix_stored
            # Do not carry a previous quantity's following property into the
            # next quantity, or borrow a label from the next line.
            previous_quantity_end = quantity.end() + (postfix.end() if postfix else 0)
            anchors = list(
                re.finditer(r"capacity|용량|stores?|stored|storing|저장량|저장|보관", prefix, re.I)
            )
            category = None
            if postfix_capacity:
                category = "capacity"
            elif postfix_stored:
                category = "stored"
            elif anchors:
                category = (
                    "capacity" if re.search(r"capacity|용량", anchors[-1][0], re.I) else "stored"
                )
            if category:
                found.setdefault(quantity[1], set()).add(category)
        return found

    observed = properties("\n".join(originals))
    for value, categories in properties(text).items():
        if value in observed and not categories <= observed[value]:
            raise QuantityPropertyError(
                "A generated claim changes capacity into an amount stored, or vice versa."
            )
