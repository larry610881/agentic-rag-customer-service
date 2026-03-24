"""Dataset Loader BDD Step Definitions"""

import textwrap

import pytest
import yaml
from pytest_bdd import given, scenarios, then, when

from prompt_optimizer.dataset import (
    Dataset,
    DatasetLoader,
    DatasetValidationError,
)

scenarios("unit/prompt_optimizer/dataset.feature")


@pytest.fixture
def context():
    return {}


@pytest.fixture
def loader():
    return DatasetLoader()


# ═══════════════════════════════════════════════════════════════
# Given steps
# ═══════════════════════════════════════════════════════════════

VALID_YAML = textwrap.dedent("""\
    schema_version: "1.0"
    metadata:
      tenant_id: "t-001"
      bot_id: "b-001"
      description: "測試用 dataset"
    test_cases:
      - id: "tc-01"
        question: "你好"
        priority: "P1"
        assertions:
          - type: "response_not_empty"
      - id: "tc-02"
        question: "退貨政策是什麼？"
        priority: "P0"
        assertions:
          - type: "contains_any"
            params: { keywords: ["退貨", "退款"] }
""")


@given("一個有效的 dataset YAML 內容")
def given_valid_yaml(context):
    context["yaml_content"] = VALID_YAML
    context["expected_count"] = 2


INCLUDE_MAIN_YAML = textwrap.dedent("""\
    schema_version: "1.0"
    metadata:
      description: "含 includes 的 dataset"
    includes:
      - "extra_cases.yaml"
    test_cases:
      - id: "main-01"
        question: "主檔案問題"
        assertions:
          - type: "response_not_empty"
""")

INCLUDE_EXTRA_YAML = textwrap.dedent("""\
    test_cases:
      - id: "extra-01"
        question: "額外問題 1"
        assertions:
          - type: "response_not_empty"
      - id: "extra-02"
        question: "額外問題 2"
        assertions:
          - type: "response_not_empty"
""")


@given("一個含 includes 的 dataset YAML")
def given_includes_yaml(context):
    context["yaml_content"] = INCLUDE_MAIN_YAML


@given("被 include 的檔案存在")
def given_include_files_exist(context, tmp_path):
    extra_file = tmp_path / "extra_cases.yaml"
    extra_file.write_text(INCLUDE_EXTRA_YAML)
    context["base_dir"] = tmp_path


MISSING_METADATA_YAML = textwrap.dedent("""\
    schema_version: "1.0"
    test_cases:
      - id: "tc-01"
        question: "你好"
""")


@given("一個缺少 metadata 的 dataset YAML")
def given_missing_metadata_yaml(context):
    context["yaml_content"] = MISSING_METADATA_YAML


UNKNOWN_ASSERTION_YAML = textwrap.dedent("""\
    schema_version: "1.0"
    metadata:
      description: "包含未知 assertion"
    test_cases:
      - id: "tc-01"
        question: "你好"
        assertions:
          - type: "totally_fake_assertion"
""")


@given("一個使用未知 assertion type 的 dataset YAML")
def given_unknown_assertion_yaml(context):
    context["yaml_content"] = UNKNOWN_ASSERTION_YAML


DUPLICATE_ID_YAML = textwrap.dedent("""\
    schema_version: "1.0"
    metadata:
      description: "重複 ID"
    test_cases:
      - id: "dup-01"
        question: "問題 A"
        assertions:
          - type: "response_not_empty"
      - id: "dup-01"
        question: "問題 B"
        assertions:
          - type: "response_not_empty"
""")


@given("一個含有重複 case ID 的 dataset YAML")
def given_duplicate_id_yaml(context):
    context["yaml_content"] = DUPLICATE_ID_YAML


DEFAULT_ASSERTIONS_YAML = textwrap.dedent("""\
    schema_version: "1.0"
    metadata:
      description: "含 default_assertions"
    default_assertions:
      - type: "response_not_empty"
      - type: "max_length"
        params: { max_chars: 500 }
    test_cases:
      - id: "tc-01"
        question: "你好"
        assertions:
          - type: "contains_any"
            params: { keywords: ["你好"] }
      - id: "tc-02"
        question: "再見"
""")


@given("一個含 default_assertions 的 dataset YAML")
def given_default_assertions_yaml(context):
    context["yaml_content"] = DEFAULT_ASSERTIONS_YAML


# ═══════════════════════════════════════════════════════════════
# When steps
# ═══════════════════════════════════════════════════════════════


@when("我載入該 dataset", target_fixture="result")
def when_load_dataset(context, loader):
    base_dir = context.get("base_dir")
    return loader.load_from_string(context["yaml_content"], base_dir=base_dir)


@when("我嘗試載入該 dataset", target_fixture="load_error")
def when_try_load_dataset(context, loader):
    try:
        loader.load_from_string(context["yaml_content"])
        return None
    except DatasetValidationError as e:
        return e


# ═══════════════════════════════════════════════════════════════
# Then steps
# ═══════════════════════════════════════════════════════════════


@then("應成功解析並回傳 Dataset 物件")
def then_dataset_returned(result):
    assert isinstance(result, Dataset)


@then("test_cases 數量應為預期值")
def then_test_cases_count(result, context):
    assert len(result.test_cases) == context["expected_count"]


@then("test_cases 應包含 include 檔案的 cases")
def then_includes_merged(result):
    ids = [tc.id for tc in result.test_cases]
    assert "main-01" in ids
    assert "extra-01" in ids
    assert "extra-02" in ids
    assert len(result.test_cases) == 3


@then("應拋出 DatasetValidationError")
def then_validation_error(load_error):
    assert load_error is not None
    assert isinstance(load_error, DatasetValidationError)


@then("應拋出 DatasetValidationError 並包含 assertion type 錯誤訊息")
def then_assertion_type_error(load_error):
    assert load_error is not None
    assert isinstance(load_error, DatasetValidationError)
    assert "assertion" in str(load_error).lower() or "unknown" in str(load_error).lower()


@then("應拋出 DatasetValidationError 並包含 duplicate 錯誤訊息")
def then_duplicate_error(load_error):
    assert load_error is not None
    assert isinstance(load_error, DatasetValidationError)
    msg = str(load_error).lower()
    assert "duplicate" in msg or "dup-01" in msg


@then("每個 case 的 assertions 應包含 default_assertions")
def then_default_assertions_merged(result):
    for tc in result.test_cases:
        types = [a.type for a in tc.assertions]
        assert "response_not_empty" in types, f"Case {tc.id} missing default assertion 'response_not_empty'"
        assert "max_length" in types, f"Case {tc.id} missing default assertion 'max_length'"
    # tc-01 should have defaults + its own
    tc01 = next(tc for tc in result.test_cases if tc.id == "tc-01")
    assert len(tc01.assertions) == 3  # 2 defaults + 1 own
    # tc-02 should have only defaults
    tc02 = next(tc for tc in result.test_cases if tc.id == "tc-02")
    assert len(tc02.assertions) == 2  # 2 defaults only
