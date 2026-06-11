import pytest
import pylibheif


def test_exception_subclass_hierarchy():
    """Verify that all new exceptions inherit from HeifError"""
    assert issubclass(pylibheif.HeifInputDoesNotExistError, pylibheif.HeifError)
    assert issubclass(pylibheif.HeifInvalidInputError, pylibheif.HeifError)
    assert issubclass(pylibheif.HeifUnsupportedFiletypeError, pylibheif.HeifError)
    assert issubclass(pylibheif.HeifUnsupportedFeatureError, pylibheif.HeifError)
    assert issubclass(pylibheif.HeifUsageError, pylibheif.HeifError)
    assert issubclass(pylibheif.HeifMemoryAllocationError, pylibheif.HeifError)
    assert issubclass(pylibheif.HeifEncodingError, pylibheif.HeifError)
    assert issubclass(pylibheif.HeifColorProfileDoesNotExistError, pylibheif.HeifError)


def test_input_does_not_exist_error():
    """Verify that reading a nonexistent file raises HeifInputDoesNotExistError"""
    ctx = pylibheif.HeifContext()

    # Verify specific exception is raised
    with pytest.raises(pylibheif.HeifInputDoesNotExistError) as exc_info:
        ctx.read_from_file("nonexistent_file_xyz.heic")

    # Verify error code and subcode are set correctly
    assert exc_info.value.code == pylibheif.HeifErrorCode.InputDoesNotExist.value
    assert isinstance(exc_info.value.subcode, int)

    # Verify it can also be caught as HeifError (backward compatibility)
    try:
        ctx.read_from_file("nonexistent_file_xyz.heic")
    except pylibheif.HeifError as e:
        assert isinstance(e, pylibheif.HeifInputDoesNotExistError)
        assert e.code == pylibheif.HeifErrorCode.InputDoesNotExist.value


def test_invalid_input_error():
    """Verify that reading corrupted memory data raises HeifInvalidInputError"""
    ctx = pylibheif.HeifContext()
    invalid_data = b"invalid garbage data"

    with pytest.raises(pylibheif.HeifInvalidInputError) as exc_info:
        ctx.read_from_memory(invalid_data)

    assert exc_info.value.code == pylibheif.HeifErrorCode.InvalidInput.value
    assert isinstance(exc_info.value.subcode, int)

    try:
        ctx2 = pylibheif.HeifContext()
        ctx2.read_from_memory(invalid_data)
    except pylibheif.HeifError as e:
        assert isinstance(e, pylibheif.HeifInvalidInputError)
        assert e.code == pylibheif.HeifErrorCode.InvalidInput.value
