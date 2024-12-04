<div align="center">

### **Make a new release**

```
poetry run pytest -v
poetry build
poetry config pypi-token.pypi your-pypi-token
poetry publish
```