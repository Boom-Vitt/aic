"""End-to-end contracts for the published MCP tool and resource schemas.

These cases use the official client. Schema checks and successful calls go through
the host stdio launcher; startup failures exercise the same launcher arguments.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from functools import wraps
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills"))

from aic.scripts.aiclib import __version__
from aic.scripts.aiclib import mcp_server

SDK_AVAILABLE = importlib.util.find_spec("mcp") is not None
if SDK_AVAILABLE:
    import jsonschema
    from mcp import Client, StdioServerParameters
    from mcp.shared.exceptions import MCPError


GUIDANCE = {
    "start": "SKILL.md",
    "workflows": "references/workflows.md",
    "templates": "references/templates.md",
    "project-plans": "references/project-plans.md",
    "routing": "references/routing.md",
    "memory": "references/memory.md",
    "safety": "references/safety.md",
    "supervision": "references/supervision.md",
    "research": "references/research.md",
    "integrations": "references/integrations.md",
}
PACKAGED_RESOURCES = {
    **{f"aic://skill/{relative}": relative for relative in GUIDANCE.values()},
    "aic://skill/assets/workflows.json": "assets/workflows.json",
    "aic://skill/assets/example-plan.json": "assets/example-plan.json",
}
TOOL_PROPERTIES = {
    "aic_get_workflow_catalog": set(),
    "aic_get_guidance": {"section"},
    "aic_inspect_project": {"max_files", "max_depth"},
    "aic_validate_recommendation": {"plan"},
}
MARKER = "PRIVATE_MCP_CONTRACT_MARKER"
SECRET = "PRIVATE_SCHEMA_VALUE_9f3c"


def stdio_session(test):
    """Drive one host-started stdio server for a single test."""
    @wraps(test)
    async def run(self):
        env = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
        for key, value in os.environ.items():
            if key.startswith("COVERAGE_"):
                env[key] = value
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-B", str(ROOT / "scripts/aic-mcp.py"), "--project", str(self.project)],
            cwd=str(self.outside),
            env=env,
        )
        async with Client(parameters) as self.client:
            await test(self)
    return run


def schema_accepts(schema, instance) -> bool:
    try:
        jsonschema.validate(instance, schema)
    except jsonschema.ValidationError:
        return False
    return True


def tool_contract(tool) -> dict:
    data = tool.model_dump(mode="json", exclude_none=True)
    return {key: data.get(key) for key in ("name", "description", "input_schema", "output_schema", "annotations")}


@unittest.skipUnless(SDK_AVAILABLE, "Install the optional MCP extra to exercise the protocol")
class McpSchemaContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixtures = ROOT / ".work"
        fixtures.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="mcp-contract-", dir=fixtures)
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.project = self.base / "approved-project"
        self.project.mkdir()
        self.outside = self.base / "outside"
        self.outside.mkdir()
        (self.project / "README.md").write_text(MARKER, encoding="utf-8")
        (self.project / "notes.txt").write_text("plain note", encoding="utf-8")
        nested = self.project / "src" / "app.py"
        nested.parent.mkdir()
        nested.write_text("print('nested')\n", encoding="utf-8")
        (self.project / ".env").write_text(SECRET, encoding="utf-8")
        self.skill = ROOT / "skills" / "aic"
        self.plan = json.loads((self.skill / "assets" / "example-plan.json").read_text(encoding="utf-8"))
        self.before = self._snapshot()

    def tearDown(self):
        self.assertEqual(self._snapshot(), self.before)

    def _snapshot(self):
        files = {}
        for path in self.project.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            files[path.relative_to(self.project).as_posix()] = path.read_bytes()
        return files

    def packaged(self, relative: str) -> str:
        return (self.skill / relative).read_text(encoding="utf-8")

    async def tools(self):
        listed = await self.client.list_tools()
        self.assertIsNone(listed.next_cursor)
        return {tool.name: tool for tool in listed.tools}

    def assert_hidden(self, result):
        rendered = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
        self.assertNotIn(MARKER, rendered)
        self.assertNotIn(SECRET, rendered)
        self.assertNotIn("Traceback", rendered)

    def assert_success(self, result, output_schema):
        self.assertFalse(result.is_error)
        self.assertIsInstance(result.structured_content, dict)
        payload = result.structured_content
        jsonschema.validate(payload, output_schema)
        texts = [block.text for block in result.content if getattr(block, "type", None) == "text"]
        self.assertEqual(len(texts), 1)
        self.assertEqual(json.loads(texts[0]), payload)
        self.assert_hidden(result)
        return payload

    @stdio_session
    async def test_stdio_publishes_server_identity_and_the_same_tool_schemas(self):
        self.assertEqual(self.client.server_info.name, "AIC")
        self.assertEqual(self.client.server_info.version, __version__)
        self.assertEqual(self.client.protocol_version, "2026-07-28")
        self.assertIn("never project contents", self.client.instructions)
        self.assertIn("explicit approval is separate", self.client.instructions)
        capabilities = self.client.server_capabilities
        self.assertFalse(capabilities.resources.subscribe)
        self.assertFalse(capabilities.resources.list_changed)
        self.assertFalse(capabilities.tools.list_changed)
        prompts = await self.client.list_prompts()
        templates = await self.client.list_resource_templates()
        self.assertEqual(prompts.prompts, [])
        self.assertEqual(templates.resource_templates, [])

        async with Client(mcp_server.build_server(self.project)) as local:
            local_tools = await local.list_tools()
        remote = await self.client.list_tools()
        self.assertEqual(
            [tool_contract(tool) for tool in remote.tools],
            [tool_contract(tool) for tool in local_tools.tools],
        )
        self.assertEqual([tool.name for tool in remote.tools], list(TOOL_PROPERTIES))

    @stdio_session
    async def test_published_input_schemas_describe_only_the_four_read_only_tools(self):
        found = await self.tools()
        self.assertEqual(set(found), set(TOOL_PROPERTIES))
        for name, properties in TOOL_PROPERTIES.items():
            tool = found[name]
            schema = tool.input_schema
            jsonschema.validators.validator_for(schema).check_schema(schema)
            self.assertEqual(schema.get("type"), "object")
            self.assertIs(schema.get("additionalProperties"), False)
            self.assertEqual(set(schema.get("properties", {})), properties)
            self.assertTrue(tool.description)
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertFalse(tool.annotations.destructive_hint)
            self.assertTrue(tool.annotations.idempotent_hint)
            self.assertFalse(tool.annotations.open_world_hint)
            output = tool.output_schema
            jsonschema.validators.validator_for(output).check_schema(output)
            self.assertEqual(output.get("type"), "object")
        self.assertFalse(found["aic_get_workflow_catalog"].input_schema.get("required"))
        self.assertFalse(found["aic_get_guidance"].input_schema.get("required"))
        self.assertFalse(found["aic_inspect_project"].input_schema.get("required"))
        self.assertEqual(found["aic_validate_recommendation"].input_schema["required"], ["plan"])
        guidance = found["aic_get_guidance"].input_schema["properties"]["section"]
        limits = found["aic_inspect_project"].input_schema["properties"]
        plan = found["aic_validate_recommendation"].input_schema["properties"]["plan"]
        self.assertEqual(guidance.get("type"), "string")
        self.assertEqual(guidance.get("default"), "start")
        self.assertEqual(limits["max_files"].get("type"), "integer")
        self.assertEqual(limits["max_files"].get("default"), 200)
        self.assertEqual(limits["max_depth"].get("type"), "integer")
        self.assertEqual(limits["max_depth"].get("default"), 4)
        self.assertNotIn("default", plan)
        if "enum" in guidance:
            self.assertEqual(set(guidance["enum"]), set(GUIDANCE))
        else:
            for section in GUIDANCE:
                self.assertIn(section, found["aic_get_guidance"].description)
        for name, bound in (("max_files", (1, 10000)), ("max_depth", (0, 32))):
            low, high = bound
            prop = limits[name]
            self.assertTrue(schema_accepts(prop, low))
            self.assertTrue(schema_accepts(prop, high))
            if "minimum" in prop:
                self.assertEqual(prop["minimum"], low)
            if "maximum" in prop:
                self.assertEqual(prop["maximum"], high)
        if "type" in plan:
            self.assertEqual(plan["type"], "object")

    @stdio_session
    async def test_schema_invalid_values_fail_on_the_schema_and_the_server(self):
        found = await self.tools()
        rejected = (
            ("aic_get_workflow_catalog", {"path": SECRET}),
            ("aic_get_guidance", {"section": 1}),
            ("aic_get_guidance", {"section": None}),
            ("aic_inspect_project", {"max_files": True}),
            ("aic_inspect_project", {"max_files": SECRET}),
            ("aic_inspect_project", {"max_depth": 1.5}),
            ("aic_inspect_project", {"max_files": 1, "unexpected": SECRET}),
            ("aic_validate_recommendation", {}),
            ("aic_validate_recommendation", {"plan": self.plan, "execute": True}),
        )
        for name, arguments in rejected:
            with self.subTest(name=name, arguments=sorted(arguments)):
                self.assertFalse(schema_accepts(found[name].input_schema, arguments))
                result = await self.client.call_tool(name, arguments)
                self.assertTrue(result.is_error)
                self.assertIsNone(result.structured_content)
                self.assert_hidden(result)
        recovered = await self.client.call_tool("aic_get_workflow_catalog", {})
        self.assertFalse(recovered.is_error)

    @stdio_session
    async def test_omitted_defaults_and_enforced_limits_round_trip(self):
        found = await self.tools()
        guidance = self.assert_success(
            await self.client.call_tool("aic_get_guidance", {}),
            found["aic_get_guidance"].output_schema,
        )
        self.assertEqual(guidance, {"uri": "aic://skill/SKILL.md", "text": self.packaged("SKILL.md")})
        inspected = self.assert_success(
            await self.client.call_tool("aic_inspect_project", {}),
            found["aic_inspect_project"].output_schema,
        )
        self.assertEqual(inspected["limits"]["max_files"], 200)
        self.assertEqual(inspected["limits"]["max_depth"], 4)
        for name, arguments in (
            ("low-files", {"max_files": 1, "max_depth": 0}),
            ("high-files", {"max_files": 10000, "max_depth": 32}),
        ):
            with self.subTest(name=name):
                self.assertTrue(schema_accepts(found["aic_inspect_project"].input_schema, arguments))
                payload = self.assert_success(
                    await self.client.call_tool("aic_inspect_project", arguments),
                    found["aic_inspect_project"].output_schema,
                )
                self.assertEqual(payload["limits"]["max_files"], arguments["max_files"])
                self.assertEqual(payload["limits"]["max_depth"], arguments["max_depth"])
        shallow = await self.client.call_tool("aic_inspect_project", {"max_files": 1, "max_depth": 0})
        shallow_payload = self.assert_success(shallow, found["aic_inspect_project"].output_schema)
        self.assertEqual(len(shallow_payload["files"]), 1)
        self.assertTrue(shallow_payload["truncated"])
        self.assertNotIn("src/app.py", [item["path"] for item in shallow_payload["files"]])
        for arguments in ({"max_files": 0}, {"max_files": 10001}, {"max_depth": -1}, {"max_depth": 33}):
            with self.subTest(arguments=arguments):
                result = await self.client.call_tool("aic_inspect_project", arguments)
                self.assertTrue(result.is_error)
                self.assert_hidden(result)

    @stdio_session
    async def test_guidance_and_resources_return_the_packaged_allowlist(self):
        found = await self.tools()
        listed = await self.client.list_resources()
        self.assertIsNone(listed.next_cursor)
        by_uri = {str(resource.uri): resource for resource in listed.resources}
        self.assertEqual(set(by_uri), set(PACKAGED_RESOURCES))
        for section, relative in GUIDANCE.items():
            uri = f"aic://skill/{relative}"
            with self.subTest(section=section):
                payload = self.assert_success(
                    await self.client.call_tool("aic_get_guidance", {"section": section}),
                    found["aic_get_guidance"].output_schema,
                )
                body = await self.resource_text(uri)
                packaged = self.packaged(relative)
                self.assertEqual(payload, {"uri": uri, "text": packaged})
                self.assertEqual(body, packaged)
                self.assertEqual(by_uri[uri].mime_type, "text/markdown")
                self.assertNotIn(MARKER, packaged)
        for uri, relative in PACKAGED_RESOURCES.items():
            if not relative.endswith(".json"):
                continue
            with self.subTest(uri=uri):
                body = await self.resource_text(uri)
                self.assertEqual(body, self.packaged(relative))
                self.assertEqual(json.loads(body), json.loads(self.packaged(relative)))
                self.assertEqual(by_uri[uri].mime_type, "application/json")
        catalog = self.assert_success(
            await self.client.call_tool("aic_get_workflow_catalog", {}),
            found["aic_get_workflow_catalog"].output_schema,
        )
        again = self.assert_success(
            await self.client.call_tool("aic_get_workflow_catalog", {}),
            found["aic_get_workflow_catalog"].output_schema,
        )
        packaged_catalog = json.loads(self.packaged("assets/workflows.json"))
        resource_catalog = json.loads(await self.resource_text("aic://skill/assets/workflows.json"))
        self.assertEqual(catalog, packaged_catalog)
        self.assertEqual(again, catalog)
        self.assertEqual(resource_catalog, packaged_catalog)
        self.assertEqual(catalog["schema_version"], 3)
        for uri in (
            (self.project / ".env").as_uri(),
            "aic://project/.env",
            "aic://skill/references/../../.env",
            "aic://skill/references/unknown.md",
        ):
            with self.subTest(uri=uri):
                with self.assertRaises(MCPError):
                    await self.client.read_resource(uri)
        recovered = await self.client.call_tool("aic_get_workflow_catalog", {})
        self.assertFalse(recovered.is_error)

    @stdio_session
    async def test_inspection_and_recommendation_results_match_their_output_schemas(self):
        found = await self.tools()
        inspected = self.assert_success(
            await self.client.call_tool("aic_inspect_project", {"max_files": 10, "max_depth": 2}),
            found["aic_inspect_project"].output_schema,
        )
        self.assertEqual(inspected["project"], str(self.project))
        self.assertEqual(inspected["schema_version"], 1)
        paths = [item["path"] for item in inspected["files"]]
        self.assertIn("README.md", paths)
        self.assertIn("src/app.py", paths)
        self.assertNotIn(".env", paths)
        for item in inspected["files"]:
            self.assertEqual(set(item), {"path", "size_bytes"})
            self.assertIsInstance(item["size_bytes"], int)
        self.assertNotIn(MARKER, json.dumps(inspected))
        valid = self.assert_success(
            await self.client.call_tool("aic_validate_recommendation", {"plan": self.plan}),
            found["aic_validate_recommendation"].output_schema,
        )
        self.assertEqual(valid, self.plan)
        self.assertIs(valid["approval_required"], True)
        self.assertEqual(valid["next_action"], "recommend")
        evidenced = dict(self.plan)
        evidenced["evidence"] = [{"path": "README.md", "observation": "A README filename exists."}]
        checked = self.assert_success(
            await self.client.call_tool("aic_validate_recommendation", {"plan": evidenced}),
            found["aic_validate_recommendation"].output_schema,
        )
        self.assertEqual(checked["evidence"], evidenced["evidence"])
        self.assertNotIn(MARKER, json.dumps(checked))
        for plan in (SECRET, json.dumps(self.plan), None, [], True):
            with self.subTest(plan=type(plan).__name__):
                result = await self.client.call_tool("aic_validate_recommendation", {"plan": plan})
                self.assertTrue(result.is_error)
                self.assert_hidden(result)
        unapproved = dict(self.plan)
        unapproved["approval_required"] = False
        refused = await self.client.call_tool("aic_validate_recommendation", {"plan": unapproved})
        self.assertTrue(refused.is_error)
        self.assert_hidden(refused)

    async def resource_text(self, uri: str) -> str:
        result = await self.client.read_resource(uri)
        self.assertEqual(len(result.contents), 1)
        content = result.contents[0]
        self.assertEqual(str(content.uri), uri)
        self.assertIsInstance(content.text, str)
        self.assertNotIn(MARKER, content.text)
        self.assertNotIn(SECRET, content.text)
        return content.text


class McpStartupContractTests(unittest.TestCase):
    def setUp(self):
        fixtures = ROOT / ".work"
        fixtures.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="mcp-startup-", dir=fixtures)
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.project = self.base / "approved-project"
        self.project.mkdir()
        (self.project / "README.md").write_text(MARKER, encoding="utf-8")
        self.outside = self.base / "outside"
        self.outside.mkdir()

    def assert_startup_rejects(self, argv):
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            with self.assertRaises(SystemExit) as caught:
                mcp_server.main(argv)
        self.assertEqual(caught.exception.code, 2)
        message = buffer.getvalue()
        self.assertNotIn("Traceback", message)
        self.assertNotIn(MARKER, message)
        return message

    def test_startup_requires_an_explicit_existing_absolute_directory(self):
        missing = self.base / "missing"
        alias = self.base / "project-alias"
        alias.symlink_to(self.project, target_is_directory=True)
        cases = {
            "omitted": [],
            "relative": ["--project", "."],
            "missing": ["--project", str(missing)],
            "file": ["--project", str(self.project / "README.md")],
            "symlink": ["--project", str(alias)],
        }
        for name, argv in cases.items():
            with self.subTest(name=name):
                message = self.assert_startup_rejects(argv)
                if name == "omitted":
                    self.assertIn("--project", message)
                else:
                    self.assertIn("existing absolute directory", message)

    def test_startup_without_the_optional_extra_fails_before_serving(self):
        code = "\n".join((
            "import sys",
            "sys.path.insert(0, sys.argv[1])",
            "from aic.scripts.aiclib.mcp_server import main",
            "raise SystemExit(main(['--project', sys.argv[2]]))",
        ))
        completed = subprocess.run(
            [sys.executable, "-S", "-B", "-c", code, str(ROOT / "skills"), str(self.project)],
            cwd=str(self.outside),
            env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(completed.stdout, "")
        self.assertIn(
            "The MCP transport requires AIC's optional mcp extra (official SDK 2.3.0).",
            completed.stderr,
        )
        self.assertNotIn("Traceback", completed.stderr)
        self.assertNotIn(MARKER, completed.stderr)


if __name__ == "__main__":
    unittest.main()
