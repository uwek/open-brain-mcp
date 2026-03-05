"""
Tests für cli.py
"""

import json
import tempfile
import os
from unittest.mock import AsyncMock, patch

import pytest

import db


class TestFormatters:
    """Tests für CLI-Formatter."""

    def test_fmt_thought_list_empty(self):
        from cli import fmt_thought_list
        result = fmt_thought_list([], "Test")
        assert "Keine Einträge" in result

    def test_fmt_thought_list_with_results(self):
        from cli import fmt_thought_list
        results = [{
            "content": "Test content",
            "metadata": {"type": "observation", "topics": ["python"]},
            "created_at": "2024-01-01T00:00:00Z",
        }]
        result = fmt_thought_list(results, "Thoughts")
        assert "Test content" in result

    def test_fmt_thought_list_with_people_and_actions(self):
        from cli import fmt_thought_list
        results = [{
            "content": "Test",
            "metadata": {"type": "task", "topics": ["python"], "people": ["Max"], "action_items": ["Do this"]},
            "created_at": "2024-01-01T00:00:00Z",
        }]
        result = fmt_thought_list(results, "Thoughts")
        assert "Max" in result
        assert "Do this" in result

    def test_fmt_search_results_empty(self):
        from cli import fmt_search_results
        result = fmt_search_results([], "query")
        assert "Keine" in result

    def test_fmt_search_results_with_results(self):
        from cli import fmt_search_results
        results = [{
            "content": "Found this",
            "metadata": {"type": "idea", "topics": ["test"], "people": ["Anna"], "action_items": ["Task"]},
            "created_at": "2024-01-01T00:00:00Z",
            "similarity": 0.85,
        }]
        result = fmt_search_results(results, "query")
        assert "Found this" in result
        assert "85.0%" in result

    def test_fmt_stats(self):
        from cli import fmt_stats
        stats = {"total": 5, "oldest": "2024-01-01", "newest": "2024-01-05",
                 "types": {"observation": 3}, "top_topics": {"python": 4}, "top_people": {"Max": 1}}
        result = fmt_stats(stats)
        assert "5" in result

    def test_fmt_stats_empty(self):
        from cli import fmt_stats
        stats = {"total": 0, "oldest": None, "newest": None, "types": {}, "top_topics": {}, "top_people": {}}
        result = fmt_stats(stats)
        assert "0" in result

    def test_fmt_add_result(self):
        from cli import fmt_add_result
        metadata = {"type": "task", "topics": ["python"], "people": ["Max"], "action_items": ["Write tests"]}
        result = fmt_add_result("abc123", metadata)
        assert "task" in result

    def test_fmt_add_result_with_content(self):
        from cli import fmt_add_result
        result = fmt_add_result("id123", {"type": "note"}, content="Test content")
        assert "Test content" in result


class TestCmdAdd:
    """Tests für cmd_add."""

    @pytest.mark.asyncio
    async def test_cmd_add_with_thought(self, capsys):
        from cli import cmd_add
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                    with patch("ai._extract_metadata_call", new_callable=AsyncMock) as mock_meta:
                        mock_emb.return_value = [0.1] * 1536
                        mock_meta.return_value = {"type": "observation"}
                        args = type("Args", (), {"thought": "Test thought", "file": None, "json": False})()
                        await cmd_add(args)
                        captured = capsys.readouterr()
                        assert "gespeichert" in captured.out.lower()

    @pytest.mark.asyncio
    async def test_cmd_add_json_output(self, capsys):
        from cli import cmd_add
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                    with patch("ai._extract_metadata_call", new_callable=AsyncMock) as mock_meta:
                        mock_emb.return_value = [0.1] * 1536
                        mock_meta.return_value = {"type": "task"}
                        args = type("Args", (), {"thought": "Test thought", "file": None, "json": True})()
                        await cmd_add(args)
                        captured = capsys.readouterr()
                        output = json.loads(captured.out)
                        assert "id" in output

    @pytest.mark.asyncio
    async def test_cmd_add_from_file(self, capsys):
        from cli import cmd_add
        with tempfile.NamedTemporaryFile(suffix=".db") as db_tmp:
            with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False) as txt_tmp:
                txt_tmp.write("Thought from file")
                txt_path = txt_tmp.name
            try:
                with patch.object(db.config, "OPENBRAIN_DB_PATH", db_tmp.name):
                    with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                        with patch("ai._extract_metadata_call", new_callable=AsyncMock) as mock_meta:
                            mock_emb.return_value = [0.1] * 1536
                            mock_meta.return_value = {"type": "observation"}
                            args = type("Args", (), {"thought": None, "file": txt_path, "json": False})()
                            await cmd_add(args)
                            captured = capsys.readouterr()
                            assert "gespeichert" in captured.out.lower()
            finally:
                os.unlink(txt_path)

    @pytest.mark.asyncio
    async def test_cmd_add_file_not_found(self):
        from cli import cmd_add
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                args = type("Args", (), {"thought": None, "file": "/nonexistent.txt", "json": False})()
                with pytest.raises(SystemExit):
                    await cmd_add(args)

    @pytest.mark.asyncio
    async def test_cmd_add_empty_file(self):
        from cli import cmd_add
        with tempfile.NamedTemporaryFile(suffix=".db") as db_tmp:
            with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False) as txt_tmp:
                txt_tmp.write("")
                txt_path = txt_tmp.name
            try:
                with patch.object(db.config, "OPENBRAIN_DB_PATH", db_tmp.name):
                    args = type("Args", (), {"thought": None, "file": txt_path, "json": False})()
                    with pytest.raises(SystemExit):
                        await cmd_add(args)
            finally:
                os.unlink(txt_path)

    @pytest.mark.asyncio
    async def test_cmd_add_no_thought_no_file(self):
        from cli import cmd_add
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                args = type("Args", (), {"thought": None, "file": None, "json": False})()
                with pytest.raises(SystemExit):
                    await cmd_add(args)


class TestCmdSearch:
    """Tests für cmd_search."""

    @pytest.mark.asyncio
    async def test_cmd_search(self, capsys):
        from cli import cmd_search
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Python", embedding=[0.5] * 1536, metadata={})
                con.close()
                with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                    mock_emb.return_value = [0.5] * 1536
                    args = type("Args", (), {"text": "python", "limit": 10, "threshold": 0.0, "json": False})()
                    await cmd_search(args)
                    captured = capsys.readouterr()
                    assert "Python" in captured.out or "Keine" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_search_json(self, capsys):
        from cli import cmd_search
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Python", embedding=[0.5] * 1536, metadata={})
                con.close()
                with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                    mock_emb.return_value = [0.5] * 1536
                    args = type("Args", (), {"text": "python", "limit": 10, "threshold": 0.0, "json": True})()
                    await cmd_search(args)
                    captured = capsys.readouterr()
                    output = json.loads(captured.out)
                    assert isinstance(output, list)


class TestCmdList:
    """Tests für cmd_list."""

    def test_cmd_list(self, capsys):
        from cli import cmd_list
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={"type": "obs"})
                con.close()
                args = type("Args", (), {"limit": 10, "type": None, "topic": None, "person": None, "days": None, "json": False})()
                cmd_list(args)

    def test_cmd_list_json(self, capsys):
        from cli import cmd_list
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                con.close()
                args = type("Args", (), {"limit": 10, "type": None, "topic": None, "person": None, "days": None, "json": True})()
                cmd_list(args)
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert len(output) == 1

    def test_cmd_list_with_filters(self, capsys):
        from cli import cmd_list
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Python Max", embedding=[0.1] * 1536,
                    metadata={"type": "observation", "topics": ["python"], "people": ["Max"]})
                con.close()
                args = type("Args", (), {"limit": 10, "type": "observation", "topic": "python", "person": "Max", "days": None, "json": True})()
                cmd_list(args)
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert len(output) == 1


class TestCmdStats:
    """Tests für cmd_stats."""

    def test_cmd_stats(self, capsys):
        from cli import cmd_stats
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                con.close()
                args = type("Args", (), {"json": False})()
                cmd_stats(args)

    def test_cmd_stats_json(self, capsys):
        from cli import cmd_stats
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                con.close()
                args = type("Args", (), {"json": True})()
                cmd_stats(args)
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["total"] == 1


class TestCmdExport:
    """Tests für cmd_export."""

    def test_cmd_export(self, capsys):
        from cli import cmd_export
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                con.close()
                args = type("Args", (), {"output": None, "full": False})()
                cmd_export(args)
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["count"] == 1

    def test_cmd_export_to_file(self, capsys):
        from cli import cmd_export
        with tempfile.NamedTemporaryFile(suffix=".db") as db_tmp:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as json_tmp:
                json_path = json_tmp.name
            try:
                with patch.object(db.config, "OPENBRAIN_DB_PATH", db_tmp.name):
                    con = db.init_db()
                    db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                    con.close()
                    args = type("Args", (), {"output": json_path, "full": False})()
                    cmd_export(args)
                    captured = capsys.readouterr()
                    assert "Export" in captured.out
                    with open(json_path) as f:
                        data = json.load(f)
                    assert data["count"] == 1
            finally:
                os.unlink(json_path)

    def test_cmd_export_with_embeddings(self, capsys):
        from cli import cmd_export
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                con.close()
                args = type("Args", (), {"output": None, "full": True})()
                cmd_export(args)
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["include_embeddings"] is True
                assert output["thoughts"][0]["embedding"] is not None


class TestCmdImport:
    """Tests für cmd_import."""

    @pytest.mark.asyncio
    async def test_cmd_import(self, capsys):
        from cli import cmd_import
        with tempfile.NamedTemporaryFile(suffix=".db") as db_tmp:
            with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as json_tmp:
                data = {"version": 1, "thoughts": [
                    {"id": "test123", "content": "Imported", "metadata": {}, "embedding": [0.1] * 1536}
                ]}
                json_tmp.write(json.dumps(data))
                json_path = json_tmp.name
            try:
                with patch.object(db.config, "OPENBRAIN_DB_PATH", db_tmp.name):
                    args = type("Args", (), {"file": json_path, "reembed": False, "on_conflict": "skip"})()
                    await cmd_import(args)
                    captured = capsys.readouterr()
                    assert "Import" in captured.out
            finally:
                os.unlink(json_path)

    @pytest.mark.asyncio
    async def test_cmd_import_list_format(self, capsys):
        from cli import cmd_import
        with tempfile.NamedTemporaryFile(suffix=".db") as db_tmp:
            with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as json_tmp:
                data = [{"id": "list123", "content": "List import", "metadata": {}, "embedding": [0.1] * 1536}]
                json_tmp.write(json.dumps(data))
                json_path = json_tmp.name
            try:
                with patch.object(db.config, "OPENBRAIN_DB_PATH", db_tmp.name):
                    args = type("Args", (), {"file": json_path, "reembed": False, "on_conflict": "skip"})()
                    await cmd_import(args)
                    captured = capsys.readouterr()
                    assert "Import" in captured.out
            finally:
                os.unlink(json_path)

    @pytest.mark.asyncio
    async def test_cmd_import_file_not_found(self):
        from cli import cmd_import
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                args = type("Args", (), {"file": "/nonexistent.json", "reembed": False, "on_conflict": "skip"})()
                with pytest.raises(SystemExit):
                    await cmd_import(args)

    @pytest.mark.asyncio
    async def test_cmd_import_invalid_format(self):
        from cli import cmd_import
        with tempfile.NamedTemporaryFile(suffix=".db") as db_tmp:
            with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as json_tmp:
                json_tmp.write('{"invalid": "format"}')
                json_path = json_tmp.name
            try:
                with patch.object(db.config, "OPENBRAIN_DB_PATH", db_tmp.name):
                    args = type("Args", (), {"file": json_path, "reembed": False, "on_conflict": "skip"})()
                    with pytest.raises(SystemExit):
                        await cmd_import(args)
            finally:
                os.unlink(json_path)

    @pytest.mark.asyncio
    async def test_cmd_import_empty_list(self, capsys):
        from cli import cmd_import
        with tempfile.NamedTemporaryFile(suffix=".db") as db_tmp:
            with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as json_tmp:
                json_tmp.write('{"thoughts": []}')
                json_path = json_tmp.name
            try:
                with patch.object(db.config, "OPENBRAIN_DB_PATH", db_tmp.name):
                    args = type("Args", (), {"file": json_path, "reembed": False, "on_conflict": "skip"})()
                    await cmd_import(args)
                    captured = capsys.readouterr()
                    assert "Keine" in captured.out
            finally:
                os.unlink(json_path)

    @pytest.mark.asyncio
    async def test_cmd_import_reembed(self, capsys):
        from cli import cmd_import
        with tempfile.NamedTemporaryFile(suffix=".db") as db_tmp:
            with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as json_tmp:
                data = {"thoughts": [{"id": "re123", "content": "Reembed", "metadata": {}, "embedding": [0.1] * 1536}]}
                json_tmp.write(json.dumps(data))
                json_path = json_tmp.name
            try:
                with patch.object(db.config, "OPENBRAIN_DB_PATH", db_tmp.name):
                    with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                        with patch("ai._extract_metadata_call", new_callable=AsyncMock) as mock_meta:
                            mock_emb.return_value = [0.1] * 1536
                            mock_meta.return_value = {"type": "observation"}
                            args = type("Args", (), {"file": json_path, "reembed": True, "on_conflict": "skip"})()
                            await cmd_import(args)
                            captured = capsys.readouterr()
                            assert "Import" in captured.out
            finally:
                os.unlink(json_path)

    @pytest.mark.asyncio
    async def test_cmd_import_without_embeddings(self, capsys):
        from cli import cmd_import
        with tempfile.NamedTemporaryFile(suffix=".db") as db_tmp:
            with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as json_tmp:
                data = {"thoughts": [{"id": "noemb123", "content": "No embedding", "metadata": {}}]}
                json_tmp.write(json.dumps(data))
                json_path = json_tmp.name
            try:
                with patch.object(db.config, "OPENBRAIN_DB_PATH", db_tmp.name):
                    with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                        with patch("ai._extract_metadata_call", new_callable=AsyncMock) as mock_meta:
                            mock_emb.return_value = [0.1] * 1536
                            mock_meta.return_value = {"type": "observation"}
                            args = type("Args", (), {"file": json_path, "reembed": False, "on_conflict": "skip"})()
                            await cmd_import(args)
                            captured = capsys.readouterr()
                            assert "Import" in captured.out
            finally:
                os.unlink(json_path)

    @pytest.mark.asyncio
    async def test_cmd_import_skip_empty_content(self, capsys):
        from cli import cmd_import
        with tempfile.NamedTemporaryFile(suffix=".db") as db_tmp:
            with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as json_tmp:
                data = {"thoughts": [{"id": "empty123", "content": "", "metadata": {}, "embedding": [0.1] * 1536}]}
                json_tmp.write(json.dumps(data))
                json_path = json_tmp.name
            try:
                with patch.object(db.config, "OPENBRAIN_DB_PATH", db_tmp.name):
                    args = type("Args", (), {"file": json_path, "reembed": False, "on_conflict": "skip"})()
                    await cmd_import(args)
                    captured = capsys.readouterr()
                    assert "Fehler" in captured.out or "Übersprungen" in captured.out
            finally:
                os.unlink(json_path)

    @pytest.mark.asyncio
    async def test_cmd_import_replace(self, capsys):
        from cli import cmd_import
        with tempfile.NamedTemporaryFile(suffix=".db") as db_tmp:
            with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as json_tmp:
                data = {"thoughts": [
                    {"id": "replace123", "content": "First", "metadata": {}, "embedding": [0.1] * 1536},
                    {"id": "replace123", "content": "Second", "metadata": {}, "embedding": [0.1] * 1536}
                ]}
                json_tmp.write(json.dumps(data))
                json_path = json_tmp.name
            try:
                with patch.object(db.config, "OPENBRAIN_DB_PATH", db_tmp.name):
                    args = type("Args", (), {"file": json_path, "reembed": False, "on_conflict": "replace"})()
                    await cmd_import(args)
                    captured = capsys.readouterr()
                    assert "ersetzt" in captured.out
            finally:
                os.unlink(json_path)


class TestBuildParser:
    """Tests für Argument-Parser."""

    def test_parser_add(self):
        from cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["add", "test thought"])
        assert args.command == "add"
        assert args.thought == "test thought"

    def test_parser_search(self):
        from cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["search", "query", "--limit", "5"])
        assert args.command == "search"
        assert args.text == "query"
        assert args.limit == 5

    def test_parser_list(self):
        from cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["list", "--type", "task", "--limit", "20"])
        assert args.command == "list"
        assert args.type == "task"
        assert args.limit == 20

    def test_parser_stats(self):
        from cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["stats", "--json"])
        assert args.command == "stats"
        assert args.json is True

    def test_parser_export_import(self):
        from cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["export", "backup.json", "--full"])
        assert args.command == "export"
        assert args.output == "backup.json"
        assert args.full is True

        args = parser.parse_args(["import", "backup.json", "--on-conflict", "replace"])
        assert args.command == "import"
        assert args.file == "backup.json"
        assert args.on_conflict == "replace"


class TestMain:
    """Tests für main()."""

    def test_main_add(self, monkeypatch):
        from cli import main
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                    with patch("ai._extract_metadata_call", new_callable=AsyncMock) as mock_meta:
                        mock_emb.return_value = [0.1] * 1536
                        mock_meta.return_value = {"type": "observation"}
                        monkeypatch.setattr("sys.argv", ["cli.py", "add", "test"])
                        main()

    def test_main_search(self, monkeypatch, capsys):
        from cli import main
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                con.close()
                with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                    mock_emb.return_value = [0.1] * 1536
                    monkeypatch.setattr("sys.argv", ["cli.py", "search", "test"])
                    main()

    def test_main_list(self, monkeypatch):
        from cli import main
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                con.close()
                monkeypatch.setattr("sys.argv", ["cli.py", "list"])
                main()

    def test_main_stats(self, monkeypatch):
        from cli import main
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                con.close()
                monkeypatch.setattr("sys.argv", ["cli.py", "stats"])
                main()

    def test_main_export(self, monkeypatch):
        from cli import main
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                con = db.init_db()
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                con.close()
                monkeypatch.setattr("sys.argv", ["cli.py", "export"])
                main()