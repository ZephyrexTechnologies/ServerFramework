def to_camel_case(snake_str):
    """Convert a snake_case string to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def pluralize(singular: str) -> str:
    """
    Convert a singular English noun to its plural form following standard English rules.

    Rules implemented:
    1. Words ending in 'y':
       - If preceded by a consonant, change 'y' to 'ies'
       - If preceded by a vowel, add 's'
    2. Words ending in 's', 'sh', 'ch', 'x', 'z': add 'es'
    3. Words ending in 'f' or 'fe': change to 'ves'
    4. Special cases like 'person' -> 'people'
    5. Default: add 's'
    """
    # Special cases dictionary
    special_cases = {
        "person": "people",
        "child": "children",
        "goose": "geese",
        "man": "men",
        "woman": "women",
        "tooth": "teeth",
        "foot": "feet",
        "mouse": "mice",
        "criterion": "criteria",
    }

    # Check for special cases
    if singular.lower() in special_cases:
        return special_cases[singular.lower()]

    # Rule 1: Words ending in 'y'
    if singular.endswith("y"):
        # Check if the letter before 'y' is a consonant
        if singular[-2].lower() not in "aeiou":
            return singular[:-1] + "ies"
        else:
            return singular + "s"

    # Rule 2: Words ending in 's', 'sh', 'ch', 'x', 'z'
    if singular.endswith(("s", "sh", "ch", "x", "z")):
        return singular + "es"

    # Rule 3: Words ending in 'f' or 'fe'
    if singular.endswith("fe"):
        return singular[:-2] + "ves"
    if singular.endswith("f"):
        return singular[:-1] + "ves"

    # Default rule: add 's'
    return singular + "s"


def singularize(plural: str) -> str:
    """
    Convert a plural English noun to its singular form following standard English rules.

    Rules implemented:
    1. Words ending in 'ies':
       - If preceded by a consonant, change 'ies' to 'y'
    2. Words ending in 'es':
       - If the word ends in 'ses', 'shes', 'ches', 'xes', or 'zes', remove 'es'
       - Otherwise, remove 's' (handled by default rule)
    3. Words ending in 'ves': change to 'f' or 'fe' as appropriate
    4. Special cases like 'people' -> 'person'
    5. Default: remove 's'
    """
    # Special cases dictionary (reverse of pluralize special cases)
    special_cases = {
        "people": "person",
        "children": "child",
        "geese": "goose",
        "men": "man",
        "women": "woman",
        "teeth": "tooth",
        "feet": "foot",
        "mice": "mouse",
        "criteria": "criterion",
    }

    # Check for special cases
    if plural.lower() in special_cases:
        return special_cases[plural.lower()]

    # Rule 1: Words ending in 'ies' (reverse of 'y' -> 'ies' rule)
    if plural.endswith("ies"):
        return plural[:-3] + "y"

    # Rule 3: Words ending in 'ves' (reverse of 'f/fe' -> 'ves' rule)
    if plural.endswith("ves"):
        # Check common words that end in 'fe' in singular form
        fe_endings = ["wife", "knife", "life", "shelf"]
        stem = plural[:-3]
        for word in fe_endings:
            if stem == word[:-2]:
                return stem + "fe"
        # Default 'f' ending
        return stem + "f"

    # Rule 2: Words ending in 'es' (reverse of 's/sh/ch/x/z' + 'es' rule)
    if plural.endswith("es"):
        # Check if the stem ends in 's', 'sh', 'ch', 'x', or 'z'
        stem = plural[:-2]
        if stem.endswith(("s", "sh", "ch", "x", "z")):
            return stem
        # Otherwise, treat it as the default case (just remove 's')
        return stem

    # Default rule: remove 's' if the word ends with 's'
    if plural.endswith("s") and len(plural) > 1:
        return plural[:-1]

    # If no rule applies, return the word unchanged
    # (it might already be in singular form)
    return plural
