import pytest

from app.services.category_service import CategoryCatalog, get_catalog
from app.services.routing_service import RoutingService, get_routing_service


@pytest.mark.parametrize("category,department", [
    ("Academic", "Academic Department"), ("Results / Marks", "Examination Department"),
    ("Examination", "Examination Department"), ("Fees / Finance", "Accounts Department"),
    ("Admission", "Admissions Department"), ("Attendance", "Academic Administration"),
    ("Transport", "Transport Department"), ("IT / Portal / LMS", "IT Department"),
    ("Library", "Library Department"), ("Facilities / Maintenance", "Administration / Maintenance"),
    ("Security", "Security / Student Affairs"), ("Hostel", "Hostel Administration"),
    ("Harassment / Bullying", "Student Affairs / Designated Safeguarding Officer"),
    ("Discrimination", "Student Affairs / Administration"),
    ("Health / Safety", "Administration / Health & Safety Officer"),
])
def test_default_routing(category, department):
    assert get_routing_service().route(category).department == department


def test_subcategory_override_and_reason():
    d = get_routing_service().route("Academic", "Assessment Marks")
    assert d.department == "Examination Department" and "Examination Department" in d.reason


def test_every_category_routes_to_a_known_department():
    routing, catalog = get_routing_service(), get_catalog()
    assert len(catalog.names) == 20
    for name in catalog.names:
        assert routing.route(name).department in routing.department_names


def test_routing_is_configurable_without_code_changes():
    custom = RoutingService(routing={"default_department": "Front Desk", "category_to_department": {"Library": "Front Desk"}},
                            departments={"departments": [{"name": "Front Desk"}]})
    assert custom.route("Library").department == "Front Desk"
    assert custom.route("Unknown").department == "Front Desk"


def test_categories_are_configurable():
    cat = CategoryCatalog({"categories": [{"name": "Sports", "keywords": ["cricket"], "subcategories": {"Nets": ["net*"]}},
                                          {"name": "Other", "keywords": []}]})
    assert cat.rank("cricket nets are broken")[0][0] == "Sports"
    assert cat.best_subcategory("Sports", "the nets") == "Nets"
    assert cat.normalize("sports") == "Sports" and cat.normalize("nonsense") is None
