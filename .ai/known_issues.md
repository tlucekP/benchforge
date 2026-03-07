# Known Issues

## Large CSV files are slow

Large CSV files are slow due to pandas memory usage.

Possible solution: stream processing

---

## nested_loop false positives — plain variable iterables

The `nested_loop` detector cannot distinguish between:

```python
# False positive — independent sub-list, not O(n²)
for group in groups:
    for entry in entries:   # 'entries' is unrelated to 'group'
        ...

# True positive — cross-product, genuinely O(n²)
for i in items:
    for j in items:         # same collection
        ...
```

Both use a plain variable as the inner iterable (`ast.Name` node).
Without type information, static analysis cannot prove independence.

Current behavior: plain variable iterables are flagged conservatively.

Skipped patterns (not flagged): `range(N≤16)`, literal collections, attribute access (`obj.attr`).

Future solution: would require dataflow / type inference — out of scope for v1.x.
