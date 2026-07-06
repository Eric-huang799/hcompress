"""Contract tests for interfaces/ — verify ABCs can't be instantiated, subclasses must implement all methods."""

import pytest
from hcompress.interfaces import (
    IEntropyCodec,
    ITransform,
    IFilter,
    IMatchFinder,
    IChecksum,
    IIOBackend,
    IIOBitStream,
    IBlockSplitter,
    ICompressHook,
    IDecompressHook,
    IObserver,
    IExtension,
)


ALL_INTERFACES = [
    IEntropyCodec,
    ITransform,
    IFilter,
    IMatchFinder,
    IChecksum,
    IIOBackend,
    IIOBitStream,
    IBlockSplitter,
    ICompressHook,
    IDecompressHook,
    IObserver,
    IExtension,
]


class TestCannotInstantiateABC:
    @pytest.mark.parametrize("iface", ALL_INTERFACES)
    def test_cannot_instantiate(self, iface):
        with pytest.raises(TypeError):
            iface()


class TestSubclassMustImplementAll:
    def test_itransform_must_implement_forward_reverse(self):
        class Bad(ITransform):
            pass
        with pytest.raises(TypeError):
            Bad()

    def test_ientropycodec_must_implement_encode_decode(self):
        class Bad(IEntropyCodec):
            pass
        with pytest.raises(TypeError):
            Bad()

    def test_ichecksum_must_implement_compute_verify(self):
        class Bad(IChecksum):
            pass
        with pytest.raises(TypeError):
            Bad()

    def test_iextension_must_implement_all(self):
        class Bad(IExtension):
            pass
        with pytest.raises(TypeError):
            Bad()


class TestValidSubclass:
    def test_minimal_ichecksum(self):
        class MyChecksum(IChecksum):
            checksum_id = 99
            digest_size = 4

            def compute(self, data):
                return b"\x00" * 4

            def verify(self, data, expected):
                return True

        cs = MyChecksum()
        assert cs.checksum_id == 99
        assert cs.compute(b"test") == b"\x00" * 4

    def test_minimal_itransform(self):
        class NoOp(ITransform):
            name = "noop"

            def forward(self, data):
                return data

            def reverse(self, data):
                return data

        t = NoOp()
        assert t.forward(b"hello") == b"hello"
        assert t.reverse(b"hello") == b"hello"


class TestImports:
    """Verify interfaces can be imported from the package root."""

    def test_import_from_hcompress_interfaces(self):
        from hcompress import interfaces
        assert hasattr(interfaces, "IEntropyCodec")
        assert hasattr(interfaces, "ITransform")
        assert hasattr(interfaces, "IExtension")

    def test_import_from_package(self):
        # The top-level package doesn't re-export interfaces (by design)
        # but should at least exist
        import hcompress
        assert hcompress.__version__ == "0.1.0"
