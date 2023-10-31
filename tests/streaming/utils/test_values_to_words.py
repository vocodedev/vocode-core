from typing import List

import pytest

from vocode.streaming.utils.values_to_words import (
    ValueToConvert,
    float_to_words,
    integer_to_words,
    find_values_to_rewrite
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("0", "nula"),
        ("5", "pět"),
        ("11", "jedenáct"),
        ("19", "devatenáct"),
        ("20", "dvacet"),
        ("31", "třicet jedna"),
        ("42", "čtyřicet dva"),
        ("53", "padesát tři"),
        ("64", "šedesát čtyři"),
        ("75", "sedmdesát pět"),
        ("86", "osmdesát šest"),
        ("97", "devadesát sedm"),
        ("100", "sto"),
        ("101", "sto jedna"),
        ("121", "sto dvacet jedna"),
        ("666", "šest set šedesát šest"),
        ("1000", "tisíc"),
        ("2004", "dva tisíce čtyři"),
        ("3015", "tři tisíce patnáct"),
        ("4406", "čtyři tisíce čtyři sta šest"),
        ("5517", "pět tisíc pět set sedmnáct"),
        ("6628", "šest tisíc šest set dvacet osm"),
        ("10000", "deset tisíc"),
        ("20002", "dvacet tisíc dva"),
        ("30090", "třicet tisíc devadesát"),
        ("40700", "čtyřicet tisíc sedm set"),
        ("50809", "padesát tisíc osm set devět"),
        ("65432", "šedesát pět tisíc čtyři sta třicet dva"),
        ("100000", "sto tisíc"),
        ("654321", "šest set padesát čtyři tisíc tři sta dvacet jedna"),
        ("1000000", "milión"),
        ("1000001", "milión jedna"),
        ("1000002", "milión dva"),
        ("1010101", "milión deset tisíc sto jedna"),
        ("2101010", "dva milióny sto jedna tisíc deset"),
        ("1000000000", "miliarda"),
        ("6942903410", "šest miliard devět set čtyřicet dva miliónů devět set tři tisíc čtyři sta deset"),
    ]
)
def test_integer_to_words(value, expected):
    assert integer_to_words(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("0.0", "nula"),
        ("0.01", "nula celá nula jedna"),
        ("0.023", "nula celá nula dva tři"),
        ("2.0", "dva"),
        ("1.6", "jedna celá šest"),
        ("3.14", "tři celá čtrnáct"),
        ("99.999", "devadesát devět celá devět set devadesát devět"),
    ]
)
def test_float_to_words(value, expected):
    assert float_to_words(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (
            "Takže počítám s vámi 2023-10-31 v 10:15 u nás na pobočce.",
            [
                ValueToConvert(
                    value="2023-10-31",
                    position=(21, 31),
                    value_type="date",
                    tts_value="v úterý třicátého prvního října",
                ),
                ValueToConvert(
                    value="10:15",
                    position=(34, 39),
                    value_type="time",
                    tts_value="v deset patnáct dopoledne",
                ),
            ],
        ),
        (
            "Říkáte 2000.",
            [
                ValueToConvert(
                    value="2000.",
                    position=(7, 12),
                    value_type="integer",
                    tts_value="dva tisíce",
                ),
            ],
        ),
        (
            "Rozumím, takže za váš Peugeot 5008 by jste chtěla 150 000 korun, je to tak?",
            [
                ValueToConvert(
                    value="5008 ",
                    position=(30, 35),
                    value_type="integer",
                    tts_value="pět tisíc osm ",
                ),
                ValueToConvert(
                    value="150 000 ",
                    position=(50, 58),
                    value_type="integer",
                    tts_value="sto padesát tisíc ",
                ),
            ],
        ),
        (
            "Takže je to 1.6 TDI.",
            [
                ValueToConvert(
                    value="1.6 ",
                    position=(12, 16),
                    value_type="float",
                    tts_value="jedna celá šest ",
                ),
            ],
        ),
        (
            "Takže je to 1.6.",
            [
                ValueToConvert(
                    value="1.6.",
                    position=(12, 16),
                    value_type="float",
                    tts_value="jedna celá šest",
                ),
            ],
        ),
        (
            "Má to výkon kolem 80  kW. Ale možná je to 90   kw.",
            [
                ValueToConvert(
                    value="80 ",
                    position=(18, 21),
                    value_type="integer",
                    tts_value="osmdesát ",
                ),
                ValueToConvert(
                    value="90 ",
                    position=(42, 45),
                    value_type="integer",
                    tts_value="devadesát ",
                ),
                ValueToConvert(
                    value="kW",
                    position=(22, 24),
                    value_type="power",
                    tts_value=" kilowattů",
                ),
                ValueToConvert(
                    value="kw",
                    position=(47, 49),
                    value_type="power",
                    tts_value=" kilowattů",
                ),
            ]
        ),
        (
            "Dnes vám dáme slevu až 10%.",
            [
                ValueToConvert(
                    value="10",
                    position=(23, 25),
                    value_type="integer",
                    tts_value="deset",
                ),
                ValueToConvert(
                    value="%",
                    position=(25, 26),
                    value_type="percent",
                    tts_value=" procent",
                ),
            ]
        ),
    ]
)
def test_find_values_to_rewrite(value: str, expected: List[str]):
    assert find_values_to_rewrite(value) == expected
