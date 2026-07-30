import pytest
from pylibheif import (
    HeifContext,
    HeifErrorCode,
    HeifError,
    HeifInputDoesNotExistError,
    HeifInvalidInputError,
)


def test_exception_diagnostics_nonexistent_file():
    """Verify rich attributes and string representation on HeifInputDoesNotExistError."""
    ctx = HeifContext()
    with pytest.raises(HeifInputDoesNotExistError) as exc_info:
        ctx.read_from_file("non_existent_file_xyz_12345.heic")

    err = exc_info.value
    assert isinstance(err, HeifError)
    assert err.code == HeifErrorCode.InputDoesNotExist.value
    assert err.subcode == 0
    assert err.code_name == "InputDoesNotExist"
    assert err.code_enum == HeifErrorCode.InputDoesNotExist

    str_msg = str(err)
    assert "[HeifInputDoesNotExistError]" in str_msg
    assert "InputDoesNotExist" in str_msg
    assert "code=1" in str_msg

    repr_msg = repr(err)
    assert "code_name='InputDoesNotExist'" in repr_msg


def test_exception_diagnostics_invalid_input_memory():
    """Verify rich attributes on HeifInvalidInputError for corrupt memory bytes."""
    ctx = HeifContext()
    with pytest.raises(HeifInvalidInputError) as exc_info:
        ctx.read_from_memory(b"invalid corrupt data stream")

    err = exc_info.value
    assert err.code == HeifErrorCode.InvalidInput.value
    assert err.code_name == "InvalidInput"
    assert err.code_enum == HeifErrorCode.InvalidInput
    assert "[HeifInvalidInputError]" in str(err)
