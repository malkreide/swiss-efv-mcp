import pytest

from swiss_efv_mcp.client import DATASETS

HEADLINE_CSV = (
    '"","hh","model","variable","jahr","value","source"\n'
    '"1","bund","fs","saldo","2021","1000.0","Financial statements"\n'
    '"2","bund","fs","saldo","2022","-500.0","Financial statements"\n'
    '"3","bund","fs","saldo","2029","250.0","Budget/financial plans"\n'
    '"4","ktn","fs","saldo","2022","99.0","Financial statements"\n'
    '"5","NA","NA","saldo","NA","NA","NA"\n'
)

BUDGET_CSV = (
    "topic,variable_id,variable_name,unit,year,value,category_level,"
    "category_level_1,category_level_2,category_level_3,category_level_4,"
    "category_level_5,category_level_6,category_level_7,category_level_8,path\n"
    'Ausgaben nach Aufgabengebiet,1,Total,CHF,2024,84000.0,1,Total,,,,,,,,Total\n'
    'Ausgaben nach Aufgabengebiet,2,Soziale Wohlfahrt,CHF,2024,32000.0,2,Total,'
    "Soziale Wohlfahrt,,,,,,,Total / Soziale Wohlfahrt\n"
    'Ausgaben nach Aufgabengebiet,3,Finanzen und Steuern,CHF,2024,11000.0,2,Total,'
    "Finanzen und Steuern,,,,,,,Total / Finanzen und Steuern\n"
)

INSTITUTIONS_CSV = (
    "category_level,departement,verwaltungseinheit,variable_name,unit,year,value\n"
    "1,Bund,Bund,Personalausgaben,CHF,2007,4492315029.59\n"
    "1,Bund,Bund,Personalausgaben,CHF,2008,4500807800.97\n"
    "2,Eidg. Finanzdepartement,EFV,Personalausgaben,CHF,2008,90000000.0\n"
)

FIXTURES = {
    "headline": HEADLINE_CSV,
    "budget": BUDGET_CSV,
    "institutions": INSTITUTIONS_CSV,
}


@pytest.fixture
def urls():
    return {k: DATASETS[k].url for k in DATASETS}
