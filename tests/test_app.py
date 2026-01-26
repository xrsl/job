import json

import pytest
from click.exceptions import Exit
from unittest.mock import patch
from job.app import (
    load_prompt,
    create_app_agent,
    read_context_files,
    read_source_file,
    _write_source_file,
    _apply_draft_to_files,
)
from job.core import JobAppDraft


def test_load_prompt_success():
    """Test loading a prompt successfully."""
    # Assuming the prompt file exists
    prompt_name = "application-writer"
    content = load_prompt(prompt_name)
    assert isinstance(content, str)
    assert len(content) > 0


def test_load_prompt_file_not_found():
    """Test loading a non-existent prompt raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_prompt("non-existent")


@patch("job.app.load_prompt")
def test_create_app_agent(mock_load_prompt):
    """Test creating an app agent."""
    mock_load_prompt.return_value = "Test prompt"
    agent = create_app_agent("test")
    assert agent is not None
    # Check that it's an Agent instance, but since it's pydantic_ai, just check it's created
    mock_load_prompt.assert_called_once_with("application-writer")


def test_read_context_files_success(tmp_path):
    """Test reading context files successfully."""
    # Create temporary files
    file1 = tmp_path / "file1.txt"
    file1.write_text("Content 1")
    file2 = tmp_path / "file2.txt"
    file2.write_text("Content 2")

    paths = [str(file1), str(file2)]
    content = read_context_files(paths)
    assert "Content 1" in content
    assert "Content 2" in content


def test_read_context_files_file_not_found(tmp_path):
    """Test reading context files when one doesn't exist."""
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("Existing content")

    paths = [str(existing_file), str(tmp_path / "nonexistent.txt")]

    with pytest.raises(Exit):  # Since typer.Exit is raised
        read_context_files(paths)


def test_read_source_file_toml(tmp_path):
    """Test reading a TOML source file."""
    toml_file = tmp_path / "test.toml"
    toml_file.write_text('key = "value"')

    data = read_source_file(str(toml_file))
    assert data == {"key": "value"}


def test_read_source_file_yaml(tmp_path):
    """Test reading a YAML source file."""
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text("key: value")

    data = read_source_file(str(yaml_file))
    assert data == {"key": "value"}


def test_read_source_file_not_found():
    """Test reading a non-existent source file."""
    with pytest.raises(Exit):
        read_source_file("nonexistent.toml")


def test_write_source_file_toml(tmp_path):
    """Test writing to a TOML source file."""
    toml_file = tmp_path / "test.toml"
    data = {"key": "value"}
    _write_source_file(str(toml_file), data, "root")
    content = toml_file.read_text()
    assert "root" in content
    assert "key" in content


def test_write_source_file_yaml(tmp_path):
    """Test writing to a YAML source file."""
    yaml_file = tmp_path / "test.yaml"
    data = {"key": "value"}
    _write_source_file(str(yaml_file), data, "root")
    content = yaml_file.read_text()
    assert "root" in content
    assert "key" in content


@patch("job.app._write_source_file")
def test_apply_draft_to_files(mock_write):
    """Test applying draft to files."""
    draft = JobAppDraft(
        job_id=1,
        model_name="test",
        cv_content=json.dumps({"cv": "content"}),
        letter_content=json.dumps({"letter": "content"}),
        source_cv_path="cv.toml",
        source_letter_path="letter.yaml",
    )
    _apply_draft_to_files(draft)
    assert mock_write.call_count == 2
