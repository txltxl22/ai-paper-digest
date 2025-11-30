import json
from datetime import datetime

import pytest


def setup_app_dirs(sp, tmp_path):
    sp.USER_DATA_DIR = tmp_path / "user_data"
    sp.SUMMARY_DIR = tmp_path / "summary"
    sp.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    sp.SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    
    # Update the existing modules with test paths
    sp.user_management_module["service"].user_data_dir = sp.USER_DATA_DIR
    sp.user_management_module["service"].admin_user_ids = ["admin1", "admin2"]
    
    sp.index_page_module["scanner"].summary_dir = sp.SUMMARY_DIR
    sp.index_page_module["renderer"].summary_dir = sp.SUMMARY_DIR
    
    sp.summary_detail_module["loader"].summary_dir = sp.SUMMARY_DIR


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import app.main as sp

    setup_app_dirs(sp, tmp_path)
    sp.app.config.update(TESTING=True)
    return sp.app.test_client()


def read_user_json(sp, uid):
    p = sp.USER_DATA_DIR / f"{uid}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def test_mark_read_saves_local_datetime_with_tz_and_counts_today(tmp_path, monkeypatch):
    import app.main as sp

    setup_app_dirs(sp, tmp_path)
    sp.app.config.update(TESTING=True)
    client = sp.app.test_client()

    uid = "u1"
    client.set_cookie("uid", uid)

    # mark read for an id
    rid = "2500.00001"
    res = client.post(f"/mark_read/{rid}")
    assert res.status_code == 200

    # verify user data read record
    data = read_user_json(sp, uid)
    assert "read" in data and rid in data["read"]
    ts = data["read"][rid]
    assert isinstance(ts, str) and "T" in ts
    # has timezone offset +HH:MM or -HH:MM
    assert ("+" in ts or "-" in ts[10:]) and ts[-3] == ":"

    # index should show today's count = 1 even with no entries
    res2 = client.get("/")
    assert res2.status_code == 200
    html = res2.data.decode("utf-8")
    assert "今日" in html
    assert ">1<" in html  # the strong tag shows 1 somewhere


def test_event_ingest_filters_non_clicks_and_converts_timezone(tmp_path, monkeypatch):
    import app.main as sp

    setup_app_dirs(sp, tmp_path)
    sp.app.config.update(TESTING=True)
    client = sp.app.test_client()
    uid = "u2"
    client.set_cookie("uid", uid)

    # non-click event should be ignored
    res = client.post("/event", json={"type": "page_view", "meta": {"page": "index"}})
    assert res.status_code == 200
    data = read_user_json(sp, uid)
    assert data.get("events", []) == []

    # click event open_pdf with client ts and tz offset
    client_ts = "2025-01-02T03:04:05Z"  # UTC
    tz_offset_min = -480  # UTC - local; for UTC+8 locales (e.g., Asia/Shanghai)
    res2 = client.post(
        "/event",
        json={
            "type": "open_pdf",
            "arxiv_id": "2500.00002",
            "meta": {"href": "https://arxiv.org/pdf/2500.00002.pdf"},
            "ts": client_ts,
            "tz_offset_min": tz_offset_min,
        },
    )
    assert res2.status_code == 200
    data = read_user_json(sp, uid)
    evts = data.get("events", [])
    assert len(evts) == 1
    evt = evts[0]
    assert evt["type"] == "open_pdf" and evt["arxiv_id"] == "2500.00002"
    # ts should be converted to local time with +08:00 offset
    ts_str = evt["ts"]
    # parse-able and expected local time
    dt = datetime.fromisoformat(ts_str)
    assert dt.isoformat(timespec="seconds").endswith("+08:00")
    # 03:04:05Z -> 11:04:05+08:00
    assert dt.hour == 11 and dt.minute == 4 and dt.second == 5


def test_event_ingest_allows_only_click_types(tmp_path, monkeypatch):
    import app.main as sp

    setup_app_dirs(sp, tmp_path)
    sp.app.config.update(TESTING=True)
    client = sp.app.test_client()
    uid = "u3"
    client.set_cookie("uid", uid)

    allowed = ["mark_read", "unmark_read", "open_pdf", "login", "logout", "reset", "read_list", "read_more"]
    for t in allowed:
        res = client.post("/event", json={"type": t, "ts": "2025-01-01T00:00:00Z"})
        assert res.status_code == 200

    # unknown event should not be recorded
    res2 = client.post("/event", json={"type": "foo", "ts": "2025-01-01T00:00:00Z"})
    assert res2.status_code == 200

    data = read_user_json(sp, uid)
    ev_types = [e["type"] for e in data.get("events", [])]
    for t in allowed:
        assert t in ev_types
    assert "foo" not in ev_types


def test_index_renders_tags_and_filters(tmp_path, monkeypatch):
    import app.main as sp

    setup_app_dirs(sp, tmp_path)
    sp.app.config.update(TESTING=True)
    client = sp.app.test_client()

    # create two summaries with tags in new service record format
    from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
    from summary_service.record_manager import save_summary_with_service_record
    
    s1_summary = StructuredSummary(
        paper_info=PaperInfo(title_zh="s1", title_en="s1", abstract="Test"),
        one_sentence_summary="content",
        innovations=[],
        results=Results(experimental_highlights=[], practical_value=[]),
        terminology=[]
    )
    s1_tags = Tags(top=["llm"], tags=["llm", "agents"])
    save_summary_with_service_record(
        arxiv_id="2506.11111",
        summary_content=s1_summary,
        tags=s1_tags,
        summary_dir=sp.SUMMARY_DIR,
        source_type="system"
    )

    s2_summary = StructuredSummary(
        paper_info=PaperInfo(title_zh="s2", title_en="s2", abstract="Test"),
        one_sentence_summary="content",
        innovations=[],
        results=Results(experimental_highlights=[], practical_value=[]),
        terminology=[]
    )
    s2_tags = Tags(top=["vision"], tags=["vision", "agents"])
    save_summary_with_service_record(
        arxiv_id="2506.22222",
        summary_content=s2_summary,
        tags=s2_tags,
        summary_dir=sp.SUMMARY_DIR,
        source_type="system"
    )

    # index should show tag chips and tag cloud
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "llm" in html and "agents" in html and "vision" in html

    # filter by tag
    res2 = client.get("/?tag=agents")
    html2 = res2.data.decode("utf-8")
    assert "2506.11111" in html2 and "2506.22222" in html2

    res3 = client.get("/?tag=llm")
    html3 = res3.data.decode("utf-8")
    assert "2506.11111" in html3 and "2506.22222" not in html3

    # detail page should render tag chips
    res4 = client.get("/summary/2506.11111")
    assert res4.status_code == 200
    html4 = res4.data.decode("utf-8")
    assert "llm" in html4 and "agents" in html4


def test_tag_cloud_built_from_all_entries(tmp_path, monkeypatch):
    """Test that tag clouds are built from all entries, not filtered ones (bug fix)."""
    import app.main as sp

    setup_app_dirs(sp, tmp_path)
    sp.app.config.update(TESTING=True)
    client = sp.app.test_client()

    # Create multiple summaries with different tags
    from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
    from summary_service.record_manager import save_summary_with_service_record
    
    summaries_data = [
        {
            "id": "2506.11111",
            "top": ["llm"],
            "tags": ["machine learning", "nlp"]
        },
        {
            "id": "2506.22222", 
            "top": ["cv"],
            "tags": ["computer vision", "image processing"]
        },
        {
            "id": "2506.33333",
            "top": ["agents"],
            "tags": ["reinforcement learning", "robotics"]
        }
    ]

    for summary_data in summaries_data:
        summary = StructuredSummary(
            paper_info=PaperInfo(title_zh=summary_data["id"], title_en=summary_data["id"], abstract="Test"),
            one_sentence_summary="content",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        tags = Tags(top=summary_data["top"], tags=summary_data["tags"])
        save_summary_with_service_record(
            arxiv_id=summary_data["id"],
            summary_content=summary,
            tags=tags,
            summary_dir=sp.SUMMARY_DIR,
            source_type="system"
        )

    # Test that all tags are shown in tag cloud when no filter is applied
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    
    # Should show all top tags
    assert "llm" in html
    assert "cv" in html  
    assert "agents" in html
    
    # Should show all detail tags
    assert "machine learning" in html
    assert "computer vision" in html
    assert "reinforcement learning" in html

    # Test that all tags are still shown when filtering by one tag
    res2 = client.get("/?tag=machine learning")
    assert res2.status_code == 200
    html2 = res2.data.decode("utf-8")
    
    # Should still show all top tags in the filter section
    assert "llm" in html2
    assert "cv" in html2
    assert "agents" in html2
    
    # Should still show all detail tags in the filter section
    assert "computer vision" in html2
    assert "reinforcement learning" in html2
    
    # But only the filtered paper should be in the results
    assert "2506.11111" in html2
    assert "2506.22222" not in html2
    assert "2506.33333" not in html2


def test_nested_tag_structure_handling(tmp_path, monkeypatch):
    """Test handling of nested tag structure (bug case)."""
    import app.main as sp

    setup_app_dirs(sp, tmp_path)
    sp.app.config.update(TESTING=True)
    client = sp.app.test_client()

    # Create summary with tags
    from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
    from summary_service.record_manager import save_summary_with_service_record
    
    summary = StructuredSummary(
        paper_info=PaperInfo(title_zh="Test", title_en="Test", abstract="Test"),
        one_sentence_summary="content",
        innovations=[],
        results=Results(experimental_highlights=[], practical_value=[]),
        terminology=[]
    )
    tags = Tags(top=["llm", "nlp"], tags=["machine learning", "natural language processing"])
    save_summary_with_service_record(
        arxiv_id="2506.12345",
        summary_content=summary,
        tags=tags,
        summary_dir=sp.SUMMARY_DIR,
        source_type="system"
    )

    # Test that the page loads correctly
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    
    # Should show the tags correctly
    assert "llm" in html
    assert "nlp" in html
    assert "machine learning" in html
    assert "natural language processing" in html

    # Test detail page
    res2 = client.get("/summary/2506.12345")
    assert res2.status_code == 200
    html2 = res2.data.decode("utf-8")
    
    # Should show tags on detail page
    assert "llm" in html2
    assert "nlp" in html2
    assert "machine learning" in html2
    assert "natural language processing" in html2


def test_detail_page_separate_tag_display(tmp_path, monkeypatch):
    """Test that detail page shows top tags and detail tags separately."""
    import app.main as sp

    setup_app_dirs(sp, tmp_path)
    sp.app.config.update(TESTING=True)
    client = sp.app.test_client()

    # Create summary with both top and detail tags
    from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
    from summary_service.record_manager import save_summary_with_service_record
    
    summary = StructuredSummary(
        paper_info=PaperInfo(title_zh="Test", title_en="Test", abstract="Test"),
        one_sentence_summary="content",
        innovations=[],
        results=Results(experimental_highlights=[], practical_value=[]),
        terminology=[]
    )
    tags = Tags(top=["llm", "nlp"], tags=["machine learning", "natural language processing"])
    save_summary_with_service_record(
        arxiv_id="2506.12345",
        summary_content=summary,
        tags=tags,
        summary_dir=sp.SUMMARY_DIR,
        source_type="system"
    )

    # Test detail page
    res = client.get("/summary/2506.12345")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    
    # Should show top tags and detail tags separately
    # Look for the specific structure we implemented
    assert "顶级标签:" in html  # Top tags label
    assert "详细标签:" in html  # Detail tags label
    
    # Should show top tags with top-chip styling
    assert 'class="top-chip pill"' in html
    
    # Should show detail tags with tag-chip styling
    assert 'class="tag-chip"' in html
    
    # Should have correct links (note: template uses single quotes)
    assert "href='/?top=llm'" in html
    assert "href='/?tag=machine learning'" in html


