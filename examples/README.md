# Examples

## basic_fusion.py

Runs the full three-engine fusion on a PDF and prints the first 20 enriched items.

```bash
pip install docomestria
python basic_fusion.py path/to/contract.pdf
```

Note: the first run downloads Docling's layout model, which can take a minute.

## Using only the fusion logic

If you already extracted items with the three engines yourself, call
`fuse_from_engines()` to skip the engine wrappers:

```python
from docomestria import fuse_from_engines

result = fuse_from_engines(lite_items, docling_blocks, visual_rects)
print(f"coverage: {result.coverage:.1%}")
for it in result.items:
    print(it)
```
