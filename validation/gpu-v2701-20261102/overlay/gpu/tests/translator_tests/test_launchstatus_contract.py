"""CPU-only CUDA-copy boundary contracts, with the driver replaced in memory."""
import ctypes
import types
import unittest
from unittest.mock import Mock

import test_dispatch_contract as dispatch
from test_runtime_contract import server


class LaunchStatusContract(unittest.TestCase):
    def make_server(self, status=(0, 0, 0)):
        item = dispatch.DispatchContract().make_server(length=16)
        del item.launch
        item.event_start, item.event_end = ctypes.c_void_p(2), ctypes.c_void_p(3)
        item.kernel_total_ms = 0.0
        item.metrics.update(kernel_device_ms=0.0, kernel_launches=0, kernel_max_device_ms=0.0,
                            status_d2h_ms=0.0, status_d2h_bytes=0)
        copies = []
        def download(target, source, size):
            copies.append((source.value, size))
            if size == 12:
                ctypes.memmove(target, (ctypes.c_int * 3)(*status), size)
            elif size == ctypes.sizeof(server.State):
                device = server.State.from_buffer_copy(item.state)
                device.RnGSeed1 = 0xFFFFFFFE
                ctypes.memmove(target, ctypes.byref(device), size)
            else:
                self.fail('Unexpected D2H copy size: ' + str(size))
            return 0
        def elapsed(target, *args):
            ctypes.cast(target, ctypes.POINTER(ctypes.c_float))[0] = 2.5
            return 0
        item.cuda = types.SimpleNamespace(check=lambda *_: None, d2h=download,
                    event_record=Mock(return_value=0), launch=Mock(return_value=0),
                    event_sync=Mock(return_value=0), event_elapsed=elapsed)
        return item, copies

    def test_each_launch_downloads_only_three_contiguous_error_fields(self):
        item, copies = self.make_server()
        before_seed = item.state.RnGSeed1 = 77
        elapsed = item.launch('fresh', 2, [ctypes.c_int(1), ctypes.c_int(2)])
        self.assertGreaterEqual(elapsed, 0)
        self.assertEqual(copies, [(item.state_address.value + server.State.DeviceError.offset, 12)])
        self.assertEqual(item.state.RnGSeed1, before_seed)
        self.assertEqual(item.metrics['status_d2h_bytes'], 12)
        self.assertEqual(item.metrics['state_d2h_bytes'], 0)
        self.assertEqual(item.metrics['kernel_device_ms'], 2.5)
        self.assertEqual(item.metrics['kernel_max_device_ms'], 2.5)
        self.assertEqual(item.metrics['kernel_launches'], 1)

    def test_full_state_is_downloaded_once_at_execute_boundary_after_chunks(self):
        item, copies = self.make_server()
        ack = item.execute(dispatch.DispatchContract().header(5, chunk=2))
        self.assertEqual([size for _, size in copies], [12, 12, 12, ctypes.sizeof(server.State)])
        self.assertEqual(item.metrics['status_d2h_bytes'], 36)
        self.assertEqual(item.metrics['state_d2h_bytes'], ctypes.sizeof(server.State))
        self.assertEqual(item.state.RnGSeed1, 0xFFFFFFFE)
        self.assertEqual(item.phase_counts['fresh'], 5)
        self.assertEqual(ack['metrics_cumulative'], item.metrics)
        self.assertEqual(item.metrics['kernel_launches'], 3)

    def test_device_error_aborts_following_chunks_and_full_state_download(self):
        item, copies = self.make_server((1, 2, 17))
        with self.assertRaisesRegex(RuntimeError, 'phase=2.*particle=17.*whole run aborted'):
            item.execute(dispatch.DispatchContract().header(5, chunk=2))
        self.assertEqual([size for _, size in copies], [12])
        self.assertEqual(item.cuda.launch.call_count, 1)
        self.assertEqual(item.phase_counts['fresh'], 0)
        self.assertEqual(item.metrics['state_d2h_bytes'], 0)
        with self.assertRaisesRegex(RuntimeError, 'results unavailable'): item.result()
        self.assertEqual([size for _, size in copies], [12])

    def test_zero_count_launches_no_kernel_but_preserves_execute_state_boundary(self):
        item, copies = self.make_server()
        ack = item.execute(dispatch.DispatchContract().header(0))
        item.cuda.launch.assert_not_called()
        self.assertEqual(copies, [(item.state_address.value, ctypes.sizeof(server.State))])
        self.assertEqual(item.metrics['status_d2h_bytes'], 0)
        self.assertEqual(item.metrics['kernel_launches'], 0)
        self.assertEqual(ack['kernel_ms'], 0)
        self.assertEqual(ack['count'], 0)

    def test_failed_status_copy_never_advances_phase_or_exports_results(self):
        item, _ = self.make_server()
        def fail(code, operation):
            if operation == 'read kernel status': raise RuntimeError('status copy failed')
        item.cuda.check = fail
        with self.assertRaisesRegex(RuntimeError, 'status copy failed'):
            item.execute(dispatch.DispatchContract().header(2))
        self.assertEqual(item.phase_counts['fresh'], 0)
        self.assertEqual(item.metrics['state_d2h_bytes'], 0)


if __name__ == '__main__':
    unittest.main()
