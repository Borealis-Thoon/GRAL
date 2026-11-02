"""CPU-only checks of the V2701 binary boundary; no CUDA context is created."""
import ctypes
import importlib.util
import io
import os
import struct
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = Path(os.environ.get("GRAL_TEST_RUNTIME", ROOT / "gpu/runtime"))
sys.path.insert(0, str(RUNTIME))
spec = importlib.util.spec_from_file_location("gral_server", RUNTIME / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class RuntimeContract(unittest.TestCase):
    def bare(self):
        item = object.__new__(server.Server)
        item.state = server.State()
        item.descriptors = {}
        item.buffers = {}
        item.metrics = {"pipe_read_wait_ms": 0, "h2d_ms": 0, "h2d_bytes": 0}
        return item

    def test_v2701_init_accepts_actual_seed_scalars(self):
        item = self.bare()
        scalars = {f["name"]: 0 for f in server.MANIFEST["fields"]
                   if not f["constant"] and not f["cpp"].startswith("Arr<")}
        scalars.update(RnGSeed1=0xFFFFFFFE, RnGSeed2=2232121, GridRecRow=0)
        item.check_init_fields({"scalars": scalars})
        item.receive({"scalars": scalars, "payload_bytes": 0})
        self.assertEqual(item.state.RnGSeed1, 4294967294)

    def test_v2701_outputs_include_double_concentration(self):
        self.assertIn("Conz3dDouble", server.OUTPUTS)

    def test_empty_csr_has_zero_pointer_and_shape(self):
        item = self.bare()
        item.state.GridRecStart.d[0] = 9
        item.state.GridRecStart.p = 123
        item.receive({"arrays": [{"name": "GridRecStart", "dtype": "Int32", "shape": [0],
                                  "is_null": False, "bytes": 0, "offset": 0}], "payload_bytes": 0})
        self.assertEqual(item.state.GridRecStart.p, 0)
        self.assertEqual(item.state.GridRecStart.d[0], 0)

    def test_wrong_dtype_is_rejected_before_upload(self):
        item = self.bare()
        with self.assertRaisesRegex(ValueError, "dtype"):
            item.receive({"arrays": [{"name": "SourceType", "dtype": "Double", "shape": [1],
                                      "is_null": False, "bytes": 8, "offset": 0}], "payload_bytes": 8})

    def test_device_failure_forbids_export(self):
        item = self.bare()
        item.state.DeviceError = 1
        item.state.DeviceErrorPhase = 2
        item.state.DeviceErrorParticle = 17
        with self.assertRaisesRegex(RuntimeError, "nonfinite.*phase=2.*particle=17"):
            item.result()

    def test_device_failure_cannot_be_cleared_by_input(self):
        item = self.bare()
        with self.assertRaisesRegex(ValueError, "scalar"):
            item.receive({"scalars": {"DeviceError": 0}, "payload_bytes": 0})

    def test_array_exceeding_frame_is_rejected_before_read_or_upload(self):
        item = self.bare()
        header = {"arrays": [{"name": "SourceType", "dtype": "Byte", "shape": [1],
                              "is_null": False, "bytes": 1, "offset": 0}], "payload_bytes": 0}
        with patch.object(server, "read_exact", side_effect=AssertionError("Payload read before frame validation")):
            with self.assertRaisesRegex(ValueError, "Payload"):
                item.receive(header)

    def test_entire_descriptor_list_is_checked_before_first_read(self):
        item = self.bare()
        header = {"arrays": [
            {"name": "SourceType", "dtype": "Byte", "shape": [1], "is_null": False, "bytes": 1, "offset": 0},
            {"name": "GridRecStart", "dtype": "Int32", "shape": [1], "is_null": False, "bytes": 4, "offset": 1},
        ], "payload_bytes": 1}
        with patch.object(server, "read_exact", side_effect=AssertionError("Payload read before descriptor validation")):
            with self.assertRaisesRegex(ValueError, "Payload"):
                item.receive(header)

    def test_payload_length_requires_a_nonnegative_integer(self):
        for total in (-1, True, False, 0.0, "0", None):
            with self.subTest(payload_bytes=total):
                with self.assertRaisesRegex(ValueError, "Payload"):
                    self.bare().receive({"payload_bytes": total})

    def test_unclaimed_payload_is_rejected_before_read(self):
        with patch.object(server, "read_exact", side_effect=AssertionError("Payload read before total validation")):
            with self.assertRaisesRegex(ValueError, "Payload"):
                self.bare().receive({"arrays": [], "payload_bytes": 1})

    def test_partial_init_retains_omitted_arrays_and_updates_sent_arrays(self):
        # Only the CUDA driver is replaced; frame validation, upload, allocation and State updates are real.
        class MemoryCuda:
            def __init__(self):
                self.buffers = []
                self.data = {}
                self.next_address = 1

            def buffer(self, size):
                pointer = ctypes.c_uint64(self.next_address)
                self.next_address += 1
                self.buffers.append(pointer)
                self.data[pointer.value] = bytearray(size)
                return pointer

            def h2d(self, pointer, source, size):
                self.data[pointer.value][:size] = ctypes.string_at(source, size)
                return 0

            def free(self, pointer):
                del self.data[pointer.value]
                return 0

            def check(self, code, operation):
                if code:
                    raise RuntimeError(operation)

        item = self.bare()
        item.cuda = MemoryCuda()
        item.metrics.update({key: 0 for key in ('buffer_reuse_count', 'buffer_free_count',
            'buffer_allocation_count', 'device_buffer_bytes', 'peak_device_buffer_bytes')})

        def receive(arrays, payload):
            header = {'command': 'init', 'arrays': arrays, 'payload_bytes': len(payload)}
            with patch.object(server.sys, 'stdin', types.SimpleNamespace(buffer=io.BytesIO(payload))):
                item.receive(header)

        mass = {'name': 'ParticleMass', 'dtype': 'Double', 'shape': [2], 'is_null': False, 'bytes': 16, 'offset': 0}
        coordinates = {'name': 'Xcoord', 'dtype': 'Double', 'shape': [2], 'is_null': False, 'bytes': 16, 'offset': 16}
        receive([mass, coordinates], struct.pack('<4d', 2, 3, 1, 4))
        mass_pointer = item.state.ParticleMass.p
        coordinate_pointer = item.state.Xcoord.p
        mass_descriptor = dict(item.descriptors['ParticleMass'])
        mass_data = bytes(item.cuda.data[mass_pointer])

        receive([{'name': 'Xcoord', 'dtype': 'Double', 'shape': [3], 'is_null': False, 'bytes': 24, 'offset': 0}],
                struct.pack('<3d', 5, 6, 7))
        self.assertEqual(item.state.ParticleMass.p, mass_pointer)
        self.assertEqual(list(item.state.ParticleMass.d), [2])
        self.assertEqual(item.descriptors['ParticleMass'], mass_descriptor)
        self.assertEqual(bytes(item.cuda.data[mass_pointer]), mass_data)
        self.assertNotEqual(item.state.Xcoord.p, coordinate_pointer)
        self.assertEqual(list(item.state.Xcoord.d), [3])
        self.assertEqual(struct.unpack('<3d', item.cuda.data[item.state.Xcoord.p]), (5, 6, 7))

        for is_null, shape in ((True, []), (False, [0])):
            with self.subTest(is_null=is_null):
                receive([mass], struct.pack('<2d', 2, 3))
                self.assertNotEqual(item.state.ParticleMass.p, 0)
                receive([{'name': 'ParticleMass', 'dtype': 'Double', 'shape': shape,
                          'is_null': is_null, 'bytes': 0, 'offset': 0}], b'')
                self.assertEqual(item.state.ParticleMass.p, 0)
                self.assertEqual(list(item.state.ParticleMass.d), [0])


if __name__ == "__main__":
    unittest.main()
