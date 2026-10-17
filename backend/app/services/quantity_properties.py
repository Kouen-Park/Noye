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
            previous_quantity_end = quantity.end()
            anchors = list(
                re.finditer(r"capacity|용량|stores?|stored|storing|저장량|저장|보관", prefix, re.I)
            )
            category = None
            if anchors:
                category = (
                    "capacity" if re.search(r"capacity|용량", anchors[-1][0], re.I) else "stored"
                )
            elif re.match(r"\s*(?:를|가)?\s*(?:저장|보관)", value[quantity.end() :]):
                category = "stored"
            if category:
                found.setdefault(quantity[1], set()).add(category)
        return found

    observed = properties("\n".join(originals))
    for value, categories in properties(text).items():
        if value in observed and not categories <= observed[value]:
            raise QuantityPropertyError(
                "A generated claim changes capacity into an amount stored, or vice versa."
            )
