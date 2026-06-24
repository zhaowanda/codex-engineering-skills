from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/core/code-design-quality-reviewer/scripts/design_quality.py"
spec = importlib.util.spec_from_file_location("design_quality", SCRIPT)
design_quality = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(design_quality)


def assert_finding(result: dict, area: str, severity: str, message_part: str) -> None:
    for item in result.get("findings", []):
        if item.get("area") == area and item.get("severity") == severity and message_part in item.get("message", ""):
            return
    raise AssertionError(f"missing finding area={area} severity={severity} message~={message_part}; findings={result.get('findings')}")


def test_controller_direct_mapper_blocks() -> None:
    diff = """diff --git a/src/api/DeviceController.java b/src/api/DeviceController.java
@@ -10,0 +11,5 @@
+@GetMapping("/device/list")
+public List<Device> list() {
+    return deviceMapper.selectList(null);
+}
"""
    result = design_quality.review(diff, requirement_id="REQ-1")
    assert result["schema"] == "codex-code-design-quality-review-v1"
    assert result["decision"] == "block"
    assert_finding(result, "responsibility_boundary", "blocker", "Controller appears to call mapper")


def test_frontend_permission_needs_refactor() -> None:
    diff = """diff --git a/src/views/settlement/index.vue b/src/views/settlement/index.vue
@@ -20,0 +21,5 @@
+if (this.user.roleId === 'admin' && this.form.tenantId === this.user.tenantId) {
+  this.permission = true
+}
+this.$axios.post('/api/settlement/save', this.form)
"""
    result = design_quality.review(diff)
    assert result["decision"] == "needs_refactor"
    assert_finding(result, "permission_boundary_assessment", "high", "Frontend appears to contain permission")


def test_service_multi_write_without_transaction_needs_refactor() -> None:
    diff = """diff --git a/src/service/SettlementService.java b/src/service/SettlementService.java
@@ -30,0 +31,8 @@
+public void settle(Order order) {
+    orderMapper.updateById(order);
+    billMapper.insert(toBill(order));
+    payLogMapper.save(toLog(order));
+}
"""
    result = design_quality.review(diff)
    assert result["decision"] == "needs_refactor"
    assert_finding(result, "data_flow_assessment", "high", "multiple writes without visible transaction")


def test_secret_and_loop_blocks() -> None:
    fake_secret = "sk-" + "abcdefghijklmnopqrstuvwx"
    diff = """diff --git a/src/service/ReportService.java b/src/service/ReportService.java
@@ -40,0 +41,10 @@
+public void push(List<Long> ids) {
+    String token = "__FAKE_SECRET__";
+    for (Long id : ids) {
+        List<Row> rows = rowMapper.selectList(id);
+        httpClient.post(url, rows);
+    }
+}
""".replace("__FAKE_SECRET__", fake_secret)
    result = design_quality.review(diff)
    assert result["decision"] == "block"
    assert_finding(result, "performance_assessment", "high", "Loop may contain DB/API/network")
    assert_finding(result, "security_assessment", "blocker", "Hardcoded secret")


def test_resolve_lifecycle_can_pass_when_all_active_mediums_closed() -> None:
    diff = """diff --git a/src/DeviceType.java b/src/DeviceType.java
@@ -1,0 +2,6 @@
+map.put("OBD_DEVICE", "OBD_DEVICE");
+dto.setType("OBD_DEVICE");
+return "OBD_DEVICE";
"""
    result = design_quality.review(diff)
    assert result["decision"] == "needs_refactor"
    resolved = result
    for item in list(result["findings"]):
        resolved = design_quality.resolve_findings(resolved, item["finding_id"], "recheck_passed", "Moved to enum and rechecked.")
    assert resolved["decision"] == "pass"
    valid, issues = design_quality.validate(resolved)
    assert valid, issues


def run_all() -> None:
    test_controller_direct_mapper_blocks()
    test_frontend_permission_needs_refactor()
    test_service_multi_write_without_transaction_needs_refactor()
    test_secret_and_loop_blocks()
    test_resolve_lifecycle_can_pass_when_all_active_mediums_closed()


if __name__ == "__main__":
    run_all()
    print("PASS code_design_quality_reviewer tests")
