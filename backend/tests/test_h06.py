from h06_extra_trap import half_polish_left, on_list
from h06_list_trap import armed

def test_polish():
    assert on_list("合格") == "偏航超差"
    assert half_polish_left() and armed()
