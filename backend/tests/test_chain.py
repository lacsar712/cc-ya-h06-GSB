"""全链路判定测试：库结论 → /api/logs 列表标色依据 → 详情说明原样透传。"""

import asyncio

import pytest

import api as api_mod
from rules import THRESHOLD_DEG, judge


def run(coro):
    return asyncio.run(coro)


# ---- 库结论：压线合格，正负双向超差不漂移 ----

def test_zero_and_seed_values():
    assert judge(0.0) == ("合格", "偏航误差 0.0° 在 ±1.5° 以内")
    assert judge(0.4)[0] == "合格"
    assert judge(3.2)[0] == "偏航超差"


def test_boundary_inclusive_both_sides():
    # ±1.5° 压线必须判合格（<=，而非 <）
    v_pos, r_pos = judge(THRESHOLD_DEG)
    v_neg, r_neg = judge(-THRESHOLD_DEG)
    assert v_pos == "合格" and v_neg == "合格"
    assert "在 ±1.5° 以内" in r_pos and "在 ±1.5° 以内" in r_neg


def test_obvious_overrun_both_directions():
    for err in (1.6, -1.6, 3.2, -3.2):
        verdict, reason = judge(err)
        assert verdict == "偏航超差", err
        assert reason == f"偏航误差 {err}° 超过 ±1.5°"


def test_just_outside_boundary_flips():
    assert judge(THRESHOLD_DEG + 1e-9)[0] == "偏航超差"
    assert judge(-THRESHOLD_DEG - 1e-9)[0] == "偏航超差"


# ---- 接口层：库中的 verdict/reason 原样到达列表与详情 ----

FAKE_ROWS = [
    {
        "id": 2,
        "turbine_code": "W07",
        "yaw_err_deg": 3.2,
        "status": "done",
        "verdict": "偏航超差",
        "reason": "偏航误差 3.2° 超过 ±1.5°",
        "created_by": "technician",
        "created_at": "2026-10-05T00:00:00+00:00",
        "processed_at": "2026-10-05T00:00:01+00:00",
    },
    {
        "id": 1,
        "turbine_code": "W01",
        "yaw_err_deg": 0.4,
        "status": "done",
        "verdict": "合格",
        "reason": "偏航误差 0.4° 在 ±1.5° 以内",
        "created_by": "technician",
        "created_at": "2026-10-05T00:00:00+00:00",
        "processed_at": "2026-10-05T00:00:01+00:00",
    },
]


@pytest.fixture
def fake_db(monkeypatch):
    async def fake_run_db(fn, *args, **kwargs):
        return FAKE_ROWS

    monkeypatch.setattr(api_mod, "run_db", fake_run_db)


def _login(username, password):
    async def go():
        client = api_mod.app.test_client()
        res = await client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        assert res.status_code == 200
        return (await res.get_json())["access_token"]

    return run(go())


def test_list_passes_verdict_and_reason_through(fake_db):
    token = _login("technician", "tech123456")

    async def go():
        client = api_mod.app.test_client()
        res = await client.get(
            "/api/logs", headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        return await res.get_json()

    rows = run(go())
    by_id = {r["id"]: r for r in rows}

    # 库里合格的行，列表结论与详情说明都不得被改写
    assert by_id[1]["verdict"] == "合格"
    assert by_id[1]["reason"] == "偏航误差 0.4° 在 ±1.5° 以内"
    # 明显超差方向同样不得漂移
    assert by_id[2]["verdict"] == "偏航超差"
    assert by_id[2]["reason"] == "偏航误差 3.2° 超过 ±1.5°"


def test_list_requires_login(fake_db):
    async def go():
        client = api_mod.app.test_client()
        return await client.get("/api/logs")

    assert run(go()).status_code == 401


def test_observer_cannot_submit():
    token = _login("observer", "obs123456")

    async def go():
        client = api_mod.app.test_client()
        return await client.post(
            "/api/logs",
            headers={"Authorization": f"Bearer {token}"},
            json={"turbine_code": "W99", "yaw_err_deg": 0.1},
        )

    assert run(go()).status_code == 403
