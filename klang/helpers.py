from enum import Enum
from typing import Type, TypeVar, Dict

TEnum = TypeVar("TEnum", bound=Enum)


def clamp(number: float, min_value: float, max_value: float) -> float:
    return min(max(number, min_value), max_value)


def next_enum_map(enum_class: Type[TEnum]) -> Dict[TEnum, TEnum]:
    variants = list(enum_class)
    result = {}
    for i, variant in enumerate(variants):
        if i == len(variants) - 1:
            break
        result[variant] = variants[i + 1]

    return result
