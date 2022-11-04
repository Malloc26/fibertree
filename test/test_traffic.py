"""Tests of the Traffic class"""

import unittest
import yaml

from fibertree import Metrics, Tensor
from fibertree.model import Format, Traffic

class TestTraffic(unittest.TestCase):
    """Tests of the Traffic class"""

    def setUp(self):
        K = 8
        M = 6
        N = 7
        density = 0.5
        # Create the tensors
        A_KM = Tensor.fromRandom(
            rank_ids=[
                "K", "M"], shape=[
                K, M], density=[
                    0.9, density], seed=0)
        self.B_KN = Tensor.fromRandom(
            rank_ids=[
                "K", "N"], shape=[
                K, N], density=[
                    0.9, density], seed=1)
        self.A_MK = A_KM.swizzleRanks(rank_ids=["M", "K"])

        b_k = self.B_KN.getRoot()
        a_m = self.A_MK.getRoot()
        T_MKN = Tensor(rank_ids=["M", "K", "N"])
        t_m = T_MKN.getRoot()

        Metrics.beginCollect("tmp/test_traffic_stage0")
        Metrics.trace("M", type_="populate_1")
        Metrics.trace("K", type_="intersect_2")
        Metrics.trace("K", type_="intersect_3")
        Metrics.trace("N")
        for m, (t_k, a_k) in t_m << a_m:
            for k, (t_n, (a_val, b_n)) in t_k << (a_k & b_k):
                for n, (t_ref, b_val) in t_n << b_n:
                    t_ref += b_val
        Metrics.endCollect()

        a_m = self.A_MK.getRoot()
        self.T_MNK = T_MKN.swizzleRanks(rank_ids=["M", "N", "K"])
        t_m = self.T_MNK.getRoot()
        self.Z_MN = Tensor(rank_ids=["M", "N"])
        z_m = self.Z_MN.getRoot()

        Metrics.beginCollect("tmp/test_traffic_stage1")
        for m, (z_n, (t_n, a_k)) in z_m << (t_m & a_m):
            for n, (z_ref, t_k) in z_n << t_n:
                for k, (t_val, a_val) in t_k & a_k:
                    z_ref += t_val * a_val
        Metrics.endCollect()

        formats = yaml.safe_load("""
        A:
            M:
                format: U
                pbits: 32
            K:
                format: C
                cbits: 32
                pbits: 64
        B:
            K:
                format: U
                rhbits: 32
                pbits: 32
            N:
                format: C
                cbits: 32
                pbits: 64
        T:
            M:
                format: U
                pbits: 32
            N:
                format: C
                rhbits: 256
                fhbits: 128
                cbits: 32
                pbits: 64
            K:
                format: C
                pbits: 64
        Z:
            K:
                format: U
                rhbits: 32
                pbits: 32
            N:
                format: C
                cbits: 32
                pbits: 64
        """)

        self.A_format = Format(self.A_MK, formats["A"])
        self.B_format = Format(self.B_KN, formats["B"])
        self.T_format = Format(self.T_MNK, formats["T"])
        self.Z_format = Format(self.Z_MN, formats["Z"])
        self.formats = {"A": self.A_format, "B": self.B_format, "T": self.T_format, "Z": self.Z_format}

        # We can also have a single-stage version of Gustavson's
        b_k = self.B_KN.getRoot()
        a_m = self.A_MK.getRoot()
        Z_MN = Tensor(rank_ids=["M", "N"])
        z_m = Z_MN.getRoot()

        Metrics.beginCollect("tmp/test_traffic_single_stage")
        Metrics.trace("K", type_="intersect_0")
        Metrics.trace("K", type_="intersect_1")
        Metrics.trace("N")
        Metrics.trace("N", type_="populate_read_0")
        Metrics.trace("N", type_="populate_write_0")
        Metrics.trace("N", type_="populate_1")
        for m, (z_n, a_k) in z_m << a_m:
            for k, (a_val, b_n) in a_k & b_k:
                for n, (z_ref, b_val) in z_n << b_n:
                    z_ref += a_val * b_val
        Metrics.endCollect()

    def test_filterTrace_more_ranks(self):
        """Test filterTrace"""
        K = 8
        M = 6
        N = 7
        density = 0.15
        # Create the tensors
        A_MK = Tensor.fromRandom(
            rank_ids=[
                "M", "K"], shape=[
                M, K], density=[
                    1, density], seed=0)
        B_KN = Tensor.fromRandom(
            rank_ids=[
                "K", "N"], shape=[
                K, N], density=[
                    0.9, density], seed=1)

        b_k = B_KN.getRoot()
        a_m = A_MK.getRoot()
        Z_MN = Tensor(rank_ids=["M", "N"])
        z_m = Z_MN.getRoot()

        Metrics.beginCollect("tmp/test_filterTrace")
        Metrics.trace("M", type_="populate_1")
        Metrics.trace("N")
        for m, (z_n, a_k) in z_m << a_m:
            for k, (a_val, b_n) in a_k & b_k:
                for n, (z_ref, b_val) in z_n << b_n:
                    z_ref += a_val * b_val
        Metrics.endCollect()

        corr = [
            "M_pos,M,fiber_pos\n",
            "1,3,1\n",
            "4,5,3\n"
        ]

        Traffic.filterTrace("tmp/test_filterTrace-M-populate_1.csv",
            "tmp/test_filterTrace-N-iter.csv",
            "tmp/test_filterTrace-test.csv")

        with open("tmp/test_filterTrace-test.csv", "r") as f:
            self.assertEqual(f.readlines(), corr)

    def test_filter_trace_leader_follower(self):
        Traffic.filterTrace("tmp/test_traffic_single_stage-K-intersect_1.csv",
            "tmp/test_traffic_single_stage-K-intersect_0.csv",
            "tmp/test_filter_trace_leader_follower-test.csv")

        corr = [
            "M_pos,K_pos,M,K,fiber_pos\n",
            "0,1,0,1,1\n",
            "0,7,0,7,7\n",
            "2,0,1,0,0\n",
            "2,5,1,5,5\n",
            "4,1,2,1,1\n",
            "4,6,2,6,6\n",
            "6,0,3,0,0\n",
            "6,2,3,2,2\n",
            "6,5,3,5,5\n",
            "8,2,4,2,2\n",
            "8,6,4,6,6\n",
            "8,7,4,7,7\n",
            "10,0,5,0,0\n",
            "10,6,5,6,6\n"
        ]

        with open("tmp/test_filter_trace_leader_follower-test.csv", "r") as f:
            self.assertEqual(f.readlines(), corr)

    def test_combineTraces_one(self):
        """Call combineTraces when there is only a read"""
        Traffic._combineTraces(
            read_fn="tmp/test_traffic_stage0-M-populate_1.csv",
            comb_fn="tmp/test_combineTraces_one.csv")

        corr = [
            "M_pos,M,fiber_pos,is_write\n",
            "0,0,0,False\n",
            "2,1,1,False\n",
            "4,2,2,False\n",
            "6,3,3,False\n",
            "8,4,4,False\n",
            "10,5,5,False\n"
        ]

        with open("tmp/test_combineTraces_one.csv", "r") as f:
            self.assertEqual(f.readlines(), corr)

    def test_combineTraces_both(self):
        """Call combineTraces when there is both read and write files"""
        Traffic._combineTraces(
            read_fn="tmp/test_traffic_single_stage-N-populate_read_0.csv",
            write_fn="tmp/test_traffic_single_stage-N-populate_write_0.csv",
            comb_fn="tmp/test_combineTraces_both.csv")

        with open("tmp/test_combineTraces_both.csv", "r") as f_test, \
            open("test_traffic-test_combineTraces_both-corr.csv", "r") as f_corr:
            self.assertEqual(f_test.readlines(), f_corr.readlines())


    def test_buildNextUseTrace(self):
        """Build a trace for each use that includes when the next use is"""
        Traffic._combineTraces(
            read_fn="tmp/test_traffic_single_stage-N-populate_1.csv",
            comb_fn="tmp/test_buildNextUseTrace-comb.csv")

        Traffic._buildNextUseTrace(["K", "N"], 2,
            "tmp/test_buildNextUseTrace-comb.csv",
            "tmp/test_buildNextUseTrace_next_uses.csv")

        with open("tmp/test_buildNextUseTrace_next_uses.csv", "r") as f_test, \
             open("test_traffic-test_buildNextUseTrace-corr.csv", "r") as f_corr:
            self.assertEqual(f_test.readlines(), f_corr.readlines())

    def test_buffetTraffic_basic(self):
        """Test buffetTraffic"""
        bindings = yaml.safe_load("""
        - tensor: A
          rank: M
          type: payload
          evict-on: root
        """)
        traces = {("A", "M", "payload", "read"): "tmp/test_traffic_stage0-M-populate_1.csv"}

        bits, overflows = Traffic.buffetTraffic(bindings, self.formats, traces, 8 * 32, 4 * 32)
        self.assertEqual(bits, {"A": {"read": 8 * 32}})
        self.assertEqual(overflows, 0)

    def test_buffetTraffic_multiple_bindings(self):
        """Test buffetTraffic multiple bindings"""
        bindings = yaml.safe_load("""
        - tensor: A
          rank: M
          type: payload
          evict-on: root

        - tensor: A
          rank: K
          type: coord
          evict-on: M

        - tensor: A
          rank: K
          type: payload
          evict-on: M
        """)

        # The payloads are needed only when they are used (in the inner-most loop)
        Traffic.filterTrace(
            "tmp/test_traffic_stage0-K-intersect_2.csv",
            "tmp/test_traffic_stage0-N-iter.csv",
            "tmp/test_buffetTraffic_multiple_bindings-K_payload.csv"
        )

        traces = {
            ("A", "M", "payload", "read"): "tmp/test_traffic_stage0-M-populate_1.csv",
            ("A", "K", "coord", "read"): "tmp/test_traffic_stage0-K-intersect_2.csv",
            ("A", "K", "payload", "read"): "tmp/test_buffetTraffic_multiple_bindings-K_payload.csv"
        }

        bits, overflows = Traffic.buffetTraffic(bindings, self.formats, traces, 8 * 32 + 4 * 32 + 4 * 64, 4 * 32)
        self.assertEqual(bits, {"A": {"read": 8 * 32 + 6 * 4 * 32 + 8 * 4 * 32}})
        self.assertEqual(overflows, 0)

    def test_buffetTraffic_multiple_tensors(self):
        """Test buffetTraffic multiple tensors"""
        bindings = yaml.safe_load("""
        - tensor: A
          rank: K
          type: payload
          evict-on: M

        # Pin the K fiber of B
        - tensor: B
          rank: K
          type: payload
          evict-on: root
        """)

        # The payloads are needed only when they are used (in the inner-most loop)
        Traffic.filterTrace(
            "tmp/test_traffic_stage0-K-intersect_2.csv",
            "tmp/test_traffic_stage0-N-iter.csv",
            "tmp/test_buffetTraffic_multiple_tensors-K_2.csv"
        )

        Traffic.filterTrace(
            "tmp/test_traffic_stage0-K-intersect_3.csv",
            "tmp/test_traffic_stage0-N-iter.csv",
            "tmp/test_buffetTraffic_multiple_tensors-K_3.csv"
        )


        traces = {
            ("A", "K", "payload", "read"): "tmp/test_buffetTraffic_multiple_tensors-K_2.csv",
            ("B", "K", "payload", "read"): "tmp/test_buffetTraffic_multiple_tensors-K_3.csv"
        }

        bits, overflows = Traffic.buffetTraffic(bindings, self.formats, traces, 2 * 8 * 32, 4 * 32)
        self.assertEqual(bits, {"A": {"read": 8 * 4 * 32}, "B": {"read": 8 * 32}})
        self.assertEqual(overflows, 0)

    def test_buffetTraffic_overflow(self):
        bindings = yaml.safe_load("""
        - tensor: A
          rank: K
          type: payload
          evict-on: M

        # Pin the K fiber of B
        - tensor: B
          rank: K
          type: payload
          evict-on: root
        """)

        # The payloads are needed only when they are used (in the inner-most loop)
        Traffic.filterTrace(
            "tmp/test_traffic_stage0-K-intersect_2.csv",
            "tmp/test_traffic_stage0-N-iter.csv",
            "tmp/test_buffetTraffic_overflow-K_2.csv"
        )

        Traffic.filterTrace(
            "tmp/test_traffic_stage0-K-intersect_3.csv",
            "tmp/test_traffic_stage0-N-iter.csv",
            "tmp/test_buffetTraffic_overflow-K_3.csv"
        )


        traces = {
            ("A", "K", "payload", "read"): "tmp/test_buffetTraffic_overflow-K_2.csv",
            ("B", "K", "payload", "read"): "tmp/test_buffetTraffic_overflow-K_3.csv"
        }

        bits, overflows = Traffic.buffetTraffic(bindings, self.formats, traces, 0, 4 * 32)
        self.assertEqual(bits, {"A": {"read": 8 * 4 * 32}, "B": {"read": 8 * 32}})
        self.assertEqual(overflows, 8)

    def test_buffetTraffic_writes(self):
        """Test the buffet traffic of writes"""
        bindings = yaml.safe_load("""
        - tensor: Z
          rank: N
          type: payload
          evict-on: K
        """)

        traces = {
            ("Z", "N", "payload", "read"): "tmp/test_traffic_single_stage-N-populate_read_0.csv",
            ("Z", "N", "payload", "write"): "tmp/test_traffic_single_stage-N-populate_write_0.csv"
        }

        bits, overflows = Traffic.buffetTraffic(bindings, self.formats, traces, 16 * 32, 4 * 32)
        self.assertEqual(bits, {"Z": {"read": 17 * 4 * 32, "write": 35 * 4 * 32}})
        self.assertEqual(overflows, 0)

#     def test_cacheTraffic(self):
#         """Test cacheTraffic"""
#         bits = Traffic.cacheTraffic_old(
#             "tmp/test_traffic_stage0", self.B_KN, "K", self.B_format, 2**10)
#         corr = 480 + 288 + 288 + 480 +  0 + 288 + 288 + 96 + 0 + 0 + 288 + 288 + 0 + 0
#         self.assertEqual(bits, corr)
#
#     def test_lruTraffic(self):
#         """Test cacheTraffic"""
#         bits = Traffic.lruTraffic_old(
#             "tmp/test_traffic_stage0", self.B_KN, "K", self.B_format, 2**10 + 2**8)
#         corr = 480 + 288 + 288 + 480 + 480 + 288 + 288 + 96 + 480 + 0 + 0 + 288 + 288 + 0
#         self.assertEqual(bits, corr)
#
#     def test_streamTraffic(self):
#         """Test streamTraffic"""
#         bits = Traffic.streamTraffic_old(
#             "tmp/test_traffic_stage1", self.T_MNK, "N", self.T_format)
#         corr = 256 + 128 * 6 + (64 + 32) * 33
#
#         self.assertEqual(bits, corr)
#
#     def test_getAllUses(self):
#         """Test _getAllUses"""
#         uses = [((0, 0, 0), (1, 2, 3)), ((4, 3, 2), (1, 2, 3)),
#                 ((0, 0, 1), (1, 2, 6)), ((0, 5, 6), (10, 8, 7)),
#                 ((2, 6, 9), (10, 8, 7)), ((3, 6, 8), (10, 8, 7))]
#
#         with open("tmp/test_getAllUses-K-iter.csv", "w") as f:
#             f.write("M_pos,N_pos,K_pos,M,N,K\n")
#             for use in uses:
#                 data = [str(i) for i in use[0] + use[1]]
#                 f.write(",".join(data) + "\n")
#
#         A_MK = Tensor(rank_ids=["M", "K"])
#         result = list(Traffic._getAllUses("tmp/test_getAllUses", A_MK, "K"))
#         corr = [(use[1][0], use[1][2]) for use in uses]
#
#         self.assertEqual(result, corr)
