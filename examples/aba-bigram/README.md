# Generated synthetic trainer

The exact reviewed ABA-produced trainer from the successful integration run.
It trains an eight-token bigram model, not an LLM. Run in an isolated Python
standard-library environment after inspecting the source:

```sh
python -I examples/aba-bigram/run.py --data-dir examples/aba-bigram --output-dir artifacts/aba-toy-local
```

This invokes the delivered trainer only, not a new ABA controller run.
The independently verified integration summary is in results/aba-synthetic-validation.json.
The optional upstream aibuildai logging import is disabled when unavailable.
No benchmark test data or credentials are provided.
