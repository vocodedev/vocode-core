import unittest

from vocode.streaming.utils import find_sparse_subarray, find_last_sparse_subarray

class TestFindSparseSubarray(unittest.TestCase):
    def test_empty_everything(self):
        actual = find_sparse_subarray([], [])
        self.assertEqual(actual, [])

    def test_empty_predicates(self):
        actual = find_sparse_subarray([1,2,3], [])
        self.assertEqual(actual, [])

    def test_no_matches(self):
        actual = find_sparse_subarray([1,2,3], [lambda x: x == 5])
        self.assertEqual(actual, None)

    def test_one_match(self):
        actual = find_sparse_subarray([1,2,3,4], [lambda x: x % 2 == 0, lambda x: x == 3])
        self.assertEqual(actual, [1,2])

    def test_multiple_matches(self):
        actual = find_sparse_subarray(["a","b","c","a","b","c"], [lambda x: x == "a", lambda x: x == "b"])
        self.assertEqual(actual, [0,1])

class TestFindLastSparseSubarray(unittest.TestCase):
    def test_empty_everything(self):
        actual = find_sparse_subarray.find_last_sparse_subarray([], [])
        self.assertEqual(actual, [])

    def test_empty_predicates(self):
        actual = find_last_sparse_subarray([1,2,3], [])
        self.assertEqual(actual, [])

    def test_no_matches(self):
        actual = find_last_sparse_subarray([1,2,3], [lambda x: x == 5])
        self.assertEqual(actual, None)

    def test_one_match(self):
        actual = find_last_sparse_subarray([1,2,3,4], [lambda x: x % 2 == 0, lambda x: x == 3])
        self.assertEqual(actual, [1,2])

    def test_multiple_matches(self):
        actual = find_last_sparse_subarray(["a","b","c","a","b","c"], [lambda x: x == "a", lambda x: x == "b"])
        self.assertEqual(actual, [3,4])
