"""Consumer-visible boundaries exercised through the official optional MCP client."""
from __future__ import annotations

import copy
import importlib.util
import json
from functools import wraps
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills"))
SDK_AVAILABLE = importlib.util.find_spec("mcp") is not None
_SECTIONS = (
    "start", "workflows", "templates", "project-plans", "routing",
    "memory", "safety", "supervision", "research", "integrations",
)
_INSPECTION_ERROR = (
    "Error executing tool aic_inspect_project: "
    "Inspection rejected: use integer limits (files 1..10000, depth 0..32) "
    "and an unchanged safe bound project directory."
)
_GUIDANCE_ERROR = (
    "Error executing tool aic_get_guidance: "
    "Unknown guidance section; use a declared section name."
)

if SDK_AVAILABLE:
    from mcp import Client, StdioServerParameters

    from mcp.shared.exceptions import MCPError
    from aic.scripts.aiclib import mcp_server


def _error_text(result) -> str:
    return "\n".join(block.text for block in result.content if getattr(block, "text", None) is not None)


def _assert_closed_and_bounded(test, schema, path):
    """Every object is closed, and every number or string carries its published limit."""
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            test.assertIs(schema.get("additionalProperties"), False, path)
        kind = schema.get("type")
        if kind in ("integer", "number"):
            test.assertIn("minimum", schema, path)
            test.assertIn("maximum", schema, path)
            test.assertLessEqual(schema["minimum"], schema["maximum"], path)
        if kind == "string":
            test.assertIsInstance(schema.get("maxLength"), int, path)
            test.assertGreater(schema["maxLength"], 0, path)
        for key, value in schema.items():
            if key == "additionalProperties" and not isinstance(value, dict):
                continue
            _assert_closed_and_bounded(test, value, f"{path}.{key}")
    elif isinstance(schema, list):
        for index, item in enumerate(schema):
            _assert_closed_and_bounded(test, item, f"{path}[{index}]")


def mcp_session(test):
    """Keep the SDK's AnyIO context entry and exit in the same test task."""
    @wraps(test)
    async def run(self):
        async with Client(self.module.build_server(self.project)) as self.client:
            await test(self)
    return run


@unittest.skipUnless(SDK_AVAILABLE, "Install the optional MCP extra to exercise the protocol")
class McpBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixtures = ROOT / ".work"
        fixtures.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="mcp-boundary-", dir=fixtures)
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.project = self.base / "approved-project"
        self.project.mkdir()
        (self.project / "README.md").write_text("private body must not be returned", encoding="utf-8")
        (self.project / "package.json").write_bytes(b"\xffthis is not JSON and must not be opened")
        (self.project / ".env").write_text("PRIVATE_MARKER_NOT_FOR_CONTEXT", encoding="utf-8")
        self.other = self.base / "other-project"
        self.other.mkdir()
        (self.other / "outside-only.py").write_text("outside project", encoding="utf-8")
        self.module = mcp_server
        self.plan = json.loads((ROOT / "skills/aic/assets/example-plan.json").read_text(encoding="utf-8"))

    @mcp_session
    async def test_resource_reads_cannot_address_project_or_arbitrary_files(self):
        for uri in (
            (self.project / ".env").as_uri(),
            "aic://project/.env",
            "aic://skill/references/../../.env",
            "aic://skill/references/%2e%2e/%2e%2e/.env",
            "aic://skill/assets/example-plan.json?path=.env",
            "aic://skill/references/unknown.md",
        ):
            with self.subTest(uri=uri), self.assertRaises(MCPError):
                await self.client.read_resource(uri)
        recovered = await self.client.call_tool("aic_get_workflow_catalog", {})
        self.assertFalse(recovered.is_error)

    @mcp_session
    async def test_every_tool_rejects_surplus_arguments(self):
        calls = (
            ("aic_get_workflow_catalog", {"path": str(self.project / ".env")}),
            ("aic_get_guidance", {"section": "start", "path": str(self.project / ".env")}),
            ("aic_inspect_project", {"ignore_file": str(self.project / ".env")}),
            ("aic_validate_recommendation", {"plan": self.plan, "project": str(self.other)}),
        )
        for name, arguments in calls:
            with self.subTest(name=name):
                result = await self.client.call_tool(name, arguments)
                self.assertTrue(result.is_error)

    @mcp_session
    async def test_recommendation_is_opaque_json_not_a_coerced_model(self):
        for plan in (None, [], True, json.dumps(self.plan)):
            with self.subTest(plan=plan):
                result = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
                self.assertTrue(result.is_error)
        plan = copy.deepcopy(self.plan)
        plan["scope"]["write"] = "README.md"
        result = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
        self.assertTrue(result.is_error)

    @mcp_session
    async def test_failed_core_validation_does_not_disclose_private_paths(self):
        (self.project / "alias").symlink_to(self.other, target_is_directory=True)
        plan = copy.deepcopy(self.plan)
        plan["scope"]["write"] = ["alias/new.md"]
        result = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
        self.assertTrue(result.is_error)
        for private in (str(self.project / "alias"), str(self.other), "Traceback"):
            self.assertNotIn(private, str(result.content))
        recovered = await self.client.call_tool("aic_validate_recommendation", {"plan": self.plan})
        self.assertFalse(recovered.is_error)

    @mcp_session
    async def test_unexpected_failure_stays_failed_and_server_recovers(self):
        with patch.object(self.module, "inspect_project", side_effect=RuntimeError("PRIVATE_CRASH_DETAIL")):
            result = await self.client.call_tool("aic_inspect_project", {})
        self.assertTrue(result.is_error)
        self.assertNotIn("PRIVATE_CRASH_DETAIL", str(result.content))
        self.assertNotIn("Traceback", str(result.content))
        recovered = await self.client.call_tool("aic_inspect_project", {})
        self.assertFalse(recovered.is_error)

    @mcp_session
    async def test_separate_servers_never_rebind_each_others_project(self):
        async with Client(self.module.build_server(self.other)) as other_client:
            inspected = await other_client.call_tool("aic_inspect_project", {})
            self.assertEqual(inspected.structured_content["project"], str(self.other))
            self.assertIn("outside-only.py", json.dumps(inspected.structured_content))
            original = await self.client.call_tool("aic_inspect_project", {})
            self.assertEqual(original.structured_content["project"], str(self.project))
            self.assertNotIn("outside-only.py", json.dumps(original.structured_content))

    @mcp_session
    async def test_evidence_requires_safe_existing_paths_without_opening_contents(self):
        plan = copy.deepcopy(self.plan)
        plan["evidence"] = [{"path": "README.md", "observation": "A README filename exists."}]
        result = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
        self.assertFalse(result.is_error)
        self.assertNotIn("private body must not be returned", str(result.content))
        for path in ("missing.md", ".env", "../other-project/outside-only.py"):
            plan["evidence"][0]["path"] = path
            with self.subTest(path=path):
                result = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
                self.assertTrue(result.is_error)

    @mcp_session
    async def test_parallel_recommendations_preserve_core_isolation_guards(self):
        plan = copy.deepcopy(self.plan)
        plan.update(template="explore-build", topology="parallel")
        plan["scope"]["write"] = ["first", "second"]
        plan["independent_subtasks"] = [
            {"goal": "Inspect the first slice.", "allowed_paths": ["first"], "acceptance": ["Report first-slice evidence."]},
            {"goal": "Inspect the second slice.", "allowed_paths": ["second"], "acceptance": ["Report second-slice evidence."]},
        ]
        valid = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
        self.assertFalse(valid.is_error)
        for collision in ("first", "first/child", "FIRST"):
            plan["independent_subtasks"][1]["allowed_paths"] = [collision]
            with self.subTest(collision=collision):
                result = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
                self.assertTrue(result.is_error)
        plan["independent_subtasks"][1]["allowed_paths"] = ["second"]
        (self.project / "first").write_text("private branch contents", encoding="utf-8")
        (self.project / "second").hardlink_to(self.project / "first")
        aliased = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
        self.assertTrue(aliased.is_error)

    @mcp_session
    async def test_inspection_is_bound_and_metadata_only(self):
        response = await self.client.call_tool("aic_inspect_project", {})
        self.assertFalse(response.is_error)
        data = response.structured_content
        self.assertEqual(data["project"], str(self.project))
        serialized = json.dumps(data)
        self.assertIn("README.md", serialized)
        self.assertIn("package.json", serialized)
        for private in ("private body must not be returned", "PRIVATE_MARKER_NOT_FOR_CONTEXT", ".env", "outside-only.py", "this is not JSON"):
            with self.subTest(private=private):
                self.assertNotIn(private, serialized)
        refused = await self.client.call_tool("aic_inspect_project", {"project": str(self.other)})
        self.assertTrue(refused.is_error)

    @mcp_session
    async def test_inspection_does_not_coerce_limits_or_ignore_bounds(self):
        for arguments in ({"max_files": True}, {"max_depth": False}, {"max_files": 1.5}, {"max_depth": "2"}):
            with self.subTest(arguments=arguments):
                result = await self.client.call_tool("aic_inspect_project", arguments)
                self.assertTrue(result.is_error)
                self.assertNotEqual(_error_text(result), _INSPECTION_ERROR)
        for arguments in ({"max_files": 0}, {"max_files": 10001}, {"max_depth": -1}, {"max_depth": 33}):
            with self.subTest(arguments=arguments):
                result = await self.client.call_tool("aic_inspect_project", arguments)
                self.assertEqual(_error_text(result), _INSPECTION_ERROR)
                for leaked in ("10001", "-1", "33"):
                    self.assertNotIn(leaked, _error_text(result))
        recovered = await self.client.call_tool("aic_inspect_project", {"max_files": 1, "max_depth": 0})
        self.assertFalse(recovered.is_error)
        self.assertEqual(recovered.structured_content["project"], str(self.project))

    async def _assert_published_bounds(self, client):
        listed = await client.list_tools()
        schemas = {tool.name: tool.input_schema for tool in listed.tools}
        for name, schema in schemas.items():
            with self.subTest(schema=name):
                _assert_closed_and_bounded(self, schema, name)
        files = schemas["aic_inspect_project"]["properties"]["max_files"]
        depth = schemas["aic_inspect_project"]["properties"]["max_depth"]
        self.assertEqual((files["minimum"], files["maximum"]), (1, 10000))
        self.assertEqual((depth["minimum"], depth["maximum"]), (0, 32))
        section = schemas["aic_get_guidance"]["properties"]["section"]
        self.assertEqual(section["enum"], list(_SECTIONS))
        self.assertEqual(section["maxLength"], max(len(name) for name in _SECTIONS))
        plan = schemas["aic_validate_recommendation"]["properties"]["plan"]
        self.assertNotIn("additionalProperties", plan)
        ceiling = await client.call_tool("aic_inspect_project", {"max_files": files["maximum"], "max_depth": depth["maximum"]})
        self.assertFalse(ceiling.is_error)
        self.assertEqual(ceiling.structured_content["project"], str(self.project))
        for arguments in (
            {"max_files": files["minimum"] - 1},
            {"max_files": files["maximum"] + 1},
            {"max_depth": depth["minimum"] - 1},
            {"max_depth": depth["maximum"] + 1},
        ):
            with self.subTest(arguments=arguments):
                result = await client.call_tool("aic_inspect_project", arguments)
                text = _error_text(result)
                self.assertEqual(text, _INSPECTION_ERROR)
                for supplied in arguments.values():
                    if str(supplied) not in _INSPECTION_ERROR:
                        self.assertNotIn(str(supplied), text)
        for name in _SECTIONS:
            with self.subTest(section=name):
                result = await client.call_tool("aic_get_guidance", {"section": name})
                self.assertFalse(result.is_error)
                self.assertTrue(result.structured_content["text"])
        marker = "PRIVATE_SECTION_MARKER"
        for section_name in ("unknown", "x" * section["maxLength"], marker + ("x" * section["maxLength"])):
            with self.subTest(section=section_name):
                result = await client.call_tool("aic_get_guidance", {"section": section_name})
                self.assertEqual(_error_text(result), _GUIDANCE_ERROR)
                self.assertNotIn(marker, _error_text(result))
                self.assertNotIn(section_name, _error_text(result))

    @mcp_session
    async def test_published_bounds_match_server_rejection(self):
        await self._assert_published_bounds(self.client)

    @mcp_session
    async def test_recommendation_cannot_remove_approval_or_become_execution(self):
        for key, value in (("approval_required", False), ("approval_required", 1), ("next_action", "execute"), ("schema_version", 2), ("schema_version", True)):
            plan = copy.deepcopy(self.plan)
            plan[key] = value
            with self.subTest(key=key, value=value):
                result = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
                self.assertTrue(result.is_error)
        valid = await self.client.call_tool("aic_validate_recommendation", {"plan": self.plan})
        self.assertFalse(valid.is_error)
        self.assertIs(valid.structured_content["approval_required"], True)
        self.assertEqual(valid.structured_content["next_action"], "recommend")

    @mcp_session
    async def test_recommendation_cannot_escape_the_approved_project(self):
        for scope in ("../other-project", str(self.other)):
            plan = copy.deepcopy(self.plan)
            plan["scope"]["write"] = [scope]
            with self.subTest(scope=scope):
                result = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
                self.assertTrue(result.is_error)
        (self.project / "alias").symlink_to(self.other, target_is_directory=True)
        plan = copy.deepcopy(self.plan)
        plan["scope"]["write"] = ["alias/new.md"]
        result = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
        self.assertTrue(result.is_error)

    @mcp_session
    async def test_unlisted_guidance_cannot_open_arbitrary_files(self):
        for section in ("../.env", str(self.project / ".env"), "file:///etc/passwd", "unknown-guide"):
            with self.subTest(section=section):
                result = await self.client.call_tool("aic_get_guidance", {"section": section})
                self.assertEqual(_error_text(result), _GUIDANCE_ERROR)
                self.assertNotIn("PRIVATE_MARKER_NOT_FOR_CONTEXT", _error_text(result))
                self.assertNotIn(section, _error_text(result))
        recovered = await self.client.call_tool("aic_validate_recommendation", {"plan": self.plan})
        self.assertFalse(recovered.is_error)

    @mcp_session
    async def test_mutation_and_agent_launch_are_not_exposed(self):
        listed = await self.client.list_tools()
        self.assertEqual({tool.name for tool in listed.tools}, {"aic_get_workflow_catalog", "aic_get_guidance", "aic_inspect_project", "aic_validate_recommendation"})
        for tool in listed.tools:
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertFalse(tool.annotations.destructive_hint)
            self.assertTrue(tool.annotations.idempotent_hint)
            self.assertFalse(tool.annotations.open_world_hint)
        before = sorted(path.relative_to(self.project).as_posix() for path in self.project.rglob("*"))
        for name in ("execute", "aic_launch_agents", "aic_write_file", "aic_promote_memory"):
            result = await self.client.call_tool(name, {"path": "new.txt", "text": "unauthorized"})
            self.assertTrue(result.is_error)
        after = sorted(path.relative_to(self.project).as_posix() for path in self.project.rglob("*"))
        self.assertEqual(after, before)

    async def test_source_stdio_works_outside_the_checkout_without_legacy_cli_shadowing(self):
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-B", str(ROOT / "scripts/aic-mcp.py"), "--project", str(self.project)],
            cwd=str(self.other),
            env={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        async with Client(parameters) as client:
            inspected = await client.call_tool("aic_inspect_project", {})
            self.assertFalse(inspected.is_error)
            self.assertEqual(inspected.structured_content["project"], str(self.project))
            plan = copy.deepcopy(self.plan)
            plan["approval_required"] = False
            refused = await client.call_tool("aic_validate_recommendation", {"plan": plan})
            self.assertTrue(refused.is_error)
            recovered = await client.call_tool("aic_validate_recommendation", {"plan": self.plan})
            self.assertFalse(recovered.is_error)
            self.assertIs(recovered.structured_content["approval_required"], True)
            await self._assert_published_bounds(client)

    async def test_startup_needs_an_explicit_existing_absolute_project(self):
        from aic.scripts.aiclib.safety import AICError

        for root in (Path("."), self.base / "missing", self.project / "README.md"):
            with self.subTest(root=root), self.assertRaises(AICError):
                self.module.build_server(root)
        alias = self.base / "project-alias"
        alias.symlink_to(self.project, target_is_directory=True)
        with self.assertRaises(AICError):
            self.module.build_server(alias)


if __name__ == "__main__":
    unittest.main()
