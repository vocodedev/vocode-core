import sys
import os.path as path
# add vocode_python to path so we can use
# from vocode import foo inside vocode package
parent_dir = path.abspath(path.dirname(__file__))
sys.path.append(parent_dir)
print(parent_dir)
print(sys.path)