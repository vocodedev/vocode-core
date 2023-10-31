import pytest
from vocode.streaming.utils.values_to_words import number_to_tts


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, "nula"),
        (5, "pět"),
        (11, "jedenáct"),
        (19, "devatenáct"),
        (20, "dvacet"),
        (31, "třicet jedna"),
        (42, "čtyřicet dva"),
        (53, "padesát tři"),
        (64, "šedesát čtyři"),
        (75, "sedmdesát pět"),
        (86, "osmdesát šest"),
        (97, "devadesát sedm"),
        (100, "sto"),
        (101, "sto jedna"),
        (121, "sto dvacet jedna"),
        (666, "šest set šedesát šest"),
        (1000, "tisíc"),
        (2004, "dva tisíce čtyři"),
        (3015, "tři tisíce patnáct"),
        (4406, "čtyři tisíce čtyři sta šest"),
        (5517, "pět tisíc pět set sedmnáct"),
        (6628, "šest tisíc šest set dvacet osm"),
        (10000, "deset tisíc"),
        (20002, "dvacet tisíc dva"),
        (30090, "třicet tisíc devadesát"),
        (40700, "čtyřicet tisíc sedm set"),
        (50809, "padesát tisíc osm set devět"),
        (65432, "šedesát pět tisíc čtyři sta třicet dva"),
        (100000, "sto tisíc"),
        (654321, "šest set padesát čtyři tisíc tři sta dvacet jedna"),
        (1000000, "milión"),
        (1000001, "milión jedna"),
        (1000002, "milión dva"),
        (1010101, "milión deset tisíc sto jedna"),
        (2101010, "dva milióny sto jedna tisíc deset"),
        (1000000000, "miliarda"),
        (6942903410, "šest miliard devět set čtyřicet dva miliónů devět set tři tisíc čtyři sta deset"),
    ]
)
def test_number_to_tts(value, expected):
    assert number_to_tts(value) == expected
