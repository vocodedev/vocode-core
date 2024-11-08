import unittest
from vocode.streaming.utils import interpolate_memories

class TestMemoryInterpolation(unittest.TestCase):
    def setUp(self):
        self.test_memories = {
            "name": {"value": "John"},
            "age": {"value": "30"},
            "missing_value": {"value": "MISSING"},
            "empty": {"value": ""}
        }

    def test_basic_interpolation(self):
        """Test basic memory interpolation with existing keys"""
        text = "Hello [[name]], you are [[age]] years old."
        expected = "Hello John, you are 30 years old."
        result = interpolate_memories(text, self.test_memories)
        self.assertEqual(result, expected)

    def test_missing_memory(self):
        """Test handling of keys that don't exist in memories"""
        text = "Hello [[nonexistent]]!"
        expected = "Hello [[nonexistent]]!"
        result = interpolate_memories(text, self.test_memories)
        self.assertEqual(result, expected)

    def test_missing_value_placeholder(self):
        """Test handling of 'MISSING' value placeholder"""
        text = "Value: [[missing_value]]"
        expected = "Value: [[missing_value]]"
        result = interpolate_memories(text, self.test_memories)
        self.assertEqual(result, expected)

    def test_empty_value(self):
        """Test handling of empty values"""
        text = "Empty value: [[empty]]"
        expected = "Empty value: "
        result = interpolate_memories(text, self.test_memories)
        self.assertEqual(result, expected)

    def test_multiple_replacements(self):
        """Test multiple replacements in the same text"""
        text = "[[name]] is [[age]] and [[name]] likes to code"
        expected = "John is 30 and John likes to code"
        result = interpolate_memories(text, self.test_memories)
        self.assertEqual(result, expected)

    def test_no_placeholders(self):
        """Test text with no placeholders"""
        text = "Hello, this is a normal text"
        expected = "Hello, this is a normal text"
        result = interpolate_memories(text, self.test_memories)
        self.assertEqual(result, expected)

    def test_empty_text(self):
        """Test empty input text"""
        text = ""
        expected = ""
        result = interpolate_memories(text, self.test_memories)
        self.assertEqual(result, expected)

    def test_empty_memories(self):
        """Test with empty memories dictionary"""
        text = "Hello [[name]]!"
        expected = "Hello [[name]]!"
        result = interpolate_memories(text, {})
        self.assertEqual(result, expected)

    def test_invalid_placeholder_format(self):
        """Test invalid placeholder formats"""
        text = "Hello [[]] [[name] [age]]"
        expected = "Hello [[]] [[name] [age]]"
        result = interpolate_memories(text, self.test_memories)
        self.assertEqual(result, expected)

    def test_special_characters(self):
        """Test handling of special characters in memory values"""
        memories_with_special_chars = {
            "special": {"value": "!@#$%^&*()"},
            "with_spaces": {"value": "hello world"}
        }
        text = "Special chars: [[special]], Spaces: [[with_spaces]]"
        expected = "Special chars: !@#$%^&*(), Spaces: hello world"
        result = interpolate_memories(text, memories_with_special_chars)
        self.assertEqual(result, expected)
