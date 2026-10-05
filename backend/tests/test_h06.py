"""链路回归：库结论 → 列表透出 → 详情说明必须同源一致。

- 压线（|误差| == 1.5°）判合格，明显超差判偏航超差，正负双向不漂。
- 列表接口原样透出库里的 verdict/reason，不得粉饰、不留半截。
- 观察员只读禁写。
"""

import asyncio
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jose import jwt

import api
from rules import judge

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _token(username: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"sub": username, "role": role, "exp": exp},
        api.SECRET,
        algorithm="HS256",
    )


def test_judge_boundary_both_directions():
    # 压线：恰好 ±1.5° 双向都判合格
    for err in (1.5, -1.5):
        verdict, reason = judge(err)
        assert verdict == "合格"
        assert "以内" in reason
    # 明显超差：正负双向都判偏航超差
    for err in (1.5001, -1.5001, 3.2, -3.2):
        verdict, reason = judge(err)
        assert verdict == "偏航超差"
        assert "超过" in reason
    # 阈值内普通值
    assert judge(0.4)[0] == "合格"
    assert judge(-0.4)[0] == "合格"


SAMPLE_ROWS = [
    {
        "id": 2,
        "turbine_code": "W07",
        "yaw_err_deg": 3.2,
        "status": "done",
        "verdict": "偏航超差",
        "reason": "偏航误差 3.2° 超过 ±1.5°",
        "created_by": "technician",
        "created_at": "2026-10-01T00:00:00+00:00",
        "processed_at": "2026-10-01T00:00:01+00:00",
    },
    {
        "id": 1,
        "turbine_code": "W01",
        "yaw_err_deg": 0.4,
        "status": "done",
        "verdict": "合格",
        "reason": "偏航误差 0.4° 在 ±1.5° 以内",
        "created_by": "technician",
        "created_at": "2026-10-01T00:00:00+00:00",
        "processed_at": "2026-10-01T00:00:01+00:00",
    },
]


def test_list_returns_db_verdict_and_reason_verbatim(monkeypatch):
    async def fake_run_db(fn, *args, **kwargs):
        return [dict(r) for r in SAMPLE_ROWS]

    monkeypatch.setattr(api, "run_db", fake_run_db)

    async def main():
        client = api.app.test_client()
        res = await client.get(
            "/api/logs",
            headers={"Authorization": f"Bearer {_token('observer', 'reader')}"},
        )
        assert res.status_code == 200
        return await res.get_json()

    data = asyncio.run(main())
    by_code = {row["turbine_code"]: row for row in data}
    # 库结论原样透出：合格不被粉饰成超差，超差不回漂成合格
    assert by_code["W01"]["verdict"] == "合格"
    assert by_code["W01"]["reason"] == "偏航误差 0.4° 在 ±1.5° 以内"
    assert by_code["W07"]["verdict"] == "偏航超差"
    assert by_code["W07"]["reason"] == "偏航误差 3.2° 超过 ±1.5°"
    # 不留半截：结论与说明同源一致
    for row in data:
        if row["verdict"] == "合格":
            assert "超差" not in row["reason"]
        else:
            assert "超过" in row["reason"]


def test_observer_read_only_cannot_write(monkeypatch):
    calls = []

    async def spy_run_db(fn, *args, **kwargs):
        calls.append(fn)
        return [dict(r) for r in SAMPLE_ROWS]

    monkeypatch.setattr(api, "run_db", spy_run_db)

    async def main():
        client = api.app.test_client()
        headers = {"Authorization": f"Bearer {_token('observer', 'reader')}"}
        get_res = await client.get("/api/logs", headers=headers)
        post_res = await client.post(
            "/api/logs",
            headers=headers,
            json={"turbine_code": "W99", "yaw_err_deg": 0.1},
        )
        return get_res.status_code, post_res.status_code

    get_status, post_status = asyncio.run(main())
    assert get_status == 200  # 观察员可读
    assert post_status == 403  # 观察员禁写
    assert len(calls) == 1  # 只有 GET 触达数据库，POST 被拦截在写库之前


@pytest.mark.parametrize("mod", ["h06_list_trap", "h06_extra_trap", "pass_polish"])
def test_polish_modules_removed(mod):
    # 粉饰链路整体拆除，不留半截
    assert not (BACKEND_DIR / f"{mod}.py").exists()
    assert importlib.util.find_spec(mod) is None
