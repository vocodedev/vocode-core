import sys, os

class HiddenPrints:
    def __init__(self, hide=True):
        self.hide = hide
    def __enter__(self):
        if self.hide:
            self._original_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')

    def __exit__(self):
        if self.hide:
            sys.stdout.close()
            sys.stdout = self._original_stdout
