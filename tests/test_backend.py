"""Backend unit tests — runs without the server, tests DB + auth + tools directly."""

import os
import uuid

import pytest

# Ensure JWT_SECRET is set for tests
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing")


class TestPasswords:
    def test_hash_and_verify(self):
        from deep_research.auth.passwords import hash_password, verify_password

        hashed = hash_password("mypassword")
        assert isinstance(hashed, str)
        assert len(hashed) == 60
        assert verify_password("mypassword", hashed)
        assert not verify_password("wrongpassword", hashed)

    def test_long_password_truncated(self):
        from deep_research.auth.passwords import hash_password, verify_password

        long_pw = "a" * 200
        hashed = hash_password(long_pw)
        assert verify_password(long_pw, hashed)


class TestJWT:
    def test_create_and_verify_access_token(self):
        from deep_research.auth.jwt import create_access_token, verify_access_token

        token = create_access_token("user-123")
        payload = verify_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_invalid_token_raises(self):
        from deep_research.auth.jwt import verify_access_token
        from jose import JWTError

        with pytest.raises(JWTError):
            verify_access_token("not.a.valid.token")

    def test_create_refresh_token(self):
        from deep_research.auth.jwt import create_refresh_token

        token, expires_at = create_refresh_token()
        assert isinstance(token, str)
        assert len(token) > 20
        assert "T" in expires_at  # ISO format


class TestDatabase:
    """Tests using Turso or local SQLite depending on env."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        from deep_research.db.client import init_db, close_db
        init_db()
        yield
        close_db()

    def test_user_crud(self):
        from deep_research.db.users import create_user, get_user_by_email, get_user_by_id

        email = f"test-{uuid.uuid4().hex[:8]}@test.com"
        user = create_user(email, "hashed_pw", "Test")
        assert user["email"] == email

        found = get_user_by_email(email)
        assert found is not None
        assert found["name"] == "Test"

        found2 = get_user_by_id(user["id"])
        assert found2 is not None
        assert found2["email"] == email

    def test_session_crud(self):
        from deep_research.db.users import create_user
        from deep_research.db.sessions import (
            create_session, get_session, update_session_result, list_user_sessions,
        )

        email = f"sess-{uuid.uuid4().hex[:8]}@test.com"
        user = create_user(email, "pw", "Sess User")
        sid = str(uuid.uuid4())

        create_session(sid, user["id"], "test query", "quick")
        sess = get_session(sid)
        assert sess["status"] == "running"
        assert sess["query"] == "test query"

        update_session_result(sid, {
            "report": "# Report",
            "distilled_summary": "Summary",
            "iterations": 2,
        })
        sess2 = get_session(sid)
        assert sess2["status"] == "completed"
        assert sess2["report"] == "# Report"
        assert sess2["iterations"] == 2

        sessions = list_user_sessions(user["id"])
        assert len(sessions) >= 1

    def test_share_links(self):
        from deep_research.db.users import create_user
        from deep_research.db.sessions import create_session, update_session_result
        from deep_research.db.shares import create_share_link, get_share_link, increment_view_count

        email = f"share-{uuid.uuid4().hex[:8]}@test.com"
        user = create_user(email, "pw", "Share User")
        sid = str(uuid.uuid4())
        create_session(sid, user["id"], "share test", "quick")
        update_session_result(sid, {"report": "content", "iterations": 1})

        token = create_share_link(sid, user["id"])
        assert isinstance(token, str)
        assert len(token) > 10

        # Idempotent — same token returned
        token2 = create_share_link(sid, user["id"])
        assert token2 == token

        share = get_share_link(token)
        assert share["session_id"] == sid
        assert share["view_count"] == 0

        increment_view_count(token)
        share2 = get_share_link(token)
        assert share2["view_count"] == 1

    def test_templates(self):
        from deep_research.db.templates import seed_builtin_templates, list_templates, get_template

        seed_builtin_templates()
        templates = list_templates()
        assert len(templates) >= 5

        t = get_template("market-analysis")
        assert t is not None
        assert t["name"] == "Market Analysis"
        assert t["is_builtin"] is True


class TestSourceScorer:
    def test_tier1_sources(self):
        from deep_research.tools.source_scorer import score_source

        result = score_source("https://nature.com/articles/123")
        assert result["credibility_tier"] == "tier1"
        assert result["credibility_score"] >= 0.9

    def test_low_sources(self):
        from deep_research.tools.source_scorer import score_source

        result = score_source("https://medium.com/@user/post")
        assert result["credibility_tier"] == "low"
        assert result["credibility_score"] <= 0.3

    def test_source_type_classification(self):
        from deep_research.tools.source_scorer import classify_source_type

        assert classify_source_type("https://arxiv.org/abs/2401.1") == "academic"
        assert classify_source_type("https://bbc.com/news") == "news_major"
        assert classify_source_type("https://reddit.com/r/test") == "forum"
        assert classify_source_type("https://docs.python.org/3") == "documentation"


class TestFactChecker:
    def test_extract_citations(self):
        from deep_research.tools.fact_checker import extract_citations_from_markdown

        md = "See [Source](https://example.com) and [Other](https://other.com)."
        citations = extract_citations_from_markdown(md)
        assert len(citations) == 2
        assert citations[0]["url"] == "https://example.com"
        assert citations[1]["text"] == "Other"

    def test_no_citations(self):
        from deep_research.tools.fact_checker import extract_citations_from_markdown

        citations = extract_citations_from_markdown("No links here.")
        assert len(citations) == 0

    def test_find_unsupported_claims(self):
        from deep_research.tools.fact_checker import find_unsupported_claims

        report = "Revenue grew 45% in 2024. Users reached 500 million worldwide."
        sources = {"src1": "revenue grew 45 percent in 2024"}
        unsupported = find_unsupported_claims(report, sources)
        # "500 million" not in sources
        assert len(unsupported) >= 1


class TestTextExtraction:
    def test_string_input(self):
        from deep_research.agents.validator import _extract_text

        assert _extract_text("hello") == "hello"

    def test_block_list(self):
        from deep_research.agents.validator import _extract_text

        blocks = [{"text": "Part 1"}, {"text": "Part 2"}]
        result = _extract_text(blocks)
        assert "Part 1" in result
        assert "Part 2" in result

    def test_empty_list(self):
        from deep_research.agents.validator import _extract_text

        assert _extract_text([]) == ""

    def test_none(self):
        from deep_research.agents.validator import _extract_text

        assert _extract_text(None) == "None"
