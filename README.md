<div align="center">

### **Make a new release**
1. Bump up the version in `pyproject.toml`
2. Run tests
```
poetry run pytest -v
```
3. Build the package
```
poetry build
```
4. Publish the package
```
poetry config pypi-token.pypi your-pypi-token
poetry publish
```
