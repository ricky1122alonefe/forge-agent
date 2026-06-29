"""Tests for T3.2 — forge-agent new template differentiation."""

from __future__ import annotations

import argparse

import pytest

from forge_agent.cli.cmd_new import TEMPLATES, run

# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------


class TestTemplateDefinitions:
    def test_all_templates_exist(self):
        expected = {"basic", "stock", "football", "social", "office"}
        assert set(TEMPLATES.keys()) == expected

    def test_each_template_has_required_fields(self):
        for name, tmpl in TEMPLATES.items():
            assert "description" in tmpl, f"{name} missing description"
            assert "domain" in tmpl, f"{name} missing domain"
            assert "agents" in tmpl, f"{name} missing agents"
            assert "extra_deps" in tmpl, f"{name} missing extra_deps"
            assert "readme_extra" in tmpl, f"{name} missing readme_extra"

    def test_each_template_has_at_least_one_agent(self):
        for name, tmpl in TEMPLATES.items():
            assert len(tmpl["agents"]) >= 1, f"{name} has no agents"

    def test_agent_defs_have_required_fields(self):
        for name, tmpl in TEMPLATES.items():
            for agent in tmpl["agents"]:
                assert "filename" in agent, f"{name} agent missing filename"
                assert "class_name" in agent, f"{name} agent missing class_name"
                assert "agent_id" in agent, f"{name} agent missing agent_id"
                assert "code" in agent, f"{name} agent missing code"

    def test_templates_are_differentiated(self):
        """Each template should produce different agent code."""
        all_codes = []
        for _name, tmpl in TEMPLATES.items():
            codes = [a["code"] for a in tmpl["agents"]]
            all_codes.append("".join(codes))
        # At least check they're not all identical
        assert len(set(all_codes)) > 1, "All templates produce identical code"

    def test_stock_has_two_agents(self):
        assert len(TEMPLATES["stock"]["agents"]) == 2

    def test_football_has_two_agents(self):
        assert len(TEMPLATES["football"]["agents"]) == 2

    def test_social_has_two_agents(self):
        assert len(TEMPLATES["social"]["agents"]) == 2

    def test_office_has_two_agents(self):
        assert len(TEMPLATES["office"]["agents"]) == 2

    def test_stock_has_pandas_dep(self):
        assert "pandas" in TEMPLATES["stock"]["extra_deps"]

    def test_domains_are_different(self):
        domains = {tmpl["domain"] for tmpl in TEMPLATES.values()}
        assert len(domains) >= 3  # at least 3 different domains


# ---------------------------------------------------------------------------
# Run function — project creation
# ---------------------------------------------------------------------------


class TestRunCreatesProject:
    def _make_args(self, tmp_path, name="myproject", template="basic"):
        return argparse.Namespace(project=tmp_path, name=name, template=template)

    def test_basic_creates_directory(self, tmp_path):
        args = self._make_args(tmp_path)
        result = run(args)
        assert result == 0
        assert (tmp_path / "myproject").is_dir()

    def test_basic_creates_agents_dir(self, tmp_path):
        run(self._make_args(tmp_path))
        assert (tmp_path / "myproject" / "agents").is_dir()
        assert (tmp_path / "myproject" / "agents" / "__init__.py").is_file()

    def test_basic_creates_pipelines_dir(self, tmp_path):
        run(self._make_args(tmp_path))
        assert (tmp_path / "myproject" / "pipelines").is_dir()

    def test_basic_creates_tests_dir(self, tmp_path):
        run(self._make_args(tmp_path))
        assert (tmp_path / "myproject" / "tests").is_dir()

    def test_basic_creates_generated_agents_dir(self, tmp_path):
        run(self._make_args(tmp_path))
        assert (tmp_path / "myproject" / "generated_agents").is_dir()

    def test_basic_creates_pyproject(self, tmp_path):
        run(self._make_args(tmp_path))
        pp = tmp_path / "myproject" / "pyproject.toml"
        assert pp.is_file()
        content = pp.read_text()
        assert "myproject" in content
        assert "forge-agent" in content

    def test_basic_creates_readme(self, tmp_path):
        run(self._make_args(tmp_path))
        readme = tmp_path / "myproject" / "README.md"
        assert readme.is_file()
        content = readme.read_text()
        assert "myproject" in content
        assert "basic" in content

    def test_basic_creates_example_agent(self, tmp_path):
        run(self._make_args(tmp_path))
        agent_file = tmp_path / "myproject" / "agents" / "example.py"
        assert agent_file.is_file()
        content = agent_file.read_text()
        assert "ExampleAgent" in content
        assert "BaseAgent" in content

    def test_existing_project_fails(self, tmp_path):
        (tmp_path / "myproject").mkdir()
        args = self._make_args(tmp_path)
        result = run(args)
        assert result == 1

    @pytest.mark.parametrize("template", ["basic", "stock", "football", "social", "office"])
    def test_all_templates_create_successfully(self, tmp_path, template):
        args = self._make_args(tmp_path, name=f"proj_{template}", template=template)
        result = run(args)
        assert result == 0
        proj = tmp_path / f"proj_{template}"
        assert proj.is_dir()
        assert (proj / "pyproject.toml").is_file()
        assert (proj / "README.md").is_file()
        assert (proj / "agents" / "__init__.py").is_file()

    @pytest.mark.parametrize("template", ["basic", "stock", "football", "social", "office"])
    def test_all_templates_create_agent_files(self, tmp_path, template):
        args = self._make_args(tmp_path, name=f"proj_{template}", template=template)
        run(args)
        proj = tmp_path / f"proj_{template}"
        tmpl = TEMPLATES[template]
        for agent_def in tmpl["agents"]:
            agent_file = proj / "agents" / agent_def["filename"]
            assert agent_file.is_file(), f"Missing {agent_def['filename']} for {template}"
            content = agent_file.read_text()
            assert agent_def["class_name"] in content
            assert "BaseAgent" in content

    def test_stock_template_has_pandas_dep(self, tmp_path):
        run(self._make_args(tmp_path, name="stock_proj", template="stock"))
        pp = (tmp_path / "stock_proj" / "pyproject.toml").read_text()
        assert "pandas" in pp

    def test_stock_template_creates_two_agents(self, tmp_path):
        run(self._make_args(tmp_path, name="stock_proj", template="stock"))
        agents_dir = tmp_path / "stock_proj" / "agents"
        assert (agents_dir / "stock_scraper.py").is_file()
        assert (agents_dir / "stock_analyzer.py").is_file()

    def test_football_template_creates_two_agents(self, tmp_path):
        run(self._make_args(tmp_path, name="fb_proj", template="football"))
        agents_dir = tmp_path / "fb_proj" / "agents"
        assert (agents_dir / "match_scraper.py").is_file()
        assert (agents_dir / "match_monitor.py").is_file()

    def test_social_template_creates_two_agents(self, tmp_path):
        run(self._make_args(tmp_path, name="soc_proj", template="social"))
        agents_dir = tmp_path / "soc_proj" / "agents"
        assert (agents_dir / "social_scraper.py").is_file()
        assert (agents_dir / "content_generator.py").is_file()

    def test_office_template_creates_two_agents(self, tmp_path):
        run(self._make_args(tmp_path, name="off_proj", template="office"))
        agents_dir = tmp_path / "off_proj" / "agents"
        assert (agents_dir / "task_monitor.py").is_file()
        assert (agents_dir / "report_generator.py").is_file()

    def test_readme_contains_getting_started(self, tmp_path):
        run(self._make_args(tmp_path))
        readme = (tmp_path / "myproject" / "README.md").read_text()
        assert "Getting Started" in readme
        assert "pip install" in readme
        assert "forge-agent" in readme

    def test_generated_agent_code_is_valid_python(self, tmp_path):
        """All generated agent files should be valid Python (importable)."""
        for template in TEMPLATES:
            args = self._make_args(tmp_path, name=f"proj_{template}", template=template)
            run(args)
            proj = tmp_path / f"proj_{template}"
            for agent_def in TEMPLATES[template]["agents"]:
                agent_file = proj / "agents" / agent_def["filename"]
                content = agent_file.read_text()
                # Basic syntax check: compile should not raise
                compile(content, str(agent_file), "exec")
